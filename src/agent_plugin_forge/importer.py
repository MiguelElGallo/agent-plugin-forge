"""Plan and apply hash-bound imports of reviewed Agent Skills."""

from __future__ import annotations

import hashlib
import json
import os
import posixpath
import re
import shutil
import stat
import subprocess
import tempfile
from contextlib import suppress
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlsplit

from .common import (
    PLUGIN_SCHEMA,
    ForgeError,
    contained_child,
    json_bytes,
    load_json,
    parse_semver,
    tree_hash,
)
from .errors import diagnostic_value
from .filesystem import (
    copy_regular_tree,
    inspect_regular_file,
    is_linklike,
    snapshot_regular_tree,
)
from .models import Catalog, CatalogPlugin, ImportPlan, ImportRequest, ProvenanceRecord, StdioServer
from .packages import PortablePackage, load_package
from .sources import SkillSource, resolve_skill_source


def _manifest_repository_url(origin: str, *, repo: Path) -> str:
    """Normalize a safe forge origin for a generated portable manifest."""

    if not origin:
        raise ForgeError("Forge origin is empty")
    if any(ord(character) < 32 or ord(character) == 127 for character in origin):
        raise ForgeError("Forge origin must not contain control characters")
    local = Path(origin).expanduser()
    if local.is_absolute():
        return local.resolve().as_uri()

    if "://" not in origin:
        if "::" in origin:
            raise ForgeError("Git remote-helper origins are not supported")
        scp = re.fullmatch(r"(?:(?P<user>[^@/:]+)@)?(?P<host>[^/:]+):(?P<path>.+)", origin)
        if scp:
            if "?" in origin or "#" in origin:
                raise ForgeError("Forge origin must not include a query or fragment")
            user = f"{scp.group('user')}@" if scp.group("user") else ""
            path = scp.group("path").lstrip("/")
            return f"ssh://{user}{scp.group('host')}/{path}"
        return (repo / local).resolve().as_uri()

    parsed = urlsplit(origin)
    if parsed.scheme == "https":
        if parsed.username is not None or parsed.password is not None:
            raise ForgeError("Forge origin URL must not embed credentials")
        if parsed.query or parsed.fragment:
            raise ForgeError("Forge origin URL must not include a query or fragment")
        if not parsed.hostname:
            raise ForgeError("Forge HTTPS origin must include a host")
        return origin
    if parsed.scheme == "ssh":
        if parsed.password is not None:
            raise ForgeError("Forge origin URL must not embed credentials")
        if parsed.query or parsed.fragment:
            raise ForgeError("Forge origin URL must not include a query or fragment")
        if not parsed.hostname:
            raise ForgeError("Forge SSH origin must include a host")
        return origin
    if parsed.scheme == "file":
        if parsed.username is not None or parsed.password is not None:
            raise ForgeError("Forge origin URL must not embed credentials")
        if parsed.query or parsed.fragment:
            raise ForgeError("Forge origin URL must not include a query or fragment")
        return origin
    if parsed.scheme:
        raise ForgeError("Forge origin must use HTTPS, SSH, scp-style SSH, or a local path")
    raise ForgeError("Forge origin is empty")


def _forge_repository_url(repo: Path) -> str:
    """Read and normalize the forge checkout's required origin remote."""

    if not (repo / ".git").exists():
        raise ForgeError("Forge checkout must be a Git worktree with an origin remote")
    result = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode or not result.stdout.strip():
        raise ForgeError("Forge checkout must have an origin remote")
    return _manifest_repository_url(result.stdout.strip(), repo=repo)


def _catalog_entry(catalog: dict[str, Any], plugin: str) -> dict[str, Any] | None:
    """Return one named catalog entry after validating the entry collection."""

    entries = catalog.get("plugins", [])
    if not isinstance(entries, list):
        raise ForgeError("catalog/plugins.json plugins must be an array")
    if not all(isinstance(entry, dict) for entry in entries):
        raise ForgeError("catalog/plugins.json plugin entries must be objects")
    return next((entry for entry in entries if entry.get("name") == plugin), None)


