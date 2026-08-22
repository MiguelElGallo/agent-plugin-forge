# Install Agent Plugin Forge

In this tutorial you will install Agent Plugin Forge directly from its marketplace and confirm that your client discovered the publication skill. You will not clone the repository.

Choose the client you use with your coding agent.

## Visual Studio Code

Open the Command Palette and run **Preferences: Open User Settings (JSON)**. Merge these entries into the existing JSON object:

```json
{
  "chat.plugins.enabled": true,
  "chat.plugins.marketplaces": ["MiguelElGallo/agent-plugin-forge"]
}
```

Open the Extensions view and search for `@agentPlugins`. Select `agent-plugin-forge` and choose **Install**.

Run **Chat: Configure Skills** from the Command Palette. `package-agent-skill` should appear. This is the deterministic proof that VS Code discovered the installed skill.

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

The installed list should include `agent-plugin-forge`. Installing it does not create a Forge checkout; the publication skill creates a disposable checkout only when you ask it to review a skill.

## Check the trigger

Open a project containing an Agent Skill and ask:

> I have a skill to publish. Explain the review checkpoint before making changes.

The response should distinguish the no-external-write review phase from the approved publication phase. Do not approve publication yet.

Next, [publish your first skill](publish-skill.md).
