# Portable core and distribution adapters

Agent Plugins 1.0 standardizes a small core: root `plugin.json`, immediate skills under `skills/`, and optional root `mcp.json`. It does not standardize marketplaces, installation policy, or every vendor-specific component. Forge v0.1 supports the skills subset and rejects MCP packages explicitly.

The forge keeps `plugins/` strictly portable. Copilot consumes those folders directly through its generated marketplace. Current Codex local development uses `.codex-plugin/plugin.json`, so the forge generates compatibility wrappers from the same source skills. This adapter is labeled and tested separately; it is not presented as part of the portable standard.

Generation prevents two hand-maintained skill copies from drifting. When Codex consumes the portable root format directly, the compatibility layer can be removed without changing the canonical packages.
