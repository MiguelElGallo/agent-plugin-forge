# Why review and publication are separate

The phrase “publish my skill” describes an outcome, but it crosses two different trust boundaries.

## Review is local and reversible

The review phase may inspect the source, clone the selected Forge repository into a disposable local directory, create a local branch, and calculate a plan. It does not change the source skill and does not create a fork, push, pull request, or merge.

The plan hash binds source bytes, executable modes, license evidence, metadata, and destination state. It gives the user a concrete object to approve instead of a vague future action.

## Publication changes shared state

Publication applies the approved plan, generates client marketplaces, runs validation, and then changes GitHub state. Fork or remote creation, pushing, and opening a pull request become authorized only at this checkpoint. Merge is another distinct action because it makes the package available to every marketplace consumer.

This boundary prevents a convenient one-prompt workflow from becoming implicit permission to publish unreviewed instructions or executable content.

## The Forge origin is part of the boundary

The bootstrap origin determines where the catalog comes from and where the pull request goes. Public GitHub, private repositories, mirrors, and GitHub Enterprise Server use the same workflow, but credentials and content never cross between them unless the user explicitly selects a different origin.

## Installation follows merge

The published package is the portable directory under `plugins/`. Codex and Copilot CLI install it by marketplace name; VS Code installs it through the Agent Plugins view. All three clients consume the same reviewed package rather than client-specific copies.
