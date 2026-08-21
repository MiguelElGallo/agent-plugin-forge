# Validation and release

The `Check` workflow runs the same repository validation on pull requests and `main`; generators run in check mode and never commit from CI. Tests run on Linux, macOS, and Windows. Third-party actions are pinned to full commits.

Pydantic models enforce the forge-owned catalog, provenance, license-evidence, and generated Codex contracts. The vendored Agent Plugins JSON Schema remains authoritative for portable manifests, while the Agent Skills frontmatter checks follow its separate specification.

The Documentation workflow deploys strict Zensical output only from `main`. Before a release, verify a fresh clone, a realistic temporary skill import, both command pairs below, and the live Pages site. Record exact client versions because plugin installation behavior can change independently of Agent Plugins 1.0.

```bash
copilot plugin marketplace add MiguelElGallo/agent-plugin-forge
copilot plugin install agent-plugin-forge@agent-plugin-forge

codex plugin marketplace add MiguelElGallo/agent-plugin-forge
codex plugin add agent-plugin-forge@agent-plugin-forge
```
