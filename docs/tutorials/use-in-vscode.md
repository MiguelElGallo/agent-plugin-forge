# Load the plugin in Visual Studio Code

Visual Studio Code can load Agent Plugins 1.0 directly. In this contributor chapter you will install a local package that has not been merged into a marketplace and verify that VS Code discovers its skill. Normal users install merged packages from the configured marketplace.

## Find the absolute plugin path

In the integrated terminal, run:

```bash
pwd
```

On Windows Git Bash, use `cygpath -m "$PWD/plugins/release-notes"` instead to obtain a VS Code-compatible `C:/...` path. Append `/plugins/release-notes` to the macOS or Linux path.

## Register the local development folder

Open the Command Palette with **Shift+Command+P** on macOS or **Ctrl+Shift+P** on Windows and Linux. Run **Preferences: Open User Settings (JSON)** and merge this entry into your settings, replacing the example path with the absolute plugin path:

```json
{
  "chat.pluginLocations": {
    "/absolute/path/to/agent-plugin-forge/plugins/release-notes": true
  }
}
```

On Windows, use the `C:/...` path from `cygpath`. Preserve existing entries in `chat.pluginLocations`. This is the [documented VS Code local development workflow](https://code.visualstudio.com/docs/agent-customization/agent-plugins#use-local-plugins); marketplace installation uses a separate source URL workflow. If the plugin view does not refresh, run **Developer: Reload Window**.

## Check it in the UI

Run **Chat: Open Customizations** from the Command Palette and select **Plugins**. `release-notes` should appear as an enabled local plugin.

Run **Chat: Configure Skills...**. The `release-notes` skill should appear. This is the direct evidence that VS Code read `plugin.json` and discovered the immediate `skills/release-notes/SKILL.md` entry.

## Check the same package with Copilot CLI

From the VS Code terminal, run:

```bash
copilot --plugin-dir ./plugins/release-notes plugin list
```

The output should contain an **External Plugins** section with `release-notes`. This command mounts the same portable folder without copying it.

## Use it

Open Copilot Chat in agent mode and send:

> Use the release-notes skill. Version 0.1.0 contains one change: add the first portable release-notes plugin. No upgrade action is required.

The response should use **Highlights** and **Changes**, and should not invent extra work. The exact prose can vary; the skill selection in **Chat: Configure Skills...** is the deterministic discovery check.

## Recap

VS Code and Copilot CLI loaded the portable package directly.

## Merge the first tutorial change

Commit and push the reviewed branch, then open a pull request into `main` on your fork. Wait for its checks, merge it, and return to a clean current `main`:

```bash
git add plugins/release-notes catalog/plugins.json .github/plugin/marketplace.json .agents/plugins/marketplace.json
git commit -m "Add release-notes plugin"
git push -u origin skill/release-notes/release-notes
git switch main
git pull --ff-only origin main
```

The next chapter assumes that pull request is merged. Next, [add an MCP server](add-mcp.md).
