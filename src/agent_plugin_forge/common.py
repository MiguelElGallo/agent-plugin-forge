from __future__ import annotations

import hashlib
import json
import re
import stat
from pathlib import Path
from typing import Any

import yaml
from license_expression import ExpressionError, get_spdx_licensing
from semantic_version import Version

PLUGIN_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
PLUGIN_NAME_RE = re.compile(r"^(?!.*(?:--|\.\.))[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$")
SKILL_NAME_RE = re.compile(r"^(?!.*--)[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")
SECRET_NAME_RE = re.compile(
    r"(^|/)(\.env(?:\..*)?|id_(?:rsa|dsa|ecdsa|ed25519)|.*\.(?:pem|p12|pfx|key))$",
    re.IGNORECASE,
)
SECRET_CONTENT_RES = (
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(rb"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(rb"AKIA[0-9A-Z]{16}"),
)
MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_TREE_BYTES = 50 * 1024 * 1024
SPDX_LICENSING = get_spdx_licensing()


class ForgeError(ValueError):
    """A user-correctable forge error."""


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ForgeError(f"Cannot read JSON from {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ForgeError(f"Expected a JSON object in {path}")
    return value


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode()


def validate_name(value: str, *, kind: str) -> None:
    pattern = SKILL_NAME_RE if kind == "skill" else PLUGIN_NAME_RE
    if len(value) > 64 or not pattern.fullmatch(value):
        raise ForgeError(
            f"Invalid {kind} name {value!r}; use the Agent Plugins lowercase name form"
        )


def contained_child(root: Path, name: str, *, kind: str) -> Path:
    validate_name(name, kind=kind)
    root_resolved = root.resolve()
    child = root / name
    if not child.resolve().is_relative_to(root_resolved):
        raise ForgeError(f"{kind.title()} path escapes its root: {name}")
    return child


def parse_semver(value: object, *, label: str) -> Version:
    if not isinstance(value, str):
        raise ForgeError(f"{label} must use strict Semantic Versioning")
    try:
        return Version(value)
    except ValueError as exc:
        raise ForgeError(f"{label} must use strict Semantic Versioning") from exc


def validate_spdx_expression(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ForgeError(f"{label} must be a valid SPDX license expression")
    try:
        SPDX_LICENSING.parse(value, validate=True, strict=True)
    except ExpressionError as exc:
        raise ForgeError(f"{label} must be a valid SPDX license expression") from exc
    return value


def parse_skill_frontmatter(skill_md: Path) -> dict[str, Any]:
    text = skill_md.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ForgeError(f"{skill_md} must start with YAML frontmatter")
    closing = text.find("\n---\n", 4)
    if closing < 0:
        raise ForgeError(f"{skill_md} has unterminated YAML frontmatter")
    frontmatter = text[4:closing]
    body = text[closing + 5 :]
    try:
        value = yaml.safe_load(frontmatter)
    except yaml.YAMLError as exc:
        raise ForgeError(f"{skill_md} has invalid YAML frontmatter: {exc}") from exc
    if not isinstance(value, dict):
        raise ForgeError(f"{skill_md} frontmatter must be a mapping")
    name = value.get("name")
    description = value.get("description")
    if not isinstance(name, str) or not isinstance(description, str) or not description.strip():
        raise ForgeError(f"{skill_md} requires string name and non-empty description fields")
    validate_name(name, kind="skill")
    if len(description) > 1024:
        raise ForgeError(f"{skill_md} description exceeds 1024 characters")
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
        raise ForgeError(f"{skill_md} has unsupported frontmatter fields: {sorted(unknown)}")
    license_value = value.get("license")
    if license_value is not None and (
        not isinstance(license_value, str) or not license_value.strip()
    ):
        raise ForgeError(f"{skill_md} license must be a non-empty string")
    compatibility = value.get("compatibility")
    if compatibility is not None and (
        not isinstance(compatibility, str) or not compatibility.strip() or len(compatibility) > 500
    ):
        raise ForgeError(f"{skill_md} compatibility must be a 1-500 character string")
    metadata = value.get("metadata")
    if metadata is not None and (
        not isinstance(metadata, dict)
        or not all(isinstance(key, str) and isinstance(item, str) for key, item in metadata.items())
    ):
        raise ForgeError(f"{skill_md} metadata must map strings to strings")
    allowed_tools = value.get("allowed-tools")
    if allowed_tools is not None and (
        not isinstance(allowed_tools, str) or not allowed_tools.strip()
    ):
        raise ForgeError(f"{skill_md} allowed-tools must be a non-empty space-separated string")
    if not body.strip():
        raise ForgeError(f"{skill_md} needs instruction content after frontmatter")
    return value


def inspect_tree(root: Path) -> list[Path]:
    if not root.is_dir():
        raise ForgeError(f"Source must be a skill directory: {root}")
    files: list[Path] = []
    folded: dict[str, str] = {}
    total = 0
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        folded_name = relative.as_posix().casefold()
        previous = folded.get(folded_name)
        if previous is not None and previous != relative.as_posix():
            raise ForgeError(f"Case-fold path collision: {previous} and {relative.as_posix()}")
        folded[folded_name] = relative.as_posix()
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode):
            raise ForgeError(f"Symlinks are not imported: {relative}")
        if path.is_dir():
            continue
        if not stat.S_ISREG(mode):
            raise ForgeError(f"Special files are not imported: {relative}")
        size = path.stat().st_size
        if size > MAX_FILE_BYTES:
            raise ForgeError(f"File exceeds {MAX_FILE_BYTES} bytes: {relative}")
        total += size
        if total > MAX_TREE_BYTES:
            raise ForgeError(f"Skill tree exceeds {MAX_TREE_BYTES} bytes")
        relative_text = relative.as_posix()
        if SECRET_NAME_RE.search(relative_text):
            raise ForgeError(f"Possible secret file is not imported: {relative_text}")
        data = path.read_bytes()
        if any(pattern.search(data) for pattern in SECRET_CONTENT_RES):
            raise ForgeError(f"Possible secret content is not imported: {relative_text}")
        files.append(path)
    if not (root / "SKILL.md").is_file():
        raise ForgeError(f"Source does not contain SKILL.md at its root: {root}")
    return files


def file_hashes(root: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for path in inspect_tree(root):
        hashes[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def tree_hash(hashes: dict[str, str]) -> str:
    digest = hashlib.sha256()
    for path, value in sorted(hashes.items()):
        digest.update(path.encode())
        digest.update(b"\0")
        digest.update(value.encode())
        digest.update(b"\n")
    return digest.hexdigest()


def repository_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / "catalog" / "plugins.json").is_file():
            return candidate
    raise ForgeError("Run this command inside an Agent Plugin Forge checkout")
