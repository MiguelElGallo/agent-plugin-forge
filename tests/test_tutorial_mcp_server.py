"""Test the tutorial MCP configuration and example server protocol flow."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from agent_plugin_forge.models import McpConfiguration, StdioServer


def request(process: subprocess.Popen[str], payload: dict[str, object]) -> dict[str, Any]:
    assert process.stdin is not None
    assert process.stdout is not None
    process.stdin.write(json.dumps(payload) + "\n")
    process.stdin.flush()
    line = process.stdout.readline()
    value = json.loads(line)
    assert isinstance(value, dict)
    return value


def notify(process: subprocess.Popen[str], payload: dict[str, object]) -> None:
    assert process.stdin is not None
    process.stdin.write(json.dumps(payload) + "\n")
    process.stdin.flush()


def test_tutorial_mcp_config_uses_the_portable_default_working_directory() -> None:
    config_path = Path(__file__).parents[1] / "examples" / "tutorial" / "status-mcp" / "mcp.json"
    configuration = McpConfiguration.model_validate_json(config_path.read_text(encoding="utf-8"))
    server = configuration.mcp_servers["release-status"]
    assert isinstance(server, StdioServer)
    assert server.command == "uv"
    assert server.args == ["run", "--no-project", "python", "${PLUGIN_ROOT}/server.py"]
    assert server.cwd is None


def test_tutorial_mcp_server_completes_handshake_and_tool_call() -> None:
    server = Path(__file__).parents[1] / "examples" / "tutorial" / "status-mcp" / "server.py"
    environment = {**os.environ, "PLUGIN_ROOT": str(server.parent), "PLUGIN_DATA": "data"}
    process = subprocess.Popen(
        [sys.executable, str(server)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=environment,
    )
    try:
        initialized = request(
            process,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "forge-test", "version": "1.0.0"},
                },
            },
        )
        assert initialized["result"]["serverInfo"]["name"] == "release-status"
        notify(process, {"jsonrpc": "2.0", "method": "notifications/initialized"})
        tools = request(process, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        assert tools["result"]["tools"][0]["name"] == "release_status"
        called = request(
            process,
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "release_status", "arguments": {}},
            },
        )
        text = called["result"]["content"][0]["text"]
        assert json.loads(text) == {
            "pluginDataAvailable": True,
            "pluginRootAvailable": True,
            "status": "ready",
        }
    finally:
        process.terminate()
        process.wait(timeout=5)
