# Open and merge a pull request

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

Review the full diff, especially imported prompt text and executable files. Push the `skill/<plugin>/<skill>` branch and open a PR. Merge only after required checks pass, review conversations are resolved, and the generated output matches the portable packages. On the hosted repository, the `main` ruleset must be enabled before claiming that direct pushes, force pushes, and branch deletion are blocked.
