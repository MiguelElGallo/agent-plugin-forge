# Maintain a team skill marketplace

Use a private Forge repository as the team's catalog of reviewed skills. Authors keep source changes in a staging workspace, reviewers approve the content and destination, maintainers merge the release, and teammates install the resulting plugins.

## Prepare the central repository

Have the repository owner provision a private GitHub or GitHub Enterprise Server repository from a reviewed, complete Forge checkout. Keep the CLI, `pyproject.toml`, `uv.lock`, `schemas/`, `tests/`, `catalog/`, `plugins/`, and workflows together. A repository containing only loose `SKILL.md` files is not an operating Forge: the installed publication helper expects a `main` branch and the subsequent CLI commands need this layout.

For example, after the private repository exists:

```bash
git clone https://github.company.example/platform/agent-skills.git
cd agent-skills
uv sync --locked
uv run forge doctor
uv run forge check
```

Choose a distinct marketplace name, such as `team-skills`, in `catalog/plugins.json`. Set its display name, owner, and description for the team. Keep the Python distribution and shipped `agent-plugin-forge` plugin names intact; the marketplace name is the identity users put after `@` when installing. Make catalog identity and configuration changes on a `forge/<topic>` branch, then run `uv run forge generate` and the [release gate](validate-release.md).

Git content does not configure the private repository's access or branch rules. The owner should restrict access to the intended team, enable the required checks, and require reviewed pull requests into `main`. Configure documentation publishing and its access separately before enabling the copied Pages workflow. Remove completed contribution branches through the team's normal workflow so their scoped names can be reused; retain unfinished work.

## Agree on ownership and names

| Role | Responsibility |
| --- | --- |
| Repository owner | Private access, branch rules, client policy, and Forge upgrades |
| Skill author | Source changes, immutable revision, applicable license, and behavior examples |
| Reviewer | Instructions, scripts, dependencies, permissions, provenance, and proposed destination |
| Maintainer | Complete checks, final commit review, authorized merge, and release communication |
| Teammate | Marketplace refresh, plugin installation or update, and a behavior check in their client |

Use one skill per plugin unless a bundle is a deliberate team choice. Reserve skill names across the whole catalog: Forge rejects the same skill name in two plugins. Record the source owner and intended users in your team's contribution process so updates have a clear reviewer.

Private hosting does not change the license checks. Every imported skill still needs its applicable SPDX expression and license evidence. The current validator accepts recognized SPDX licenses; custom identifiers such as `LicenseRef-Company-Internal` and `Proprietary` are not supported. Resolve the distribution policy before intake when those identifiers are required. Do not replace an internal or upstream license with MIT merely to pass validation.

## Publish a new team skill

First [create and commit the source skill](create-skill.md), or stage an upstream skill at its reviewed immutable revision. Test your own deterministic helpers in that source workspace before intake; Forge does not execute imported scripts to establish trust.

Install the Forge from the [private marketplace](private-marketplace.md), then include the destination origin in the request:

> Use the installed package-agent-skill workflow. My skill is at `/absolute/path/to/incident-summary`. Use Forge origin `https://github.company.example/platform/agent-skills.git`. Review it as plugin `incident-summary`, version `0.1.0`, category `Operations`. Inspect the source and license, prepare the complete review plan, and stop for approval.

Installing from a private marketplace does not set the publication origin. On first use, confirm the team's URL and ask the agent to remember it as your default across projects. Subsequent requests reuse the saved destination and display it in every plan. A one-time `--origin` or `AGENT_PLUGIN_FORGE_ORIGIN` override does not replace that default. Confirm any change of destination and verify the selected repository in the returned plan before approving it.

The report should identify the source revision, destination, version, files and modes, license evidence, checkout revision, and exact plan hash. Save the JSON review artifact outside the checkout. After review, approve the specific actions, for example:

> Apply reviewed plan `PLAN_SHA256`, run the complete gate, commit and push its branch to our selected private repository, and open a pull request into its `main`. Do not merge.

Use the organization's approved writable remote when direct pushes are unavailable. The approval should explicitly include any fork creation. Merge requires separate authorization, the exact reviewed head SHA, and green required checks.

Ordinary imports update the portable package, catalog, and generated client indexes. They do not require changing `tests/golden/`: renderer snapshots use a fixed test marketplace, while `forge check` validates the real catalog.