def _reject_duplicate_skill_destination(
    repo: Path, catalog: dict[str, Any], plugin: str, skill: str
) -> None:
    """Reject a skill destination already owned by another cataloged plugin."""

    entries = catalog.get("plugins", [])
    if not isinstance(entries, list) or not all(isinstance(entry, dict) for entry in entries):
        raise ForgeError("catalog/plugins.json plugin entries must be objects")
    for entry in entries:
        other_name = entry.get("name")
        if not isinstance(other_name, str) or other_name == plugin:
            continue
        other_root = contained_child(repo / "plugins", other_name, kind="plugin")
        duplicate = contained_child(other_root / "skills", skill, kind="skill")
        if duplicate.exists() or duplicate.is_symlink():
            raise ForgeError(
                f"Skill name {skill!r} already exists in plugin {other_name!r}; "
                "skill names must be repository-wide unique"
            )


def _validate_request_metadata(request: ImportRequest) -> bytes:
    """Validate import metadata files before constructing a review plan."""

    return inspect_regular_file(request.license_file, file_label="License file")


def _require_available_output(plugin_root: Path, target: Path, *, label: str) -> None:
    """Require a new output path with only safe existing parent directories."""

    if target.exists() or target.is_symlink():
        raise ForgeError(f"{label} already exists: {diagnostic_value(target)}")
    current = target.parent
    while current != plugin_root:
        if current.exists() and (current.is_symlink() or not current.is_dir()):
            raise ForgeError(f"{label} parent is not a safe directory: {diagnostic_value(current)}")
        current = current.parent


def _directory_names(root: Path) -> list[str]:
    """List safe relative directories, including empty MCP working directories."""

    pending = [root]
    directories: list[str] = []
    resolved_root = root.resolve()
    try:
        while pending:
            current = pending.pop()
            if is_linklike(current) or not current.resolve().is_relative_to(resolved_root):
                raise ForgeError(
                    "Destination directory changed or escaped its root: "
                    f"{diagnostic_value(current)}"
                )
            for path in current.iterdir():
                if is_linklike(path):
                    raise ForgeError(
                        f"Destination contains a link or junction: {diagnostic_value(path)}"
                    )
                if stat.S_ISDIR(path.lstat().st_mode):
                    directories.append(path.relative_to(root).as_posix())
                    pending.append(path)
    except OSError as exc:
        raise ForgeError(
            f"Cannot inspect destination directories: {diagnostic_value(exc)}"
        ) from exc
    return sorted(directories)


def _target_state(plugin_root: Path, entry: dict[str, Any] | None) -> dict[str, Any] | None:
    """Capture the current destination package state for plan binding."""

    if not plugin_root.exists():
        return None
    files = snapshot_regular_tree(
        plugin_root,
        required_root_file="plugin.json",
        tree_label="Destination plugin",
    )
    return {
        "catalogEntry": entry,
        "directories": _directory_names(plugin_root),
        "files": {
            path.relative_to(plugin_root).as_posix(): hashlib.sha256(snapshot.content).hexdigest()
            for path, snapshot in files.items()
        },
        "fileModes": {
            path.relative_to(plugin_root).as_posix(): snapshot.executable
            for path, snapshot in files.items()
        },
    }


def plan_import(repo: Path, request: ImportRequest) -> ImportPlan:
    """Create a non-mutating, hash-bound plan for one Agent Skill import."""

    return _plan_change(repo, request, update=False)


def plan_update(repo: Path, request: ImportRequest) -> ImportPlan:
    """Plan replacement of one recorded skill while preserving its containing package."""

    return _plan_change(repo, request, update=True)


