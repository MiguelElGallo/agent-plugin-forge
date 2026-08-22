"""Validate repository schemas, packages, provenance, and generated outputs."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path, PurePosixPath
from typing import Any

from jsonschema import Draft202012Validator
from pydantic import ValidationError

from .common import ForgeError, file_hashes, load_json, tree_hash
from .filesystem import inspect_regular_tree
from .generator import generation_drift
from .models import ProvenanceRecord
from .packages import PortablePackage, load_catalog, load_package


def _schema_errors(instance: dict[str, Any], schema: dict[str, Any], label: str) -> list[str]:
    """Return sorted JSON Schema validation errors for one instance."""

    validator = Draft202012Validator(schema)
    return [
        f"{label}: "
        f"{'/'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}"
        for error in sorted(
            validator.iter_errors(instance), key=lambda item: list(item.absolute_path)
        )
    ]


def _checksum_errors(root: Path, label: str) -> list[str]:
    """Validate vendored JSON files against their SHA256SUMS manifest."""

    try:
        lines = (root / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        return [f"Cannot read {label} checksums: {exc}"]
    errors: list[str] = []
    try:
        schema_names = {
            path.relative_to(root).as_posix()
            for path in inspect_regular_tree(root, tree_label=f"Vendored {label}")
            if path.suffix == ".json"
        }
    except ForgeError as exc:
        return [str(exc)]
    listed: set[str] = set()
    for line_number, line in enumerate(lines, start=1):
        match = re.fullmatch(r"([0-9a-f]{64})  ([A-Za-z0-9._-]+\.json)", line)
        if match is None:
            errors.append(f"Invalid {label} checksum entry on line {line_number}")
            continue
        expected, name = match.groups()
        if name in listed:
            errors.append(f"Duplicate {label} checksum entry: {name}")
            continue
        listed.add(name)
        try:
            actual = hashlib.sha256((root / name).read_bytes()).hexdigest()
        except OSError as exc:
            errors.append(f"Invalid {label} checksum entry on line {line_number}: {exc}")
            continue
        if actual != expected:
            errors.append(f"Vendored {label} checksum mismatch: {name}")
    if listed != schema_names:
        errors.append(
            f"Vendored {label} checksum coverage differs: "
            f"schemas={sorted(schema_names)}, checksums={sorted(listed)}"
        )
    return errors


def _schema_checksum_errors(repo: Path) -> list[str]:
    """Return checksum errors for vendored Agent Plugins schemas."""

    return _checksum_errors(repo / "schemas" / "agent-plugins" / "1.0.0", "schema")


def _provenance_errors(
    plugin_root: Path,
    skill_name: str,
    provenance: dict[str, Any],
    hashes: dict[str, str],
    modes: dict[str, bool] | None = None,
) -> list[str]:
    """Validate one skill's provenance identity, evidence, hashes, and modes."""

    try:
        record = ProvenanceRecord.model_validate(provenance)
    except ValidationError as exc:
        return [
            f"Invalid provenance for {skill_name} at "
            f"{'.'.join(str(part) for part in error['loc']) or '<root>'}: {error['msg']}"
            for error in exc.errors(include_url=False)
        ]
    errors: list[str] = []
    if record.skill != skill_name:
        errors.append(f"Provenance skill identity differs for {skill_name}")
    relative = PurePosixPath(record.license_evidence.path)
    evidence_path = plugin_root.joinpath(*relative.parts)
    if not evidence_path.is_file() or evidence_path.is_symlink():
        errors.append(f"License evidence is missing for {skill_name}: {relative}")
    elif hashlib.sha256(evidence_path.read_bytes()).hexdigest() != record.license_evidence.sha256:
        errors.append(f"License evidence hash drift for {skill_name}: {relative}")
    if record.files != hashes or record.content_sha256 != tree_hash(hashes):
        errors.append(f"Provenance content hash drift for {skill_name}")
    if modes is not None and record.file_modes != modes:
        errors.append(f"Provenance executable-mode drift for {skill_name}")
    return errors


