# Repository layout

```text
plugins/<plugin>/
├── plugin.json                       portable closed manifest
├── skills/<skill>/SKILL.md           optional, immediate children only
├── mcp.json                          optional portable MCP configuration
├── server.py / bin/ / config/        optional packaged MCP runtime files
├── LICENSE / LICENSES/ / licenses/   distributed license evidence
└── provenance/<skill>.json           one record per imported skill

catalog/plugins.json                  category and compatibility policy
.github/plugin/marketplace.json       generated Copilot marketplace
.agents/plugins/marketplace.json      generated Codex marketplace
schemas/agent-plugins/1.0.0/          pinned portable schemas
examples/tutorial/                    runnable documentation inputs
```

Agent Plugins discovers only immediate directories under `skills/` and only root `mcp.json`. Category is marketplace taxonomy, never a nesting level.

Portable packages may be skill-only, MCP-only, or mixed. A useful forge package must expose at least one skill or one non-empty MCP server. Both generated marketplace indexes point directly to these portable packages.
