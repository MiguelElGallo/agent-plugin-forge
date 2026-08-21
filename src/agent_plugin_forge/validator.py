from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath
from typing import Any

from jsonschema import Draft202012Validator
from pydantic import ValidationError

from .codex_contract import codex_schema_checksum_errors
from .common import (
    PLUGIN_SCHEMA,
    ForgeError,
    contained_child,
    file_hashes,
    inspect_tree,
    load_json,
    parse_semver,
    parse_skill_frontmatter,
    tree_hash,
    validate_name,
    validate_spdx_expression,
)
from .generator import generation_drift
from .importer import IMMUTABLE_REVISION_RE
from .models import Catalog, ProvenanceRecord


def _schema_errors(instance: dict[str, Any], schema: dict[str, Any], label: str) -> list[str]:
    validator = Draft202012Validator(schema)
    return [
        f"{label}: "
        f"{'/'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}"
        for error in sorted(
            validator.iter_errors(instance), key=lambda item: list(item.absolute_path)
        )
    ]


def _schema_checksum_errors(repo: Path) -> list[str]:
    schema_root = repo / "schemas" / "agent-plugins" / "1.0.0"
    errors: list[str] = []
    for line in (schema_root / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        expected, name = line.split(maxsplit=1)
        actual = hashlib.sha256((schema_root / name).read_bytes()).hexdigest()
        if actual != expected:
            errors.append(f"Vendored schema checksum mismatch: {name}")
    return errors


def _provenance_errors(
    plugin_root: Path, skill_name: str, provenance: dict[str, Any], hashes: dict[str, str]
) -> list[str]:
    errors: list[str] = []
    try:
        record = ProvenanceRecord.model_validate(provenance)
    except ValidationError as exc:
        return [f"Invalid provenance for {skill_name}: {error['msg']}" for error in exc.errors()]
    if record.skill != skill_name:
        errors.append(f"Provenance skill identity differs for {skill_name}")
    if IMMUTABLE_REVISION_RE.fullmatch(record.revision) is None:
        errors.append(f"Provenance revision is not immutable for {skill_name}")
    parsed = PurePosixPath(record.source_subpath)
    if parsed.is_absolute() or ".." in parsed.parts:
        errors.append(f"Provenance sourceSubpath is unsafe for {skill_name}")
    try:
        validate_spdx_expression(record.license, label=f"Provenance license for {skill_name}")
    except ForgeError as exc:
        errors.append(str(exc))
    relative = PurePosixPath(record.license_evidence.path)
    if relative.is_absolute() or ".." in relative.parts:
        errors.append(f"License evidence path is unsafe for {skill_name}")
    else:
        evidence_path = plugin_root.joinpath(*relative.parts)
        if not evidence_path.is_file() or evidence_path.is_symlink():
            errors.append(f"License evidence is missing for {skill_name}")
        elif (
            hashlib.sha256(evidence_path.read_bytes()).hexdigest() != record.license_evidence.sha256
        ):
            errors.append(f"License evidence hash drift for {skill_name}")
    if record.files != hashes or record.content_sha256 != tree_hash(hashes):
        errors.append(f"Provenance content hash drift for {skill_name}")
    return errors


def validate_repository(repo: Path) -> list[str]:
    errors = [*_schema_checksum_errors(repo), *codex_schema_checksum_errors(repo)]
    plugin_schema = load_json(repo / "schemas" / "agent-plugins" / "1.0.0" / "plugin.schema.json")
    try:
        catalog = Catalog.model_validate(load_json(repo / "catalog" / "plugins.json"))
    except ValidationError as exc:
        return [*errors, *[f"Invalid catalog: {error['msg']}" for error in exc.errors()]]
    catalog_entries = catalog.model_dump(by_alias=True)["plugins"]

    seen_plugins: set[str] = set()
    seen_skills: dict[str, str] = {}
    for entry in catalog_entries:
        if not isinstance(entry, dict):
            errors.append("Catalog plugin entries must be objects")
            continue
        name = entry.get("name")
        if not isinstance(name, str):
            errors.append("Catalog plugin entry is missing a string name")
            continue
        try:
            validate_name(name, kind="plugin")
            plugin_root = contained_child(repo / "plugins", name, kind="plugin")
        except ForgeError as exc:
            errors.append(str(exc))
            continue
        if name in seen_plugins:
            errors.append(f"Duplicate catalog plugin: {name}")
        seen_plugins.add(name)
        if not isinstance(entry.get("category"), str) or not entry["category"].strip():
            errors.append(f"Catalog category must be non-empty for {name}")
        if not isinstance(entry.get("codexCompatibility"), bool):
            errors.append(f"codexCompatibility must be Boolean for {name}")
        try:
            manifest = load_json(plugin_root / "plugin.json")
        except ForgeError as exc:
            errors.append(str(exc))
            continue
        errors.extend(_schema_errors(manifest, plugin_schema, f"plugins/{name}/plugin.json"))
        if manifest.get("$schema") != PLUGIN_SCHEMA:
            errors.append(f"{name} does not target Agent Plugins 1.0.0")
        if manifest.get("name") != name:
            errors.append(f"Catalog and manifest name differ for {name}")
        try:
            validate_spdx_expression(manifest.get("license"), label=f"{name} license")
        except ForgeError as exc:
            errors.append(str(exc))
        try:
            parse_semver(manifest.get("version"), label=f"{name} version")
        except ForgeError as exc:
            errors.append(str(exc))
        if (plugin_root / "mcp.json").exists():
            errors.append(f"{name}: v0.1 is skills-only and rejects mcp.json")
        skills_root = plugin_root / "skills"
        if not skills_root.is_dir():
            errors.append(f"{name} has no skills directory")
            continue
        for path in plugin_root.rglob("*"):
            if path.is_symlink():
                errors.append(
                    f"Symlink is forbidden in plugin {name}: {path.relative_to(plugin_root)}"
                )
        direct_skills = [path for path in skills_root.iterdir() if path.is_dir()]
        for nested in skills_root.glob("*/*/SKILL.md"):
            errors.append(f"Nested, undiscoverable SKILL.md: {nested.relative_to(repo)}")
        plugin_skill_names: set[str] = set()
        for skill_root in direct_skills:
            skill_md = skill_root / "SKILL.md"
            try:
                inspect_tree(skill_root)
                metadata = parse_skill_frontmatter(skill_md)
            except (ForgeError, OSError, UnicodeError) as exc:
                errors.append(str(exc))
                continue
            skill_name = metadata["name"]
            plugin_skill_names.add(skill_name)
            if skill_name != skill_root.name:
                errors.append(f"Skill folder/name mismatch: {skill_root.relative_to(repo)}")
            previous = seen_skills.get(skill_name)
            if previous is not None:
                errors.append(f"Duplicate skill name {skill_name} in {previous} and {name}")
            seen_skills[skill_name] = name
            provenance_path = plugin_root / "provenance" / f"{skill_name}.json"
            try:
                provenance = load_json(provenance_path)
            except ForgeError as exc:
                errors.append(str(exc))
                continue
            hashes = file_hashes(skill_root)
            errors.extend(_provenance_errors(plugin_root, skill_name, provenance, hashes))
        provenance_dir = plugin_root / "provenance"
        provenance_names = (
            {path.stem for path in provenance_dir.glob("*.json")}
            if provenance_dir.exists()
            else set()
        )
        if provenance_names != plugin_skill_names:
            errors.append(
                f"Orphan or missing provenance in {name}: "
                f"skills={sorted(plugin_skill_names)}, provenance={sorted(provenance_names)}"
            )
    plugins_root = repo / "plugins"
    plugin_dirs = {path.name for path in plugins_root.iterdir() if path.is_dir()}
    if plugin_dirs != seen_plugins:
        errors.append(
            f"Catalog/plugin directory drift: catalog={sorted(seen_plugins)}, "
            f"dirs={sorted(plugin_dirs)}"
        )
    try:
        errors.extend(generation_drift(repo))
    except ForgeError as exc:
        errors.append(str(exc))
    return errors


def assert_valid_repository(repo: Path) -> None:
    errors = validate_repository(repo)
    if errors:
        raise ForgeError("Validation failed:\n- " + "\n- ".join(errors))
