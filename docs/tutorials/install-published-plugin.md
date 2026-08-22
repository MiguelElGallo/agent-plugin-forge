# Install a published plugin

In this tutorial you will install a plugin after its Agent Plugin Forge pull request has merged. The marketplace source is already available from the Forge installation, so no repository clone or second marketplace setup is needed.

Replace `PLUGIN_NAME` with the name reported by the publication pull request. Replace `MARKETPLACE_NAME` only when your private or mirrored marketplace declares a different name.

## Codex

Refresh the marketplace snapshot, then install:

```bash
codex plugin marketplace upgrade MARKETPLACE_NAME
codex plugin add PLUGIN_NAME@MARKETPLACE_NAME
```

For the public Forge, `MARKETPLACE_NAME` is `agent-plugin-forge`. Confirm the result:

```bash
codex plugin list --json
```

## GitHub Copilot CLI

Refresh the marketplace catalog, then install:

```bash
copilot plugin marketplace update MARKETPLACE_NAME
copilot plugin install PLUGIN_NAME@MARKETPLACE_NAME
copilot plugin list
```

The installed list should include `PLUGIN_NAME`.

## Visual Studio Code

Run **Extensions: Check for Extension Updates** from the Command Palette to fetch current marketplace content immediately. VS Code also checks eligible plugin sources approximately every 24 hours when automatic extension updates are enabled.

Run **Chat: Open Customizations**, choose **Plugins**, and choose **Browse Marketplace**. Select `PLUGIN_NAME`, choose **Install**, and return to the installed Plugins list to confirm that it is enabled.

VS Code does not currently expose the Agent Plugins marketplace installation as the same shell command used by Copilot CLI. It consumes the same portable package through its Plugins UI.

## Use the plugin

Start a new agent chat and make a request that matches the installed skill's description. Use **Chat: Configure Skills...** in VS Code or the client plugin list when you need to confirm discovery independently of model output.

You have now completed the full journey: install the Forge, publish through a reviewed checkpoint, and install the resulting plugin.
