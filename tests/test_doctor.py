"""Exercise local readiness diagnostics and read-only failure handling."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from agent_plugin_forge import doctor

from .conftest import git


@pytest.fixture
def ready_repo(empty_forge: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    git(empty_forge, "config", "user.name", "Test")
    git(empty_forge, "config", "user.email", "test@example.com")
    git(empty_forge, "add", ".")
    git(empty_forge, "commit", "-m", "seed")
    git(empty_forge, "update-ref", "refs/remotes/origin/main", "HEAD")
    git_path = shutil.which("git")
    monkeypatch.setattr(doctor.shutil, "which", lambda name: git_path if name == "git" else None)
    return empty_forge


def check(repo: Path, name: str) -> dict[str, str]:
    return next(item for item in doctor.diagnose(repo)["checks"] if item["name"] == name)


def test_ready_report_is_read_only_and_optional_gh_does_not_block(
    ready_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_which = doctor.shutil.which
    monkeypatch.setattr(
        doctor.shutil, "which", lambda name: "/unused/uv" if name == "uv" else real_which(name)
    )
    index = ready_repo / ".git" / "index"
    original = (index.read_bytes(), index.stat().st_mtime_ns)
    result = doctor.diagnose(ready_repo)
    assert result["ready"]
    assert "Optional" in check(ready_repo, "gh")["detail"]
    assert "no fetch" in check(ready_repo, "alignment")["detail"]
    assert (index.read_bytes(), index.stat().st_mtime_ns) == original
    json.dumps(result)


@pytest.mark.parametrize("mode", ["dirty", "feature", "detached", "missing-cache", "behind"])
def test_checkout_not_ready(ready_repo: Path, mode: str) -> None:
    expected = "alignment"
    if mode == "dirty":
        (ready_repo / "new.txt").write_text("unfinished", encoding="utf-8")
        expected = "worktree"
    elif mode == "feature":
        git(ready_repo, "switch", "-c", "forge/task")
        expected = "branch"
    elif mode == "detached":
        git(ready_repo, "checkout", "--detach")
        expected = "branch"
    elif mode == "missing-cache":
        git(ready_repo, "update-ref", "-d", "refs/remotes/origin/main")
    else:
        old = git(ready_repo, "rev-parse", "HEAD")
        git(ready_repo, "commit", "--allow-empty", "-m", "next")
        git(ready_repo, "update-ref", "refs/remotes/origin/main", "HEAD")
        git(ready_repo, "reset", "--hard", old)
    assert check(ready_repo, expected)["status"] == "warning"
    assert not doctor.diagnose(ready_repo)["ready"]


@pytest.mark.parametrize("origin", [None, "https://user:secret@example.com/repo.git", "https://["])
def test_missing_and_unsafe_origins_are_redacted(ready_repo: Path, origin: str | None) -> None:
    if origin is None:
        git(ready_repo, "remote", "remove", "origin")
    else:
        git(ready_repo, "remote", "set-url", "origin", origin)
    assert check(ready_repo, "origin")["status"] == "error"
    assert "secret" not in json.dumps(doctor.diagnose(ready_repo))


def test_missing_tools_and_old_python(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(doctor.shutil, "which", lambda name: None)
    monkeypatch.setattr(doctor.sys, "version_info", (3, 10))
    result = doctor.diagnose(tmp_path)
    assert not result["ready"]
    for name in ("python", "git", "uv", "checkout"):
        assert check(tmp_path, name)["status"] == "error"


def test_non_repository(tmp_path: Path) -> None:
    assert check(tmp_path, "checkout")["status"] == "error"


def test_git_probes_are_bounded_local_and_suppress_errors(
    ready_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []
    real_run = subprocess.run

    def recording_run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        assert kwargs["timeout"] == 5
        assert kwargs["env"]["GIT_OPTIONAL_LOCKS"] == "0"
        assert args[1:3] == ["-c", "core.fsmonitor=false"]
        assert args[3] in {"rev-parse", "symbolic-ref", "status", "config", "ls-files"}
        if args[3] == "status":
            assert "--ignore-submodules=all" in args
            return subprocess.CompletedProcess(args, 1, "secret", "secret")
        return real_run(args, **kwargs)

    monkeypatch.setattr(doctor.subprocess, "run", recording_run)
    result = doctor.diagnose(ready_repo)
    assert calls
    assert check(ready_repo, "worktree")["status"] == "error"
    assert "secret" not in json.dumps(result)


@pytest.mark.parametrize("kind", ["clean", "process"])
def test_configured_filters_never_execute(ready_repo: Path, kind: str) -> None:
    marker = ready_repo / "filter-ran"
    (ready_repo / ".gitattributes").write_text("*.txt filter=probe\n", encoding="utf-8")
    source = ready_repo / "sample.txt"
    source.write_text("original\n", encoding="utf-8")
    git(ready_repo, "add", ".gitattributes", "sample.txt")
    git(ready_repo, "commit", "-m", "filter fixture")
    git(ready_repo, "config", f"filter.probe.{kind}", "echo ran > filter-ran")
    source.write_text("changed content\n", encoding="utf-8")
    result = doctor.diagnose(ready_repo)
    assert not marker.exists()
    assert not result["ready"]
    assert "skipped" in check(ready_repo, "worktree")["detail"]
    assert not marker.exists()


def test_submodule_worktrees_are_not_inspected(ready_repo: Path) -> None:
    child = ready_repo / "child"
    child.mkdir()
    git(child, "init", "-b", "main")
    git(child, "config", "user.name", "Test")
    git(child, "config", "user.email", "test@example.com")
    (child / ".gitattributes").write_text("*.txt filter=probe\n", encoding="utf-8")
    (child / "sample.txt").write_text("original\n", encoding="utf-8")
    git(child, "add", ".")
    git(child, "commit", "-m", "child")
    git(child, "config", "filter.probe.clean", "echo ran > filter-ran")
    (child / "sample.txt").write_text("changed content\n", encoding="utf-8")
    git(
        ready_repo,
        "update-index",
        "--add",
        "--cacheinfo",
        "160000",
        git(child, "rev-parse", "HEAD"),
        "child",
    )
    assert check(ready_repo, "submodules")["status"] == "warning"
    assert not doctor.diagnose(ready_repo)["ready"]
    assert not (child / "filter-ran").exists()


@pytest.mark.parametrize("failed_command", ["config", "ls-files"])
def test_unavailable_filter_or_submodule_probe_blocks_readiness(
    ready_repo: Path, monkeypatch: pytest.MonkeyPatch, failed_command: str
) -> None:
    real_git = doctor._git

    def probe(repo: Path, executable: str, *args: str) -> str | None:
        if args[0] == failed_command:
            return None
        if failed_command == "config":
            assert args[0] != "status"
        return real_git(repo, executable, *args)

    monkeypatch.setattr(doctor, "_git", probe)
    name = "worktree" if failed_command == "config" else "submodules"
    assert check(ready_repo, name)["status"] == "warning"
    assert not doctor.diagnose(ready_repo)["ready"]


@pytest.mark.parametrize("failure", [OSError("secret"), subprocess.TimeoutExpired("git", 5)])
def test_git_launch_failure_is_safe(
    ready_repo: Path, monkeypatch: pytest.MonkeyPatch, failure: Exception
) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise failure

    monkeypatch.setattr(doctor.subprocess, "run", fail)
    result = doctor.diagnose(ready_repo)
    assert not result["ready"]
    assert "secret" not in json.dumps(result)
