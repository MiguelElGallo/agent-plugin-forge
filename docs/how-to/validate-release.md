# Validate and release the forge

The `Check` workflow runs the same repository gate on pull requests and pushes to `main`. Unit and integration tests run on Linux, macOS, and Windows. Third-party actions are pinned to full commits.

## Local release gate

```bash
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run ty check
uv run pytest
uv run forge generate --check
uv run forge check
uv run zensical build --clean --strict
```

Pydantic owns forge-specific catalog, provenance, marketplace, and MCP semantic contracts. Vendored JSON Schema remains authoritative for Agent Plugins `plugin.json` and `mcp.json`. Schema bytes are pinned by complete checksums for offline validation.

## Client acceptance matrix

Before release, record exact versions and test both the installed user journey and direct contributor workflow:

1. install the exact current `agent-plugin-forge` package in an isolated VS Code profile and confirm `package-agent-skill` in **Chat: Configure Skills**;
2. run the packaged bootstrap helper against an isolated Git remote and verify temporary creation, alternate origin, persistent reuse, clean `main`, and exact revision;
3. install the same package in isolated Copilot CLI and Codex homes;
4. open a disposable contributor clone in VS Code and run the manual tutorial commands;
5. register a local portable fixture with `chat.pluginLocations`, confirm its skill and MCP server, and call a credential-free tool.

Marketplace command pairs:

```bash
copilot plugin marketplace add MiguelElGallo/agent-plugin-forge
copilot plugin install agent-plugin-forge@agent-plugin-forge
copilot plugin list

codex plugin marketplace add MiguelElGallo/agent-plugin-forge
codex plugin add agent-plugin-forge@agent-plugin-forge
codex plugin list
```

Use isolated client homes for repeatable tests. Do not remove or replace a user's existing marketplace registrations during acceptance.

For private-marketplace qualification, use a disposable private or local Git source. Confirm that all clients accept the same HTTPS or SSH marketplace URL and that publication derives its host and PR target from the selected origin. Never place real private credentials in fixtures or logs.

## Publish and read back

Merge only the reviewed head SHA after every required check succeeds. Then verify clean `main`, the live GitHub ruleset, generated marketplace bytes, a fresh marketplace install, and the deployed Zensical site. Documentation deploys only from `main`.
