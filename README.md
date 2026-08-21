# Agent Plugin Forge

Give your coding agent a skill folder and this repository turns it into a reviewed, validated [Agent Plugins 1.0](https://agent-plugins.org/) package.

Clone the forge, point the agent at the skill, and ask:

> I have a skill at `/path/to/my-skill`. Package it in this repository.

The repository instructions route the agent through a safe workflow: discover missing metadata, create `skill/<plugin>/<skill>`, plan the import, preserve the source byte-for-byte, add portable metadata and provenance, generate client distribution files, validate everything, and prepare a pull request.

## Quick start

```bash
git clone https://github.com/MiguelElGallo/agent-plugin-forge.git
cd agent-plugin-forge
uv sync --locked
uv run forge check
```

The default is one skill per plugin. Bundles are explicit. Categories organize the catalog without breaking the standard's required `skills/<name>/SKILL.md` discovery layout.

## What is generated

- `plugins/` is the portable Agent Plugins 1.0 source of truth.
- `.github/plugin/marketplace.json` distributes those packages to GitHub Copilot.
- `compat/codex/` and `.agents/plugins/marketplace.json` are generated compatibility outputs for the current Codex local plugin format.

Do not hand-edit generated outputs. Run `uv run forge generate`, then `uv run forge check`.

Read the [documentation](https://miguelelgallo.github.io/agent-plugin-forge/) or [contribution workflow](CONTRIBUTING.md) for the complete path.

## Install the forge plugin

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

Version 0.1 packages skills only. It rejects `mcp.json` rather than silently producing a partial Codex compatibility wrapper.
