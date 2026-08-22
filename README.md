# Agent Plugin Forge

Give your coding agent a skill folder, a lone `SKILL.md`, or an existing plugin. Agent Plugin Forge turns the selected skill into a reviewed, validated [Agent Plugins 1.0](https://agent-plugins.org/) package that works in Visual Studio Code, GitHub Copilot, and Codex.

Fork the repository, clone your fork, open it in VS Code, and ask your agent:

> I have a skill at `/path/to/my-skill`. Package it in this repository.

The repository instructions guide the agent through the missing choices, a no-write plan, byte-for-byte import, immutable provenance, client metadata, deterministic generation, tests, and a scoped pull request.

## Start in VS Code

```bash
git clone https://github.com/YOUR-GITHUB-USER/agent-plugin-forge.git
cd agent-plugin-forge
git remote add upstream https://github.com/MiguelElGallo/agent-plugin-forge.git
uv sync --locked
uv run forge check
```

Open the cloned folder in VS Code and use **Terminal > New Terminal** for the commands. Then follow the [step-by-step tutorial](https://miguelelgallo.github.io/agent-plugin-forge/tutorials/prepare-vscode/). It creates a real plugin, validates it, and loads it in VS Code.

## What the forge produces

- `plugins/` is the portable Agent Plugins 1.0 source of truth. VS Code loads its root `plugin.json`, immediate `skills/`, and optional `mcp.json` directly.
- `.github/plugin/marketplace.json` distributes the portable packages to GitHub Copilot.
- `.agents/plugins/marketplace.json` distributes the same portable packages to Codex.
- `catalog/plugins.json` adds marketplace category and compatibility policy; it does not change portable discovery.

The default is one skill per plugin. Bundles are explicit. MCP-only and mixed skill-plus-MCP packages are supported. Do not edit generated marketplaces by hand.

```bash
uv run forge generate
uv run forge check
```

## Install the forge itself

In VS Code, add these entries to **Preferences: Open User Settings (JSON)**:

```json
"chat.plugins.enabled": true,
"chat.plugins.marketplaces": ["MiguelElGallo/agent-plugin-forge"]
```

Then open the Extensions view, search for `@agentPlugins`, and install `agent-plugin-forge`.

GitHub Copilot CLI:

```bash
copilot plugin marketplace add MiguelElGallo/agent-plugin-forge
copilot plugin install agent-plugin-forge@agent-plugin-forge
```

Codex:

```bash
codex plugin marketplace add MiguelElGallo/agent-plugin-forge
codex plugin add agent-plugin-forge@agent-plugin-forge
```

See [Contributing](CONTRIBUTING.md), the [CLI reference](https://miguelelgallo.github.io/agent-plugin-forge/reference/cli/), and the [trust model](https://miguelelgallo.github.io/agent-plugin-forge/explanation/trust-model/) for the complete contracts.
