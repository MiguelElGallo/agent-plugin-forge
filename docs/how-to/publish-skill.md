# Publish a skill with your agent

Use this guide after installing `agent-plugin-forge`. Work from the project that contains the skill; do not clone the Forge repository.

## Before you start

You need:

- Agent Plugin Forge installed through [Install Agent Plugin Forge](../tutorials/install-forge.md);
- a local skill directory or lone `SKILL.md`;
- a destination repository containing the complete Forge runtime and catalog on `main`; see [prepare a team repository](maintain-team-marketplace.md#prepare-the-central-repository) if needed;
- [Git](https://git-scm.com/downloads) and [uv](https://docs.astral.sh/uv/getting-started/installation/) available to the agent for the review checkout;
- GitHub CLI authentication only when you approve publication.

## Prepare the review

Send:

> My skill is at `/absolute/path/to/my-skill`. Review it and prepare it for publication through Agent Plugin Forge. Stop after the review plan and ask me before publishing.

On first use, the agent asks **which repository should receive the skill**, shows the exact URL, and confirms whether to remember it as your default across projects. Installation does not choose a publication repository, and Forge has no public fallback.

After you confirm, the agent saves that choice in your user settings. On later requests, it reuses the saved destination and shows it in the plan without asking the same setup question. You can request a different repository for one publication, or explicitly replace the saved default. Both choices are confirmed; a one-time override leaves your saved default intact. See [destination settings](../reference/cli.md#remembered-destination) for storage locations and commands.

Answer any metadata questions the agent cannot resolve from the source, license, or destination marketplace. The agent then bootstraps a temporary Forge checkout and returns a 64-character plan hash without external GitHub writes. Remembering a destination does not approve publication.

Before approving anything, confirm the report includes:

- the checkout, selected Forge origin, whether it used the saved default or an override, normalized repository URL, and exact `main` revision;
- the source path, immutable source revision, and license evidence;
- the destination plugin name, version, category, and client compatibility;
- every instruction, executable, asset, and destination reviewed;
- the 64-character Forge review-plan hash;
- every external action proposed for publication.

The review phase may retrieve public content and create local temporary files. It must not create a fork, push a branch, open a pull request, or merge.

## Publish the approved plan

Send an approval that includes the exact hash and scope:

> Publish reviewed plan `PLAN_SHA256` by applying it, testing it, pushing the branch, and opening a pull request. Do not merge.

Add fork creation only when the authenticated GitHub account cannot push upstream. Add merge only when you intend to authorize it; the agent must still verify the exact PR head SHA and green required checks.

If the plan changes, review and approve the new hash instead. A prior approval never applies to changed source or destination state. The import date is also part of the hash: when resuming on another day, the agent must preserve the reviewed `--imported-at` date. See [recover from a plan mismatch](troubleshoot.md#the-review-plan-hash-no-longer-matches).

After the pull request merges, continue with [Install a published plugin](../tutorials/install-published-plugin.md).
