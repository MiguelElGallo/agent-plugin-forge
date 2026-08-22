"""Load and validate portable MCP server configurations."""

from __future__ import annotations

import os
import stat
from pathlib import Path

from jsonschema import Draft202012Validator
from pydantic import ValidationError

from .common import load_json
from .errors import ForgeError
from .models import McpConfiguration, StdioServer


def _location(parts: tuple[object, ...]) -> str:
    """Format a validation-error location for a user-facing message."""

    return ".".join(str(part) for part in parts) or "<root>"


def load_mcp_configuration(repo: Path, plugin_root: Path) -> McpConfiguration | None:
    """Load and fully validate optional portable MCP configuration."""
    path = plugin_root / "mcp.json"
    if not path.exists():
        return None
    payload = load_json(path)
    schema = load_json(repo / "schemas" / "agent-plugins" / "1.0.0" / "mcp.schema.json")
    schema_errors = sorted(
        Draft202012Validator(schema).iter_errors(payload),
        key=lambda item: list(item.absolute_path),
    )
    if schema_errors:
        error = schema_errors[0]
        raise ForgeError(f"{path}: {_location(tuple(error.absolute_path))}: {error.message}")
    try:
        configuration = McpConfiguration.model_validate(payload)
    except ValidationError as exc:
        first = exc.errors(include_url=False)[0]
        raise ForgeError(f"{path}: {_location(tuple(first['loc']))}: {first['msg']}") from exc
    component_errors = mcp_component_errors(plugin_root, configuration)
    if component_errors:
        raise ForgeError(f"{path}: {component_errors[0]}")
    return configuration


def _plugin_root_path(plugin_root: Path, value: str) -> Path | None:
    """Resolve a supported plugin-root-relative MCP path expression."""

    if value.startswith("./"):
        return plugin_root.joinpath(*Path(value[2:]).parts)
    marker = "${PLUGIN_ROOT}"
    if value == marker:
        return plugin_root
    if value.startswith(f"{marker}/"):
        return plugin_root.joinpath(*Path(value[len(marker) + 1 :]).parts)
    return None


def mcp_component_errors(plugin_root: Path, configuration: McpConfiguration) -> list[str]:
    """Return packaged-command and working-directory errors for MCP servers."""

    errors: list[str] = []
    root = plugin_root.resolve()
    for name, server in configuration.mcp_servers.items():
        if not isinstance(server, StdioServer):
            continue
        if server.command.startswith("./"):
            command = _plugin_root_path(plugin_root, server.command)
            if command is None or not command.resolve().is_relative_to(root):
                errors.append(f"MCP server {name!r} command escapes the plugin root")
            else:
                try:
                    mode = command.lstat().st_mode
                except OSError as exc:
                    errors.append(f"MCP server {name!r} command does not exist: {command} ({exc})")
                else:
                    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
                        errors.append(
                            f"MCP server {name!r} command must be a regular packaged file: "
                            f"{command}"
                        )
                    elif os.name != "nt" and not mode & 0o111:
                        errors.append(f"MCP server {name!r} command is not executable: {command}")
        if server.cwd is not None:
            cwd = _plugin_root_path(plugin_root, server.cwd)
            if cwd is not None:
                if not cwd.resolve().is_relative_to(root):
                    errors.append(f"MCP server {name!r} cwd escapes the plugin root")
                elif not cwd.is_dir():
                    errors.append(f"MCP server {name!r} cwd is not a packaged directory: {cwd}")
    return errors
