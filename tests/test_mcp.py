from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from agent_plugin_forge.common import ForgeError
from agent_plugin_forge.generator import generate, generation_drift
from agent_plugin_forge.mcp import load_mcp_configuration
from agent_plugin_forge.models import McpConfiguration
from agent_plugin_forge.validator import validate_repository

from .test_importer import apply_reviewed

MCP_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json"


def configuration(server: dict[str, object]) -> dict[str, object]:
    return {"$schema": MCP_SCHEMA, "mcpServers": {"test-server": server}}


def write_mcp(plugin_root: Path, server: dict[str, object]) -> None:
    (plugin_root / "mcp.json").write_text(json.dumps(configuration(server)), encoding="utf-8")


@pytest.mark.parametrize(
    "command",
    [
        "/bin/server",
        "../server",
        "./../server",
        "${PLUGIN_ROOT}/server",
        "python -m mcp",
        " python3",
        "python3 ",
    ],
)
def test_stdio_rejects_nonportable_commands(command: str) -> None:
    with pytest.raises(ValidationError, match="command"):
        McpConfiguration.model_validate(configuration({"type": "stdio", "command": command}))


@pytest.mark.parametrize(
    "cwd",
    ["data", "../data", "./../data", "${PLUGIN_ROOT}/../data", "${PLUGIN_DATA}/../data"],
)
def test_stdio_rejects_escaping_working_directories(cwd: str) -> None:
    with pytest.raises(ValidationError, match="cwd"):
        McpConfiguration.model_validate(
            configuration({"type": "stdio", "command": "python3", "cwd": cwd})
        )


def test_stdio_rejects_case_variant_root_override() -> None:
    with pytest.raises(ValidationError, match="environment cannot override"):
        McpConfiguration.model_validate(
            configuration({"type": "stdio", "command": "python3", "env": {"plugin_root": "bad"}})
        )


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com/mcp",
        "https://user@example.com/mcp",
        "https://example.com/mcp#fragment",
        "https://example.com:notaport/mcp",
        "https://example.com:99999/mcp",
        "https://example.com/a path",
        "ftp://example.com/mcp",
        "/relative/mcp",
    ],
)
def test_remote_transport_rejects_unsafe_urls(url: str) -> None:
    with pytest.raises(ValidationError, match="url|loopback"):
        McpConfiguration.model_validate(configuration({"type": "streamable-http", "url": url}))


@pytest.mark.parametrize(
    "url",
    ["https://example.com/mcp", "http://localhost:8000/mcp", "http://127.0.0.1/mcp"],
)
def test_remote_transport_accepts_secure_and_loopback_urls(url: str) -> None:
    model = McpConfiguration.model_validate(configuration({"type": "streamable-http", "url": url}))
    assert model.mcp_servers["test-server"].type == "streamable-http"


def test_remote_transport_rejects_case_duplicate_headers() -> None:
    with pytest.raises(ValidationError, match="duplicate case-insensitive"):
        McpConfiguration.model_validate(
            configuration(
                {
                    "type": "streamable-http",
                    "url": "https://example.com/mcp",
                    "headers": {"X-Tenant": "one", "x-tenant": "two"},
                }
            )
        )


