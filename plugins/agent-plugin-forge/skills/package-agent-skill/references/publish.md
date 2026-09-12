# Publish from an installed Forge skill

Use this workflow to select a destination and publish a new skill through the installed Forge. It also applies when the current workspace happens to contain a Forge checkout. The user should never need to clone the repository manually.

## Select and remember the publication repository

Resolve `scripts/bootstrap_forge.py` relative to this skill's `SKILL.md`. Inspect the configured destination without cloning or writing settings:

```bash
uv run --no-project python /absolute/path/to/package-agent-skill/scripts/bootstrap_forge.py --show-origin
```

The JSON reports `origin`, `origin_source`, `saved_origin`, and `settings_path`. Selection order is an explicit helper `--origin`, then `AGENT_PLUGIN_FORGE_ORIGIN`, then the saved user default. Without any selection, `origin` is `null`; a normal bootstrap refuses to proceed. There is no built-in repository fallback. Installation does not configure publication.

On first use, ask: **Which Forge repository should receive this skill?** It must contain the complete Forge runtime and catalog on `main`. Do not substitute the public Forge or the skill's source repository. If the requested repository has not been prepared, explain the required setup and resolve that separately.

If the user already supplied a destination, or the environment provides one, use it as the candidate instead of asking for the URL again. Show the exact selected URL and ask: **Use `URL` for publication and remember it as your default across projects?** An explicit instruction to use and remember that exact repository already supplies this confirmation. Normalize a candidate through `--show-origin --origin URL` when needed. After confirmation, persist it without cloning:

```bash
uv run --no-project python /absolute/path/to/package-agent-skill/scripts/bootstrap_forge.py \
  --origin CONFIRMED_FORGE_URL --remember-origin
```

Read back the returned `saved_origin` and `settings_path`. The preference belongs to the operating-system user and is shared across projects and clients on that machine. It survives plugin updates; do not write it into a project, installed plugin, or client conversation memory. The helper's `--config PATH` is an explicit settings-location override for managed use and tests, not a project-level default.

On subsequent requests, reuse the saved destination and display it in the review plan without asking the same setup question. If an environment override differs from the saved default, show both and confirm the selected repository unless the user already selected it for this request. If a request implies a different or private destination that the saved choice does not satisfy, ask for that repository before proceeding.

For a different destination, establish whether the user wants a one-time override or a new default. Pass a confirmed one-time choice through `--origin` on the bootstrap command; that does not update settings. Replacing a saved default requires the user's explicit confirmation of the new default and both `--remember-origin` and `--replace-saved-origin`. An unreadable or invalid settings file is an error to resolve, never a reason to fall back to another repository. Saving a preference grants no publication approval.

## Bootstrap the review checkout

Run the bundled helper through `uv`; do not copy or recreate it. It clones the selected repository's current `main` into a new operating-system temporary directory, verifies the exact remote revision, and prints JSON containing the destination settings, checkout path, and commit. Pass the resolved URL explicitly so the checkout uses the destination just shown to the user:

```bash
uv run --no-project python /absolute/path/to/package-agent-skill/scripts/bootstrap_forge.py \
  --origin SELECTED_FORGE_URL
```

Use `--destination ABSOLUTE_PATH` when the user requests a persistent local checkout. On later clean `main` sessions, add `--reuse`; the helper refuses a dirty checkout, another branch, or a different origin. Never overwrite an existing destination. A saved repository URL does not imply permission to reuse an arbitrary checkout. When working in an existing Forge checkout, verify that its origin identifies the selected publication repository before creating a branch or plan.

For a private repository, mirror, custom checkout, or GitHub Enterprise Server, read [private-github.md](private-github.md). Derive the publication repository and authentication host from the bootstrap JSON instead of assuming GitHub.com or `MiguelElGallo`. A local/file origin is valid for review and acceptance testing, but the automated push-and-pull-request phase requires a GitHub.com or GitHub Enterprise Server origin.

Move all Forge operations into the returned checkout. Keep the user's source skill in place and pass its absolute path to the importer. Run `uv sync --locked` before invoking the Forge CLI.

## Phase 1: review

Treat the user's initial request to publish as permission to prepare a review, not permission to create a fork, push, open a pull request, or merge.

1. Inspect the source and license without executing scripts or hooks.
2. Resolve the destination and provenance fields described in [intake.md](intake.md).
3. From clean current `main`, create the skill branch with `uv run forge branch --plugin NAME --skill NAME`. Use the contributor workflow for existing-skill, MCP, or Forge maintenance.
4. Run `uv run forge import` without `--apply`.
5. Review every source file, executable mode, license byte, destination, and plan field.
6. Report the checkout, base revision, selected Forge origin, whether it came from the saved default or an override, normalized repository URL printed by the Forge CLI, plugin name and version, compatibility, provenance, and 64-character review-plan hash. Check that the plan's repository matches the selected destination before requesting approval.
7. Stop and ask the user whether to publish that exact reviewed plan. State that publication will apply the plan, test it, create or reuse their GitHub fork when needed, push the branch, and open a pull request. Merge requires separate authorization after the pull request's exact head and checks are available.

If the plan or source changes, discard the old approval hash and review a new plan.

## Phase 2: publish

Continue only after the user approves the exact plan and the listed external actions.

1. Repeat the reviewed import with `--apply --expected-sha256 HASH`.
2. Run generation, Forge validation, Ruff, formatting, ty, pytest, strict Zensical build, and `git diff --check`.
3. Review the complete diff. Do not execute imported code merely to test it.
4. Commit the reviewed files.
5. Verify that the selected origin is a GitHub.com or GitHub Enterprise Server repository, then run `gh auth status` for its host. Push directly only when the authenticated account has upstream permission; otherwise create or reuse a writable fork or remote on that host, push there, and open a pull request against the selected Forge origin's `main` branch. Do not run GitHub CLI against a `local` host.
6. Read back the pull request URL, exact head SHA, and checks. Merge only after separate authorization for the reviewed head and green required checks.

After the plugin is merged into the selected marketplace, report its install name. Users who already configured that marketplace can install it with:

```bash
codex plugin marketplace upgrade MARKETPLACE_NAME
codex plugin add PLUGIN_NAME@MARKETPLACE_NAME
copilot plugin marketplace update MARKETPLACE_NAME
copilot plugin install PLUGIN_NAME@MARKETPLACE_NAME
```

Run the matching refresh command before the install command so a client configured before the merge sees the new catalog entry. For the public Forge, `MARKETPLACE_NAME` is `agent-plugin-forge`. For another origin, derive it from that repository's marketplace metadata. VS Code users run **Extensions: Check for Extension Updates**, then install the same plugin from **Chat: Open Customizations** → **Plugins** → **Browse Marketplace**. Do not claim the marketplace install is available before the pull request is merged.