def _canonical_output_path(relative: str, target_state: dict[str, Any]) -> str:
    """Reuse existing component spelling and reject ambiguous case aliases on any host."""

    paths = set(target_state["files"]) | set(target_state["directories"])
    parts: list[str] = []
    for part in PurePosixPath(relative).parts:
        prefix = "/".join(parts) + "/" if parts else ""
        children = {
            path[len(prefix) :].split("/", 1)[0] for path in paths if path.startswith(prefix)
        }
        matches = sorted(child for child in children if child.casefold() == part.casefold())
        if len(matches) > 1:
            raise ForgeError(
                "Update license destination has ambiguous case aliases: "
                f"{diagnostic_value(prefix + part)}"
            )
        parts.append(matches[0] if matches else part)
    return "/".join(parts)


def _validate_update_mcp_arguments(
    package: PortablePackage, skill: str, target_state: dict[str, Any], hashes: dict[str, str]
) -> None:
    """Preserve existing explicit MCP argument files and directories in the replaced skill."""

    if package.mcp is None:
        return
    prefix = f"skills/{skill}/"
    directories = {parent.as_posix() for path in hashes for parent in PurePosixPath(path).parents}
    existing_directories = set(target_state["directories"]) | {"."}
    for name, server in package.mcp.mcp_servers.items():
        if not isinstance(server, StdioServer):
            continue
        for argument in server.args:
            match = re.fullmatch(r"(?:--?[^=]+=)?\$\{PLUGIN_ROOT\}/(.+)", argument, flags=re.DOTALL)
            if match is None:
                continue
            suffix = match[1].lstrip("/")
            parent = "."
            traversable = True
            ancestors: list[str] = []
            for component in suffix.split("/")[:-1]:
                parent = posixpath.normpath(posixpath.join(parent, component))
                if parent not in existing_directories:
                    traversable = False
                    break
                ancestors.append(parent)
            if not traversable:
                continue
            path = posixpath.normpath(suffix)
            if path not in target_state["files"] and path not in existing_directories:
                continue
            for referenced in [*ancestors, path]:
                if not referenced.startswith(prefix):
                    continue
                relative = referenced.removeprefix(prefix)
                removed_file = referenced in target_state["files"] and relative not in hashes
                removed_directory = (
                    referenced in existing_directories and relative not in directories
                )
                if removed_file or removed_directory:
                    raise ForgeError(
                        f"Update would remove or change the type of MCP server {name!r} argument "
                        f"path: {diagnostic_value(argument)}"
                    )


def _update_license_destination(
    repo: Path,
    request: ImportRequest,
    source: SkillSource,
    entry: dict[str, Any] | None,
    target_state: dict[str, Any],
) -> str:
    """Validate the installed package and reserve evidence owned by the updated skill."""

    from .validator import _package_provenance_errors

    skill = source.name
    if entry is None:
        raise ForgeError(f"Existing plugin {request.plugin} is missing from the catalog")
    package = load_package(repo, CatalogPlugin.model_validate(entry))
    errors = _package_provenance_errors(repo, package, {})
    if errors:
        raise ForgeError("Cannot update an invalid installed package:\n- " + "\n- ".join(errors))
    previous = ProvenanceRecord.model_validate(
        load_json(package.root / "provenance" / f"{skill}.json")
    )
    if previous.license != request.license_id:
        raise ForgeError(
            "Changing a skill's SPDX license requires a plugin-wide contributor review"
        )
    if request.description is not None or request.author is not None:
        raise ForgeError("Updates preserve shared description and author; omit these options")
    relative = _canonical_output_path(f"licenses/{skill}/LICENSE", target_state)
    target = package.root / relative
    skill_root = (package.root / "skills" / skill).resolve()
    source_hashes = source.hashes()
    _validate_update_mcp_arguments(package, skill, target_state, source_hashes)
    rewritten_metadata = {
        (package.root / "plugin.json").resolve(),
        (package.root / "provenance" / f"{skill}.json").resolve(),
    }
    for record_path in (package.root / "provenance").glob("*.json"):
        record = ProvenanceRecord.model_validate(load_json(record_path))
        if record.skill == skill:
            continue
        evidence = (package.root / record.license_evidence.path).resolve()
        if evidence in rewritten_metadata:
            raise ForgeError(
                "Update would rewrite metadata used as another skill's license evidence"
            )
        if evidence == target.resolve():
            raise ForgeError("Update license destination is shared with another skill")
        if evidence.is_relative_to(skill_root):
            source_path = evidence.relative_to(skill_root).as_posix()
            if source_hashes.get(source_path) != record.license_evidence.sha256:
                raise ForgeError(
                    "Update would change or remove license evidence shared with another skill"
                )
    if target.exists():
        if (package.root / previous.license_evidence.path).resolve() != target.resolve():
            raise ForgeError(
                "Update license destination already exists and is not owned by this skill"
            )
    else:
        _require_available_output(package.root, target, label="Update license destination")
    return relative


