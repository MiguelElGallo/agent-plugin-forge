# Turn a skill into a portable plugin

Agent Plugin Forge is a repository your coding agent can operate. Give the agent a local or staged Agent Skill and ask it to package the skill here. Repository instructions route it through questions, provenance, deterministic generation, validation, and pull-request review.

```text
skill source
    ↓ review and dry-run
portable plugins/<plugin>/
    ↓ deterministic generation
Copilot marketplace + Codex compatibility wrapper
    ↓ checks and PR
reviewed main
```

The portable package targets [Agent Plugins 1.0](https://agent-plugins.org/). It remains the source of truth; client marketplace files are distribution adapters.

## Start here

- Follow [Package your first skill](tutorials/first-skill.md) for a guided run.
- Use [Import an existing skill](how-to/import-skill.md) when you already know the workflow.
- Read [Architecture](explanation/architecture.md) to understand the portable and client-specific layers.
- Read [Trust model](explanation/trust-model.md) before importing third-party content.
