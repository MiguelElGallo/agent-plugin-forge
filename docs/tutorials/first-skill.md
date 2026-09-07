# Import your first skill

In this chapter you will package the tutorial `release-notes` skill. The first command only plans the import. Nothing is copied until you repeat the exact plan with its approval hash.

This contributor chapter starts from the clean checkout prepared in [Prepare a Forge development checkout](prepare-vscode.md). Users publishing through the installed skill can instead follow [Publish a skill with your agent](../how-to/publish-skill.md).

## Look at the source

Open `examples/tutorial/release-notes/SKILL.md` in VS Code. It is a complete, minimal Agent Skill:

```yaml
---
name: release-notes
description: Create concise release notes from a reviewed list of changes.
---
```

Read the instructions below the frontmatter. The importer copies instructions; it does not decide whether they are trustworthy.

## Create the skill branch

Run:

```bash
uv run forge branch --plugin release-notes --skill release-notes
```

You should see:

```text
Created skill/release-notes/release-notes
```

The command refuses a dirty checkout, an outdated `main`, or an existing local or remote branch. It never pushes the branch.

## Plan the import

In the VS Code terminal on macOS, Linux, or Git Bash, run this complete command:

```bash
uv run forge import \
  --source examples/tutorial/release-notes \
  --plugin release-notes \
  --category "Developer Tools" \
  --version 0.1.0 \
  --description "Create concise release notes from reviewed changes." \
  --author "MiguelElGallo" \
  --license MIT \
  --license-file LICENSE \
  --origin https://github.com/MiguelElGallo/agent-plugin-forge \
  --revision "$(git rev-parse HEAD)" \
  --source-subpath examples/tutorial/release-notes
```

The summary begins with `Plan:` and contains a 64-character `review plan sha256`. The command also says `No files changed`, then prints a complete apply command that preserves the date and hash. Save that command for use after review.

To keep a review for later, add `--json` and save the output outside the checkout as described in the [CLI reference](../reference/cli.md#forge-import). If you apply on another day, pass `--imported-at YYYY-MM-DD` with the original `review_payload.importedAt` date; the default date is part of the approval hash.

## Review the plan

Before applying it, check the source again:

```bash
git status --short
git diff
```

Both commands should show no changes. Review every source file and the `LICENSE` text. Do not run scripts from an untrusted imported skill just to see what they do.

## Apply the reviewed plan

After the exact plan is approved, use the printed apply command from the same Forge checkout. It includes the original `--imported-at` date, so it also works when approval happens on a later day. Alternatively, repeat the original command with the reviewed hash and `--apply` as below, preserving the original date explicitly if needed:

```bash
uv run forge import \
  --source examples/tutorial/release-notes \
  --plugin release-notes \
  --category "Developer Tools" \
  --version 0.1.0 \
  --description "Create concise release notes from reviewed changes." \
  --author "MiguelElGallo" \
  --license MIT \
  --license-file LICENSE \
  --origin https://github.com/MiguelElGallo/agent-plugin-forge \
  --revision "$(git rev-parse HEAD)" \
  --source-subpath examples/tutorial/release-notes \
  --expected-sha256 PASTE_THE_REVIEW_PLAN_SHA256_HERE \
  --apply
```

The forge recalculates the whole plan. It refuses the apply if source bytes, executable modes, license bytes, metadata, or the destination changed after review.

## Check it

Run:

```bash
uv run forge generate
uv run forge check
```

You should again see `Agent Plugin Forge checks passed`.

Open `plugins/release-notes/` in the Explorer. It now contains the portable manifest, the copied skill, license evidence, and provenance. The copied `SKILL.md` is byte-identical to the example source.

## Recap

You created a scoped branch, reviewed a no-write plan, and applied exactly that plan. Next, [run the complete package checks](review-generate.md).