def _validate_staged_package(repo: Path, staged_plugin: Path, entry: dict[str, Any] | None) -> None:
    """Reject broken MCP references, metadata, or provenance before publishing a stage."""

    from .validator import _package_provenance_errors

    package = load_package(repo, CatalogPlugin.model_validate(entry), plugin_root=staged_plugin)
    errors = _package_provenance_errors(repo, package, {})
    if errors:
        raise ForgeError("Staged package is invalid:\n- " + "\n- ".join(errors))


def _skill_changes(
    target_state: dict[str, Any], skill: str, hashes: dict[str, str], modes: dict[str, bool]
) -> dict[str, list[str]]:
    """Describe content and executable changes relative to the installed skill snapshot."""

    prefix = f"skills/{skill}/"
    before = {
        path.removeprefix(prefix): digest
        for path, digest in target_state["files"].items()
        if path.startswith(prefix)
    }
    before_modes = target_state["fileModes"]
    common = before.keys() & hashes.keys()
    return {
        "added": sorted(hashes.keys() - before.keys()),
        "removed": sorted(before.keys() - hashes.keys()),
        "modified": sorted(path for path in common if before[path] != hashes[path]),
        "mode_changed": sorted(
            path for path in common if before_modes[prefix + path] != modes[path]
        ),
    }


def _read_catalog(repo: Path) -> tuple[dict[str, Any], str]:
    """Parse and hash the same catalog bytes for approval and publication."""

    path = repo / "catalog" / "plugins.json"
    try:
        content = path.read_bytes()
        catalog = json.loads(content)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ForgeError(f"Cannot read catalog: {diagnostic_value(exc)}") from exc
    if not isinstance(catalog, dict):
        raise ForgeError("catalog/plugins.json must contain an object")
    return catalog, hashlib.sha256(content).hexdigest()


