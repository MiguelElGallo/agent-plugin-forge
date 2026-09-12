# Troubleshoot installation and imports

Start with the symptom below. Run Forge commands from its checkout; marketplace commands run in your client terminal.

For a quick local checkout diagnosis, run `uv run forge doctor`. Use `--json` for a structured report. It checks prerequisites and readiness to start a branch without network calls or repository writes. Its `origin/main` comparison uses cached refs, so live remote alignment remains the branch helper's responsibility. A warning about your active feature branch or unfinished work is expected while making changes. See [doctor's checks and exit statuses](../reference/cli.md#forge-doctor).

## The plugin or skill is missing

Check marketplace discovery separately from installation:

| Client | Inspect available plugins | Inspect installed plugins |
| --- | --- | --- |
| Codex | `codex plugin list --marketplace MARKETPLACE_NAME --available --json` | `codex plugin list --json` |
| Copilot CLI | `copilot plugin marketplace browse MARKETPLACE_NAME` | `copilot plugin list` |
| VS Code | **Chat: Open Customizations** → **Plugins** → **Browse Marketplace** | Extensions view → `@agentPlugins`; then **Chat: Configure Skills...** |

For the public Forge, use `agent-plugin-forge` as the marketplace name. If the plugin is absent from the catalog, confirm its pull request merged and [refresh the marketplace](../reference/client-installation.md). If it is installed but its skill is absent, check whether the plugin is enabled and whether organization policy permits plugins. For a local development package, follow [the local VS Code setup](../tutorials/use-in-vscode.md).

A catalog entry proves availability; an installed entry proves installation; a skill listing proves discovery. To verify behavior, invoke the skill or call an MCP tool. See the [dated compatibility evidence](../reference/compatibility.md) before assuming a client has passed runtime acceptance.

## A branch helper refuses the checkout

For `Refusing to create a branch from a dirty worktree`, inspect `git status --short` and preserve or finish your existing work before returning to a clean `main`.

If doctor reports configured Git filters or submodules, it has deliberately left those checks incomplete. Review that repository configuration before inspecting it with ordinary Git commands, which may invoke filters. Doctor does not disable or rewrite your configuration.

For `Local main is not aligned with origin/main`, inspect your local commits. If `main` is only behind the intended origin, update it:

```bash
git switch main
git pull --ff-only origin main
```

Then repeat the appropriate [branch helper](../reference/cli.md). If fast-forwarding fails, inspect the divergence before proceeding. For an existing local or remote branch, inspect whether it already contains the intended work; use a fresh permitted name for a separate task. The helper deliberately refuses to reuse or overwrite a branch.

## The review-plan hash no longer matches

`--expected-sha256 must match the reviewed full-plan hash` means the recomputed plan differs from the approved one. Repeat the original import command without `--apply`, adding `--json`, and compare it with the saved plan.

The diagnostic includes the recomputed hash and import date. It lists recovery steps rather than guessing which field changed. Do not copy that new hash into an apply command without reviewing the changed plan.

The import date is included in the hash. The apply command printed after a text plan already preserves it. When continuing manually on another day, preserve the original `review_payload.importedAt` date with `--imported-at YYYY-MM-DD`. If source files, modes, license, metadata, origin, or destination changed, review the new plan and obtain approval for its new hash. If the original review artifact is unavailable, make a fresh review plan.

The JSON artifact is for review; Forge does not accept it as an apply input. See [saving and applying plans](../reference/cli.md#forge-import).

## Import reports missing metadata or invalid source

`New plugins require: ...` lists the missing destination fields. A new plugin needs category, version, description, and author, while a bundle inherits category and requires a higher version. Every import also needs source identity, immutable revision, and license evidence. Follow [import an existing skill](import-skill.md) or [record a new skill's source](create-skill.md#record-the-source-and-license).

For malformed frontmatter, mismatched names, links, unsafe paths, or missing license evidence, correct your own source in its staging workspace and review it again. An invalid third-party skill needs a separately reviewed source correction before intake. Forge does not normalize imported content for you.

## Generated marketplace output is stale

For `Generated marketplace is stale: PATH`, regenerate from the portable packages and catalog:

```bash
uv run forge generate
uv run forge check
```

Review the generated diff. Both marketplace files are derived outputs; make metadata corrections in `plugins/` or `catalog/plugins.json` first. Use `uv run forge generate --check` when you only want a read-only drift check; success exits silently with status `0`.

## Marketplace generation reports a rollback failure

If generation fails while replacing an output, Forge attempts to restore every output it touched. If any restoration fails, the error identifies a `.forge-generate-*` recovery directory in the checkout. Keep that directory: its `backups/` tree contains originals that could not be restored, under their repository-relative paths.

Inspect the reported error and filesystem permissions, recover any remaining originals from `backups/`, then run `uv run forge generate` and `uv run forge check`. Remove the recovery directory only after verifying the outputs and preserving any files you need.
