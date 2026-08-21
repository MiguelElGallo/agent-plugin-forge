from __future__ import annotations

import os
import shutil
import stat
import tempfile
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from pydantic import ValidationError

from .codex_contract import assert_valid_codex_wrapper
from .common import ForgeError, contained_child, json_bytes, load_json, parse_semver, validate_name
from .importer import _copy_regular_tree
from .models import Catalog, CodexManifest


def _path_safety_errors(repo: Path, path: Path, *, directory: bool) -> list[str]:
    errors: list[str] = []
    try:
        relative = path.relative_to(repo)
    except ValueError:
        return [f"Generated output escapes the repository: {path}"]
    current = repo
    for index, part in enumerate(relative.parts):
        current /= part
        try:
            mode = current.lstat().st_mode
        except FileNotFoundError:
            break
        if stat.S_ISLNK(mode):
            errors.append(f"Generated output path contains a symlink: {current.relative_to(repo)}")
            break
        is_target = index == len(relative.parts) - 1
        if not is_target and not stat.S_ISDIR(mode):
            errors.append(
                f"Generated output parent is not a directory: {current.relative_to(repo)}"
            )
            break
        if is_target:
            expected = stat.S_ISDIR(mode) if directory else stat.S_ISREG(mode)
            if not expected:
                kind = "directory" if directory else "regular file"
                errors.append(f"Generated output must be a {kind}: {relative}")
    return errors


def _tree_safety_errors(repo: Path, root: Path) -> list[str]:
    errors = _path_safety_errors(repo, root, directory=True)
    if errors or not root.exists():
        return errors
    for path in sorted(root.rglob("*")):
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode):
            errors.append(f"Generated output contains a symlink: {path.relative_to(repo)}")
        elif not stat.S_ISDIR(mode) and not stat.S_ISREG(mode):
            errors.append(f"Generated output contains a special file: {path.relative_to(repo)}")
    return errors


def _output_safety_errors(repo: Path, marketplace_paths: list[Path]) -> list[str]:
    errors: list[str] = []
    for path in marketplace_paths:
        errors.extend(_path_safety_errors(repo, path, directory=False))
    errors.extend(_tree_safety_errors(repo, repo / "compat" / "codex" / "plugins"))
    return errors


