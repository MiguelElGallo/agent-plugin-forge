# Portable core and client adapters

Agent Plugins 1.0 standardizes a deliberately small portable package: root `plugin.json`, immediate Agent Skills under `skills/`, and root `mcp.json`. It does not standardize marketplace schemas, installation policy, branch workflows, or every vendor-specific customization.

## Installed assistant and operating checkout

The `agent-plugin-forge` plugin is the user-facing assistant. It can be installed from a marketplace without cloning this repository. When asked to publish from another workspace, its bundled bootstrap helper clones the selected Forge origin into a disposable or user-selected location and verifies clean current `main` before the Forge CLI runs.

```text
installed package-agent-skill
        ↓ bootstrap selected origin
clean Forge checkout
        ↓ review plan, then explicit approval
portable package and pull request
```

The origin is configurable. Public GitHub, a private repository, a mirror, and GitHub Enterprise Server use the same package layout. The selected origin also defines the publication target so private content is not redirected to the public marketplace.

## One source of truth

Forge keeps the portable package under `plugins/`. Visual Studio Code and compatible GitHub Copilot clients load that package directly:

```text
plugins/<plugin>/
        ├── plugin.json
        ├── skills/
        └── mcp.json
             │
             ├──> VS Code portable loader
             └──> Copilot marketplace
```

The root manifest never contains `skills`, `mcpServers`, or `category`. Skills and MCP use fixed locations; category belongs to distribution metadata.

## Two marketplace indexes, one package

VS Code, GitHub Copilot, and current Codex releases consume the portable Agent Plugins package. Copilot and Codex use different marketplace schemas, so Forge derives two indexes that both point to the same directory:

```text
portable plugins/<plugin>/
        ├──> .github/plugin/marketplace.json
        └──> .agents/plugins/marketplace.json
```

The indexes are validated independently because their distribution metadata differs. No package translation occurs, so skills, supported MCP configuration, runtime files, and environment-variable semantics remain identical across clients. Forge rejects hidden `.codex-plugin` overlays and prevents SSE packages from claiming Codex compatibility, keeping the declared execution surface honest.

## Cohesive code boundaries

The implementation mirrors those responsibilities:

- `sources.py` resolves supported intake shapes;
- `filesystem.py` owns path, file-type, size, secret, copying, and mode safety;
- `models.py` owns Pydantic data contracts;
- `mcp.py` owns portable MCP semantics;
- `packages.py` loads portable packages;
- `marketplaces.py` renders client-specific marketplace schemas;
- `generator.py` stages, publishes, rolls back, and checks drift;
- `validator.py` aggregates repository-level evidence.

This separation keeps a validation error close to the contract that produced it and lets edge-case tests exercise each boundary independently.
