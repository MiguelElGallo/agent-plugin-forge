from __future__ import annotations

import json
import os
import runpy
import subprocess
import sys
from pathlib import Path

import pytest

from .conftest import git

SCRIPT = (
    Path(__file__).parents[1]
    / "plugins"
    / "agent-plugin-forge"
    / "skills"
    / "package-agent-skill"
    / "scripts"
    / "bootstrap_forge.py"
)


def _remote(tmp_path: Path) -> tuple[Path, str, Path]:
    source = tmp_path / "source"
    source.mkdir()
    git(source, "init", "-b", "main")
    git(source, "config", "user.email", "bootstrap@example.com")
    git(source, "config", "user.name", "Bootstrap Test")
    (source / "README.md").write_text("forge\n", encoding="utf-8")
    git(source, "add", "README.md")
    git(source, "commit", "-m", "seed forge")
    revision = git(source, "rev-parse", "HEAD")

    remote = tmp_path / "forge.git"
    git(tmp_path, "init", "--bare", str(remote))
    git(source, "remote", "add", "origin", str(remote))
    git(source, "push", "-u", "origin", "main")
    return remote, revision, source


def test_bootstrap_treats_windows_absolute_origin_as_local() -> None:
    namespace = runpy.run_path(str(SCRIPT))

    assert namespace["_origin_host"](r"C:\work\agent-plugin-forge.git") == "local"


def test_bootstrap_disables_git_line_ending_conversion(monkeypatch: pytest.MonkeyPatch) -> None:
    namespace = runpy.run_path(str(SCRIPT))
    commands: list[list[str]] = []

    def capture(command: list[str], *, cwd: Path | None = None) -> str:
        commands.append(command)
        return ""

    monkeypatch.setitem(namespace["_git"].__globals__, "_run", capture)
    namespace["_git"](["status"], hooks_path=Path("hooks"))

    assert "core.autocrlf=false" in commands[0]


def test_bootstrap_creates_clean_current_main_checkout(tmp_path: Path) -> None:
    remote, revision, _ = _remote(tmp_path)
    destination = tmp_path / "review" / "agent-plugin-forge"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--origin",
            str(remote),
            "--destination",
            str(destination),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert payload == {
        "branch": "main",
        "checkout": str(destination),
        "host": "local",
        "origin": str(remote),
        "revision": revision,
    }
    assert git(destination, "branch", "--show-current") == "main"
    assert git(destination, "rev-parse", "HEAD") == revision
    assert git(destination, "status", "--porcelain") == ""


def test_bootstrap_refuses_an_existing_destination(tmp_path: Path) -> None:
    remote, _, _ = _remote(tmp_path)
    destination = tmp_path / "already-there"
    destination.mkdir()
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--origin",
            str(remote),
            "--destination",
            str(destination),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "Destination already exists" in result.stderr


def test_bootstrap_rejects_embedded_http_credentials(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--origin",
            "https://token@github.company.example/platform/forge.git",
            "--destination",
            str(tmp_path / "checkout"),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "must not embed credentials" in result.stderr
    assert not (tmp_path / "checkout").exists()


@pytest.mark.parametrize(
    "origin, message",
    [
        (
            "https://github.company.example/platform/forge.git?token=secret",
            "query or fragment",
        ),
        (
            "https://github.company.example/platform/forge.git#token=secret",
            "query or fragment",
        ),
        ("file://token@localhost/private/forge.git", "must not embed credentials"),
        ("git://github.company.example/platform/forge.git", "must use HTTPS"),
        ("ext::sh -c id", "remote-helper"),
        ("foo::payload", "remote-helper"),
    ],
)
def test_bootstrap_rejects_unsafe_origins_before_writing(
    tmp_path: Path, origin: str, message: str
) -> None:
    destination = tmp_path / "checkout"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--origin",
            origin,
            "--destination",
            str(destination),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert message in result.stderr
    assert not destination.exists()


def test_bootstrap_reports_file_origin_as_local(tmp_path: Path) -> None:
    remote, _, _ = _remote(tmp_path)
    destination = tmp_path / "file-origin-checkout"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--origin",
            remote.as_uri(),
            "--destination",
            str(destination),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(result.stdout)["host"] == "local"


def test_failed_bootstrap_does_not_publish_partial_destination(tmp_path: Path) -> None:
    remote = tmp_path / "missing-main.git"
    git(tmp_path, "init", "--bare", str(remote))
    destination = tmp_path / "failed-checkout"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--origin",
            str(remote),
            "--destination",
            str(destination),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert not destination.exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows junction behavior")
def test_bootstrap_refuses_reuse_of_windows_junction(tmp_path: Path) -> None:
    remote, _, _ = _remote(tmp_path)
    target = tmp_path / "junction-target"
    target.mkdir()
    destination = tmp_path / "junction"
    subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(destination), str(target)],
        check=True,
        capture_output=True,
        text=True,
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--origin",
            str(remote),
            "--destination",
            str(destination),
            "--reuse",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "not a regular directory" in result.stderr


def test_bootstrap_normalizes_relative_local_origin_for_reuse(tmp_path: Path) -> None:
    remote, _, _ = _remote(tmp_path)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    destination = tmp_path / "relative-origin-checkout"
    command = [
        sys.executable,
        str(SCRIPT),
        "--origin",
        "../forge.git",
        "--destination",
        str(destination),
    ]

    first = subprocess.run(
        command,
        cwd=workspace,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(first.stdout)
    assert payload["origin"] == str(remote.resolve())

    reused = subprocess.run(
        [*command, "--reuse"],
        cwd=workspace,
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(reused.stdout)["origin"] == str(remote.resolve())


def test_bootstrap_reuses_only_the_matching_clean_main_checkout(tmp_path: Path) -> None:
    remote, revision, source = _remote(tmp_path)
    destination = tmp_path / "persistent-forge"
    first = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--origin",
            str(remote),
            "--destination",
            str(destination),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(first.stdout)["revision"] == revision

    (source / "CHANGELOG.md").write_text("next\n", encoding="utf-8")
    git(source, "add", "CHANGELOG.md")
    git(source, "commit", "-m", "advance forge")
    advanced_revision = git(source, "rev-parse", "HEAD")
    git(source, "push", "origin", "main")

    reused = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--origin",
            str(remote),
            "--destination",
            str(destination),
            "--reuse",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(reused.stdout)["revision"] == advanced_revision

    (destination / "dirty.txt").write_text("dirty\n", encoding="utf-8")
    refused = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--origin",
            str(remote),
            "--destination",
            str(destination),
            "--reuse",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert refused.returncode == 1
    assert "Reusable checkout is dirty" in refused.stderr


@pytest.mark.skipif(os.name == "nt", reason="POSIX hook executable mode")
def test_bootstrap_reuse_does_not_execute_repository_hooks(tmp_path: Path) -> None:
    remote, _, source = _remote(tmp_path)
    destination = tmp_path / "hook-safe-checkout"
    subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--origin",
            str(remote),
            "--destination",
            str(destination),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    hook = destination / ".git" / "hooks" / "post-merge"
    hook.write_text("#!/bin/sh\ntouch .git/post-merge-ran\n", encoding="utf-8")
    hook.chmod(0o755)

    (source / "NEXT.md").write_text("next\n", encoding="utf-8")
    git(source, "add", "NEXT.md")
    git(source, "commit", "-m", "advance for hook test")
    git(source, "push", "origin", "main")
    subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--origin",
            str(remote),
            "--destination",
            str(destination),
            "--reuse",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert not (destination / ".git" / "post-merge-ran").exists()
