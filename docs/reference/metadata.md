# Metadata and provenance

`plugin.json` is authoritative for portable plugin identity and version. Its closed Agent Plugins 1.0 schema permits only the standard fields and namespaced extensions.

`catalog/plugins.json` adds distribution category and whether a generated Codex compatibility wrapper is supported. Generators derive both marketplaces from the catalog plus each portable manifest.

Each `provenance/<skill>.json` records origin, immutable revision, source subpath, import date, validated SPDX license expression, transformations, per-file SHA-256 values, and a deterministic tree hash. The reviewed plan also binds the license bytes and their exact destination path. The copied skill tree remains byte-identical.
