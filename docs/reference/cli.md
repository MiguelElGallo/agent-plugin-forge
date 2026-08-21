# CLI reference

## `forge branch`

Creates `skill/<plugin>/<skill>` from a clean, aligned base branch. It refuses dirty worktrees and local or remote collisions. It never pushes or merges.

## `forge import`

Plans a local skill-directory import. Add `--apply --expected-sha256 HASH` to write the exact reviewed plan. New plugins require category, version, description, author, license text, origin, and immutable revision. Bundles require a strictly higher version.

## `forge generate`

Regenerates the Copilot marketplace, Codex marketplace, and Codex compatibility wrappers. `--check` reports drift without writing.

## `forge check`

Validates vendored schema checksums, portable manifests, the Agent Skills frontmatter contract, provenance and license hashes, catalog/path consistency, marketplaces, and compatibility wrappers. Version 0.1 rejects MCP packages.
