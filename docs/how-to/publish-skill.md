# Publish a skill with your agent

Use this guide after installing `agent-plugin-forge`. Work from the project that contains the skill; do not clone the Forge repository.

## Prepare the review

Send:

> My skill is at `/absolute/path/to/my-skill`. Review it and prepare it for publication through Agent Plugin Forge. Stop after the review plan and ask me before publishing.

Answer only metadata questions the agent cannot resolve from the source, license, or destination marketplace. The agent bootstraps a temporary Forge checkout and returns a 64-character plan hash without external GitHub writes.

Review the reported source revision, license, plugin name, version, category, compatibility, file inventory, and proposed external actions.

## Publish the approved plan

Send an approval that includes the exact hash and scope:

> Publish reviewed plan `PLAN_SHA256` by applying it, testing it, pushing the branch, and opening a pull request. Do not merge.

Add fork creation only when the authenticated GitHub account cannot push upstream. Add merge only when you intend to authorize it; the agent must still verify the exact PR head SHA and green required checks.

If the plan changes, review and approve the new hash instead. A prior approval never applies to changed source or destination state.
