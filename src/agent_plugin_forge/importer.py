from __future__ import annotations

import hashlib
import os
import re
import shutil
import stat
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any

from .common import (
    MAX_FILE_BYTES,
    PLUGIN_SCHEMA,
    ForgeError,
    contained_child,
    file_hashes,
    inspect_tree,
    json_bytes,
    load_json,
    parse_semver,
    parse_skill_frontmatter,
    tree_hash,
    validate_name,
    validate_spdx_expression,
)

IMMUTABLE_REVISION_RE = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64}|sha256:[0-9a-f]{64})$")


@dataclass(frozen=True)
class ImportRequest:
    source: Path
    plugin: str
    category: str | None
    version: str | None
    description: str | None
    author: str | None
    license_id: str
    license_file: Path
    origin: str
    revision: str
    source_subpath: str
    imported_at: str
    expected_sha256: str | None = None
    transformations: tuple[str, ...] = ()


@dataclass(frozen=True)
class ImportPlan:
    plugin: str
    skill: str
    destination: Path
    creates_plugin: bool
    file_count: int
    content_sha256: str
    license_sha256: str
    license_destination: str
    plan_sha256: str
    files: dict[str, str]


def _catalog_entry(catalog: dict[str, Any], plugin: str) -> dict[str, Any] | None:
    entries = catalog.get("plugins", [])
    if not isinstance(entries, list):
        raise ForgeError("catalog/plugins.json plugins must be an array")
    return next((entry for entry in entries if entry.get("name") == plugin), None)


def _validate_request_metadata(request: ImportRequest) -> None:
    if not request.origin.strip():
        raise ForgeError("Origin must be non-empty")
    if IMMUTABLE_REVISION_RE.fullmatch(request.revision) is None:
        raise ForgeError("Revision must be a full Git object ID or sha256:<64 lowercase hex>")
    subpath = PurePosixPath(request.source_subpath)
    if subpath.is_absolute() or ".." in subpath.parts:
        raise ForgeError("Source subpath must be relative and cannot contain '..'")
    try:
        date.fromisoformat(request.imported_at)
    except ValueError as exc:
        raise ForgeError("Import date must use YYYY-MM-DD") from exc
    validate_spdx_expression(request.license_id, label="License")
    if request.license_file.is_symlink() or not request.license_file.is_file():
        raise ForgeError("--license-file must be a regular, non-symlink file")
    if request.license_file.stat().st_size > MAX_FILE_BYTES:
        raise ForgeError(f"License file exceeds {MAX_FILE_BYTES} bytes")


def plan_import(repo: Path, request: ImportRequest) -> ImportPlan:
    validate_name(request.plugin, kind="plugin")
    _validate_request_metadata(request)
    files = inspect_tree(request.source)
    metadata = parse_skill_frontmatter(request.source / "SKILL.md")
    skill = str(metadata["name"])
    if request.source.name != skill:
        raise ForgeError(
            f"Source directory {request.source.name!r} must match SKILL.md name {skill!r}; "
            "normalize it in a separate reviewed change"
        )
    plugin_root = contained_child(repo / "plugins", request.plugin, kind="plugin")
    destination = contained_child(plugin_root / "skills", skill, kind="skill")
    if destination.exists():
        raise ForgeError(f"Destination already exists: {destination}")
    creates_plugin = not plugin_root.exists()
    catalog = load_json(repo / "catalog" / "plugins.json")
    entry = _catalog_entry(catalog, request.plugin)
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
    hashes = file_hashes(request.source)
    content_sha256 = tree_hash(hashes)
    license_sha256 = hashlib.sha256(request.license_file.read_bytes()).hexdigest()
    license_destination = (
        "LICENSE"
        if creates_plugin
        else (Path("licenses") / skill / request.license_file.name).as_posix()
    )
    plan_payload = {
        "plugin": request.plugin,
        "skill": skill,
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
        "importedAt": request.imported_at,
        "transformations": list(request.transformations),
        "contentSha256": content_sha256,
    }
    plan_sha256 = hashlib.sha256(json_bytes(plan_payload)).hexdigest()
    return ImportPlan(
        plugin=request.plugin,
        skill=skill,
        destination=destination,
        creates_plugin=creates_plugin,
        file_count=len(files),
        content_sha256=content_sha256,
        license_sha256=license_sha256,
        license_destination=license_destination,
        plan_sha256=plan_sha256,
        files=hashes,
    )


def _copy_regular_tree(source: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    folded: set[str] = set()
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        key = relative.as_posix().casefold()
        if key in folded:
            raise ForgeError(f"Case-fold path collision while staging: {relative}")
        folded.add(key)
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode) or (not stat.S_ISDIR(mode) and not stat.S_ISREG(mode)):
            raise ForgeError(f"Unsafe file while staging: {relative}")
        target = destination / relative
        if stat.S_ISDIR(mode):
            target.mkdir(exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(path.read_bytes())


def _copy_reviewed_skill(source: Path, destination: Path, expected: dict[str, str]) -> None:
    destination.mkdir(parents=True)
    for relative, expected_hash in sorted(expected.items()):
        source_file = source / relative
        if source_file.is_symlink() or not source_file.is_file():
            raise ForgeError(f"Reviewed source changed before apply: {relative}")
        content = source_file.read_bytes()
        if hashlib.sha256(content).hexdigest() != expected_hash:
            raise ForgeError(f"Reviewed source changed before apply: {relative}")
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    if file_hashes(destination) != expected:
        raise ForgeError("Staged skill does not match the reviewed source hash")


def _enforce_branch(repo: Path, plugin: str, skill: str) -> None:
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
    plan = plan_import(repo, request)
    if request.expected_sha256 != plan.plan_sha256:
        raise ForgeError("--expected-sha256 must match the reviewed full-plan hash")
    _enforce_branch(repo, plan.plugin, plan.skill)
    plugin_root = contained_child(repo / "plugins", request.plugin, kind="plugin")
    catalog_path = repo / "catalog" / "plugins.json"
    catalog_before = catalog_path.read_bytes()
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
                "repository": f"https://github.com/MiguelElGallo/{repo.name}",
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
        _copy_reviewed_skill(request.source, staged_skill, plan.files)
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
            "importedAt": request.imported_at,
            "license": request.license_id,
            "licenseEvidence": {
                "path": license_relative.as_posix(),
                "sha256": license_hash,
            },
            "contentSha256": plan.content_sha256,
            "files": plan.files,
            "transformations": list(request.transformations),
        }
        provenance_dir = staged_plugin / "provenance"
        provenance_dir.mkdir(exist_ok=True)
        (provenance_dir / f"{plan.skill}.json").write_bytes(json_bytes(provenance))

        backup = temporary_root / "backup"
        replaced_existing = plugin_root.exists()
        try:
            if replaced_existing:
                os.replace(plugin_root, backup)
            os.replace(staged_plugin, plugin_root)
            catalog_temp = catalog_path.with_name(f".{catalog_path.name}.{os.getpid()}.tmp")
            catalog_temp.write_bytes(json_bytes(catalog))
            os.replace(catalog_temp, catalog_path)
        except Exception:
            if plugin_root.exists():
                shutil.rmtree(plugin_root)
            if replaced_existing and backup.exists():
                os.replace(backup, plugin_root)
            catalog_path.write_bytes(catalog_before)
            raise
    return plan


def default_import_date() -> str:
    return date.today().isoformat()
