# Use a private Forge marketplace

Use this guide for a private repository, mirror, GitHub Enterprise Server, or a Forge checkout stored outside the operating system's temporary directory.

Set one Git URL for installation and publication. The examples use:

```text
ssh://git@github.company.example/platform/agent-plugin-forge.git
```

## Install from the private source

Codex:

```bash
codex plugin marketplace add ssh://git@github.company.example/platform/agent-plugin-forge.git
codex plugin add agent-plugin-forge@agent-plugin-forge
```

GitHub Copilot CLI:

```bash
copilot plugin marketplace add ssh://git@github.company.example/platform/agent-plugin-forge.git
copilot plugin install agent-plugin-forge@agent-plugin-forge
```

Visual Studio Code user settings:

```json
{
  "chat.plugins.enabled": true,
  "chat.plugins.marketplaces": [
    "ssh://git@github.company.example/platform/agent-plugin-forge.git"
  ]
}
```

All three clients accept HTTPS or SSH Git marketplace URLs. Their Git operations use your existing credential helper or SSH configuration. Never embed a personal access token in the URL.

## Authenticate GitHub CLI

Before the publication phase, authenticate the private host according to your organization's policy:

```bash
gh auth status --hostname github.company.example
```

If forks are disabled, arrange a writable branch or remote with the repository administrator. The agent must not redirect private skill content to the public Forge.

## Tell the agent which Forge to use

Include the origin in the review prompt:

> My skill is at `/absolute/path/to/my-skill`. Use Forge origin `ssh://git@github.company.example/platform/agent-plugin-forge.git`. Review it for publication and stop after the review plan.

The installed helper passes the selected GitHub or GHES origin through clone, validation, push, and pull-request targeting. Local/file Git sources are useful for offline review and acceptance tests, but they do not have a GitHub pull-request endpoint. A local-origin plan is bound to its `file://` repository URL and is review-only. To publish, bootstrap the final GitHub/GHES origin and generate, review, and approve a new plan; never reuse the local-origin hash.

## Use a persistent checkout location

Ask the agent to bootstrap at an unused absolute path:

> Use `/work/agent-plugin-forge` as the persistent Forge checkout.

The first run creates it. Later sessions use the helper's `--reuse` mode, which updates only a clean checkout on `main` with the matching origin. It refuses dirty worktrees, another branch, symlinks, and origin changes rather than overwriting them.

The marketplace name comes from the private repository's catalog. If administrators rename it, use that name after `@` in client installation commands.
