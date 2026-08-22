# Repository layout

```text
plugins/<plugin>/
├── plugin.json                       portable closed manifest
├── skills/<skill>/                   optional, immediate children only
│   ├── SKILL.md                      required skill entrypoint
│   ├── references/                   optional progressive guidance
│   └── scripts/                      optional packaged helpers
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

The installed `package-agent-skill` keeps its bootstrap helper under its own `scripts/` directory. This makes the no-clone publication entrypoint travel with the plugin while the complete Forge runtime stays in the current selected checkout.
