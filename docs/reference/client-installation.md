# Client installation

Marketplace configuration is a one-time client setup. Refresh its snapshot after a new plugin merges, then install that plugin.

| Client | Configure marketplace once | Refresh after merge | Install a plugin |
| --- | --- | --- | --- |
| Codex | `codex plugin marketplace add MARKETPLACE_SOURCE` | `codex plugin marketplace upgrade MARKETPLACE_NAME` | `codex plugin add PLUGIN_NAME@MARKETPLACE_NAME` |
| GitHub Copilot CLI | `copilot plugin marketplace add MARKETPLACE_SOURCE` | `copilot plugin marketplace update MARKETPLACE_NAME` | `copilot plugin install PLUGIN_NAME@MARKETPLACE_NAME` |
| Visual Studio Code | **Chat: Install Plugin from Source** → `MARKETPLACE_SOURCE` | **Extensions: Check for Extension Updates** | **Chat: Open Customizations** → **Plugins** → **Browse Marketplace** → **Install** |

VS Code automatically discovers plugins installed by GitHub Copilot CLI under `~/.copilot/installed-plugins/`. Users of both clients can install with Copilot CLI once and manage the same plugin from VS Code.

For the public Forge:

- `MARKETPLACE_SOURCE` is `MiguelElGallo/agent-plugin-forge`;
- `MARKETPLACE_NAME` is `agent-plugin-forge`;
- use `agent-plugin-forge` as `PLUGIN_NAME` to install the Forge itself.

For **Chat: Install Plugin from Source**, use the public repository URL `https://github.com/MiguelElGallo/agent-plugin-forge`. VS Code reviews the source, asks for trust, and clones it without a manual settings edit. If the marketplace contains multiple plugins, select `agent-plugin-forge` from the picker.

Source forms depend on the client. Public GitHub repositories accept `owner/repo` shorthand. Full HTTPS Git URLs are suitable for GitHub Enterprise Server, private repositories, and mirrors. VS Code also documents SCP-style SSH remotes and `file:///` marketplace sources. Use forms that resolve to the intended repository; automated publication is limited to GitHub.com and GitHub Enterprise Server origins.

## Manual Visual Studio Code marketplace registration

Use settings only when you need to register a marketplace without installing the Forge immediately, or when an administrator supplies the setting. `chat.plugins.marketplaces` is a user setting. Merge these entries into the existing user settings object:

```json
{
  "chat.plugins.marketplaces": ["MARKETPLACE_SOURCE"]
}
```

`chat.plugins.enabled` defaults to enabled in current VS Code. Check that setting only when plugins were explicitly disabled or an organization manages the feature.

Do not use `chat.pluginLocations` for a marketplace installation. That setting loads a local package during development and requires a filesystem path.

## Update an installed plugin

Refresh and update an existing installation with the client-specific operation:

| Client | Update an installed plugin |
| --- | --- |
| Codex | `codex plugin marketplace upgrade MARKETPLACE_NAME`, then `codex plugin add PLUGIN_NAME@MARKETPLACE_NAME` |
| GitHub Copilot CLI | `copilot plugin marketplace update MARKETPLACE_NAME`, then `copilot plugin update PLUGIN_NAME@MARKETPLACE_NAME` |
| Visual Studio Code | Run **Extensions: Check for Extension Updates**, then choose **Update** when the installed plugin offers it |

## Upgrade Forge to 1.0.1

Refresh the marketplace and update `agent-plugin-forge` with the commands above, then verify that its installed version is `1.0.1`. Start a new chat so the agent loads the updated package.

Version 1.0.1 fixes two low-severity issues: inconsistent file snapshots during import approval and control characters in terminal diagnostics. It adds the exact source file map to the approval hash. Plans created by older versions need to be generated, reviewed, and approved again; do not substitute a new hash without review. File bytes, filenames, and decoded JSON values are not rewritten by diagnostic escaping.

Version 1.0.0 removes the automatic public publication target. The first publication asks for your destination and confirms whether to remember it across projects. An existing `AGENT_PLUGIN_FORGE_ORIGIN` remains an explicit override; the agent shows it and confirms whether to save it. A bare bootstrap command with no configured destination now stops before cloning. Automated callers must supply `--origin`, set the environment override, or save a confirmed default. See [destination settings](cli.md#remembered-destination).

Installing or updating the Forge does not select a publication repository. Register the repository where you publish separately if you want to install its resulting plugins.

## Availability boundary

A plugin becomes available through a marketplace only after its pull request merges and the client refreshes its marketplace snapshot. A branch or open pull request is not a marketplace release.

See [client compatibility evidence](compatibility.md) for the dated qualification scope. The current upstream references are [VS Code agent plugins](https://code.visualstudio.com/docs/agent-customization/agent-plugins), [GitHub Copilot CLI plugins](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-plugin-reference), and [Codex plugin commands](https://developers.openai.com/codex/cli/reference/#codex-plugin).
