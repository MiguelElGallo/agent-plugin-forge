"""Inspect local prerequisites for beginning a Forge review without network access."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from .errors import ForgeError
from .importer import _manifest_repository_url


def _git(repo: Path, executable: str, *args: str) -> str | None:
    """Run a bounded read-only Git probe without exposing failure output."""

    try:
        result = subprocess.run(
            [executable, "-c", "core.fsmonitor=false", *args],
            cwd=repo,
            env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
            capture_output=True,
            text=True,
            errors="replace",
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def diagnose(repo: Path) -> dict[str, Any]:
    """Report local readiness to start a review; cached refs do not prove freshness."""

    checks: list[dict[str, str]] = []

    def add(name: str, status: str, detail: str) -> None:
        """Append a JSON-serializable check without raw command output."""

        checks.append({"name": name, "status": status, "detail": detail})

    python_ok = sys.version_info >= (3, 11)
    add(
        "python",
        "ok" if python_ok else "error",
        "Running Python is 3.11 or newer." if python_ok else "Python 3.11 or newer is required.",
    )
    git = shutil.which("git")
    uv = shutil.which("uv")
    add("git", "ok" if git else "error", "Git found on PATH." if git else "Install Git.")
    add("uv", "ok" if uv else "error", "uv found on PATH." if uv else "Install uv.")
    add(
        "gh",
        "ok",
        "GitHub CLI found; authentication was not checked."
        if shutil.which("gh")
        else "Optional GitHub CLI is absent; it is needed only for approved GitHub publication.",
    )
    if git is None:
        add("checkout", "error", "Checkout checks require Git.")
    elif _git(repo, git, "rev-parse", "--is-inside-work-tree") != "true":
        add("checkout", "error", "Cannot inspect a Git worktree at this location.")
    else:
        add("checkout", "ok", "Git worktree detected.")
        branch = _git(repo, git, "symbolic-ref", "--quiet", "--short", "HEAD")
        add(
            "branch",
            "ok" if branch == "main" else "warning",
            "On main."
            if branch == "main"
            else "Not on main, or HEAD is detached; inspect before starting a new review branch.",
        )
        config_names = _git(repo, git, "config", "--name-only", "--list", "--null")
        filters_present = config_names is not None and any(
            name.lower().startswith("filter.") and name.lower().endswith((".clean", ".process"))
            for name in config_names.split("\0")
        )
        if config_names is None or filters_present:
            add(
                "worktree",
                "warning",
                "Worktree inspection skipped: Git filters may execute configured commands."
                if filters_present
                else "Worktree inspection skipped: Git filter configuration could not be checked.",
            )
        else:
            state = _git(
                repo,
                git,
                "status",
                "--porcelain",
                "--untracked-files=normal",
                "--ignore-submodules=all",
            )
            add(
                "worktree",
                "error" if state is None else "warning" if state else "ok",
                "Cannot inspect worktree changes."
                if state is None
                else "Worktree has changes; preserve them before starting a new review branch."
                if state
                else "Worktree is clean outside submodules.",
            )
        tracked = _git(repo, git, "ls-files", "--stage", "-z")
        if tracked is None:
            add("submodules", "warning", "Tracked submodules could not be checked.")
        elif any(entry.startswith("160000 ") for entry in tracked.split("\0")):
            add(
                "submodules",
                "warning",
                "Tracked submodules exist; their worktrees were not inspected.",
            )
        else:
            add("submodules", "ok", "No tracked submodules.")
        origin = _git(repo, git, "config", "--get", "remote.origin.url")
        if origin is None:
            add(
                "origin",
                "error",
                "Origin is missing or cannot be read; configure the intended remote.",
            )
        else:
            try:
                _manifest_repository_url(origin, repo=repo)
            except (ForgeError, ValueError, OSError):
                add("origin", "error", "Origin is invalid or unsafe; its value is withheld.")
            else:
                add("origin", "ok", "Origin format is valid; reachability was not checked.")
        local = _git(repo, git, "rev-parse", "--verify", "refs/heads/main")
        remote = _git(repo, git, "rev-parse", "--verify", "refs/remotes/origin/main")
        if local is None or remote is None:
            add("alignment", "warning", "Local main or cached origin/main is unavailable.")
        elif local != remote:
            add(
                "alignment",
                "warning",
                "Local main differs from cached origin/main; inspect divergence before updating.",
            )
        else:
            add("alignment", "ok", "Local main matches cached origin/main; no fetch was performed.")
    return {"ready": all(check["status"] == "ok" for check in checks), "checks": checks}
