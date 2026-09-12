# Agent instructions

This repository packages Agent Skills and MCP servers as Agent Plugins. When a user asks to add, copy, create, organize, bundle, or publish a skill, MCP server, or plugin, read `plugins/agent-plugin-forge/skills/package-agent-skill/SKILL.md` completely and follow it.

Portable packages under `plugins/` are authoritative. Treat `.github/plugin/marketplace.json` and `.agents/plugins/marketplace.json` as generated files.

Never execute imported scripts or hooks during intake. Never silently repair an invalid third-party skill. Use `skill/<plugin>/<skill>` for one skill, `plugin/<plugin>/<topic>` for MCP or plugin-wide work, and `forge/<topic>` for forge maintenance. Use the forge CLI for branch creation, import, generation, and validation.

An initial request to publish starts the review phase only. On first use, ask for the publication repository, confirm the exact URL and whether to remember it, and save the confirmed default through the bundled helper. Reuse that user default across projects and identify the destination in every plan; there is no public fallback. Confirm a change of destination or saved default. Stop after the hash-bound plan and obtain explicit approval before applying it or changing GitHub state. Respect the selected Forge origin and checkout location, and never redirect private content to the public marketplace. Merge requires separate authorization plus the exact reviewed head SHA and green required checks.

Python changes must pass Ruff, ty, and pytest. Documentation must pass `uv run zensical build --clean --strict`.