def _plan_change(repo: Path, request: ImportRequest, *, update: bool) -> ImportPlan:
    """Bind a new import or explicit update to its inspected source and destination."""

    license_content = _validate_request_metadata(request)
    source = resolve_skill_source(request.source, request.source_skill)
    skill = source.name
    plugin_root = contained_child(repo / "plugins", request.plugin, kind="plugin")
    destination = contained_child(plugin_root / "skills", skill, kind="skill")
    if update and not destination.is_dir():
        raise ForgeError(
            f"Update requires an existing skill destination: {diagnostic_value(destination)}"
        )
    if not update and destination.exists():
        raise ForgeError(f"Destination already exists: {diagnostic_value(destination)}")
    creates_plugin = not plugin_root.exists()
    license_destination = (
        "LICENSE"
        if creates_plugin
        else (Path("licenses") / skill / request.license_file.name).as_posix()
    )
    if not creates_plugin and not update:
        _require_available_output(plugin_root, destination, label="Skill destination")
        _require_available_output(
            plugin_root,
            plugin_root / license_destination,
            label="License destination",
        )
        _require_available_output(
            plugin_root,
            plugin_root / "provenance" / f"{skill}.json",
            label="Provenance destination",
        )
    catalog, catalog_sha256 = _read_catalog(repo)
    if update:
        Catalog.model_validate(catalog)
    _reject_duplicate_skill_destination(repo, catalog, request.plugin, skill)
    entry = _catalog_entry(catalog, request.plugin)
    target_state = _target_state(plugin_root, entry)
    if update:
        assert target_state is not None
        license_destination = _update_license_destination(
            repo, request, source, entry, target_state
        )
    if creates_plugin:
        missing = [
            name
            for name, value in (
                ("category", request.category),
                ("version", request.version),
                ("description", request.description),
                ("author", request.author),
            )
            if not value
        ]
        if missing:
            raise ForgeError(f"New plugins require: {', '.join(missing)}")
        parse_semver(request.version, label="New plugin version")
        if entry is not None:
            raise ForgeError(f"Catalog already contains missing plugin directory {request.plugin}")
    else:
        if entry is None:
            raise ForgeError(f"Existing plugin {request.plugin} is missing from the catalog")
        if request.category and request.category != entry.get("category"):
            raise ForgeError("Existing bundles inherit their catalog category; do not replace it")
        manifest = load_json(plugin_root / "plugin.json")
        current = parse_semver(manifest.get("version"), label="Current plugin version")
        proposed = parse_semver(request.version, label="Bundle version")
        if proposed <= current:
            action = "Updating a skill" if update else "Adding to an existing bundle"
            raise ForgeError(f"{action} requires a higher --version")
    hashes = source.hashes()
    file_modes = source.modes()
    content_sha256 = tree_hash(hashes)
    license_sha256 = hashlib.sha256(license_content).hexdigest()
    repository_url = _forge_repository_url(repo)
    plan_payload = {
        "plugin": request.plugin,
        "skill": skill,
        "sourceKind": source.kind,
        "sourceSkill": request.source_skill,
        "category": request.category,
        "version": request.version,
        "description": request.description,
        "author": request.author,
        "license": request.license_id,
        "licenseSha256": license_sha256,
        "licenseDestination": license_destination,
        "origin": request.origin,
        "revision": request.revision,
        "sourceSubpath": request.source_subpath,
        "importedAt": request.imported_at.isoformat(),
        "transformations": list(request.transformations),
        "contentSha256": content_sha256,
        "files": hashes,
        "fileModes": file_modes,
        "targetState": target_state,
        "repositoryUrl": repository_url,
        "catalogSha256": catalog_sha256,
    }
    changes: dict[str, list[str]] = {}
    update_metadata: dict[str, Any] = {}
    if update:
        assert target_state is not None
        changes = _skill_changes(target_state, skill, hashes, file_modes)
        update_metadata = {
            "previousVersion": manifest["version"],
            "version": request.version,
            "manifestPath": "plugin.json",
            "provenancePath": f"provenance/{skill}.json",
            "licensePath": license_destination,
            "licenseAction": "replace" if (plugin_root / license_destination).exists() else "add",
            "preservesSharedLicense": True,
        }
        plan_payload.update(operation="update", changes=changes, updateMetadata=update_metadata)
    plan_sha256 = hashlib.sha256(json_bytes(plan_payload)).hexdigest()
    return ImportPlan(
        plugin=request.plugin,
        skill=skill,
        source_kind=source.kind,
        destination=destination,
        repository_url=repository_url,
        catalog_sha256=catalog_sha256,
        creates_plugin=creates_plugin,
        file_count=len(hashes),
        content_sha256=content_sha256,
        license_sha256=license_sha256,
        license_destination=license_destination,
        plan_sha256=plan_sha256,
        review_payload=plan_payload,
        files=hashes,
        file_modes=file_modes,
        operation="update" if update else "import",
        changes=changes,
        update_metadata=update_metadata,
    )


def _copy_regular_tree(source: Path, destination: Path) -> None:
    """Copy an existing plugin's safe files and preserve its empty directories."""

    copy_regular_tree(source, destination)
    for relative in _directory_names(source):
        (destination / relative).mkdir(parents=True, exist_ok=True)


