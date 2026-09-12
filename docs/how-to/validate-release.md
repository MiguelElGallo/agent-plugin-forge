# Validate and release the forge

The `Check` workflow runs the same repository gate on pull requests and pushes to `main`. Unit and integration tests run on Linux, macOS, and Windows. Third-party actions are pinned to full commits.

## Local release gate

```bash
uv sync --locked
uv run forge --version
uv run ruff check .
uv run ruff format --check .
uv run ty check
uv run pytest
uv run forge generate --check
uv run forge check
uv run zensical build --clean --strict
```

Pydantic owns forge-specific catalog, provenance, marketplace, and MCP semantic contracts. Vendored JSON Schema remains authoritative for Agent Plugins `plugin.json` and `mcp.json`. Schema bytes are pinned by complete checksums for offline validation.

When updating Python libraries, review their supported Python versions and migration notes, update `pyproject.toml`, and run `uv lock --upgrade` followed by the local gate. The project supports Python 3.11 and later; CI also tests the minimum version. Subprocess coverage uses `[tool.coverage.run] patch = ["subprocess"]`, as required by [pytest-cov 7](https://pytest-cov.readthedocs.io/en/latest/subprocess-support.html).

Keep the project version, shipped Forge plugin, and marketplace version aligned. Generate the client indexes with `uv run forge generate` and review the changes. The Python package and `forge --version` read the installed distribution metadata; the test suite checks that it matches the project, lockfile, plugin, and catalog. Renderer golden tests use a fixed synthetic marketplace: ordinary imports and version bumps do not change those snapshots. Update them only when an intentional renderer change alters the reviewed fixture output. `forge check` validates the live repository's marketplace contents and generated indexes.

## Client acceptance matrix

Before release, record exact versions and test both the installed user journey and direct contributor workflow:

1. run **Chat: Install Plugin from Source** against the exact public repository in an isolated VS Code profile, accept the source trust prompt, select `agent-plugin-forge` when a multi-entry marketplace presents a picker, confirm that it shows **Manage**, and find `package-agent-skill` in **Chat: Configure Skills...**;
2. run the packaged bootstrap helper with isolated settings: verify that first use asks for a destination before creating a checkout, save a confirmed repository, reuse it from another project, and check overrides and explicit default replacement; then verify temporary creation, persistent checkout reuse, clean `main`, and exact revision against an isolated Git remote;
3. install the same package in isolated Copilot CLI and Codex homes;
4. open a disposable contributor clone in VS Code and run the manual tutorial commands;
5. register a local portable fixture using [`chat.pluginLocations`](../tutorials/use-in-vscode.md), confirm its skill and MCP server, and call a credential-free tool.

Marketplace command pairs:

```bash
copilot plugin marketplace add MiguelElGallo/agent-plugin-forge
copilot plugin install agent-plugin-forge@agent-plugin-forge
copilot plugin list

codex plugin marketplace add MiguelElGallo/agent-plugin-forge
codex plugin add agent-plugin-forge@agent-plugin-forge
codex plugin list
```

Use isolated client homes for repeatable tests. Do not remove or replace a user's existing marketplace registrations during acceptance.

For destination tests, use the helper's `--config SETTINGS_PATH` or a temporary `XDG_CONFIG_HOME`. Exercise the helper from the installed package and compare its files with the reviewed source. Settings checks must not modify the user's real saved destination. Distinguish deterministic helper execution, package installation, and a full agent publication invocation in the compatibility record.

For VS Code update acceptance, run **Extensions: Check for Extension Updates** and confirm the new plugin version before relying on the approximately daily automatic check.

Treat local-origin and private-host acceptance as separate checks. A disposable local Git source qualifies offline review, origin hashing, and refusal to publish without a GitHub endpoint.

Private-marketplace qualification requires a disposable private GitHub.com or GitHub Enterprise Server remote. Confirm each client accepts its documented HTTPS or SSH form, every form resolves to the intended repository, the review prompt retains the private origin, and publication derives its authentication host and pull-request target from that origin. Never place real private credentials in fixtures or logs.

## Publish and read back

Merge only the reviewed head SHA after every required check succeeds. Then verify clean `main`, the live GitHub branch protections or ruleset, generated marketplace bytes, a fresh marketplace install, and the deployed Zensical site. Documentation deploys only from `main`.

Build the Python wheel and source distribution from the reviewed release tree with `uv build`, and smoke-test the wheel in an isolated environment. Tag the verified merged commit as `vVERSION` and publish a GitHub release containing both archives and their `SHA256SUMS`. Read back the release tag, asset hashes, marketplace version, and deployed documentation. Plugin consumers install from the Git marketplace; the Python archives provide the Forge CLI. This workflow does not publish to PyPI.
