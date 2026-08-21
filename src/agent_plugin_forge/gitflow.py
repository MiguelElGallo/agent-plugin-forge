from __future__ import annotations

import subprocess
from pathlib import Path

from .common import ForgeError, validate_name


def _git(repo: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
    )
    if check and result.returncode:
        detail = result.stderr.strip() or result.stdout.strip()
        raise ForgeError(f"git {' '.join(args)} failed: {detail}")
    return result.stdout.strip()


def create_skill_branch(repo: Path, plugin: str, skill: str, base: str = "main") -> str:
    validate_name(plugin, kind="plugin")
    validate_name(skill, kind="skill")
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
    branch = f"skill/{plugin}/{skill}"
    if _git(repo, "show-ref", "--verify", f"refs/heads/{branch}", check=False):
        raise ForgeError(f"Local branch already exists: {branch}")
    if _git(repo, "ls-remote", "--heads", "origin", branch):
        raise ForgeError(f"Remote branch already exists: {branch}")
    _git(repo, "switch", "-c", branch)
    return branch


def validate_skill_branch(branch: str) -> tuple[str, str]:
    parts = branch.split("/")
    if len(parts) != 3 or parts[0] != "skill":
        raise ForgeError("Skill branches must use skill/<plugin>/<skill>")
    validate_name(parts[1], kind="plugin")
    validate_name(parts[2], kind="skill")
    return parts[1], parts[2]


def validate_pr_scope(repo: Path, branch: str, base: str) -> list[str]:
    plugin, skill = validate_skill_branch(branch)
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
    changed = _git(repo, "diff", "--name-only", f"{base_ref}...HEAD").splitlines()
    if bootstrap:
        return changed
    exact = {
        ".agents/plugins/marketplace.json",
        ".github/plugin/marketplace.json",
        "catalog/plugins.json",
        f"plugins/{plugin}/plugin.json",
        f"plugins/{plugin}/provenance/{skill}.json",
        f"plugins/{plugin}/LICENSE",
        f"plugins/{plugin}/NOTICE",
        f"compat/codex/plugins/{plugin}/.codex-plugin/plugin.json",
        f"compat/codex/plugins/{plugin}/LICENSE",
        f"compat/codex/plugins/{plugin}/NOTICE",
    }
    prefixes = (
        f"plugins/{plugin}/skills/{skill}/",
        f"plugins/{plugin}/licenses/{skill}/",
        f"plugins/{plugin}/LICENSES/{skill}/",
        f"compat/codex/plugins/{plugin}/skills/{skill}/",
        f"compat/codex/plugins/{plugin}/licenses/{skill}/",
        f"compat/codex/plugins/{plugin}/LICENSES/{skill}/",
    )
    outside = [path for path in changed if path not in exact and not path.startswith(prefixes)]
    if outside:
        raise ForgeError(
            f"PR changes files outside branch scope {plugin}/{skill}: {', '.join(outside)}"
        )
    return changed
