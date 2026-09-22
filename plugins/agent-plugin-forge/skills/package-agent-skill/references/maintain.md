# Maintain an existing skill

Use `forge update` when the requested skill already exists in the selected Forge repository. `forge import` adds new destinations and refuses an existing `skills/<name>` directory, even with a higher version. Do not delete the destination or its provenance to bypass that check. Updating an installed client plugin is a separate operation after publication.

For a request to check or review only, inspect and report without changing files. An initial publication request authorizes the review phase only; stop at the exact update plan and obtain approval before applying it or changing GitHub state. Preserve the selected private origin throughout checkout, review, and approved publication.

## Prepare and review the revision

1. Resolve the selected origin as described in [publish.md](publish.md), then bootstrap it or use its existing clean, current checkout. Record the origin and base revision.
2. Inspect the current skill, provenance, license, and proposed source revision. Test the author's own helpers in the source workspace when authorized; never execute imported scripts or hooks during intake. Correct invalid third-party content in a separately reviewed source change.
3. Create `skill/<plugin>/<skill>` with `uv run forge branch --plugin NAME --skill NAME`. If the branch already exists, inspect its work instead of resetting it. Shared runtime, MCP, or license-expression changes need a separately reviewed plugin-wide contributor change.
4. Prepare the no-write update plan from the reviewed local source, requiring the existing destination plugin and a higher plugin version. The source skill's name must match the existing destination and its current provenance must be valid.

For example, after staging a committed revision of an existing `incident-summary` skill:

```bash
uv run forge update \
  --source /absolute/path/to/skill-sources/skills/incident-summary \
  --plugin incident-summary \
  --version 0.2.0 \
  --license MIT \
  --license-file /absolute/path/to/skill-sources/LICENSE \
  --origin https://github.company.example/platform/skill-sources.git \
  --revision "$(git -C /absolute/path/to/skill-sources rev-parse HEAD)" \
  --source-subpath skills/incident-summary
```

Replace the example paths, identity, license, and version with reviewed values. Verify that the local source matches the declared immutable revision; never label uncommitted edits with an older commit. Forge records the declaration without fetching the source. A source plugin with several skills needs `--source-skill NAME`; a lone `SKILL.md` is also supported.

Review every instruction, script, asset, removal, executable-mode change, license, and destination. The plan identifies the update operation, old and new versions, added, removed, modified, and mode-changed files, and provenance and license paths. Its hash binds the complete source snapshot, metadata, catalog, and current destination package, including empty directory paths. Report the selected Forge URL and exact hash, then stop for approval. Save `--json` output outside the checkout when review will continue later. Saved bundle plans made before directory tracking require a fresh review of the expanded payload.

## Apply the approved plan

Repeat the same command with `--apply --expected-sha256 HASH` only after approval of that exact plan. Preserve the original `review_payload.importedAt` date with `--imported-at YYYY-MM-DD` when continuing on another day. The JSON file is a review artifact, not an apply input. Changed inputs require a fresh plan and approval; a recomputed hash is not authorization.

Forge replaces the selected skill's tree, removes obsolete skill files, updates its provenance, and increases the shared plugin version. Other skills, MCP files, catalog metadata, and remaining manifest fields stay unchanged. Category, author, and description overrides are not supported.

The SPDX expression must match the target skill's current provenance. New license evidence goes to `licenses/<skill>/LICENSE`; shared `LICENSE` files and old license files outside the replaced skill tree remain intact. Evidence inside that tree follows its reviewed file changes. If the dedicated evidence path already exists, Forge replaces it only when current provenance records establish that the target skill owns it exclusively. An update cannot invalidate another skill's license evidence, including evidence stored inside the updated tree or in rewritten metadata. Resolve shared or unowned evidence conflicts through a separately reviewed contributor change.

Apply validates the staged manifest, MCP references, and provenance before replacing installed files. File removals and mode changes cannot break a packaged command or working directory. Existing directories outside the replaced skill tree, including empty MCP working directories, are preserved. A staging or validation failure leaves the installed package intact.

Apply checks the catalog, destination, and Forge origin again before the final file moves and attempts rollback on replacement failure. It does not lock the directory tree or combine the package and catalog replacements into one atomic filesystem operation. Preserve any reported recovery directory until restoration and validation are complete.

## Validate and publish

Run `uv run forge generate`, `uv run forge check`, Ruff lint and format checks, `uv run ty check`, `uv run pytest`, `uv run zensical build --clean --strict`, and `git diff --check`. Renderer golden tests use a fixed fixture; updating a real skill or plugin version does not require changing `tests/golden/`. Review the complete source-to-package diff and perform an authorized behavior check in the intended client.

Approval to apply the local update does not authorize GitHub publication. Commit, push, and open a pull request only when those actions were authorized against the selected origin. Merge is separate and requires authorization for the reviewed head SHA and green required checks. After merge, report the plugin version and applicable commands for an existing installation:

```bash
codex plugin marketplace upgrade MARKETPLACE_NAME
codex plugin add PLUGIN_NAME@MARKETPLACE_NAME
copilot plugin marketplace update MARKETPLACE_NAME
copilot plugin update PLUGIN_NAME@MARKETPLACE_NAME
```

Derive the marketplace name from the selected repository. VS Code users run **Extensions: Check for Extension Updates** and choose **Update** when it is offered, then confirm the skill in a new chat.
