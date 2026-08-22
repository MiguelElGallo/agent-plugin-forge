# Install, publish, install

Agent Plugin Forge has three user journeys. Choose the one that matches what you want to do.

## 1. Install Agent Plugin Forge

You do not need to clone the repository. Add the marketplace once and install `agent-plugin-forge` in Visual Studio Code, Codex, or GitHub Copilot CLI.

[Install the Forge →](tutorials/install-forge.md)

## 2. Publish your skill

Open the project that already contains your skill and tell the agent where it is:

> My skill is at `/absolute/path/to/my-skill`. Review it and prepare it for publication through Agent Plugin Forge. Stop after the review plan and ask me before publishing.

The agent creates its own disposable Forge checkout. The workflow has a hard checkpoint:

```text
your skill
    │
    ▼
review phase: inspect → plan → report hash → stop
    │
    ▼ your explicit approval
publish phase: apply → validate → push → pull request
```

Nothing is pushed and no pull request is opened during review. Merge requires separate authorization.

[Publish your first skill →](tutorials/publish-skill.md)

## 3. Install the published plugin

After the pull request is merged, users refresh the configured marketplace and install the new plugin. VS Code users do both from the Plugins customization view.

[Install a published plugin →](tutorials/install-published-plugin.md)

## Private and self-hosted marketplaces

The same workflow supports private repositories, mirrors, GitHub Enterprise Server, and a persistent checkout in another local directory. Configure the Git marketplace URL once, then give the agent that Forge origin when publishing.

[Use a private Forge marketplace →](how-to/private-marketplace.md)

## Maintainers and contributors

Clone the repository only when you intend to develop the Forge itself or work directly on its marketplace. The [Forge contributor tutorial](tutorials/prepare-vscode.md) covers that separate workflow.

Use the [how-to guides](how-to/publish-skill.md) for focused tasks, [reference](reference/client-installation.md) for exact commands and contracts, and [explanation](explanation/review-and-publish.md) for the design behind the approval boundary.
