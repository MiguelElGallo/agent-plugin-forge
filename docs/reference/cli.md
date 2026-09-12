# CLI reference

The `forge` CLI is built with [Typer](https://typer.tiangolo.com/). Run commands from the repository root with `uv run forge`. Commands return `0` on success and `2` for invalid command input or a user-correctable forge or Pydantic contract error.

Typer generates command and option help from the CLI's Python type annotations:

```bash
uv run forge --help
uv run forge --version
uv run forge import --help
```

`forge --version` prints the installed package version and works outside a Forge checkout when the `forge` executable is on your path.

It also provides shell-completion helpers:

```bash
uv run forge --show-completion
uv run forge --install-completion
```

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

## `forge doctor`

Inspect local prerequisites and readiness to start a new branch:

```bash
uv run forge doctor
uv run forge doctor --json
```

Doctor checks the running Python version, availability of Git and `uv`, the Git checkout, current branch, worktree cleanliness, a safe configured origin, and alignment of local `main` with cached `origin/main`. GitHub CLI availability is informational because review does not require publication authentication. If Git clean/process filters are configured, doctor skips the worktree-status probe and reports a warning so those programs cannot run. Submodule contents are not inspected; tracked submodules also produce a warning instead of a complete-readiness claim.

The JSON report contains `ready` and a `checks` array with `name`, `status`, and `detail`. Exit status is `0` when ready and `2` when a warning or error needs attention. A feature branch or dirty worktree can be normal during ongoing work; the result describes readiness to **start a new branch**, not whether your current work is valid.

Doctor does not fetch, contact the remote, authenticate, refresh the Git index, or run imported content. Cached alignment can be stale. Branch helpers still perform their live remote checks, and `forge check` still validates packages. Run doctor from a Forge checkout. Like any `uv run` command, the launcher may prepare its Python environment before doctor starts; `uv sync --locked` prepares that environment separately.

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

Compares `origin/<base>...HEAD` with the scope encoded in the branch. Pull requests must target `main`. Renames are checked as both a removal and an addition, so moving a file into the permitted directory does not hide an out-of-scope removal. Filename whitespace, Unicode, and line breaks are preserved during scope validation.

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

Import adds a new skill destination. It refuses to overwrite an existing `skills/<name>` directory, even with a higher version; it is not an in-place skill-update command. Updating an installed client plugin is a separate [client operation](client-installation.md#update-an-installed-plugin).

Add `--json` to print only the complete plan as JSON, during either planning or application.
The output includes the destination, source file hashes and executable modes, license digest,
and `review_payload`: the exact metadata and destination state bound by `plan_sha256`.
For bundles, `review_payload.targetState` includes existing file hashes, executable modes,
and the catalog entry.
The default text output remains a short summary.

For a no-write plan, text output also prints a complete apply command for a POSIX shell or Windows Git Bash. It preserves all reviewed import options, absolute source and license paths, the date, and the plan hash. Run it from the reported Forge checkout only after approval. The command is not PowerShell or Command Prompt syntax. `--json` continues to emit only the review artifact, with no command text added.

Save the planning output with shell redirection to a file outside the checkout:

```bash
uv run forge import [IMPORT_OPTIONS] --json > /absolute/path/review-plan.json
```

Review that file along with the source and license. Apply by repeating the same import options
with `--apply --expected-sha256 HASH`, using the saved `plan_sha256` value. Preserve
`--imported-at` from `review_payload.importedAt` when applying on a different day. The JSON
file is a review artifact, not an input accepted by the CLI; Forge recomputes the plan before
applying it and rejects a mismatched hash.

On a hash mismatch, the error reports the recomputed hash and import date, then explains how to compare a fresh JSON plan with the saved review. It cannot identify the changed field from a hash alone. The displayed recomputed hash does not authorize a changed plan; preserve the original date or review and approve the new inputs.

If publication fails, Forge rolls back completed file moves. If rollback itself fails,
Forge reports the recovery directory and keeps it for manual recovery. Its `backup`
subdirectory, when created, contains the original plugin. Preserve these recovery files
until the original plugin has been restored and the repository validated.

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
