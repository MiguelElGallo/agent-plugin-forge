# Install a published plugin

In this tutorial you will install a plugin after its Agent Plugin Forge pull request has merged. Use the repository where the skill was published. It may differ from the repository where you installed the Forge tool.

Replace `PLUGIN_NAME` and `MARKETPLACE_NAME` with the plugin and marketplace names reported for that publication repository. Saving a publication destination does not register it in your client's marketplace list.

## Codex

If the publication repository is not registered yet, add its Git URL:

```bash
codex plugin marketplace add FORGE_GIT_URL
```

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

If the publication repository is not registered yet, add it:

```bash
copilot plugin marketplace add FORGE_GIT_URL
```

Refresh the marketplace catalog, then install:

```bash
copilot plugin marketplace update MARKETPLACE_NAME
copilot plugin install PLUGIN_NAME@MARKETPLACE_NAME
copilot plugin list
```

The installed list should include `PLUGIN_NAME`.

## Visual Studio Code

If the publication repository is not registered, run **Chat: Install Plugin from Source**, enter its Git URL, review the source, and select the published plugin. For a private source, follow [private marketplace installation](../how-to/private-marketplace.md#install-from-the-private-source).

Run **Extensions: Check for Extension Updates** from the Command Palette to fetch current marketplace content immediately. VS Code also checks eligible plugin sources approximately every 24 hours when automatic extension updates are enabled.

Run **Chat: Open Customizations**, choose **Plugins**, and choose **Browse Marketplace**. Select `PLUGIN_NAME`, choose **Install**, and return to the installed Plugins list to confirm that it is enabled.

VS Code does not currently expose the Agent Plugins marketplace installation as the same shell command used by Copilot CLI. It consumes the same portable package through its Plugins UI.

## Use the plugin

Start a new agent chat and make a request that matches the installed skill's description. Use **Chat: Configure Skills...** in VS Code or the client plugin list when you need to confirm discovery independently of model output.

You have now completed the full journey: install the Forge, publish through a reviewed checkpoint, and install the resulting plugin.
