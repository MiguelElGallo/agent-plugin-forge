# Standards and Forge policy

Reviewed on **2026-09-07** against the published specification and repository baseline `0c3881c`, with the working-directory correction described below.

## Published standard

Agent Plugins **1.0.0** remains the current published release. Version **1.1.0** is a working draft, so Forge continues to target 1.0.0. See the [upstream status at the reviewed revision](https://github.com/agentplugins/agent-plugins-spec/blob/ff8ab5e392cc87bd88d87c060815a87490e51003/README.md).

Forge's root `plugin.json`, immediate `skills/<name>/SKILL.md` discovery, and optional root `mcp.json` follow the [portable specification](https://agent-plugins.org/specification). The shipped publication skill follows the [Agent Skills format](https://agentskills.io/specification).

The vendored plugin schema matches the canonical 1.0.0 schema semantically. The canonical MCP schema contains additional titles and descriptions, but its validation rules match the vendored schema. `SHA256SUMS` pins the local bytes; it does not claim byte-for-byte identity with the upstream files. See [canonical plugin schema](https://agent-plugins.org/schemas/1.0.0/plugin.schema.json) and [canonical MCP schema](https://agent-plugins.org/schemas/1.0.0/mcp.schema.json).

## Distribution policy

Passing the portable schema and passing Forge's publication gate are different checks. Forge intentionally accepts a narrower distribution profile:

| Area | Agent Plugins 1.0.0 | Forge requirement |
| --- | --- | --- |
| Identity | `$schema` and `name` are required | Also requires version, description, and license |
| Version and license | Optional string metadata | Semantic version and valid SPDX expression |
| Components | Empty packages are permitted | At least one skill or non-empty MCP server configuration |
| Links | Contained symlinks are permitted | Symlinks and junctions are rejected |
| Nested skill files | Not discovered as additional skills | Nested `SKILL.md` files under `skills/` are rejected during package validation |
| Distribution | Marketplace schemas are outside the portable contract | Separate generated Copilot and Codex indexes |

License evidence and per-skill provenance are additional Forge review requirements. Their contracts are described in [Metadata and provenance](metadata.md). Catalog-wide validation is a publication gate; it does not establish a client's runtime failure-isolation behavior.

## MCP working directories and compatibility

Forge accepts `"cwd": "./data"` and `"cwd": "${PLUGIN_ROOT}/data"` for an existing contained package directory. Omit `cwd` when the plugin root is sufficient. `${PLUGIN_DATA}` and its subdirectories identify client-managed persistent storage.

The review identified and corrected a prefix check that rejected `./data`. Regression tests cover nested relative directories, missing directories, traversal, and filesystem-resolved escapes. Forge continues to reject paths that escape their permitted root.

Forge also requires `codexCompatibility: false` for legacy SSE packages. See [MCP packaging](../how-to/add-mcp.md) for the supported transports and policy.

## Client evidence

Schema validation establishes package structure. Marketplace listing establishes discovery. Neither demonstrates that a client can execute a skill or successfully start and call an MCP server. Use the [dated client evidence](compatibility.md) and [release acceptance procedure](../how-to/validate-release.md) for those checks.
