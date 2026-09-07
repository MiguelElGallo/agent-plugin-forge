# Prepare a Forge development checkout

This is the contributor tutorial for changing Forge code or marketplace contents directly. Installing the Forge and publishing through its agent workflow do not require a manual clone; use [Install Agent Plugin Forge](install-forge.md) for that journey.

In this chapter you will open a fresh development checkout in Visual Studio Code, install the locked Python environment, and prove that the repository starts valid.

## Prerequisites

Install [Git](https://git-scm.com/downloads), [uv](https://docs.astral.sh/uv/getting-started/installation/), and Visual Studio Code. Forge requires Python 3.11 or newer; `uv sync --locked` can provision a compatible interpreter. You also need a GitHub account to create the tutorial fork.

Confirm the tools are available in the terminal you will use:

```bash
git --version
uv --version
```

Before committing, configure your [Git author identity](https://git-scm.com/book/en/v2/Getting-Started-First-Time-Git-Setup). The tutorial uses macOS, Linux, or Windows Git Bash shell syntax.

## Fork and clone the repository

Create a fork with GitHub's **Fork** button so you have a repository where you can push and merge the tutorial changes. Then, in a macOS, Linux, or Git Bash terminal, run:

```bash
git clone https://github.com/YOUR-GITHUB-USER/agent-plugin-forge.git
cd agent-plugin-forge
git remote add upstream https://github.com/MiguelElGallo/agent-plugin-forge.git
```

Open **Visual Studio Code**, choose **File > Open Folder**, and select the `agent-plugin-forge` folder. If VS Code asks whether you trust the authors, review the repository URL and choose **Trust**.

The tutorial uses POSIX shell syntax. On Windows, select **Git Bash** as the VS Code integrated-terminal profile.

Open **Terminal > New Terminal**. The terminal should start in the repository root.

## Install the locked environment

Run:

```bash
uv sync --locked
```

`uv` creates `.venv` and installs the exact dependency versions recorded in `uv.lock`. It does not install the forge globally.

Inspect local branch readiness before making changes:

```bash
uv run forge doctor
```

Doctor reports missing prerequisites, checkout state, and alignment with cached `origin/main`. It does not fetch; the branch helper performs the live remote check later. Follow any reported recovery steps before starting a new branch.

## Check it

Run the repository validator:

```bash
uv run forge check
```

You should see:

```text
Agent Plugin Forge checks passed
```

If this first check fails, stop here. A fresh checkout should be valid before you add a skill.

## Recap

You now have:

- a fresh fork open in VS Code;
- the locked development environment;
- a known-good validation result.

Next, [import your first skill](first-skill.md).
