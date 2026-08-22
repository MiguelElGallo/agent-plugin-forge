# CLI reference

Run commands from the repository root with `uv run forge`. Commands return `0` on success and `2` for a user-correctable forge or Pydantic contract error.

Users publishing through the installed plugin do not run these commands manually. The agent bootstraps a checkout, presents the import plan, and uses the CLI after the review checkpoint.

## Bootstrap helper

The installed `package-agent-skill` includes `scripts/bootstrap_forge.py`. Resolve the helper from the installed skill rather than the Forge repository root. It clones current `main` without modifying the user's project and prints the selected origin, host, checkout, branch, and exact revision as JSON.

```bash
uv run --no-project python /absolute/path/to/package-agent-skill/scripts/bootstrap_forge.py \
  [--origin GIT_URL] \
  [--destination ABSOLUTE_PATH] \
  [--reuse]
```

`AGENT_PLUGIN_FORGE_ORIGIN` supplies a default alternate origin. `--reuse` accepts only a regular, clean checkout on `main` whose configured origin exactly matches. Without `--destination`, the helper creates a new operating-system temporary location.

## `forge branch`

Creates `skill/<plugin>/<skill>` from a clean local base aligned with `origin/main`.

```bash
uv run forge branch --plugin NAME --skill NAME [--base main]
```

## `forge plugin-branch`

Creates `plugin/<plugin>/<topic>` for MCP or plugin-wide changes.

```bash
uv run forge plugin-branch --plugin NAME --topic TOPIC [--base main]
```

## `forge maintenance-branch`

Creates `forge/<topic>` for tooling, schema, CI, or documentation work.

```bash
uv run forge maintenance-branch --topic TOPIC [--base main]
```

All branch helpers refuse dirty worktrees, an unexpected base, a local base that differs from the freshly fetched remote base, and existing local or live remote branch names. They never push or merge.

## `forge branch-name`

Validates one of the three supported branch forms without writing:

```bash
uv run forge branch-name --branch BRANCH
```

## `forge pr-scope`

Compares `origin/<base>...HEAD` with the scope encoded in the branch. Pull requests must target `main`.

```bash
uv run forge pr-scope --branch BRANCH --base main
```

## `forge import`

Plans a local skill import. It accepts a skill directory, a lone `SKILL.md`, or an existing plugin. Use `--source-skill NAME` to select one skill from a multi-skill source plugin.

New destination plugins require `--category`, `--version`, `--description`, and `--author`. Every import requires `--license`, `--license-file`, `--origin`, and `--revision`. `--source-subpath` defaults to `.`. Revisions must be exactly a 40- or 64-character lowercase Git object ID, or `sha256:<64 lowercase hex>`.

Without `--apply`, the command writes nothing and prints a full-plan SHA-256. Apply only the same plan:

```text
--expected-sha256 HASH --apply
```

Existing bundles inherit their catalog category and require a strictly higher semantic version.

## `forge generate`

Regenerates both client marketplaces as one staged transaction. Both indexes point to the authoritative portable packages.

```bash
uv run forge generate
uv run forge generate --check
```

`--check` is read-only. It compares both generated marketplace files with a fresh render and rejects obsolete compatibility output.

## `forge check`

Validates vendored schema checksums, Pydantic-owned metadata, portable manifests, Agent Skills frontmatter, MCP schema and semantics, package paths, provenance, licenses, catalog identity, and both generated marketplaces.

```bash
uv run forge check
```
