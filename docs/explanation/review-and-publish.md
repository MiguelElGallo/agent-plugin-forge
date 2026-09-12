# Why review and publication are separate

The phrase “publish my skill” describes an outcome, but it crosses two different trust boundaries.

## Review is local and reversible

The review phase may inspect the source, clone the selected Forge repository into a disposable local directory, create a local branch, and calculate a plan. It does not change the source skill and does not create a fork, push, pull request, or merge.

The plan hash binds source bytes, executable modes, license evidence, metadata, and destination state. It gives the user a concrete object to approve instead of a vague future action.

## Publication changes shared state

Publication applies the approved plan, generates client marketplaces, runs validation, and then changes GitHub state. Fork or remote creation, pushing, and opening a pull request become authorized only at this checkpoint. Merge is another distinct action because it makes the package available to every marketplace consumer.

This boundary prevents a convenient one-prompt workflow from becoming implicit permission to publish unreviewed instructions or executable content.

## The Forge origin is part of the boundary

Installing the Forge selects where to obtain the tool. Publication has its own destination choice: the agent asks on first use, confirms the exact repository and whether to remember it, and saves a user preference shared across projects. There is no hardcoded publication repository. Future reviews reuse and display that saved destination. A changed destination is confirmed, and a one-time override does not silently replace the default.

The saved URL is a routing preference, not approval to publish. Each new import still produces its own review plan with the final repository URL bound into its hash. A saved preference or an old plan cannot authorize changed content or a different target.

The bootstrap origin determines where the catalog and review plan come from. GitHub.com and GitHub Enterprise Server origins also determine the automated pull-request target. Local sources and other Git hosts support review and acceptance, but publication requires a separately reviewed contribution workflow bound to the final repository URL. Credentials and content never cross between origins unless the user explicitly selects a different one.

## Installation follows merge

The published package is the portable directory under `plugins/`. Codex and Copilot CLI install it by marketplace name; VS Code installs it through the Agent Plugins view. All three clients consume the same reviewed package rather than client-specific copies.
