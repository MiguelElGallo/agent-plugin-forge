# Package your first skill

This tutorial packages a local skill named `release-notes` as its own plugin.

## 1. Prepare the forge

```bash
git clone https://github.com/MiguelElGallo/agent-plugin-forge.git
cd agent-plugin-forge
uv sync --locked
uv run forge check
```

## 2. Ask your agent

Tell the agent:

> I have a skill at `/absolute/path/release-notes`. Package it here as a new Developer Tools plugin. The upstream license is MIT and the source revision is `<commit>`.

The agent reads the forge skill, confirms any missing identity or provenance fields, and creates `skill/release-notes/release-notes`.

## 3. Review the plan

The first `forge import` command omits `--apply`. It prints the destination, file count, and deterministic content hash without writing files. Review the source instructions, scripts, assets, and license before allowing the applied import.

## 4. Review the result

The portable result appears under `plugins/release-notes/`. Generated Copilot and Codex distribution files change after `forge generate`. The agent then runs the same checks CI will run and prepares a pull request.

No source script runs during this process.
