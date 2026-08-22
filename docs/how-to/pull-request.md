# Open and merge a pull request

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

The hosted `main` ruleset requires a pull request, green required checks, linear history, and resolved review conversations. It blocks force pushes and deletion. CI has read-only contents permission, receives no pull-request secrets, does not use `pull_request_target`, and never commits generated output.