def _copy_reviewed_skill(
    source: SkillSource,
    destination: Path,
    expected: dict[str, str],
    expected_modes: dict[str, bool],
) -> None:
    """Copy a skill only while its reviewed hashes and modes still match."""

    if source.hashes() != expected or source.modes() != expected_modes:
        raise ForgeError("Reviewed source bytes, paths, or modes changed before apply")
    captured = {
        source.relative_path(path): snapshot
        for path, snapshot in zip(source.files, source.snapshots, strict=True)
    }
    destination.mkdir(parents=True)
    for relative, expected_hash in sorted(expected.items()):
        snapshot = captured[relative]
        content = snapshot.content
        if hashlib.sha256(content).hexdigest() != expected_hash:
            raise ForgeError(f"Reviewed source changed before apply: {diagnostic_value(relative)}")
        executable = snapshot.executable
        if executable != expected_modes[relative]:
            raise ForgeError(
                f"Reviewed source mode changed before apply: {diagnostic_value(relative)}"
            )
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        target.chmod(0o755 if executable else 0o644)
    staged = resolve_skill_source(destination)
    if staged.hashes() != expected:
        raise ForgeError("Staged skill does not match the reviewed source hash")


def _enforce_branch(repo: Path, plugin: str, skill: str) -> None:
    """Require imports in Git worktrees to use the scoped skill branch."""

    if not (repo / ".git").exists():
        return
    result = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    expected = f"skill/{plugin}/{skill}"
    if result.stdout.strip() != expected:
        raise ForgeError(f"Applied imports require branch {expected!r}")


def apply_import(repo: Path, request: ImportRequest) -> ImportPlan:
    """Apply an unchanged reviewed import plan as a transactional update."""

    plan = plan_import(repo, request)
    return _apply_change(repo, request, plan)


def apply_update(repo: Path, request: ImportRequest) -> ImportPlan:
    """Apply only the exact approved update using the shared staging and rollback path."""

    return _apply_change(repo, request, plan_update(repo, request))


