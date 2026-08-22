# Agent Plugin Forge

For skill intake, creation, copying, bundling, MCP packaging, or publication, read and follow `plugins/agent-plugin-forge/skills/package-agent-skill/SKILL.md`.

Use `uv run forge`; do not hand-edit generated marketplaces. Preserve imported skill trees byte-for-byte, keep provenance outside the copied tree, and never execute imported content during intake. Treat MCP runtimes and endpoints as untrusted until reviewed.

When the current workspace is not the Forge, use the installed skill's packaged bootstrap helper; do not require the user to clone manually. Treat an initial publication request as review-only. Stop after the hash-bound plan and obtain explicit approval before apply, fork or remote creation, push, or pull request. Merge requires separate authorization.

Honor a user-selected Forge Git origin and checkout location. Derive private GitHub or GitHub Enterprise authentication and publication targets from that origin rather than sending content to the public repository.

Run Ruff, ty, pytest, the forge validator, and strict Zensical build before opening a pull request.
