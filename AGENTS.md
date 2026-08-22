# Agent instructions

This repository packages Agent Skills and MCP servers as Agent Plugins. When a user asks to add, copy, create, organize, bundle, or publish a skill, MCP server, or plugin, read `plugins/agent-plugin-forge/skills/package-agent-skill/SKILL.md` completely and follow it.

Portable packages under `plugins/` are authoritative. Treat `.github/plugin/marketplace.json` and `.agents/plugins/marketplace.json` as generated files.

Never execute imported scripts or hooks during intake. Never silently repair an invalid third-party skill. Use `skill/<plugin>/<skill>` for one skill, `plugin/<plugin>/<topic>` for MCP or plugin-wide work, and `forge/<topic>` for forge maintenance. Use the forge CLI for branch creation, import, generation, and validation.

Python changes must pass Ruff, ty, and pytest. Documentation must pass `uv run zensical build --clean --strict`.
