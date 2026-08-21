# Agent instructions

This repository packages Agent Skills. When a user asks to add, copy, create, organize, bundle, or publish a skill, read `plugins/agent-plugin-forge/skills/package-agent-skill/SKILL.md` completely and follow it.

Portable packages under `plugins/` are authoritative. Treat `.github/plugin/marketplace.json`, `.agents/plugins/marketplace.json`, and `compat/codex/` as generated files.

Never execute imported scripts or hooks during intake. Never silently repair an invalid third-party skill. Keep a new skill on `skill/<plugin>/<skill>` and use the forge CLI for branch creation, import, generation, and validation.

Python changes must pass Ruff, ty, and pytest. Documentation must pass `uv run zensical build --clean --strict`.
