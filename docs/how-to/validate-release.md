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

Before release, record exact versions and test from a disposable fresh clone:

1. open the clone in VS Code;
2. run the tutorial commands in its integrated terminal;
3. register a local portable plugin with `chat.pluginLocations`;
4. confirm its skill in **Chat: Configure Skills**;
5. confirm its MCP server in the MCP list and call a credential-free tool;
6. mount the same portable package with Copilot CLI;
7. install the same portable package with Codex.

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

## Publish and read back

Merge only the reviewed head SHA after every required check succeeds. Then verify clean `main`, the live GitHub ruleset, generated marketplace bytes, a fresh marketplace install, and the deployed Zensical site. Documentation deploys only from `main`.
