"""Load and validate portable Agent Plugin packages from the catalog."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from jsonschema import Draft202012Validator
from pydantic import ValidationError

from .common import contained_child, load_json, parse_skill_frontmatter
from .errors import ForgeError, diagnostic_value
from .filesystem import inspect_regular_tree
from .mcp import load_mcp_configuration
from .models import Catalog, CatalogPlugin, McpConfiguration, PortableManifest, SseServer


@dataclass(frozen=True)
class PortablePackage:
    """Represent one validated portable plugin and its discovered components."""

    entry: CatalogPlugin
    manifest: PortableManifest
    root: Path
    skill_roots: tuple[Path, ...]
    mcp: McpConfiguration | None

    @property
    def has_skills(self) -> bool:
        """Return whether the package contains at least one Agent Skill."""

        return bool(self.skill_roots)

    @property
    def has_mcp(self) -> bool:
        """Return whether the package defines at least one MCP server."""

        return self.mcp is not None and bool(self.mcp.mcp_servers)


def load_catalog(repo: Path) -> Catalog:
    """Load and validate the repository's canonical plugin catalog."""

    try:
        return Catalog.model_validate(load_json(repo / "catalog" / "plugins.json"))
    except ValidationError as exc:
        first = exc.errors(include_url=False)[0]
        location = ".".join(str(part) for part in first["loc"]) or "<root>"
        raise ForgeError(
            f"Invalid catalog at {diagnostic_value(location)}: {diagnostic_value(first['msg'])}"
        ) from exc


def _load_manifest(repo: Path, plugin_root: Path, expected_name: str) -> PortableManifest:
    """Load a portable manifest and verify its schema and catalog identity."""

    path = plugin_root / "plugin.json"
    payload = load_json(path)
    schema = load_json(repo / "schemas" / "agent-plugins" / "1.0.0" / "plugin.schema.json")
    schema_errors = sorted(
        Draft202012Validator(schema).iter_errors(payload),
        key=lambda item: list(item.absolute_path),
    )
    if schema_errors:
        error = schema_errors[0]
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        raise ForgeError(
            f"Invalid portable manifest {diagnostic_value(path)} at {diagnostic_value(location)}: "
            f"{diagnostic_value(error.message)}"
        )
    try:
        manifest = PortableManifest.model_validate(payload)
    except ValidationError as exc:
        first = exc.errors(include_url=False)[0]
        location = ".".join(str(part) for part in first["loc"]) or "<root>"
        raise ForgeError(
            f"Invalid portable manifest {diagnostic_value(path)} at {diagnostic_value(location)}: "
            f"{diagnostic_value(first['msg'])}"
        ) from exc
    if manifest.name != expected_name:
        raise ForgeError(
            f"Catalog name {expected_name!r} does not match manifest name {manifest.name!r}"
        )
    return manifest


def _skill_roots(plugin_root: Path) -> tuple[Path, ...]:
    """Discover and validate immediate Agent Skill directories in a plugin."""

    skills_root = plugin_root / "skills"
    if not skills_root.exists():
        return ()
    if not skills_root.is_dir() or skills_root.is_symlink():
        raise ForgeError(f"skills must be a real directory: {diagnostic_value(skills_root)}")
    unexpected = [path.name for path in skills_root.iterdir() if not path.is_dir()]
    if unexpected:
        raise ForgeError(f"skills contains non-directory entries: {sorted(unexpected)}")
    direct = tuple(sorted(skills_root.iterdir(), key=lambda path: path.name))
    for skill_root in direct:
        inspect_regular_tree(
            skill_root,
            required_root_file="SKILL.md",
            tree_label=f"Skill {skill_root.name}",
        )
        metadata = parse_skill_frontmatter(skill_root / "SKILL.md")
        if metadata["name"] != skill_root.name:
            raise ForgeError(
                f"Skill folder/name mismatch: {skill_root.name!r} != {metadata['name']!r}"
            )
    for skill_md in skills_root.rglob("SKILL.md"):
        if skill_md.parent.parent != skills_root:
            raise ForgeError(f"Nested, undiscoverable SKILL.md: {diagnostic_value(skill_md)}")
    return direct


def load_package(repo: Path, entry: CatalogPlugin) -> PortablePackage:
    """Load and validate one cataloged portable plugin package."""

    plugin_root = contained_child(repo / "plugins", entry.name, kind="plugin")
    inspect_regular_tree(plugin_root, required_root_file="plugin.json", tree_label="Plugin")
    if (plugin_root / ".codex-plugin").exists():
        raise ForgeError(
            f"Plugin {entry.name!r} contains reserved Codex overlay .codex-plugin; "
            "portable packages must have one client-independent execution surface"
        )
    manifest = _load_manifest(repo, plugin_root, entry.name)
    skills = _skill_roots(plugin_root)
    mcp = load_mcp_configuration(repo, plugin_root)
    if (
        entry.codex_compatibility
        and mcp is not None
        and any(isinstance(server, SseServer) for server in mcp.mcp_servers.values())
    ):
        raise ForgeError(
            f"Plugin {entry.name!r} enables Codex compatibility but uses unsupported SSE MCP"
        )
    if not skills and (mcp is None or not mcp.mcp_servers):
        raise ForgeError(f"Plugin {entry.name!r} has no discoverable skill or MCP server")
    if not manifest.version:
        raise ForgeError(f"Marketplace distribution requires version for {entry.name}")
    if not manifest.description or not manifest.description.strip():
        raise ForgeError(f"Marketplace distribution requires description for {entry.name}")
    return PortablePackage(entry, manifest, plugin_root, skills, mcp)


def load_packages(repo: Path) -> tuple[Catalog, tuple[PortablePackage, ...]]:
    """Load the canonical catalog and every package referenced by it."""

    catalog = load_catalog(repo)
    packages = tuple(load_package(repo, entry) for entry in catalog.plugins)
    return catalog, packages
