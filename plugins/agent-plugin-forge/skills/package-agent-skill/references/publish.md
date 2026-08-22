# Publish from an installed Forge skill

Use this workflow when Agent Plugin Forge is installed in the client but the current workspace is not a Forge checkout. The user should never need to clone the repository manually.

## Bootstrap the review checkout

Resolve `scripts/bootstrap_forge.py` relative to this skill's `SKILL.md`, then run it through `uv`. Do not copy or recreate the helper. It clones current `main` into a new operating-system temporary directory, verifies the exact remote revision, and prints JSON containing the checkout path and commit.

```bash
uv run --no-project python /absolute/path/to/package-agent-skill/scripts/bootstrap_forge.py
```

Use `--destination ABSOLUTE_PATH` when the user requests a persistent location. On later clean `main` sessions, add `--reuse`; the helper refuses a dirty checkout, another branch, or a different origin. Never overwrite an existing destination. Use `--origin` or `AGENT_PLUGIN_FORGE_ORIGIN` when the user selects a mirror, private repository, or GitHub Enterprise Server. Marketplace installation does not configure the helper origin automatically. If the request implies a private or alternate Forge but does not identify its origin, stop and ask instead of using the public default.

For a non-default origin, read [private-github.md](private-github.md). Derive the publication repository and authentication host from the bootstrap JSON instead of assuming GitHub.com or `MiguelElGallo`. A local/file origin is valid for review and acceptance testing, but the automated push-and-pull-request phase requires a GitHub.com or GitHub Enterprise Server origin.

Move all Forge operations into the returned checkout. Keep the user's source skill in place and pass its absolute path to the importer. Run `uv sync --locked` before invoking the Forge CLI.

## Phase 1: review

Treat the user's initial request to publish as permission to prepare a review, not permission to create a fork, push, open a pull request, or merge.

1. Inspect the source and license without executing scripts or hooks.
2. Resolve the destination and provenance fields described in [intake.md](intake.md).
3. From clean current `main`, create the correctly scoped local branch with `uv run forge branch`, `plugin-branch`, or `maintenance-branch`.
4. Run `uv run forge import` without `--apply`.
5. Review every source file, executable mode, license byte, destination, and plan field.
6. Report the checkout, base revision, selected Forge origin, normalized repository URL printed by the Forge CLI, plugin name and version, compatibility, provenance, and 64-character review-plan hash.
7. Stop and ask the user whether to publish that exact reviewed plan. State that publication will apply the plan, test it, create or reuse their GitHub fork when needed, push the branch, and open a pull request. State separately whether merge is included.

If the plan or source changes, discard the old approval hash and review a new plan.

## Phase 2: publish

Continue only after the user approves the exact plan and the listed external actions.

1. Repeat the reviewed import with `--apply --expected-sha256 HASH`.
2. Run generation, Forge validation, Ruff, formatting, ty, pytest, strict Zensical build, and `git diff --check`.
3. Review the complete diff. Do not execute imported code merely to test it.
4. Commit the reviewed files.
5. Verify that the selected origin is a GitHub.com or GitHub Enterprise Server repository, then run `gh auth status` for its host. Push directly only when the authenticated account has upstream permission; otherwise create or reuse a writable fork or remote on that host, push there, and open a pull request against the selected Forge origin's `main` branch. Do not run GitHub CLI against a `local` host.
6. Read back the pull request URL, exact head SHA, and checks. Do not merge unless the user's approval explicitly included merge; before merging, require the same head SHA and green required checks.

After the plugin is merged into the selected marketplace, report its install name. Users who already configured that marketplace can install it with:

```bash
codex plugin marketplace upgrade MARKETPLACE_NAME
codex plugin add PLUGIN_NAME@MARKETPLACE_NAME
copilot plugin marketplace update MARKETPLACE_NAME
copilot plugin install PLUGIN_NAME@MARKETPLACE_NAME
```

Run the matching refresh command before the install command so a client configured before the merge sees the new catalog entry. For the public Forge, `MARKETPLACE_NAME` is `agent-plugin-forge`. For another origin, derive it from that repository's marketplace metadata. VS Code users run **Extensions: Check for Extension Updates**, then install the same plugin from **Chat: Open Customizations** → **Plugins** → **Browse Marketplace**. Do not claim the marketplace install is available before the pull request is merged.
