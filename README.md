# Agent Plugin Forge

[![CI](https://github.com/MiguelElGallo/agent-plugin-forge/actions/workflows/check.yml/badge.svg?branch=main)](https://github.com/MiguelElGallo/agent-plugin-forge/actions/workflows/check.yml)
[![Documentation](https://github.com/MiguelElGallo/agent-plugin-forge/actions/workflows/docs.yml/badge.svg?branch=main)](https://github.com/MiguelElGallo/agent-plugin-forge/actions/workflows/docs.yml)
[![Tested platforms](https://img.shields.io/badge/tested-Ubuntu%20%7C%20macOS%20%7C%20Windows-555)](https://github.com/MiguelElGallo/agent-plugin-forge/actions/workflows/check.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**Documentation:** [Read the Agent Plugin Forge documentation](https://miguelelgallo.github.io/agent-plugin-forge/).

Install the Forge once, give your coding agent a skill, approve its review plan, and publish a portable [Agent Plugins 1.0](https://agent-plugins.org/) package for Visual Studio Code, GitHub Copilot, and Codex.

You do **not** need to clone this repository to use the Forge.

The CI workflow runs linting, formatting, type checking, Forge validation, and a strict documentation build on Ubuntu. The pytest suite runs on Ubuntu, macOS, and Windows.

## 1. Install Agent Plugin Forge

### Visual Studio Code

Open the Command Palette, run **Chat: Install Plugin from Source**, and enter:

```text
https://github.com/MiguelElGallo/agent-plugin-forge
```

Review the source URL and choose **Trust**. If VS Code shows the marketplace's plugin list, select `agent-plugin-forge`. Then run **Chat: Configure Skills...** to confirm that `package-agent-skill` is available. No repository clone or `settings.json` edit is required.

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

Follow [Publish a skill with your agent](https://miguelelgallo.github.io/agent-plugin-forge/how-to/publish-skill/) for the complete two-phase workflow.

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

VS Code users run **Extensions: Check for Extension Updates**, then open **Chat: Open Customizations**, choose **Plugins**, and install `PLUGIN_NAME` from **Browse Marketplace**. See [Install a published plugin](https://miguelelgallo.github.io/agent-plugin-forge/tutorials/install-published-plugin/).

## Private GitHub and custom locations

The Forge is not tied to GitHub.com or a fixed local path. Codex, Copilot CLI, and VS Code accept Git marketplace sources, and the publication skill can create or safely reuse a checkout at a location you choose. GitHub.com and GitHub Enterprise Server origins support the automated push and pull-request phase. Other Git hosts support installation and review but require a separately reviewed host-specific contribution workflow.

See [Use a private Forge marketplace](https://miguelelgallo.github.io/agent-plugin-forge/how-to/private-marketplace/) for GitHub Enterprise Server, private repositories, mirrors, and persistent checkout setup.

For a team sharing skills from one central repository, follow [Maintain a team skill marketplace](docs/how-to/maintain-team-marketplace.md). It covers repository ownership, review and merge responsibilities, private-origin selection, installation, and the current contributor workflow for changing an existing skill.

## How the Forge stores packages

- `plugins/` contains the authoritative portable packages.
- `.github/plugin/marketplace.json` is the generated Copilot marketplace.
- `.agents/plugins/marketplace.json` is the generated Codex marketplace.
- `catalog/plugins.json` holds distribution category and compatibility policy.

The default is one skill per plugin. Bundles are explicit. Skill-only, MCP-only, and mixed packages are supported.

See [Standards and Forge policy](docs/reference/standards.md) for the dated standards review, working-directory support, and client compatibility policy. For setup failures or rejected imports, start with [Troubleshooting](docs/how-to/troubleshoot.md).

## Contribute to the Forge itself

Clone the repository only when changing Forge code, schemas, tests, documentation, or marketplace content directly. Start with [Contributing](CONTRIBUTING.md) and the [Forge contributor tutorial](https://miguelelgallo.github.io/agent-plugin-forge/tutorials/prepare-vscode/). Run `uv run forge doctor` for an offline prerequisite and checkout-readiness report. Import plans print a date-preserving apply command to use after approval.
