# Client compatibility evidence

This page records the most recent client versions checked against the documentation. These are qualification observations, not minimum supported versions.

## Evidence recorded on 2026-08-22

| Client | Version | Evidence recorded |
| --- | --- | --- |
| Visual Studio Code | 1.134.0 (`110a328ea54b42367b803ec53ee0bf52ef26b419`, arm64) | Installed public Forge plugin `0.3.0` from repository revision [`30cb97adeacfbc7280044728af167f5b206ec106`](https://github.com/MiguelElGallo/agent-plugin-forge/commit/30cb97adeacfbc7280044728af167f5b206ec106) in a disposable profile; verified the trust prompt, **Manage** state, `package-agent-skill` discovery, and **Extensions: Check for Extension Updates** command. |
| Codex CLI | 0.149.0 | Verified the local command interfaces for marketplace add, list, upgrade, plugin add, and plugin list. The generated Codex marketplace passes the repository schema and golden tests. |
| GitHub Copilot CLI | 1.0.79-9 | Verified the local command interfaces for marketplace add, list, update, plugin install, plugin update, and plugin list. The generated Copilot marketplace passes the repository schema and golden tests. |

The working-tree candidate is plugin version `0.3.1`. Its package, provenance, generated marketplaces, tests, and strict documentation build pass locally, but the public-repository installation above qualifies the `0.3.0` baseline, not an unpublished `0.3.1` remote install. Fresh `0.3.1` marketplace installs remain required after the candidate is published.

The 2026-08-22 documentation change did not qualify authentication against a live private GitHub or GitHub Enterprise Server host. Private-host release acceptance remains a separate required test.

## Record a new qualification

Update this page when a release changes client installation, marketplace generation, or portable runtime behavior. Record exact versions and distinguish a live install or runtime test from command-surface and schema validation.
