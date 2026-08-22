# Build portable agent plugins in VS Code

Agent Plugin Forge is a repository your coding agent can operate. Point the agent at a local skill and it creates the portable package, provenance, client marketplaces, tests, and pull-request-ready diff.

The smallest useful request is:

> I have a skill at `/absolute/path/my-skill`. Package it here.

You stay in control of the decisions that cannot be inferred: destination bundle, category, version, source revision, and license evidence.

## What you will build

```text
local skill or existing plugin
        ↓ plan, inspect, approve
plugins/<plugin>/                 portable source of truth
        ├── plugin.json
        ├── skills/<skill>/
        └── mcp.json              optional
        ↓ deterministic generation
Copilot marketplace + Codex marketplace
        ↓ tests and scoped PR
reviewed main
```

Visual Studio Code is the primary tutorial client. It loads the Agent Plugins 1.0 package directly. The same portable package is distributed to GitHub Copilot and Codex through their client-specific marketplace indexes.

## Start the tutorial

The tutorial is cumulative and runnable. Each chapter ends with a check before adding the next capability.

1. [Prepare VS Code and the repository](tutorials/prepare-vscode.md)
2. [Import your first skill](tutorials/first-skill.md)
3. [Generate and test the package](tutorials/review-generate.md)
4. [Load the plugin in VS Code](tutorials/use-in-vscode.md)
5. [Add an MCP server](tutorials/add-mcp.md)

If you already know the workflow, use the focused [how-to guides](how-to/import-skill.md). For exact contracts, use [Reference](reference/cli.md). For the reasons behind the design, read [Architecture](explanation/architecture.md) and the [Trust model](explanation/trust-model.md).
