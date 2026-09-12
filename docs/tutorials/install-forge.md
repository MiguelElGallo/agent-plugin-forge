# Install Agent Plugin Forge

In this tutorial you will install Agent Plugin Forge and confirm that your client discovered the publication skill. You will not clone the repository yourself.

Choose the client you use with your coding agent.

## Visual Studio Code

Open the Command Palette and run **Chat: Install Plugin from Source**. Enter:

```text
https://github.com/MiguelElGallo/agent-plugin-forge
```

VS Code identifies the repository as a plugin marketplace and clones it. Review the source URL in the trust prompt and choose **Trust** only when it matches the repository above. If VS Code presents the marketplace's plugin list, select `agent-plugin-forge`.

Open the Extensions view and enter `@agentPlugins` if you want to inspect the result. `agent-plugin-forge` should show **Manage**, not **Install**.

Run **Chat: Configure Skills...** from the Command Palette. Search for `package-agent-skill`; it should appear. This is the deterministic proof that VS Code discovered the installed skill.

## Codex

Run:

```bash
codex plugin marketplace add MiguelElGallo/agent-plugin-forge
codex plugin add agent-plugin-forge@agent-plugin-forge
```

Then inspect the installed state:

```bash
codex plugin list --json
```

The installed array should include `agent-plugin-forge`. Codex documents plugin installation and marketplace sources in its [CLI reference](https://developers.openai.com/codex/cli/reference/#codex-plugin).

## GitHub Copilot CLI

Run:

```bash
copilot plugin marketplace add MiguelElGallo/agent-plugin-forge
copilot plugin install agent-plugin-forge@agent-plugin-forge
copilot plugin list
```

The installed list should include `agent-plugin-forge`. Installing it does not create an operating Forge checkout; the publication skill creates a disposable checkout only when you ask it to review a skill.

If you use both Copilot CLI and VS Code, you do not need a second VS Code installation. VS Code automatically discovers plugins installed under Copilot CLI's plugin directory. Confirm `package-agent-skill` with **Chat: Configure Skills...** in VS Code.

## Check the trigger

Open a project containing an Agent Skill and ask:

> I have a skill to publish. Explain the review checkpoint before making changes.

The response should explain that the first publication asks for a destination repository, confirms whether to remember it across projects, and then prepares a plan showing that repository. Later publications reuse the saved destination. It should also distinguish the no-external-write review phase from the approved publication phase. Do not approve publication yet.

If discovery fails, use [Troubleshooting](../how-to/troubleshoot.md#the-plugin-or-skill-is-missing). Next, [publish a skill with your agent](../how-to/publish-skill.md).
