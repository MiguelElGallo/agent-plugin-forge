# Install, publish, install

Agent Plugin Forge has three user journeys. Choose the one that matches what you want to do.

## 1. Install Agent Plugin Forge

You do not need to clone the repository. Visual Studio Code can install the Forge from its Git repository with one Command Palette action. Codex and GitHub Copilot CLI register the marketplace and install `agent-plugin-forge` with their exact command pairs.

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

[Publish a skill with your agent →](how-to/publish-skill.md)

## 3. Install the published plugin

After the pull request is merged, users refresh the configured marketplace and install the new plugin. VS Code users trigger an extension update check, then install from the Plugins customization view.

[Install a published plugin →](tutorials/install-published-plugin.md)

## Private and self-hosted marketplaces

Private GitHub repositories and GitHub Enterprise Server use the same reviewed publication workflow and can keep a persistent checkout in another local directory. Mirrors and other Git hosts support installation and review, but automated pull-request publication requires GitHub.com or GitHub Enterprise Server. Configure the selected Git marketplace source once, then give the agent that Forge origin when publishing.

[Use a private Forge marketplace →](how-to/private-marketplace.md)

## Maintainers and contributors

Clone the repository only when you intend to develop the Forge itself or work directly on its marketplace. The [Forge contributor tutorial](tutorials/prepare-vscode.md) covers that separate workflow.

Use the [how-to guides](how-to/publish-skill.md) for focused tasks, [reference](reference/client-installation.md) for exact commands and contracts, and [explanation](explanation/review-and-publish.md) for the design behind the approval boundary.
