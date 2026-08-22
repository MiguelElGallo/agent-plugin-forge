#!/usr/bin/env python3
"""Dependency-free MCP server used by the Agent Plugin Forge tutorial."""

from __future__ import annotations

import json
import os
import sys
from typing import Any

PROTOCOL_VERSION = "2024-11-05"
TOOL_NAME = "release_status"


def response(request_id: object, result: object) -> dict[str, object]:
    """Build a successful JSON-RPC response object."""

    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def error(request_id: object, code: int, message: str) -> dict[str, object]:
    """Build a JSON-RPC error response object."""

    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }


def handle(message: dict[str, Any]) -> dict[str, object] | None:
    """Handle one MCP JSON-RPC message and return an optional response."""

    request_id = message.get("id")
    method = message.get("method")
    if method == "initialize":
        return response(
            request_id,
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "release-status", "version": "1.0.0"},
            },
        )
    if method == "notifications/initialized" or (
        isinstance(method, str) and method.startswith("notifications/")
    ):
        return None
    if method == "tools/list":
        return response(
            request_id,
            {
                "tools": [
                    {
                        "name": TOOL_NAME,
                        "description": "Report whether the tutorial plugin runtime is ready.",
                        "inputSchema": {"type": "object", "properties": {}},
                    }
                ]
            },
        )
    if method == "tools/call":
        params = message.get("params")
        name = params.get("name") if isinstance(params, dict) else None
        if name != TOOL_NAME:
            return error(request_id, -32601, f"Unknown tool: {name}")
        status = {
            "status": "ready",
            "pluginRootAvailable": bool(os.environ.get("PLUGIN_ROOT")),
            "pluginDataAvailable": bool(os.environ.get("PLUGIN_DATA")),
        }
        return response(
            request_id,
            {"content": [{"type": "text", "text": json.dumps(status, sort_keys=True)}]},
        )
    if method == "ping":
        return response(request_id, {})
    return error(request_id, -32601, f"Method not found: {method}")


def send(message: dict[str, object]) -> None:
    """Write one compact JSON-RPC message to standard output."""

    sys.stdout.write(json.dumps(message, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def main() -> None:
    """Serve newline-delimited MCP messages on standard input and output."""

    for line in sys.stdin:
        try:
            message = json.loads(line)
            if not isinstance(message, dict):
                raise ValueError("request must be an object")
            result = handle(message)
        except (json.JSONDecodeError, ValueError) as exc:
            result = error(None, -32700, f"Parse error: {exc}")
        except Exception as exc:  # defensive process boundary
            result = error(None, -32603, f"Internal error: {exc}")
        if result is not None:
            send(result)


if __name__ == "__main__":
    main()
