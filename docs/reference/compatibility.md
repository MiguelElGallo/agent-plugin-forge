# Client compatibility evidence

This page records dated client checks. These are qualification observations, not minimum supported versions. Structural conformance is tracked separately in [Standards and Forge policy](standards.md).

## Evidence recorded on 2026-09-07

The project, shipped Forge plugin, and marketplace version are reset to `0.0.1`. This is an intentional version reset from the earlier `0.3.x` numbering. The historical installation evidence below retains its original versions; it does not qualify a fresh `0.0.1` client installation. Clients may not offer a lower version as an automatic update, so verify the installed version after explicitly selecting the reset release.

| Client | Version | Evidence recorded |
| --- | --- | --- |
| Codex CLI | 0.153.4 | Local help confirms the documented marketplace add/upgrade, plugin add/list, and available-plugin inspection commands. No fresh install or skill execution was performed. |
| GitHub Copilot CLI | 1.0.84-1 | Local help confirms marketplace add/update/browse and plugin install/update/list. `copilot --plugin-dir ./plugins/agent-plugin-forge plugin list` discovers the local portable package under **External Plugins**. No skill execution or MCP invocation was performed. |
| Visual Studio Code | Not requalified | The local tutorial now uses the officially documented `chat.pluginLocations` setting. The live install evidence below remains dated 2026-08-22. |

The command review used the current [Codex reference](https://learn.chatgpt.com/docs/developer-commands?surface=cli#codex-plugin), [Copilot CLI reference](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-plugin-reference), and [VS Code plugin documentation](https://code.visualstudio.com/docs/agent-customization/agent-plugins). This review did not qualify private-host authentication or an end-to-end publication.

## Evidence recorded on 2026-08-22

| Client | Version | Evidence recorded |
| --- | --- | --- |
| Visual Studio Code | 1.134.0 (`110a328ea54b42367b803ec53ee0bf52ef26b419`, arm64) | Installed public Forge plugin `0.3.0` from repository revision [`30cb97adeacfbc7280044728af167f5b206ec106`](https://github.com/MiguelElGallo/agent-plugin-forge/commit/30cb97adeacfbc7280044728af167f5b206ec106) in a disposable profile; verified the trust prompt, **Manage** state, `package-agent-skill` discovery, and **Extensions: Check for Extension Updates** command. |
| Codex CLI | 0.149.0 | Verified the local command interfaces for marketplace add, list, upgrade, plugin add, and plugin list. The generated Codex marketplace passes the repository schema and golden tests. |
| GitHub Copilot CLI | 1.0.79-9 | Verified the local command interfaces for marketplace add, list, update, plugin install, plugin update, and plugin list. The generated Copilot marketplace passes the repository schema and golden tests. |

At that time, the working-tree candidate was plugin version `0.3.1`; its local package, provenance, generated marketplaces, tests, and strict documentation build passed. The public-repository installation above qualifies the `0.3.0` baseline. It does not qualify a `0.3.1` remote installation; a fresh release install must be recorded separately.

The 2026-08-22 documentation change did not qualify authentication against a live private GitHub or GitHub Enterprise Server host. Private-host release acceptance remains a separate required test.

## Record a new qualification

Update this page when a release changes client installation, marketplace generation, or portable runtime behavior. Record exact versions and distinguish a live install or runtime test from command-surface and schema validation.
