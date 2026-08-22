# Generate and test the package

The portable files under `plugins/release-notes/` are authoritative. This chapter derives both marketplace formats, then runs the same gate as CI.

## Inspect what changed

In VS Code, open the Source Control view. You should see changes in four groups:

- `plugins/release-notes/` — portable source and provenance;
- `catalog/plugins.json` — distribution category and policy;
- `.github/plugin/marketplace.json` — Copilot distribution metadata;
- `.agents/plugins/marketplace.json` — Codex distribution metadata.

The Copilot entry should contain the same plugin name and version as `plugins/release-notes/plugin.json`. The Codex entry should contain the same name and point to `./plugins/release-notes`. Do not fix generated drift by editing either file.

## Regenerate from scratch

Generation is deterministic and transactional:

```bash
uv run forge generate
uv run forge generate --check
```

The second command prints nothing when both generated marketplace files match.

## Run the complete local gate

Run:

```bash
uv run forge check
uv run ruff check .
uv run ruff format --check .
uv run ty check
uv run pytest
uv run zensical build --clean --strict
```

The tests include malformed manifests, path escapes, links and special files, case collisions, secret patterns, plan tampering, transaction rollback, MCP transports, generated drift, and a complete CLI import.

## Check the diff

Run:

```bash
git diff --check
git status --short
```

Review all prompt text and executable content before committing. CI will accept this plugin on `skill/release-notes/release-notes` but will reject unrelated repository changes on that branch.

## Recap

The portable package and both client outputs now agree, and the full quality gate passes. Next, [load the portable plugin in VS Code](use-in-vscode.md).
