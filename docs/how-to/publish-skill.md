# Publish a skill with your agent

Use this guide after installing `agent-plugin-forge`. Work from the project that contains the skill; do not clone the Forge repository.

## Before you start

You need:

- Agent Plugin Forge installed through [Install Agent Plugin Forge](../tutorials/install-forge.md);
- a local skill directory or lone `SKILL.md`;
- Git and `uv` for the review checkout;
- GitHub CLI authentication only when you approve publication.

## Prepare the review

Send:

> My skill is at `/absolute/path/to/my-skill`. Review it and prepare it for publication through Agent Plugin Forge. Stop after the review plan and ask me before publishing.

Answer only metadata questions the agent cannot resolve from the source, license, or destination marketplace. The agent bootstraps a temporary Forge checkout and returns a 64-character plan hash without external GitHub writes.

Before approving anything, confirm the report includes:

- the checkout, selected Forge origin, normalized repository URL, and exact `main` revision;
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

If the plan changes, review and approve the new hash instead. A prior approval never applies to changed source or destination state.

After the pull request merges, continue with [Install a published plugin](../tutorials/install-published-plugin.md).
