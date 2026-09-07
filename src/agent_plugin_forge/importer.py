"""Plan and apply hash-bound imports of reviewed Agent Skills."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import tempfile
from contextlib import suppress
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .common import (
    PLUGIN_SCHEMA,
    ForgeError,
    contained_child,
    json_bytes,
    load_json,
    parse_semver,
)
from .filesystem import (
    MAX_FILE_BYTES,
    copy_regular_tree,
    inspect_regular_file,
    inspect_regular_tree,
)
from .models import ImportPlan, ImportRequest
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


def _validate_request_metadata(request: ImportRequest) -> None:
    """Validate import metadata files before constructing a review plan."""

    content = inspect_regular_file(request.license_file, file_label="License file")
    if len(content) > MAX_FILE_BYTES:  # pragma: no cover - enforced by inspect_regular_file
        raise ForgeError(f"License file exceeds {MAX_FILE_BYTES} bytes")


def _require_available_output(plugin_root: Path, target: Path, *, label: str) -> None:
    """Require a new output path with only safe existing parent directories."""

    if target.exists() or target.is_symlink():
        raise ForgeError(f"{label} already exists: {target}")
    current = target.parent
    while current != plugin_root:
        if current.exists() and (current.is_symlink() or not current.is_dir()):
            raise ForgeError(f"{label} parent is not a safe directory: {current}")
        current = current.parent


def _target_state(plugin_root: Path, entry: dict[str, Any] | None) -> dict[str, Any] | None:
    """Capture the current destination package state for plan binding."""

    if not plugin_root.exists():
        return None
    files = inspect_regular_tree(
        plugin_root,
        required_root_file="plugin.json",
        tree_label="Destination plugin",
    )
    return {
        "catalogEntry": entry,
        "files": {
            path.relative_to(plugin_root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in files
        },
        "fileModes": {
            path.relative_to(plugin_root).as_posix(): bool(path.stat().st_mode & 0o111)
            for path in files
        },
    }


def plan_import(repo: Path, request: ImportRequest) -> ImportPlan:
    """Create a non-mutating, hash-bound plan for one Agent Skill import."""

    _validate_request_metadata(request)
    source = resolve_skill_source(request.source, request.source_skill)
    skill = source.name
    plugin_root = contained_child(repo / "plugins", request.plugin, kind="plugin")
    destination = contained_child(plugin_root / "skills", skill, kind="skill")
    if destination.exists():
        raise ForgeError(f"Destination already exists: {destination}")
    creates_plugin = not plugin_root.exists()
    license_destination = (
        "LICENSE"
        if creates_plugin
        else (Path("licenses") / skill / request.license_file.name).as_posix()
    )
    if not creates_plugin:
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
    catalog_path = repo / "catalog" / "plugins.json"
    catalog = load_json(catalog_path)
    catalog_sha256 = hashlib.sha256(catalog_path.read_bytes()).hexdigest()
    _reject_duplicate_skill_destination(repo, catalog, request.plugin, skill)
    entry = _catalog_entry(catalog, request.plugin)
    target_state = _target_state(plugin_root, entry)
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
            raise ForgeError("Adding to an existing bundle requires a higher --version")
    hashes = source.hashes()
    file_modes = source.modes()
    content_sha256 = source.content_sha256()
    license_sha256 = hashlib.sha256(request.license_file.read_bytes()).hexdigest()
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
        "fileModes": file_modes,
        "targetState": target_state,
        "repositoryUrl": repository_url,
        "catalogSha256": catalog_sha256,
    }
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
    )


def _copy_regular_tree(source: Path, destination: Path) -> None:
    """Copy an existing plugin tree through the shared safe copier."""

    copy_regular_tree(source, destination)


def _copy_reviewed_skill(
    source: SkillSource,
    destination: Path,
    expected: dict[str, str],
    expected_modes: dict[str, bool],
) -> None:
    """Copy a skill only while its reviewed hashes and modes still match."""

    destination.mkdir(parents=True)
    for relative, expected_hash in sorted(expected.items()):
        source_file = source.path_for(relative)
        if source_file.is_symlink() or not source_file.is_file():
            raise ForgeError(f"Reviewed source changed before apply: {relative}")
        content = source_file.read_bytes()
        if hashlib.sha256(content).hexdigest() != expected_hash:
            raise ForgeError(f"Reviewed source changed before apply: {relative}")
        executable = bool(source_file.stat().st_mode & 0o111)
        if executable != expected_modes[relative]:
            raise ForgeError(f"Reviewed source mode changed before apply: {relative}")
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
    if request.expected_sha256 != plan.plan_sha256:
        raise ForgeError("--expected-sha256 must match the reviewed full-plan hash")
    _enforce_branch(repo, plan.plugin, plan.skill)
    plugin_root = contained_child(repo / "plugins", request.plugin, kind="plugin")
    plugins_root = plugin_root.parent
    plugins_root_existed = plugins_root.exists()
    catalog_path = repo / "catalog" / "plugins.json"
    catalog_before = catalog_path.read_bytes()
    if hashlib.sha256(catalog_before).hexdigest() != plan.catalog_sha256:
        raise ForgeError("Catalog changed after the reviewed plan")
    catalog = load_json(catalog_path)

    with tempfile.TemporaryDirectory(prefix=".forge-import-", dir=repo) as temporary:
        temporary_root = Path(temporary)
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
            manifest_path = staged_plugin / "plugin.json"
            manifest = load_json(manifest_path)
            manifest["version"] = request.version
            manifest_path.write_bytes(json_bytes(manifest))
        license_relative = Path(plan.license_destination)

        staged_skill = staged_plugin / "skills" / plan.skill
        source = resolve_skill_source(request.source, request.source_skill)
        _copy_reviewed_skill(source, staged_skill, plan.files, plan.file_modes)
        license_content = request.license_file.read_bytes()
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
        staged_catalog = temporary_root / "catalog.json"
        staged_catalog.write_bytes(json_bytes(catalog))

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
            if installed:
                shutil.rmtree(plugin_root)
            if backed_up:
                os.replace(backup, plugin_root)
            # Catalog replacement is the last operation; a failed rename leaves it intact.
            if not plugins_root_existed:
                with suppress(OSError):
                    plugins_root.rmdir()
            raise
    return plan


def default_import_date() -> str:
    """Return today's local date in ISO format for CLI import defaults."""

    return date.today().isoformat()
