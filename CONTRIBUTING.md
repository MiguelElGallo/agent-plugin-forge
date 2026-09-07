# Contributing

This guide is for people changing the Forge repository or its marketplace directly. Users installing the Forge or publishing a skill through the installed agent workflow do not need to clone this repository; start from the [documentation homepage](https://miguelelgallo.github.io/agent-plugin-forge/).

Install the locked environment and start from a clean, current `main`:

```bash
uv sync --locked
uv run forge doctor
uv run forge check
```

`doctor` is an offline readiness check for starting a branch. It uses cached remote refs and does not authenticate or fetch; the branch helpers still check the live remote. Warnings about a feature branch or unfinished changes are expected during ongoing work.

## Choose the branch scope

- One skill: `uv run forge branch --plugin NAME --skill NAME`
- MCP or plugin-wide change: `uv run forge plugin-branch --plugin NAME --topic TOPIC`
- Forge tooling, CI, schema, or docs: `uv run forge maintenance-branch --topic TOPIC`

Each helper checks the live remote for collisions and alignment. It never pushes or merges.

## Import a skill

1. Stage remote content locally at an immutable revision and inspect it without executing it.
2. Run `uv run forge import` without `--apply`.
3. Review the complete plan, source, license, and destination.
4. Repeat with `--apply --expected-sha256 HASH`.
5. Run `uv run forge generate`.

New plugins require category, version, description, author, license, origin, and immutable revision. Bundles inherit category and require a version bump. Imported content remains under its applicable upstream license.

## Run the gate

```bash
uv run forge check
uv run ruff check .
uv run ruff format --check .
uv run ty check
uv run pytest
uv run zensical build --clean --strict
```

Review all instructions, executable code, MCP endpoints, licenses, provenance, and generated output. Open a pull request targeting `main`; merge only after required checks pass and review conversations are resolved.

## Place documentation with Diátaxis

Keep each page focused on one user need, following [Diátaxis](https://diataxis.fr/):

- `docs/tutorials/` provides a reliable, cumulative learning experience with concrete results;
- `docs/how-to/` gives goal-oriented steps for competent users solving a specific problem;
- `docs/reference/` describes CLI and data contracts precisely and completely;
- `docs/explanation/` discusses architecture, trust, and design decisions.

Link across categories instead of mixing teaching, task instructions, exhaustive facts, and conceptual discussion on one page.
