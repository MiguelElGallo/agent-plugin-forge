from __future__ import annotations

import hashlib
from pathlib import Path

from jsonschema import Draft202012Validator
from pydantic import ValidationError

from .common import (
    ForgeError,
    inspect_tree,
    load_json,
    parse_semver,
    parse_skill_frontmatter,
    validate_spdx_expression,
)
from .models import CodexManifest

TODO_MARKER = "[TODO:"


def _todo_marker_errors(value: object, path: str = "$") -> list[str]:
    if isinstance(value, str):
        return (
            [f"Codex manifest {path} contains a [TODO: ...] placeholder"]
            if TODO_MARKER in value
            else []
        )
    if isinstance(value, list):
        return [
            error
            for index, item in enumerate(value)
            for error in _todo_marker_errors(item, f"{path}[{index}]")
        ]
    if isinstance(value, dict):
        return [
            error
            for key, item in value.items()
            for error in _todo_marker_errors(item, f"{path}.{key}")
        ]
    return []


def codex_schema_checksum_errors(repo: Path) -> list[str]:
    schema_root = repo / "schemas" / "codex" / "current"
    errors: list[str] = []
    try:
        lines = (schema_root / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return [f"Cannot read Codex contract checksums: {exc}"]
    for line in lines:
        expected, name = line.split(maxsplit=1)
        actual = hashlib.sha256((schema_root / name).read_bytes()).hexdigest()
        if actual != expected:
            errors.append(f"Vendored Codex contract checksum mismatch: {name}")
    return errors


def codex_wrapper_errors(repo: Path, plugin_root: Path) -> list[str]:
    errors = codex_schema_checksum_errors(repo)
    try:
        schema = load_json(repo / "schemas" / "codex" / "current" / "plugin.schema.json")
        manifest = load_json(plugin_root / ".codex-plugin" / "plugin.json")
    except ForgeError as exc:
        return [*errors, str(exc)]
    validator = Draft202012Validator(schema)
    errors.extend(_todo_marker_errors(manifest))
    errors.extend(
        f"Codex manifest: {'/'.join(str(part) for part in error.absolute_path) or '<root>'}: "
        f"{error.message}"
        for error in sorted(
            validator.iter_errors(manifest), key=lambda item: list(item.absolute_path)
        )
    )
    try:
        validated = CodexManifest.model_validate(manifest)
        parse_semver(validated.version, label="Generated Codex version")
        if validated.license is not None:
            validate_spdx_expression(validated.license, label="Generated Codex license")
    except (ValidationError, ForgeError) as exc:
        errors.append(f"Invalid generated Codex manifest: {exc}")

    skills_root = plugin_root / "skills"
    if not skills_root.is_dir():
        errors.append("Generated Codex wrapper is missing skills/")
        return errors
    for skill_root in sorted(skills_root.iterdir(), key=lambda path: path.name):
        if not skill_root.is_dir():
            errors.append(f"Generated Codex skills entry is not a directory: {skill_root.name}")
            continue
        try:
            inspect_tree(skill_root)
            metadata = parse_skill_frontmatter(skill_root / "SKILL.md")
        except (ForgeError, OSError, UnicodeError) as exc:
            errors.append(str(exc))
            continue
        if metadata["name"] != skill_root.name:
            errors.append(f"Generated Codex skill folder/name mismatch: {skill_root.name}")
    return errors


def assert_valid_codex_wrapper(repo: Path, plugin_root: Path) -> None:
    errors = codex_wrapper_errors(repo, plugin_root)
    if errors:
        raise ForgeError("Codex compatibility validation failed:\n- " + "\n- ".join(errors))
