# Agent Plugin Forge

Choose the workflow that matches what you want to do.

| What you want to do | Start here |
| --- | --- |
| Install Forge for your coding agent | [Install the Forge](tutorials/install-forge.md) |
| Publish an existing skill | [Publish a skill with your agent](how-to/publish-skill.md) |
| Install a plugin already in the marketplace | [Install a published plugin](tutorials/install-published-plugin.md) |
| Develop Forge or package an MCP server | [Prepare a development checkout](tutorials/prepare-vscode.md) |
| Share and maintain skills in a private team repository | [Maintain a team skill marketplace](how-to/maintain-team-marketplace.md) |
| Resolve an installation or import error | [Troubleshooting](how-to/troubleshoot.md) |

## 1. Install Agent Plugin Forge

You do not need to clone the repository. Visual Studio Code can install the Forge from its Git repository with one Command Palette action. Codex and GitHub Copilot CLI register the marketplace and install `agent-plugin-forge` with their exact command pairs.

[Install the Forge →](tutorials/install-forge.md)

## 2. Publish your skill

Open the project that already contains your skill and tell the agent where it is:

> My skill is at `/absolute/path/to/my-skill`. Review it and prepare it for publication through Agent Plugin Forge. Stop after the review plan and ask me before publishing.

On first use, the agent asks which repository should receive the skill and confirms whether to remember it as your default across projects. Later runs reuse that saved destination and show it in the plan. There is no built-in publication repository. The agent creates its own disposable checkout of the selected Forge, then follows this review checkpoint:

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

Private GitHub repositories and GitHub Enterprise Server use the same reviewed publication workflow and can keep a persistent checkout in another local directory. Mirrors and other Git hosts support installation and review, but automated pull-request publication requires GitHub.com or GitHub Enterprise Server. Configure the Git marketplace source for installation, then confirm and remember the publication destination on first use.

[Use a private Forge marketplace →](how-to/private-marketplace.md)

For ownership, review responsibilities, existing-skill maintenance, and team rollout, follow [Maintain a team skill marketplace](how-to/maintain-team-marketplace.md).

## Maintainers and contributors

Clone the repository only when you intend to develop the Forge itself or work directly on its marketplace. The [Forge contributor tutorial](tutorials/prepare-vscode.md) covers that separate workflow.

Use the [how-to guides](how-to/publish-skill.md) for focused tasks, [reference](reference/client-installation.md) for exact commands and contracts, and [explanation](explanation/review-and-publish.md) for the design behind the approval boundary.
