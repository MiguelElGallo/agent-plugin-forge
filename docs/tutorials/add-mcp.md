# Add an MCP server

Agent Plugins 1.0 supports skill-only, MCP-only, and mixed packages. This chapter adds a Python-standard-library-only MCP server to the `release-notes` plugin and verifies its handshake before VS Code starts it.

Begin after the first skill pull request is merged. Switch to a clean, current `main`, then create a plugin-wide branch:

```bash
git switch main
git pull --ff-only
uv run forge plugin-branch --plugin release-notes --topic add-status-mcp
```

Skill branches stay limited to one skill. A `plugin/<plugin>/<topic>` branch allows MCP and other plugin-wide files without allowing changes to another plugin.

## Add the runtime and portable configuration

Copy the tested tutorial files:

```bash
cp examples/tutorial/status-mcp/server.py plugins/release-notes/server.py
cp examples/tutorial/status-mcp/mcp.json plugins/release-notes/mcp.json
```

Open `plugins/release-notes/plugin.json` and change its version from `0.1.0` to `0.2.0`.

The portable `mcp.json` uses the cross-platform `uv` launcher and passes each argument separately. It omits `cwd`, so the Agent Plugins default is the plugin root. It does not contain a shell command, credentials, or a path outside the plugin.

## Test the server process directly

Run one MCP initialize request without involving an AI model:

```bash
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"forge-tutorial","version":"1.0.0"}}}' \
  '{"jsonrpc":"2.0","method":"notifications/initialized"}' \
  | PLUGIN_ROOT="$PWD/plugins/release-notes" PLUGIN_DATA="$PWD/.tmp-plugin-data" \
    uv run --no-project python plugins/release-notes/server.py
```

The one-line JSON response should contain `"name":"release-status"` and `"version":"1.0.0"`.

## Generate both client marketplaces

Run:

```bash
uv run forge generate
uv run forge check
uv run pytest --no-cov tests/test_mcp.py tests/test_tutorial_mcp_server.py
```

The portable package keeps `mcp.json` and `server.py` unchanged. Both client marketplaces point to that same package, and Forge validates the portable MCP contract once.

## Check it in VS Code

Run **Developer: Reload Window**, then open **Chat: Open Customizations > Plugins**. The `release-notes` plugin should still be enabled. Its `release-status` server should also appear in the MCP server list.

In Copilot Chat, ask:

> Call `release_status` and report the result exactly.

The tool returns `status: ready` and confirms that VS Code supplied `PLUGIN_ROOT` and `PLUGIN_DATA`.

## Recap

You added a real MCP process, tested the complete wire handshake without AI credentials, regenerated both marketplaces, and loaded the portable configuration in VS Code.
