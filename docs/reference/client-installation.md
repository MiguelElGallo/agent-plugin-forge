# Client installation

Marketplace configuration is a one-time client setup. Refresh its snapshot after a new plugin merges, then install that plugin.

| Client | Configure marketplace once | Refresh after merge | Install a plugin |
| --- | --- | --- | --- |
| Codex | `codex plugin marketplace add MARKETPLACE_SOURCE` | `codex plugin marketplace upgrade MARKETPLACE_NAME` | `codex plugin add PLUGIN_NAME@MARKETPLACE_NAME` |
| GitHub Copilot CLI | `copilot plugin marketplace add MARKETPLACE_SOURCE` | `copilot plugin marketplace update MARKETPLACE_NAME` | `copilot plugin install PLUGIN_NAME@MARKETPLACE_NAME` |
| Visual Studio Code | Add `MARKETPLACE_SOURCE` to `chat.plugins.marketplaces` | **Chat: Open Customizations** → **Plugins** → **Update Plugins** | **Browse Marketplace** → **Install** |

For the public Forge:

- `MARKETPLACE_SOURCE` is `MiguelElGallo/agent-plugin-forge`;
- `MARKETPLACE_NAME` is `agent-plugin-forge`;
- use `agent-plugin-forge` as `PLUGIN_NAME` to install the Forge itself.

`MARKETPLACE_SOURCE` can also be an HTTPS Git URL, SSH Git URL, or supported local source. This allows mirrors and private GitHub servers to keep installation and publication inside their own boundary.

## Visual Studio Code settings

`chat.plugins.marketplaces` is a user setting. Merge these entries into the existing user settings object:

```json
{
  "chat.plugins.enabled": true,
  "chat.plugins.marketplaces": ["MARKETPLACE_SOURCE"]
}
```

Do not use `chat.pluginLocations` for a marketplace installation. That setting loads a local package during development and requires a filesystem path.

## Availability boundary

A plugin becomes available through a marketplace only after its pull request merges and the client refreshes its marketplace snapshot. A branch or open pull request is not a marketplace release.
