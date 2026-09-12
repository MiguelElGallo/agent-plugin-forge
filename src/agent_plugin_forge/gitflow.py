"""Create forge branches and validate branch names and pull-request scope."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from .common import ForgeError, validate_name


def _git(repo: Path, *args: str, check: bool = True, raw: bool = False) -> str:
    """Run Git, preserving exact filename bytes when raw output is requested."""

    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=False,
        capture_output=True,
    )
    output = os.fsdecode(result.stdout)
    if check and result.returncode:
        detail = os.fsdecode(result.stderr).strip() or output.strip()
        raise ForgeError(f"git {' '.join(args)} failed: {detail}")
    return output if raw else output.strip()


def _create_branch(repo: Path, branch: str, base: str) -> str:
    """Create a clean branch from an aligned base after collision checks."""

    if _git(repo, "status", "--porcelain"):
        raise ForgeError("Refusing to create a branch from a dirty worktree")
    current = _git(repo, "branch", "--show-current")
    if current != base:
        raise ForgeError(
            f"Switch to {base!r} before creating a skill branch; current is {current!r}"
        )
    _git(repo, "fetch", "--quiet", "origin", base)
    local_base = _git(repo, "rev-parse", base)
    remote_base = _git(repo, "rev-parse", "FETCH_HEAD")
    if local_base != remote_base:
        raise ForgeError(f"Local {base} is not aligned with origin/{base}")
    if _git(repo, "show-ref", "--verify", f"refs/heads/{branch}", check=False):
        raise ForgeError(f"Local branch already exists: {branch}")
    if _git(repo, "ls-remote", "--heads", "origin", branch):
        raise ForgeError(f"Remote branch already exists: {branch}")
    _git(repo, "switch", "-c", branch)
    return branch


def create_skill_branch(repo: Path, plugin: str, skill: str, base: str = "main") -> str:
    """Create a scoped branch for importing or updating one skill."""

    validate_name(plugin, kind="plugin")
    validate_name(skill, kind="skill")
    return _create_branch(repo, f"skill/{plugin}/{skill}", base)


def create_maintenance_branch(repo: Path, topic: str, base: str = "main") -> str:
    """Create a forge maintenance branch for repository-wide tooling changes."""

    validate_name(topic, kind="skill")
    return _create_branch(repo, f"forge/{topic}", base)


def create_plugin_branch(repo: Path, plugin: str, topic: str, base: str = "main") -> str:
    """Create a scoped branch for MCP or plugin-wide changes."""

    validate_name(plugin, kind="plugin")
    validate_name(topic, kind="skill")
    return _create_branch(repo, f"plugin/{plugin}/{topic}", base)


def validate_skill_branch(branch: str) -> tuple[str, str]:
    """Validate a skill branch and return its plugin and skill names."""

    parts = branch.split("/")
    if len(parts) != 3 or parts[0] != "skill":
        raise ForgeError("Skill branches must use skill/<plugin>/<skill>")
    validate_name(parts[1], kind="plugin")
    validate_name(parts[2], kind="skill")
    return parts[1], parts[2]


def validate_maintenance_branch(branch: str) -> str:
    """Validate a forge maintenance branch and return its topic."""

    parts = branch.split("/")
    if len(parts) != 2 or parts[0] != "forge":
        raise ForgeError("Maintenance branches must use forge/<topic>")
    validate_name(parts[1], kind="skill")
    return parts[1]


def validate_plugin_branch(branch: str) -> tuple[str, str]:
    """Validate a plugin branch and return its plugin and topic names."""

    parts = branch.split("/")
    if len(parts) != 3 or parts[0] != "plugin":
        raise ForgeError("Plugin branches must use plugin/<plugin>/<topic>")
    validate_name(parts[1], kind="plugin")
    validate_name(parts[2], kind="skill")
    return parts[1], parts[2]


def validate_pr_scope(repo: Path, branch: str, base: str) -> list[str]:
    """Validate changed paths against the branch type and return those paths."""

    if base != "main":
        raise ForgeError("Pull requests must target main")
    base_ref = f"origin/{base}"
    bootstrap = (
        subprocess.run(
            ["git", "cat-file", "-e", f"{base_ref}:pyproject.toml"],
            cwd=repo,
            check=False,
            capture_output=True,
        ).returncode
        != 0
    )
    changed = [
        path
        for path in _git(
            repo, "diff", "--no-renames", "--name-only", "-z", f"{base_ref}...HEAD", raw=True
        ).split("\0")
        if path
    ]
    if bootstrap:
        return changed
    if branch.startswith("forge/"):
        validate_maintenance_branch(branch)
        return changed
    if branch.startswith("plugin/"):
        plugin, _ = validate_plugin_branch(branch)
        exact = {
            ".agents/plugins/marketplace.json",
            ".github/plugin/marketplace.json",
            "catalog/plugins.json",
        }
        prefixes = (f"plugins/{plugin}/",)
        outside = [path for path in changed if path not in exact and not path.startswith(prefixes)]
        if outside:
            raise ForgeError(
                f"PR changes files outside plugin branch scope {plugin}: {', '.join(outside)}"
            )
        return changed
    plugin, skill = validate_skill_branch(branch)
    exact = {
        ".agents/plugins/marketplace.json",
        ".github/plugin/marketplace.json",
        "catalog/plugins.json",
        f"plugins/{plugin}/plugin.json",
        f"plugins/{plugin}/provenance/{skill}.json",
        f"plugins/{plugin}/LICENSE",
        f"plugins/{plugin}/NOTICE",
    }
    prefixes = (
        f"plugins/{plugin}/skills/{skill}/",
        f"plugins/{plugin}/licenses/{skill}/",
        f"plugins/{plugin}/LICENSES/{skill}/",
    )
    outside = [path for path in changed if path not in exact and not path.startswith(prefixes)]
    if outside:
        raise ForgeError(
            f"PR changes files outside branch scope {plugin}/{skill}: {', '.join(outside)}"
        )
    return changed