def _apply_change(repo: Path, request: ImportRequest, plan: ImportPlan) -> ImportPlan:
    """Stage an approved skill operation and preserve recovery data if rollback fails."""

    if request.expected_sha256 != plan.plan_sha256:
        raise ForgeError(
            "--expected-sha256 must match the reviewed full-plan hash. No import files changed. "
            f"Recomputed plan: {plan.plan_sha256}; import date: {request.imported_at.isoformat()}. "
            "A hash alone cannot identify which input changed. Compare a fresh plan without "
            "--apply (use --json) with the saved review. If resuming on another day, preserve "
            "the original review_payload.importedAt using --imported-at YYYY-MM-DD. "
            "Changes to source bytes, modes, license, metadata, origin, or destination require "
            "review and approval of a new plan; do not simply replace the approved hash."
        )
    _enforce_branch(repo, plan.plugin, plan.skill)
    plugin_root = contained_child(repo / "plugins", request.plugin, kind="plugin")
    plugins_root = plugin_root.parent
    plugins_root_existed = plugins_root.exists()
    catalog_path = repo / "catalog" / "plugins.json"
    catalog, catalog_sha256 = _read_catalog(repo)
    if catalog_sha256 != plan.catalog_sha256:
        raise ForgeError("Catalog changed after the reviewed plan")

    temporary_root = Path(tempfile.mkdtemp(prefix=".forge-import-", dir=repo))
    preserve_recovery = False
    try:
        staged_plugin = temporary_root / "plugin"
        if plan.creates_plugin:
            staged_plugin.mkdir()
            manifest = {
                "$schema": PLUGIN_SCHEMA,
                "name": request.plugin,
                "version": request.version,
                "description": request.description,
                "author": {"name": request.author},
                "repository": plan.repository_url,
                "license": request.license_id,
                "keywords": ["agent-plugin", "agent-skill"],
            }
            (staged_plugin / "plugin.json").write_bytes(json_bytes(manifest))
            catalog["plugins"].append(
                {"name": request.plugin, "category": request.category, "codexCompatibility": True}
            )
            catalog["plugins"] = sorted(catalog["plugins"], key=lambda item: item["name"])
        else:
            _copy_regular_tree(plugin_root, staged_plugin)
            if (
                _target_state(staged_plugin, _catalog_entry(catalog, plan.plugin))
                != plan.review_payload["targetState"]
            ):
                raise ForgeError("Destination plugin changed while staging the reviewed plan")
            manifest_path = staged_plugin / "plugin.json"
            manifest = load_json(manifest_path)
            manifest["version"] = request.version
            manifest_path.write_bytes(json_bytes(manifest))
        license_relative = Path(plan.license_destination)

        staged_skill = staged_plugin / "skills" / plan.skill
        if plan.operation == "update":
            shutil.rmtree(staged_skill)
        source = resolve_skill_source(request.source, request.source_skill)
        _copy_reviewed_skill(source, staged_skill, plan.files, plan.file_modes)
        license_content = inspect_regular_file(request.license_file, file_label="License file")
        if hashlib.sha256(license_content).hexdigest() != plan.license_sha256:
            raise ForgeError("Reviewed license changed before apply")
        license_target = staged_plugin / license_relative
        license_target.parent.mkdir(parents=True, exist_ok=True)
        license_target.write_bytes(license_content)
        license_hash = plan.license_sha256
        provenance = {
            "skill": plan.skill,
            "origin": request.origin,
            "revision": request.revision,
            "sourceSubpath": request.source_subpath,
            "importedAt": request.imported_at.isoformat(),
            "license": request.license_id,
            "licenseEvidence": {
                "path": license_relative.as_posix(),
                "sha256": license_hash,
            },
            "contentSha256": plan.content_sha256,
            "files": plan.files,
            "fileModes": plan.file_modes,
            "transformations": list(request.transformations),
        }
        provenance_dir = staged_plugin / "provenance"
        provenance_dir.mkdir(exist_ok=True)
        (provenance_dir / f"{plan.skill}.json").write_bytes(json_bytes(provenance))
        _validate_staged_package(repo, staged_plugin, _catalog_entry(catalog, plan.plugin))
        staged_catalog = temporary_root / "catalog.json"
        staged_catalog.write_bytes(json_bytes(catalog))

        _, current_catalog_sha256 = _read_catalog(repo)
        if current_catalog_sha256 != plan.catalog_sha256:
            raise ForgeError("Catalog changed while staging the reviewed plan")
        if (
            _target_state(plugin_root, _catalog_entry(catalog, plan.plugin))
            != plan.review_payload["targetState"]
        ):
            raise ForgeError("Destination plugin changed while staging the reviewed plan")
        if _forge_repository_url(repo) != plan.repository_url:
            raise ForgeError("Forge origin changed while staging the reviewed plan")

        backup = temporary_root / "backup"
        replaced_existing = plugin_root.exists()
        backed_up = False
        installed = False
        try:
            plugins_root.mkdir(parents=True, exist_ok=True)
            if replaced_existing:
                os.replace(plugin_root, backup)
                backed_up = True
            os.replace(staged_plugin, plugin_root)
            installed = True
            os.replace(staged_catalog, catalog_path)
        except Exception:
            try:
                if installed:
                    shutil.rmtree(plugin_root)
                if backed_up:
                    os.replace(backup, plugin_root)
            except Exception as recovery_error:
                preserve_recovery = True
                raise ForgeError(
                    f"Import rollback failed; recovery files preserved at "
                    f"{diagnostic_value(temporary_root)}. "
                    f"Original plugin backup, if created: {diagnostic_value(backup)}"
                ) from recovery_error
            # Catalog replacement is the last operation; a failed rename leaves it intact.
            if not plugins_root_existed:
                with suppress(OSError):
                    plugins_root.rmdir()
            raise
    finally:
        if not preserve_recovery:
            shutil.rmtree(temporary_root)
    return plan


def default_import_date() -> str:
    """Return today's local date in ISO format for CLI import defaults."""

    return date.today().isoformat()
