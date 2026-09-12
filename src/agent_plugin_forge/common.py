"""Provide shared parsing, hashing, validation, and repository helpers."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import yaml
from license_expression import ExpressionError, get_spdx_licensing
from semantic_version import Version

from .errors import ForgeError, diagnostic_value
from .filesystem import file_hashes as _file_hashes
from .filesystem import inspect_regular_tree

PLUGIN_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
PLUGIN_NAME_RE = re.compile(r"^(?!.*(?:--|\.\.))[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$")
SKILL_NAME_RE = re.compile(r"^(?!.*--)[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")
SPDX_LICENSING = get_spdx_licensing()


def load_json(path: Path) -> dict[str, Any]:
    """Load a UTF-8 JSON object or raise an actionable forge error."""

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ForgeError(
            f"Cannot read JSON from {diagnostic_value(path)}: {diagnostic_value(exc)}"
        ) from exc
    if not isinstance(value, dict):
        raise ForgeError(f"Expected a JSON object in {diagnostic_value(path)}")
    return value


def json_bytes(value: object) -> bytes:
    """Serialize a value as stable, indented, newline-terminated JSON bytes."""

    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode()


def validate_name(value: str, *, kind: str) -> None:
    """Validate a plugin or skill name against the portable naming contract."""

    pattern = SKILL_NAME_RE if kind == "skill" else PLUGIN_NAME_RE
    if len(value) > 64 or not pattern.fullmatch(value):
        raise ForgeError(
            f"Invalid {kind} name {value!r}; use the Agent Plugins lowercase name form"
        )


def contained_child(root: Path, name: str, *, kind: str) -> Path:
    """Return a validated named child that cannot escape its root directory."""

    validate_name(name, kind=kind)
    root_resolved = root.resolve()
    child = root / name
    if not child.resolve().is_relative_to(root_resolved):
        raise ForgeError(f"{kind.title()} path escapes its root: {name}")
    return child


def parse_semver(value: object, *, label: str) -> Version:
    """Parse a strict semantic version with a label-specific error message."""

    if not isinstance(value, str):
        raise ForgeError(f"{label} must use strict Semantic Versioning")
    try:
        return Version(value)
    except ValueError as exc:
        raise ForgeError(f"{label} must use strict Semantic Versioning") from exc


def validate_spdx_expression(value: object, *, label: str) -> str:
    """Validate and return a non-empty SPDX license expression."""

    if not isinstance(value, str) or not value.strip():
        raise ForgeError(f"{label} must be a valid SPDX license expression")
    try:
        SPDX_LICENSING.parse(value, validate=True, strict=True)
    except ExpressionError as exc:
        raise ForgeError(f"{label} must be a valid SPDX license expression") from exc
    return value


def parse_skill_frontmatter(skill_md: Path, *, content: bytes | None = None) -> dict[str, Any]:
    """Parse and validate Agent Skill YAML frontmatter and instruction content."""

    try:
        text = skill_md.read_text(encoding="utf-8") if content is None else content.decode("utf-8")
        text = text.replace("\r\n", "\n").replace("\r", "\n")
    except (OSError, UnicodeError) as exc:
        raise ForgeError(
            f"Cannot read Agent Skill metadata from {diagnostic_value(skill_md)}: "
            f"{diagnostic_value(exc)}"
        ) from exc
    if not text.startswith("---\n"):
        raise ForgeError(f"{diagnostic_value(skill_md)} must start with YAML frontmatter")
    closing = text.find("\n---\n", 4)
    if closing < 0:
        raise ForgeError(f"{diagnostic_value(skill_md)} has unterminated YAML frontmatter")
    frontmatter = text[4:closing]
    body = text[closing + 5 :]
    try:
        value = yaml.safe_load(frontmatter)
    except yaml.YAMLError as exc:
        raise ForgeError(
            f"{diagnostic_value(skill_md)} has invalid YAML frontmatter: {diagnostic_value(exc)}"
        ) from exc
    if not isinstance(value, dict):
        raise ForgeError(f"{diagnostic_value(skill_md)} frontmatter must be a mapping")
    name = value.get("name")
    description = value.get("description")
    if not isinstance(name, str) or not isinstance(description, str) or not description.strip():
        raise ForgeError(
            f"{diagnostic_value(skill_md)} requires string name and non-empty description fields"
        )
    validate_name(name, kind="skill")
    if len(description) > 1024:
        raise ForgeError(f"{diagnostic_value(skill_md)} description exceeds 1024 characters")
    allowed_fields = {
        "name",
        "description",
        "license",
        "compatibility",
        "metadata",
        "allowed-tools",
    }
    unknown = set(value) - allowed_fields
    if unknown:
        raise ForgeError(
            f"{diagnostic_value(skill_md)} has unsupported frontmatter fields: {sorted(unknown)}"
        )
    license_value = value.get("license")
    if license_value is not None and (
        not isinstance(license_value, str) or not license_value.strip()
    ):
        raise ForgeError(f"{diagnostic_value(skill_md)} license must be a non-empty string")
    compatibility = value.get("compatibility")
    if compatibility is not None and (
        not isinstance(compatibility, str) or not compatibility.strip() or len(compatibility) > 500
    ):
        raise ForgeError(
            f"{diagnostic_value(skill_md)} compatibility must be a 1-500 character string"
        )
    metadata = value.get("metadata")
    if metadata is not None and (
        not isinstance(metadata, dict)
        or not all(isinstance(key, str) and isinstance(item, str) for key, item in metadata.items())
    ):
        raise ForgeError(f"{diagnostic_value(skill_md)} metadata must map strings to strings")
    allowed_tools = value.get("allowed-tools")
    if allowed_tools is not None and (
        not isinstance(allowed_tools, str) or not allowed_tools.strip()
    ):
        raise ForgeError(
            f"{diagnostic_value(skill_md)} allowed-tools must be a non-empty space-separated string"
        )
    if not body.strip():
        raise ForgeError(
            f"{diagnostic_value(skill_md)} needs instruction content after frontmatter"
        )
    return value


def inspect_tree(root: Path) -> list[Path]:
    """Inspect a skill tree and return its safe regular files."""

    return inspect_regular_tree(root, required_root_file="SKILL.md", tree_label="Source")


def file_hashes(root: Path) -> dict[str, str]:
    """Return SHA-256 hashes for every safe file in a skill tree."""

    return _file_hashes(root, required_root_file="SKILL.md")


def tree_hash(hashes: dict[str, str]) -> str:
    """Compute a deterministic aggregate SHA-256 for a relative-path hash map."""

    digest = hashlib.sha256()
    for path, value in sorted(hashes.items()):
        digest.update(path.encode())
        digest.update(b"\0")
        digest.update(value.encode())
        digest.update(b"\n")
    return digest.hexdigest()


def repository_root(start: Path | None = None) -> Path:
    """Find the nearest Agent Plugin Forge repository root."""

    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / "catalog" / "plugins.json").is_file():
            return candidate
    raise ForgeError("Run this command inside an Agent Plugin Forge checkout")