## Maintain existing skills

Choose the workflow from the actual change:

| Change | Workflow |
| --- | --- |
| Add a new skill as a new plugin | `forge branch`, then the reviewed `forge import` plan |
| Add a different skill to a bundle | `forge branch`, then `forge import` with a higher bundle version |
| Change an existing skill's contents | `forge branch`, then the reviewed `forge update` plan |
| Change MCP or shared plugin configuration | `forge plugin-branch`, then a reviewed plugin change |
| Upgrade Forge code or adjust catalog identity | `forge maintenance-branch` and the complete release gate |

`forge import` adds destinations and refuses an existing skill directory, even with a higher version. Use `forge update` to replace an existing skill; do not delete the destination or its provenance to bypass validation.

Stage the reviewed source revision locally, inspect every changed file and removal, and verify that the files match the declared immutable revision. From the selected clean, current Forge checkout, create the scoped branch and prepare a no-write plan:

```bash
uv run forge branch --plugin incident-summary --skill incident-summary
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

Replace the example values with the actual source, license, and a version higher than the current destination plugin. The source skill name must match the existing destination. For a source plugin with several skills, point `--source` at its root and add `--source-skill incident-summary`.

Review the plan's source identity, selected Forge origin, old and new versions, file additions, removals, content and executable-mode changes, license destination, and exact hash. Save `--json` output outside the checkout if needed. After approval of that hash, repeat the same command with `--apply --expected-sha256 HASH`. Preserve the original date with `--imported-at YYYY-MM-DD` when applying on another day. A newly computed hash does not carry forward approval.

Add `--diff` to the planning command to see instruction and license text changes alongside file and executable-mode changes. It also compares the previous and proposed source origin, revision, subpath, import date, and transformations. It is read-only and does not change the plan hash. Review the full contents of any files whose diffs are omitted because they are binary or exceed the preview limits. If the provenance comparison is omitted, compare the installed `provenance/<skill>.json` with the proposed values in a separate `--json` plan's `review_payload`. Use the printed apply command after approval; `--diff` cannot be combined with `--apply` or `--json`.

The update replaces the selected skill tree and its [provenance](../reference/metadata.md), removes obsolete skill files, and increases the plugin version together. It preserves other bundle skills, MCP configuration, and shared manifest fields. The skill's existing SPDX expression must stay the same; license-expression or shared configuration changes need a plugin-wide contributor review. New evidence goes to `licenses/<skill>/LICENSE`, while shared licenses and old license files outside the replaced skill tree remain intact. Evidence inside the tree follows its reviewed file changes, but an update cannot invalidate another skill's evidence. See [`forge update`](../reference/cli.md#forge-update) for required options and evidence-path conflicts.

Forge validates the staged package's MCP references, manifest, and provenance before replacing installed files. It rejects changes that break a packaged command or working directory; staging failures leave the installed package intact. Existing directories outside the replaced skill tree, including empty MCP working directories, are preserved.

Run generation, the complete release gate, and a focused behavior check in the target client before merging. A client install/update is a separate operation from this repository maintenance.

Approval to apply an update covers that local change. Obtain explicit authorization for committing, pushing, and opening a pull request against the selected origin. Merge remains separately authorized against the reviewed head SHA and green required checks.

Give simultaneous contributions separate checkouts or worktrees. Import and update plans bind the catalog and destination state, including empty directory paths: if those inputs change before application, recompute and review the plan. Saved bundle plans created before directory tracking need a fresh review. If a later rebase changes the applied result, review that final diff and rerun checks before approving its new merge head.

## Distribute and verify each release

After merge, report the plugin name, version, marketplace name, and a short behavior example to the team. Teammates first refresh the marketplace, then use the correct [install or update command](../reference/client-installation.md#update-an-installed-plugin). In particular, updating an installed Copilot CLI plugin uses `copilot plugin update`, rather than the initial `install` command.

Confirm the installed version and skill discovery, then start a new agent chat and run the example. A catalog entry establishes availability; an invocation checks behavior. Keep the tested client versions and results with the release record. For failures, use [Troubleshooting](troubleshoot.md) and preserve any Forge recovery directory until the repository is restored.
