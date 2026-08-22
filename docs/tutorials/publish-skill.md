# Publish your first skill

In this tutorial your installed Forge skill will inspect an existing local skill, prepare an immutable review plan, and wait for approval before publishing.

You need:

- Agent Plugin Forge installed through [the previous tutorial](install-forge.md);
- a local skill directory or lone `SKILL.md`;
- Git and `uv` for the review checkout;
- GitHub CLI authentication only when you decide to publish.

## Ask for the review

Use an absolute source path so the disposable checkout can refer back to your skill. Send this prompt from the project that contains it:

> My skill is at `/absolute/path/to/my-skill`. Review it and prepare it for publication through Agent Plugin Forge. Stop after the review plan and ask me before publishing.

The agent resolves the installed skill's bootstrap helper and creates a current Forge checkout in the operating system's temporary directory. You do not clone or manage that checkout yourself.

The agent may ask for facts that cannot be inferred safely, such as license evidence, upstream revision, destination category, or whether the skill belongs in an existing bundle.

## Inspect the review report

The review phase may read remote public content and create local temporary files. It must not create a GitHub fork, push a branch, open a pull request, or merge.

Before stopping, the agent should report:

- the disposable checkout, selected Forge origin, normalized repository URL, and exact `main` revision;
- source path, immutable origin revision, and license evidence;
- destination plugin name, version, category, and client compatibility;
- every instruction, executable, asset, and destination it reviewed;
- the 64-character Forge review-plan hash;
- the external actions proposed for publication.

If any input changes, ask the agent to produce a new plan. Never approve an old hash for changed content.

## Approve publication

When the report is correct, send an approval that names the plan and its allowed external actions:

> Publish reviewed plan `PLAN_SHA256` by applying it, running all checks, creating or reusing my GitHub fork if needed, pushing the branch, and opening a pull request. Do not merge.

The agent recalculates the plan before applying it. A changed source byte, executable mode, license, metadata field, or destination invalidates the hash.

It then runs the complete repository gate, reviews the diff, commits it, pushes to an authorized remote, and opens a pull request against the selected marketplace. It should report the PR URL, exact head SHA, and check state.

Merge is intentionally not implied. Authorize it separately only after the required checks and review are complete.

## Finish

Once the pull request is merged, the plugin becomes installable from that marketplace. Continue with [Install a published plugin](install-published-plugin.md).
