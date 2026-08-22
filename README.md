# Agent Plugin Forge

Install the Forge once, give your coding agent a skill, approve its review plan, and publish a portable [Agent Plugins 1.0](https://agent-plugins.org/) package for Visual Studio Code, GitHub Copilot, and Codex.

You do **not** need to clone this repository to use the Forge.

## 1. Install Agent Plugin Forge

### Visual Studio Code

Open **Preferences: Open User Settings (JSON)** and merge these entries into the existing object:

```json
{
  "chat.plugins.enabled": true,
  "chat.plugins.marketplaces": ["MiguelElGallo/agent-plugin-forge"]
}
```

Open the Extensions view, search for `@agentPlugins`, and install `agent-plugin-forge`.

### Codex

```bash
codex plugin marketplace add MiguelElGallo/agent-plugin-forge
codex plugin add agent-plugin-forge@agent-plugin-forge
```

### GitHub Copilot CLI

```bash
copilot plugin marketplace add MiguelElGallo/agent-plugin-forge
copilot plugin install agent-plugin-forge@agent-plugin-forge
```

See [Install Agent Plugin Forge](https://miguelelgallo.github.io/agent-plugin-forge/tutorials/install-forge/) for the complete first-time walkthrough.

## 2. Ask the agent to publish your skill

Open the project that contains your skill and ask:

> My skill is at `/absolute/path/to/my-skill`. Review it and prepare it for publication through Agent Plugin Forge. Stop after the review plan and ask me before publishing.

The installed skill creates a disposable, current Forge checkout itself. It inspects the source without executing imported scripts, resolves missing metadata, creates a hash-bound no-write plan, and stops.

Publication begins only when you approve that exact plan. The agent then applies it, runs the complete validation suite, creates or reuses your GitHub fork or writable remote when necessary, pushes the branch, and opens a pull request. Merge remains a separate authorization.

Follow [Publish your first skill](https://miguelelgallo.github.io/agent-plugin-forge/tutorials/publish-skill/) for the complete two-phase experience.

## 3. Install the published plugin

After its pull request is merged, refresh the configured marketplace and install the new plugin:

```bash
codex plugin marketplace upgrade agent-plugin-forge
codex plugin add PLUGIN_NAME@agent-plugin-forge
```

or:

```bash
copilot plugin marketplace update agent-plugin-forge
copilot plugin install PLUGIN_NAME@agent-plugin-forge
```

VS Code users open **Chat: Open Customizations**, choose **Plugins**, refresh, and install `PLUGIN_NAME`. See [Install a published plugin](https://miguelelgallo.github.io/agent-plugin-forge/tutorials/install-published-plugin/).

## Private GitHub and custom locations

The Forge is not tied to GitHub.com or a fixed local path. Codex, Copilot CLI, and VS Code accept a Git marketplace URL. The publication skill accepts a custom HTTPS or SSH Forge origin and can create or safely reuse a checkout at a location you choose.

See [Use a private Forge marketplace](https://miguelelgallo.github.io/agent-plugin-forge/how-to/private-marketplace/) for GitHub Enterprise Server, private repositories, mirrors, and persistent checkout setup.

## How the Forge stores packages

- `plugins/` contains the authoritative portable packages.
- `.github/plugin/marketplace.json` is the generated Copilot marketplace.
- `.agents/plugins/marketplace.json` is the generated Codex marketplace.
- `catalog/plugins.json` holds distribution category and compatibility policy.

The default is one skill per plugin. Bundles are explicit. Skill-only, MCP-only, and mixed packages are supported.

## Contribute to the Forge itself

Clone the repository only when changing Forge code, schemas, tests, documentation, or marketplace content directly. Start with [Contributing](CONTRIBUTING.md) and the [Forge contributor tutorial](https://miguelelgallo.github.io/agent-plugin-forge/tutorials/prepare-vscode/).
