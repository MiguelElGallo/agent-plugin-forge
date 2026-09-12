# Client compatibility evidence

This page records dated client checks. These are qualification observations, not minimum supported versions. Structural conformance is tracked separately in [Standards and Forge policy](standards.md).

## Current release: 1.0.1

The project, shipped Forge plugin, marketplace, and lockfile use `1.0.1`. This patch addresses two low-severity issues: import approval snapshot consistency and untrusted terminal diagnostics. The packaged skill instructions and bootstrap helper are unchanged from 1.0.0.

The regression suite covers source replacement between inspection and open, mutation during reads, bounded reads, byte-preserving copies, license snapshot hashing, exact file-map approval, CRLF metadata, all C0/DEL/C1 terminal controls, and POSIX surrogateescape output. It checks that ordinary Unicode paths and decoded JSON values remain unchanged. Import plans from older versions require fresh review after upgrade.

On macOS, the 1.0.1 suite passed 386 tests on both Python 3.11.16 and 3.12.13, with two platform-specific skips and 92% coverage. Ruff, ty, Forge validation, generation drift, actionlint, and the strict documentation build passed. Independent patch review identified a non-UTF-8 filename edge case; it was corrected and covered by a regression before the final full-suite runs.

The wheel installed into a fresh Python 3.12 environment and passed version, branch-name, and repository-validation smoke checks. Copilot CLI `1.0.84-1` enabled the 1.0.1 plugin with one skill from an isolated local marketplace. This is local installation evidence, not a fresh remote download or agent publication invocation. VS Code and Codex runtime acceptance was not repeated for this CLI-only patch; the dated 1.0.0 and earlier observations below retain their original scope. The GitHub release records final cross-platform CI and public marketplace read-back.

Initial Windows CI exposed a cross-API file-metadata mismatch. The correction preserves file identity and read-change checks while accounting for CPython's [Windows path-stat timestamp and executable-suffix behavior](https://github.com/python/cpython/blob/v3.12.10/Modules/posixmodule.c#L1894-L2149). The regression suite includes modeled Windows metadata and executable suffixes.

## Previous release: 1.0.0

The project, shipped Forge plugin, marketplace, and lockfile use `1.0.0`. This release removes the built-in publication repository and adds a confirmed destination saved across projects. The [publication guide](../how-to/publish-skill.md) and [destination settings reference](cli.md#remembered-destination) describe first use, reuse, overrides, and replacement of the saved default.

The destination regression suite covers missing configuration before any checkout, read-only inspection, persistence across processes and projects, override precedence, protected replacement, competing saves, invalid settings, failed-write recovery, and lock release after a client exits unexpectedly. The real CLI tutorial also runs from a remembered destination through plan, approved apply, generation, and validation, checking the repository shown in the plan and manifest.

On macOS, the 1.0.0 suite passed 288 tests on both Python 3.11.16 and 3.12.13, with two platform-specific skips and 92% coverage. Ruff, ty, Forge validation, generation drift checks, and the strict documentation build passed. The built wheel installed into a fresh environment and passed `forge --version`, branch-name validation, and `forge check`. A one-file benchmark smoke run completed the documented workflow; it is not a new performance benchmark.

Copilot CLI `1.0.84-1` registered a local marketplace in an isolated configuration and enabled the 1.0.0 Forge plugin with one skill. That client loads local marketplace packages live from the source directory, so this is local installation evidence, not a remote download or an agent publication invocation.

The client commands were checked on 2026-09-12 against local Codex CLI `0.153.4`, GitHub Copilot CLI `1.0.84-1`, and the upstream [Codex](https://developers.openai.com/codex/cli/reference/#codex-plugin), [Copilot CLI](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-plugin-reference), and [VS Code](https://code.visualstudio.com/docs/agent-customization/agent-plugins) references. Historical client experiments below retain their actual versions and scope; they are not fresh `1.0.0` installation or runtime evidence. GitHub Enterprise Server authentication still requires separate qualification.

## Previous release: 0.3.0

The `0.3.0` release passed 257 tests on Python 3.11 and 3.12. A fresh public Copilot CLI `1.0.84-1` installation matched all nine package files from merged revision `2a97c34889aa9fa035b6e1397e799df491cb7562`, and the installed skill completed its check-only workflow without changing files or branches. That evidence is recorded in the [0.3.0 release](https://github.com/MiguelElGallo/agent-plugin-forge/releases/tag/v0.3.0).

Earlier development snapshots also used `0.3.0` and `0.3.1`, as recorded below. After an explicit refresh and update, verify the installed `1.0.1` version and package content.

## Evidence recorded on 2026-09-11–12

The local `0.0.2` candidate passed the full suite on macOS with Python 3.11.16 and 3.12.13: 257 tests passed, two platform-specific tests skipped, and coverage reached 92%. Ruff, ty, Forge validation, the strict documentation build, and the built wheel's version and branch-name commands passed.

| Client | Version | Evidence recorded |
| --- | --- | --- |
| Visual Studio Code | 1.137.0 (`645f29cc3176500b4b5762ba887cf2a7f0ffdf2c`, arm64) | In a temporary profile, installed a harmless `forge-smoke` plugin from a private GitHub.com repository using **Chat: Install Plugin from Source**. Verified source trust, **Manage** state, Skills discovery, slash-command completion, and an invocation returning `FORGE_SMOKE_OK_20260911`. |
| GitHub Copilot CLI | 1.0.84-1 | In an isolated client home, installed three new plugins containing four skills from the private GitHub.com fixture, verified installed bytes, and invoked every skill. Refreshed the marketplace and updated only `team-review` from `0.1.0` to `0.1.1`; its runtime marker changed to V2 while all other installed package hashes stayed equal. |

Forge `0.0.2` created the fixture's skill branch, applied the reviewed import hash, generated both marketplaces, and validated the package. The installed cache matched fixture revision `a170e50d5417695c6d0780276ee2aa664adfc8fd`; its skill bytes matched the reviewed source.

The multi-skill installation used fixture revision `796fb8f149f0cbc045f762235206355809e9cffd`; the update used `8985331bed92c8de7de9073476f4f14a8ffb9342`. Private visibility and the final remote revision were read back. The original `forge-smoke` package stayed unchanged.

The shipped skill also passed five local conformance scenarios and an independent existing-skill maintenance walkthrough, including the documented provenance example and full local gates. The [benchmark guide](../how-to/benchmark-skill.md) describes methodology, measured results, and boundaries.

This qualifies private GitHub.com fixture installation and skill invocation, plus the recorded local contributor workflows. It does not qualify a fresh public `0.0.2` release installation, the complete installed Forge publication journey, GitHub Enterprise Server authentication, executable MCP or hook behavior, or Linux/Windows execution for this candidate.

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
