# Repository layout

```text
plugins/<plugin>/
├── plugin.json
├── skills/<skill>/SKILL.md
├── LICENSE / licenses/      distributed license evidence
└── provenance/<skill>.json

.github/plugin/marketplace.json       generated Copilot marketplace
.agents/plugins/marketplace.json      generated Codex marketplace
compat/codex/plugins/                 generated Codex wrappers
catalog/plugins.json                  distribution category and policy
schemas/agent-plugins/1.0.0/          vendored validation schemas
schemas/codex/current/                pinned forge compatibility contract
```

Agent Plugins discovers only immediate child skills under `skills/`. Categories therefore live in the catalog rather than in nested package directories.

Version 0.1 is deliberately skills-only. A package containing `mcp.json` fails validation until portable-to-Codex MCP translation is implemented and independently tested.