def _license_errors(package: PortablePackage) -> list[str]:
    """Return distribution errors for a package's declared license."""

    if package.manifest.license is None:
        return [f"{package.entry.name} must declare an SPDX license expression"]
    root_license = package.root / "LICENSE"
    licenses_dir = package.root / "LICENSES"
    if root_license.is_file():
        return []
    if licenses_dir.is_dir():
        try:
            if inspect_regular_tree(licenses_dir, tree_label="License distribution"):
                return []
        except ForgeError as exc:
            return [str(exc)]
    return [f"{package.entry.name} must distribute its declared license in LICENSE or LICENSES/"]


def _package_provenance_errors(
    repo: Path,
    package: PortablePackage,
    seen_skills: dict[str, str],
) -> list[str]:
    """Validate every skill provenance record in one portable package."""

    errors = _license_errors(package)
    plugin_skill_names = {skill_root.name for skill_root in package.skill_roots}
    for skill_root in package.skill_roots:
        skill_name = skill_root.name
        previous = seen_skills.get(skill_name)
        if previous is not None:
            errors.append(
                f"Duplicate skill name {skill_name!r} in plugins {previous!r} and "
                f"{package.entry.name!r}"
            )
        seen_skills[skill_name] = package.entry.name
        provenance_path = package.root / "provenance" / f"{skill_name}.json"
        try:
            provenance = load_json(provenance_path)
        except ForgeError as exc:
            errors.append(str(exc))
            continue
        hashes = file_hashes(skill_root)
        modes = {path: bool((skill_root / path).stat().st_mode & 0o111) for path in hashes}
        errors.extend(_provenance_errors(package.root, skill_name, provenance, hashes, modes))
    provenance_dir = package.root / "provenance"
    provenance_names = (
        {path.stem for path in provenance_dir.glob("*.json")} if provenance_dir.is_dir() else set()
    )
    if provenance_names != plugin_skill_names:
        errors.append(
            f"Orphan or missing provenance in {package.entry.name}: "
            f"skills={sorted(plugin_skill_names)}, provenance={sorted(provenance_names)}"
        )
    return errors


def validate_repository(repo: Path) -> list[str]:
    """Return all repository validation errors without raising for drift."""

    errors = _schema_checksum_errors(repo)
    try:
        catalog = load_catalog(repo)
    except ForgeError as exc:
        return [*errors, str(exc)]

    seen_skills: dict[str, str] = {}
    package_errors = False
    for entry in catalog.plugins:
        try:
            package = load_package(repo, entry)
        except ForgeError as exc:
            errors.append(f"{entry.name}: {exc}")
            package_errors = True
            continue
        package_specific = _package_provenance_errors(repo, package, seen_skills)
        if package_specific:
            package_errors = True
            errors.extend(package_specific)

    plugins_root = repo / "plugins"
    try:
        plugin_dirs = {path.name for path in plugins_root.iterdir() if path.is_dir()}
    except OSError as exc:
        errors.append(f"Cannot list plugins directory: {exc}")
        package_errors = True
        plugin_dirs = set()
    catalog_names = {entry.name for entry in catalog.plugins}
    if plugin_dirs != catalog_names:
        errors.append(
            f"Catalog/plugin directory drift: catalog={sorted(catalog_names)}, "
            f"dirs={sorted(plugin_dirs)}"
        )
        package_errors = True
    if not package_errors:
        try:
            errors.extend(generation_drift(repo))
        except ForgeError as exc:
            errors.append(str(exc))
    return errors


def assert_valid_repository(repo: Path) -> None:
    """Raise a single actionable error when repository validation fails."""

    errors = validate_repository(repo)
    if errors:
        raise ForgeError("Validation failed:\n- " + "\n- ".join(errors))
