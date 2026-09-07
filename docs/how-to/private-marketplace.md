# Use a private Forge marketplace

Use this guide for a private repository, mirror, GitHub Enterprise Server, or a Forge checkout stored outside the operating system's temporary directory.

Set one Git URL for installation and publication. The examples use:

```text
https://github.company.example/platform/agent-plugin-forge.git
```

## Install from the private source

Codex:

```bash
codex plugin marketplace add https://github.company.example/platform/agent-plugin-forge.git
codex plugin marketplace list --json
codex plugin add agent-plugin-forge@MARKETPLACE_NAME
```

GitHub Copilot CLI:

```bash
copilot plugin marketplace add https://github.company.example/platform/agent-plugin-forge.git
copilot plugin marketplace list
copilot plugin install agent-plugin-forge@MARKETPLACE_NAME
```

Use the marketplace name reported by the add or list command. A private fork may retain `agent-plugin-forge`, while a mirror can declare another name.

Visual Studio Code:

1. Run **Chat: Install Plugin from Source** from the Command Palette.
2. Enter `https://github.company.example/platform/agent-plugin-forge.git`.
3. Review the private host and repository in the trust prompt, then choose **Trust**.
4. If VS Code presents the marketplace's plugin list, select `agent-plugin-forge`.
5. Run **Chat: Configure Skills...** and confirm that `package-agent-skill` appears.

Installing a plugin trusts its bundled MCP servers as part of that plugin. Inspect executable and MCP content in a private or mirrored marketplace before confirming the source.

To register the marketplace without installing immediately, add it to VS Code user or managed settings:

```json
{
  "chat.plugins.marketplaces": [
    "https://github.company.example/platform/agent-plugin-forge.git"
  ]
}
```

All three clients document full HTTPS Git marketplace URLs. HTTPS Git authentication may use a configured credential helper; SSH uses the SSH agent and configuration. Confirm that the selected client can authenticate to the intended host under your organization's policy. Never embed a personal access token in the URL. Live private-host authentication has not been qualified in the [recorded compatibility evidence](../reference/compatibility.md).

Installing from a private marketplace does not automatically change the publication helper's default origin. Include the private Forge URL in every review or reuse prompt. As an alternative, set `AGENT_PLUGIN_FORGE_ORIGIN` in the environment that launches your agent client.

## Authenticate GitHub CLI

Before the publication phase, authenticate the private host according to your organization's policy:

```bash
gh auth status --hostname github.company.example
```

If forks are disabled, arrange a writable branch or remote with the repository administrator. The agent must not redirect private skill content to the public Forge.

## Tell the agent which Forge to use

Include the origin in the review prompt:

> My skill is at `/absolute/path/to/my-skill`. Use Forge origin `https://github.company.example/platform/agent-plugin-forge.git`. Review it for publication and stop after the review plan.

The installed helper passes the selected GitHub or GHES origin through clone, validation, push, and pull-request targeting. Local/file Git sources are useful for offline review and acceptance tests, but they do not have a GitHub pull-request endpoint. A local-origin plan is bound to its `file://` repository URL and is review-only. To publish, bootstrap the final GitHub/GHES origin and generate, review, and approve a new plan; never reuse the local-origin hash.

A mirror on another Git host can also be installed and reviewed, but the automated pull-request phase supports only GitHub.com and GitHub Enterprise Server. Use the host's contribution workflow only after generating and approving a new plan bound to that final repository URL.

## Use a persistent checkout location

Ask the agent to bootstrap at an unused absolute path:

> Use Forge origin `https://github.company.example/platform/agent-plugin-forge.git` and `/work/agent-plugin-forge` as the persistent Forge checkout.

The first run creates it. Later sessions use the helper's `--reuse` mode, which updates only a clean checkout on `main` with the matching origin. It refuses dirty worktrees, another branch, symlinks, and origin changes rather than overwriting them.

The marketplace name comes from the private repository's catalog. Continue using the name reported by the client after `@` in installation and update commands.
