from __future__ import annotations

from pathlib import Path

import pytest

from agent_plugin_forge.common import ForgeError
from agent_plugin_forge.gitflow import create_skill_branch, validate_pr_scope, validate_skill_branch

from .conftest import git


def initialized_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    remote = tmp_path / "remote.git"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    git(repo, "add", "README.md")
    git(repo, "commit", "-m", "seed")
    git(tmp_path, "init", "--bare", str(remote))
    git(repo, "remote", "add", "origin", str(remote))
    git(repo, "push", "-u", "origin", "main")
    return repo


def test_branch_uses_plugin_and_skill(tmp_path: Path) -> None:
    repo = initialized_repo(tmp_path)
    branch = create_skill_branch(repo, "sample-plugin", "sample-skill")
    assert branch == "skill/sample-plugin/sample-skill"
    assert git(repo, "branch", "--show-current") == branch


def test_branch_refuses_dirty_worktree(tmp_path: Path) -> None:
    repo = initialized_repo(tmp_path)
    (repo / "dirty.txt").write_text("dirty\n", encoding="utf-8")
    with pytest.raises(ForgeError, match="dirty worktree"):
        create_skill_branch(repo, "sample-plugin", "sample-skill")


def test_branch_detects_unseen_remote_collision(tmp_path: Path) -> None:
    repo = initialized_repo(tmp_path)
    git(repo, "push", "origin", "main:refs/heads/skill/sample-plugin/sample-skill")
    with pytest.raises(ForgeError, match="Remote branch already exists"):
        create_skill_branch(repo, "sample-plugin", "sample-skill")


@pytest.mark.parametrize("branch", ["feature/test", "skill/only-two", "skill/a/dotted.skill"])
def test_branch_name_contract(branch: str) -> None:
    with pytest.raises(ForgeError):
        validate_skill_branch(branch)


def test_pr_scope_rejects_unrelated_paths(tmp_path: Path) -> None:
    repo = initialized_repo(tmp_path)
    (repo / "pyproject.toml").write_text("[project]\nname='test'\n", encoding="utf-8")
    git(repo, "add", "pyproject.toml")
    git(repo, "commit", "-m", "complete bootstrap")
    git(repo, "push", "origin", "main")
    git(repo, "switch", "-c", "skill/sample-plugin/sample-skill")
    (repo / "unrelated.txt").write_text("outside scope\n", encoding="utf-8")
    git(repo, "add", "unrelated.txt")
    git(repo, "commit", "-m", "unrelated")
    with pytest.raises(ForgeError, match="outside branch scope"):
        validate_pr_scope(repo, "skill/sample-plugin/sample-skill", "main")
