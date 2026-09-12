# Open and merge a pull request

Publication has two phases. A review request may create a local branch and no-write plan, but it does not authorize a fork, push, or pull request. Continue with the steps below only after the user approves the exact plan hash and lists the external actions.

Use the branch type that matches the change:

- `skill/<plugin>/<skill>` for one skill import;
- `plugin/<plugin>/<topic>` for MCP or plugin-wide changes;
- `forge/<topic>` for tooling, CI, schemas, or documentation.

The branch helper refuses dirty, outdated, detached, or colliding branches. It never pushes or merges.

Before opening a PR, run:

```bash
uv run forge generate
uv run forge check
uv run ruff check .
uv run ruff format --check .
uv run ty check
uv run pytest
uv run zensical build --clean --strict
```

Review the complete diff, especially imported instructions, executable files, MCP endpoints, and generated client output. Push the branch and open a PR targeting `main`.

Merge is a separate authorization. Before merging, verify that the PR head SHA still matches the reviewed commit and every required check is green.

Configure the marketplace's `main` ruleset to require a pull request, green required checks, and resolved review conversations, and to block force pushes and deletion. Repository access and branch rules are host settings; copying the Forge files into a private repository does not copy those protections. The included PR workflow has read-only contents permission, receives no pull-request secrets, does not use `pull_request_target`, and never commits generated output. See [team marketplace maintenance](maintain-team-marketplace.md) for the surrounding ownership and release workflow.
