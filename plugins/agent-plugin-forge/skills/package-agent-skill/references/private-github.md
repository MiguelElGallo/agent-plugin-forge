# Alternate and private Forge origins

Read this reference when the user publishes through a mirror, private repository, another checkout location, or GitHub Enterprise Server (GHES).

## Resolve the origin

Accept an HTTPS Git URL, SSH Git URL, scp-style Git URL, or local path selected by the user. Prefer SSH for a private host when their Git credentials already use SSH. Never copy a token into the origin URL. Local and `file://` origins support offline review and acceptance testing only; automated pull-request publication requires a GitHub.com or GitHub Enterprise Server origin.

Pass the origin to the bootstrap helper:

```bash
uv run --no-project python /absolute/path/to/package-agent-skill/scripts/bootstrap_forge.py \
  --origin ssh://git@github.company.example/platform/agent-plugin-forge.git
```

The user may set `AGENT_PLUGIN_FORGE_ORIGIN` instead. For a persistent checkout outside the temporary directory, add `--destination ABSOLUTE_PATH`; use `--reuse` in later sessions only when that checkout should be updated.

## Authenticate the host

Git clone, fetch, and push use the user's existing Git credential helper or SSH configuration. GitHub CLI operations require authentication for the same host:

```bash
gh auth status --hostname github.company.example
```

If authentication is absent, stop and ask the user to authenticate with their organization's required method. Do not request or embed a personal access token in a prompt, command, remote URL, or repository file.

Derive repository and pull-request targets from the selected GitHub origin. Do not redirect private content to the public Agent Plugin Forge repository. GHES may disable forks; in that case, use an existing writable remote or ask the user for the organization's contribution path. If the selected origin is local or belongs to another Git host, stop after review. To use a GitHub/GHES publication target, bootstrap that origin and generate, review, and approve a new plan; the local-origin hash binds a `file://` repository URL and must never be reused. An alternative contribution workflow also requires a new plan bound to its final repository URL and separate explicit approval.

## Client marketplace source

Codex and Copilot CLI accept HTTPS and SSH Git marketplace URLs. VS Code accepts Git URLs in `chat.plugins.marketplaces`. Use the same private source in each client so installation and publication target the same catalog.

After merge, report install commands using the marketplace name declared by that repository. Do not assume its name is `agent-plugin-forge` if the mirror changed the catalog metadata.