@pytest.mark.parametrize(
    ("headers", "message"),
    [
        ({"Bad Header": "value"}, "invalid HTTP header name"),
        ({"Authorization": "token"}, "credentials"),
    ],
)
def test_remote_transport_rejects_invalid_or_secret_headers(
    headers: dict[str, str], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        McpConfiguration.model_validate(
            configuration(
                {"type": "streamable-http", "url": "https://example.com/mcp", "headers": headers}
            )
        )


def test_remote_transport_rejects_delete_in_header_value() -> None:
    with pytest.raises(ValidationError, match="invalid HTTP header value"):
        McpConfiguration.model_validate(
            configuration(
                {
                    "type": "streamable-http",
                    "url": "https://example.com/mcp",
                    "headers": {"X-Public": "bad\x7fvalue"},
                }
            )
        )


def test_mcp_server_identifier_is_not_silently_trimmed() -> None:
    payload = {
        "$schema": MCP_SCHEMA,
        "mcpServers": {" spaced ": {"type": "streamable-http", "url": "https://example.com/mcp"}},
    }
    model = McpConfiguration.model_validate(payload)
    assert list(model.mcp_servers) == [" spaced "]


def test_load_rejects_missing_relative_command(empty_forge: Path, skill_source: Path) -> None:
    apply_reviewed(empty_forge, skill_source)
    plugin_root = empty_forge / "plugins" / "sample-skill"
    write_mcp(plugin_root, {"type": "stdio", "command": "./bin/missing"})
    with pytest.raises(ForgeError, match="command does not exist"):
        load_mcp_configuration(empty_forge, plugin_root)


def test_mixed_plugin_uses_portable_package_for_codex(
    empty_forge: Path, skill_source: Path
) -> None:
    apply_reviewed(empty_forge, skill_source)
    plugin_root = empty_forge / "plugins" / "sample-skill"
    runtime = plugin_root / "server.py"
    runtime.write_text("print('server')\n", encoding="utf-8")
    write_mcp(
        plugin_root,
        {
            "type": "stdio",
            "command": "python3",
            "args": ["${PLUGIN_ROOT}/server.py"],
        },
    )

    generate(empty_forge)

    marketplace = json.loads((empty_forge / ".agents" / "plugins" / "marketplace.json").read_text())
    assert marketplace["plugins"][0]["source"]["path"] == "./plugins/sample-skill"
    assert json.loads((plugin_root / "mcp.json").read_text())["$schema"] == MCP_SCHEMA
    assert (plugin_root / "server.py").read_bytes() == runtime.read_bytes()
    assert generation_drift(empty_forge) == []


def test_mcp_only_plugin_is_listed_for_codex(empty_forge: Path) -> None:
    catalog_path = empty_forge / "catalog" / "plugins.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    catalog["plugins"].append(
        {"name": "mcp-only", "category": "Developer Tools", "codexCompatibility": True}
    )
    catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
    plugin = empty_forge / "plugins" / "mcp-only"
    plugin.mkdir()
    (plugin / "plugin.json").write_text(
        json.dumps(
            {
                "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
                "name": "mcp-only",
                "version": "1.0.0",
                "description": "An MCP-only plugin.",
                "author": {"name": "Test Author"},
                "license": "MIT",
            }
        ),
        encoding="utf-8",
    )
    (plugin / "LICENSE").write_text("Test license\n", encoding="utf-8")
    (plugin / "server.py").write_text("print('server')\n", encoding="utf-8")
    write_mcp(
        plugin,
        {"type": "stdio", "command": "python3", "args": ["${PLUGIN_ROOT}/server.py"]},
    )

    generate(empty_forge)

    marketplace = json.loads((empty_forge / ".agents" / "plugins" / "marketplace.json").read_text())
    assert marketplace["plugins"][0]["source"]["path"] == "./plugins/mcp-only"


def test_codex_compatible_plugin_rejects_sse_transport(
    empty_forge: Path, skill_source: Path
) -> None:
    apply_reviewed(empty_forge, skill_source)
    plugin = empty_forge / "plugins" / "sample-skill"
    write_mcp(plugin, {"type": "sse", "url": "https://example.com/events"})
    errors = validate_repository(empty_forge)
    assert any("unsupported SSE MCP" in error for error in errors)


def test_portable_package_rejects_codex_overlay(empty_forge: Path, skill_source: Path) -> None:
    apply_reviewed(empty_forge, skill_source)
    overlay = empty_forge / "plugins" / "sample-skill" / ".codex-plugin"
    overlay.mkdir()
    (overlay / "plugin.json").write_text("{}\n", encoding="utf-8")
    errors = validate_repository(empty_forge)
    assert any("reserved Codex overlay" in error for error in errors)


def test_load_reports_json_schema_location(empty_forge: Path, skill_source: Path) -> None:
    apply_reviewed(empty_forge, skill_source)
    plugin_root = empty_forge / "plugins" / "sample-skill"
    payload = configuration({"type": "stdio", "command": "python3", "unexpected": True})
    (plugin_root / "mcp.json").write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ForgeError, match="not valid under any of the given schemas"):
        load_mcp_configuration(empty_forge, plugin_root)


def test_relative_command_and_plugin_cwd_must_exist(empty_forge: Path, skill_source: Path) -> None:
    apply_reviewed(empty_forge, skill_source)
    plugin_root = empty_forge / "plugins" / "sample-skill"
    binary = plugin_root / "bin" / "server"
    binary.parent.mkdir()
    binary.write_text("server\n", encoding="utf-8")
    binary.chmod(0o755)
    write_mcp(
        plugin_root,
        {"type": "stdio", "command": "./bin/server", "cwd": "${PLUGIN_ROOT}/bin"},
    )
    loaded = load_mcp_configuration(empty_forge, plugin_root)
    assert loaded is not None


@pytest.mark.skipif(os.name == "nt", reason="Windows does not expose portable execute bits")
def test_relative_command_must_be_executable(empty_forge: Path, skill_source: Path) -> None:
    apply_reviewed(empty_forge, skill_source)
    plugin_root = empty_forge / "plugins" / "sample-skill"
    binary = plugin_root / "bin" / "server"
    binary.parent.mkdir()
    binary.write_text("server\n", encoding="utf-8")
    binary.chmod(0o644)
    write_mcp(plugin_root, {"type": "stdio", "command": "./bin/server"})
    with pytest.raises(ForgeError, match="command is not executable"):
        load_mcp_configuration(empty_forge, plugin_root)
