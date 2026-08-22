"""Test branch creation, naming contracts, and pull-request scope checks."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_plugin_forge.common import ForgeError
from agent_plugin_forge.gitflow import (
    create_maintenance_branch,
    create_plugin_branch,
    create_skill_branch,
    validate_maintenance_branch,
    validate_plugin_branch,
    validate_pr_scope,
    validate_skill_branch,
)

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
    git(remote, "symbolic-ref", "HEAD", "refs/heads/main")
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


def test_maintenance_branch_uses_forge_prefix(tmp_path: Path) -> None:
    repo = initialized_repo(tmp_path)
    branch = create_maintenance_branch(repo, "validator-hardening")
    assert branch == "forge/validator-hardening"
    assert git(repo, "branch", "--show-current") == branch


def test_plugin_branch_scopes_plugin_wide_changes(tmp_path: Path) -> None:
    repo = initialized_repo(tmp_path)
    branch = create_plugin_branch(repo, "sample-plugin", "add-mcp")
    assert branch == "plugin/sample-plugin/add-mcp"
    assert git(repo, "branch", "--show-current") == branch


def test_branch_detects_unseen_remote_collision(tmp_path: Path) -> None:
    repo = initialized_repo(tmp_path)
    git(repo, "push", "origin", "main:refs/heads/skill/sample-plugin/sample-skill")
    with pytest.raises(ForgeError, match="Remote branch already exists"):
        create_skill_branch(repo, "sample-plugin", "sample-skill")


@pytest.mark.parametrize("branch", ["feature/test", "skill/only-two", "skill/a/dotted.skill"])
def test_branch_name_contract(branch: str) -> None:
    with pytest.raises(ForgeError):
        validate_skill_branch(branch)


@pytest.mark.parametrize("branch", ["feature/test", "forge/two/levels", "forge/dotted.topic"])
def test_maintenance_branch_name_contract(branch: str) -> None:
    with pytest.raises(ForgeError):
        validate_maintenance_branch(branch)


@pytest.mark.parametrize("branch", ["plugin/only-two", "plugin/valid-plugin/dotted.topic"])
def test_plugin_branch_name_contract(branch: str) -> None:
    with pytest.raises(ForgeError):
        validate_plugin_branch(branch)


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


def test_maintenance_pr_scope_allows_tooling_changes(tmp_path: Path) -> None:
    repo = initialized_repo(tmp_path)
    (repo / "pyproject.toml").write_text("[project]\nname='test'\n", encoding="utf-8")
    git(repo, "add", "pyproject.toml")
    git(repo, "commit", "-m", "complete bootstrap")
    git(repo, "push", "origin", "main")
    git(repo, "switch", "-c", "forge/validator-hardening")
    (repo / "src").mkdir()
    (repo / "src" / "validator.py").write_text("# changed\n", encoding="utf-8")
    git(repo, "add", "src/validator.py")
    git(repo, "commit", "-m", "harden validator")
    assert validate_pr_scope(repo, "forge/validator-hardening", "main") == ["src/validator.py"]


def test_pr_scope_requires_main_base(tmp_path: Path) -> None:
    repo = initialized_repo(tmp_path)
    with pytest.raises(ForgeError, match="target main"):
        validate_pr_scope(repo, "forge/validator-hardening", "develop")


def test_plugin_pr_scope_rejects_other_plugin(tmp_path: Path) -> None:
    repo = initialized_repo(tmp_path)
    (repo / "pyproject.toml").write_text("[project]\nname='test'\n", encoding="utf-8")
    git(repo, "add", "pyproject.toml")
    git(repo, "commit", "-m", "complete bootstrap")
    git(repo, "push", "origin", "main")
    git(repo, "switch", "-c", "plugin/sample-plugin/add-mcp")
    path = repo / "plugins" / "other-plugin"
    path.mkdir(parents=True)
    (path / "mcp.json").write_text("{}\n", encoding="utf-8")
    git(repo, "add", "plugins/other-plugin/mcp.json")
    git(repo, "commit", "-m", "wrong plugin")
    with pytest.raises(ForgeError, match="outside plugin branch scope"):
        validate_pr_scope(repo, "plugin/sample-plugin/add-mcp", "main")


def test_branch_refuses_unaligned_local_main(tmp_path: Path) -> None:
    repo = initialized_repo(tmp_path)
    clone = tmp_path / "other"
    git(tmp_path, "clone", str(tmp_path / "remote.git"), str(clone))
    git(clone, "config", "user.email", "test@example.com")
    git(clone, "config", "user.name", "Test")
    (clone / "remote-change.txt").write_text("remote\n", encoding="utf-8")
    git(clone, "add", "remote-change.txt")
    git(clone, "commit", "-m", "remote change")
    git(clone, "push", "origin", "main")
    with pytest.raises(ForgeError, match="not aligned"):
        create_skill_branch(repo, "sample-plugin", "sample-skill")