def _entries(repo: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    try:
        catalog = Catalog.model_validate(load_json(repo / "catalog" / "plugins.json"))
    except ValidationError as exc:
        raise ForgeError(f"Invalid catalog: {exc.errors()[0]['msg']}") from exc
    payload = catalog.model_dump(by_alias=True)
    marketplace = payload["marketplace"]
    entries = payload["plugins"]
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ForgeError("Catalog plugin entries must be objects")
        name = entry.get("name")
        if not isinstance(name, str):
            raise ForgeError("Catalog plugin names must be strings")
        validate_name(name, kind="plugin")
        if name in seen:
            raise ForgeError(f"Duplicate catalog plugin: {name}")
        seen.add(name)
        if not isinstance(entry.get("category"), str) or not entry["category"].strip():
            raise ForgeError(f"Catalog category must be non-empty for {name}")
        if not isinstance(entry.get("codexCompatibility"), bool):
            raise ForgeError(f"codexCompatibility must be Boolean for {name}")
    return marketplace, entries


def render_marketplaces(repo: Path) -> dict[Path, bytes]:
    marketplace, entries = _entries(repo)
    manifests = _validated_manifests(repo, entries)
    copilot = {
        "name": marketplace["name"],
        "owner": marketplace["owner"],
        "metadata": {
            "description": marketplace["description"],
            "version": marketplace["version"],
        },
        "plugins": [
            {
                "name": manifest["name"],
                "description": manifest["description"],
                "version": manifest["version"],
                "source": f"./plugins/{entry['name']}",
            }
            for entry, manifest in manifests
        ],
    }
    codex = {
        "name": marketplace["name"],
        "interface": {"displayName": marketplace["displayName"]},
        "plugins": [
            {
                "name": entry["name"],
                "source": {
                    "source": "local",
                    "path": f"./compat/codex/plugins/{entry['name']}",
                },
                "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
                "category": entry["category"],
            }
            for entry, _ in manifests
            if entry["codexCompatibility"]
        ],
    }
    return {
        repo / ".github" / "plugin" / "marketplace.json": json_bytes(copilot),
        repo / ".agents" / "plugins" / "marketplace.json": json_bytes(codex),
    }


def _validated_manifests(
    repo: Path, entries: list[dict[str, Any]]
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    schema = load_json(repo / "schemas" / "agent-plugins" / "1.0.0" / "plugin.schema.json")
    validator = Draft202012Validator(schema)
    manifests: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for entry in entries:
        plugin_root = contained_child(repo / "plugins", entry["name"], kind="plugin")
        if (plugin_root / "mcp.json").exists():
            raise ForgeError("Agent Plugin Forge v0.1 is skills-only; mcp.json is not supported")
        manifest = load_json(plugin_root / "plugin.json")
        schema_errors = list(validator.iter_errors(manifest))
        if schema_errors:
            raise ForgeError(
                f"Invalid portable manifest for {entry['name']}: {schema_errors[0].message}"
            )
        if manifest.get("name") != entry["name"]:
            raise ForgeError(f"Catalog and manifest identity differ for {entry['name']}")
        parse_semver(manifest.get("version"), label=f"{entry['name']} version")
        if entry["codexCompatibility"]:
            if (
                not isinstance(manifest.get("description"), str)
                or not manifest["description"].strip()
            ):
                raise ForgeError(f"Codex compatibility requires description for {entry['name']}")
            author = manifest.get("author")
            if (
                not isinstance(author, dict)
                or not isinstance(author.get("name"), str)
                or not author["name"].strip()
            ):
                raise ForgeError(f"Codex compatibility requires author.name for {entry['name']}")
        manifests.append((entry, manifest))
    return manifests


def _codex_manifest(manifest: dict[str, Any], entry: dict[str, Any]) -> dict[str, Any]:
    allowed = (
        "name",
        "version",
        "description",
        "author",
        "homepage",
        "repository",
        "license",
        "keywords",
    )
    result = {key: manifest[key] for key in allowed if key in manifest}
    result["skills"] = "./skills/"
    description = str(manifest.get("description", "Agent plugin"))
    display_name = str(manifest["name"]).replace("-", " ").title()
    interface: dict[str, Any] = {
        "displayName": display_name,
        "shortDescription": description,
        "longDescription": description,
        "developerName": manifest.get("author", {}).get("name", "Unknown"),
        "category": entry["category"],
        "capabilities": ["Instructions"],
        "defaultPrompt": [f"Use {display_name} for this task."],
    }
    if "homepage" in manifest:
        interface["websiteURL"] = manifest["homepage"]
    result["interface"] = interface
    _validate_codex_manifest(result)
    return result


def _validate_codex_manifest(manifest: dict[str, Any]) -> None:
    try:
        validated = CodexManifest.model_validate(manifest)
    except ValidationError as exc:
        raise ForgeError(f"Invalid generated Codex manifest: {exc.errors()[0]['msg']}") from exc
    parse_semver(validated.version, label="Generated Codex version")


def _write_wrappers(repo: Path, destination: Path) -> None:
    _, entries = _entries(repo)
    for entry, manifest in _validated_manifests(repo, entries):
        if not entry["codexCompatibility"]:
            continue
        name = entry["name"]
        portable = contained_child(repo / "plugins", name, kind="plugin")
        wrapper = contained_child(destination, name, kind="plugin")
        (wrapper / ".codex-plugin").mkdir(parents=True)
        (wrapper / ".codex-plugin" / "plugin.json").write_bytes(
            json_bytes(_codex_manifest(manifest, entry))
        )
        _copy_regular_tree(portable / "skills", wrapper / "skills")
        for notice_name in ("LICENSE", "NOTICE"):
            notice = portable / notice_name
            if notice.exists():
                if notice.is_symlink() or not notice.is_file():
                    raise ForgeError(f"Unsafe distribution notice: {notice}")
                (wrapper / notice_name).write_bytes(notice.read_bytes())
        for notice_dir in ("licenses", "LICENSES"):
            source_dir = portable / notice_dir
            if source_dir.exists():
                _copy_regular_tree(source_dir, wrapper / notice_dir)
        assert_valid_codex_wrapper(repo, wrapper)


def generate(repo: Path) -> None:
    rendered = render_marketplaces(repo)
    wrappers = repo / "compat" / "codex" / "plugins"
    safety_errors = _output_safety_errors(repo, list(rendered))
    if safety_errors:
        raise ForgeError("Unsafe generated output:\n- " + "\n- ".join(safety_errors))

    with tempfile.TemporaryDirectory(prefix=".forge-generate-", dir=repo) as temporary:
        staging = Path(temporary) / "staging"
        for path, content in rendered.items():
            staged = staging / path.relative_to(repo)
            staged.parent.mkdir(parents=True, exist_ok=True)
            staged.write_bytes(content)
        staged_wrappers = staging / wrappers.relative_to(repo)
        staged_wrappers.mkdir(parents=True)
        _write_wrappers(repo, staged_wrappers)

        targets = [*rendered, wrappers]
        backups = Path(temporary) / "backups"
        replaced: list[tuple[Path, Path | None]] = []
        try:
            for target in targets:
                staged = staging / target.relative_to(repo)
                target.parent.mkdir(parents=True, exist_ok=True)
                backup: Path | None = None
                if target.exists():
                    backup = backups / target.relative_to(repo)
                    backup.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(target, backup)
                replaced.append((target, backup))
                os.replace(staged, target)
        except Exception:
            for target, backup in reversed(replaced):
                if target.is_dir():
                    shutil.rmtree(target)
                elif target.exists():
                    target.unlink()
                if backup is not None and backup.exists():
                    backup.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(backup, target)
            raise


def generation_drift(repo: Path) -> list[str]:
    errors: list[str] = []
    rendered = render_marketplaces(repo)
    safety_errors = _output_safety_errors(repo, list(rendered))
    if safety_errors:
        return safety_errors
    for path, expected in rendered.items():
        if not path.is_file() or path.read_bytes() != expected:
            errors.append(f"Generated marketplace is stale: {path.relative_to(repo)}")
    with tempfile.TemporaryDirectory() as temp:
        expected_root = Path(temp) / "plugins"
        expected_root.mkdir()
        _write_wrappers(repo, expected_root)
        actual_root = repo / "compat" / "codex" / "plugins"
        expected_files = {
            path.relative_to(expected_root): path.read_bytes()
            for path in expected_root.rglob("*")
            if path.is_file()
        }
        actual_files = (
            {
                path.relative_to(actual_root): path.read_bytes()
                for path in actual_root.rglob("*")
                if path.is_file()
            }
            if actual_root.exists()
            else {}
        )
        if actual_files != expected_files:
            errors.append("Generated Codex compatibility wrappers are stale")
    return errors
