# Add MCP to a plugin

Use a plugin-wide branch for `mcp.json`, packaged runtimes, or configuration shared by several skills:

```bash
uv run forge plugin-branch --plugin my-plugin --topic add-mcp
```

Place the portable configuration at `plugins/my-plugin/mcp.json`. It must target the canonical Agent Plugins 1.0 MCP schema. Keep packaged runtimes inside the plugin and bump `plugin.json` to a higher semantic version.

```json
{
  "$schema": "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json",
  "mcpServers": {
    "my-server": {
      "type": "stdio",
      "command": "uv",
      "args": ["run", "--no-project", "python", "${PLUGIN_ROOT}/server.py"]
    }
  }
}
```

Forge supports `stdio`, `streamable-http`, and legacy `sse`. Because Codex does not support Agent Plugins SSE, set `codexCompatibility` to `false` for any package that uses it. Forge rejects a Codex-compatible SSE listing, command strings, path escapes, non-loopback HTTP, URL credentials or fragments, invalid or case-duplicate headers, embedded credential headers, root-variable overrides, missing packaged commands, and unsafe files.

For stdio, omit `cwd` to use the plugin root, or use a contained directory such as `"cwd": "./data"` or `"cwd": "${PLUGIN_ROOT}/data"`. Plugin-relative directories must exist in the package; traversal and resolved escapes remain invalid. `${PLUGIN_DATA}` supports client-managed persistent data directories.

```bash
uv run forge generate
uv run forge check
uv run pytest --no-cov tests/test_mcp.py
```

For Codex-compatible transports, both generated marketplaces point to this portable package. An SSE package appears only in the Copilot marketplace because its catalog policy must set `codexCompatibility` to `false`. Generation never translates or copies the MCP configuration.

## Create an MCP-only plugin

For a package with no skills, create `plugins/my-plugin/plugin.json`, its license, the runtime, and a non-empty root `mcp.json`; then add the plugin's name, category, and `codexCompatibility` policy to `catalog/plugins.json`. The root manifest still needs the portable schema, name, semantic version, description, and SPDX license. Use a `plugin/my-plugin/<topic>` branch because this is plugin-wide work, then run the same generation and validation commands above.
