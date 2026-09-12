"""Test safe creation and reuse of Agent Plugin Forge checkouts."""

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


@pytest.fixture(autouse=True)
def isolated_preferences(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.delenv("AGENT_PLUGIN_FORGE_ORIGIN", raising=False)


def _helper(*arguments: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *arguments],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
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
        "origin_source": "argument",
        "saved_origin": None,
        "settings_path": str(tmp_path / "config" / "agent-plugin-forge" / "settings.json"),
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


def test_bootstrap_reuse_requires_an_explicit_destination(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--origin", str(tmp_path / "missing.git"), "--reuse"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "--reuse requires --destination" in result.stderr
    assert not list(tmp_path.iterdir())


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
        (
            "git@github.company.example:platform/forge.git?token=secret",
            "query or fragment",
        ),
        (
            "git@github.company.example:platform/forge.git#token=secret",
            "query or fragment",
        ),
        (
            "git?token@github.company.example:platform/forge.git",
            "query or fragment",
        ),
        (
            "git@github.company.example#token:platform/forge.git",
            "query or fragment",
        ),
        ("git@github.company.example:platform/forge.git\nsecret", "control characters"),
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


def test_first_use_requires_a_destination_before_creating_anything(tmp_path: Path) -> None:
    result = _helper("--destination", str(tmp_path / "checkout"))

    assert result.returncode == 1
    assert "Ask the user where to publish" in result.stderr
    assert not list(tmp_path.iterdir())


def test_show_unset_destination_is_read_only(tmp_path: Path) -> None:
    result = _helper("--show-origin")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["origin"] is None
    assert payload["origin_source"] == "unset"
    assert payload["saved_origin"] is None
    assert not list(tmp_path.iterdir())


def test_saved_destination_is_reused_by_a_new_process_in_another_project(tmp_path: Path) -> None:
    remote, revision, _ = _remote(tmp_path)
    first_project = tmp_path / "project-one"
    second_project = tmp_path / "project-two"
    first_project.mkdir()
    second_project.mkdir()

    remembered = _helper("--origin", "../forge.git", "--remember-origin", cwd=first_project)
    assert remembered.returncode == 0, remembered.stderr
    settings = Path(json.loads(remembered.stdout)["settings_path"])
    assert json.loads(settings.read_text()) == {"version": 1, "origin": str(remote.resolve())}
    assert not list(first_project.iterdir())

    destination = tmp_path / "review"
    reused = _helper("--destination", str(destination), cwd=second_project)
    assert reused.returncode == 0, reused.stderr
    payload = json.loads(reused.stdout)
    assert payload["origin"] == str(remote.resolve())
    assert payload["saved_origin"] == str(remote.resolve())
    assert payload["origin_source"] == "saved"
    assert payload["revision"] == revision
    assert git(destination, "remote", "get-url", "origin") == str(remote.resolve())


def test_explicit_and_environment_overrides_do_not_replace_saved_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    saved = "https://github.company.example/team/default.git"
    environment = "https://github.company.example/team/environment.git"
    explicit = "https://github.company.example/team/one-off.git"
    remembered = _helper("--origin", saved, "--remember-origin")
    assert remembered.returncode == 0, remembered.stderr
    settings = Path(json.loads(remembered.stdout)["settings_path"])
    before = settings.read_bytes()

    monkeypatch.setenv("AGENT_PLUGIN_FORGE_ORIGIN", environment)
    from_environment = json.loads(_helper("--show-origin").stdout)
    assert from_environment["origin"] == environment
    assert from_environment["origin_source"] == "environment"
    from_argument = json.loads(_helper("--show-origin", "--origin", explicit).stdout)
    assert from_argument["origin"] == explicit
    assert from_argument["origin_source"] == "argument"
    assert from_argument["saved_origin"] == saved
    assert settings.read_bytes() == before
    assert list(tmp_path.iterdir()) == [tmp_path / "config"]


def test_replacing_a_saved_destination_requires_an_explicit_replacement() -> None:
    first = "https://github.company.example/team/first.git"
    second = "https://github.company.example/team/second.git"
    remembered = _helper("--origin", first, "--remember-origin")
    assert remembered.returncode == 0, remembered.stderr
    settings = Path(json.loads(remembered.stdout)["settings_path"])
    before = settings.read_bytes()

    refused = _helper("--origin", second, "--remember-origin")
    assert refused.returncode == 1
    assert "Confirm the replacement with the user" in refused.stderr
    assert settings.read_bytes() == before

    replaced = _helper("--origin", second, "--remember-origin", "--replace-saved-origin")
    assert replaced.returncode == 0, replaced.stderr
    assert json.loads(_helper("--show-origin").stdout)["origin"] == second


def test_remember_requires_an_explicit_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_PLUGIN_FORGE_ORIGIN", "https://github.company.example/team/forge.git")
    result = _helper("--remember-origin")
    assert result.returncode == 1
    assert "requires an explicit, user-confirmed --origin" in result.stderr


@pytest.mark.parametrize("value", ["", "   "])
def test_empty_override_cannot_fall_back_to_saved_origin(
    value: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert (
        _helper(
            "--origin", "https://github.company.example/team/forge.git", "--remember-origin"
        ).returncode
        == 0
    )
    monkeypatch.setenv("AGENT_PLUGIN_FORGE_ORIGIN", value)
    result = _helper("--show-origin")
    assert result.returncode == 1
    assert "Forge origin is empty" in result.stderr


@pytest.mark.parametrize(
    "content",
    [
        "not JSON",
        "[]",
        "{}",
        '{"version": true, "origin": "https://github.company.example/team/forge.git"}',
        '{"version": 2, "origin": "https://github.company.example/team/forge.git"}',
        '{"version": 1, "origin": "https://secret@github.company.example/team/forge.git"}',
        '{"version": 1, "origin": "../relative.git"}',
    ],
)
def test_invalid_settings_stop_without_cloning_or_overwriting(tmp_path: Path, content: str) -> None:
    settings = tmp_path / "invalid.json"
    settings.write_text(content, encoding="utf-8")
    result = _helper("--config", str(settings), "--destination", str(tmp_path / "checkout"))

    assert result.returncode == 1
    assert "Invalid Forge settings" in result.stderr
    assert "secret" not in result.stderr
    assert settings.read_text(encoding="utf-8") == content
    assert not (tmp_path / "checkout").exists()


def test_unsafe_origin_cannot_be_remembered(tmp_path: Path) -> None:
    result = _helper(
        "--origin", "https://secret@github.company.example/team/forge.git", "--remember-origin"
    )
    assert result.returncode == 1
    assert "must not embed credentials" in result.stderr
    assert not list(tmp_path.iterdir())


def test_settings_directory_is_rejected_before_bootstrap(tmp_path: Path) -> None:
    settings = tmp_path / "not-a-file"
    settings.mkdir()
    result = _helper("--config", str(settings), "--destination", str(tmp_path / "checkout"))
    assert result.returncode == 1
    assert "settings must be a regular file" in result.stderr
    assert not (tmp_path / "checkout").exists()


@pytest.mark.skipif(os.name == "nt", reason="POSIX symbolic link support")
def test_settings_symlink_is_rejected_without_replacing_its_target(tmp_path: Path) -> None:
    target = tmp_path / "target.json"
    content = '{"version": 1, "origin": "https://github.company.example/team/forge.git"}'
    target.write_text(content, encoding="utf-8")
    settings = tmp_path / "linked.json"
    settings.symlink_to(target)
    result = _helper("--config", str(settings), "--show-origin")
    assert result.returncode == 1
    assert "settings must be a regular file" in result.stderr
    assert target.read_text(encoding="utf-8") == content


@pytest.mark.parametrize(
    "arguments",
    [
        ["--show-origin", "--destination", "unused"],
        ["--show-origin", "--reuse"],
        ["--remember-origin", "--destination", "unused"],
        ["--remember-origin", "--reuse"],
        ["--replace-saved-origin"],
    ],
)
def test_settings_actions_cannot_accidentally_clone(tmp_path: Path, arguments: list[str]) -> None:
    result = _helper("--origin", "https://github.company.example/team/forge.git", *arguments)
    assert result.returncode == 1
    assert not list(tmp_path.iterdir())


def test_failed_settings_replacement_preserves_previous_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    namespace = runpy.run_path(str(SCRIPT))
    settings = tmp_path / "settings.json"
    namespace["_remember_origin"](
        settings, "https://github.company.example/team/first.git", replace=False
    )
    before = settings.read_bytes()

    def fail_replace(source: Path, destination: Path) -> None:
        raise OSError("simulated write failure")

    monkeypatch.setattr(os, "replace", fail_replace)
    with pytest.raises(OSError, match="simulated write failure"):
        namespace["_remember_origin"](
            settings, "https://github.company.example/team/second.git", replace=True
        )
    assert settings.read_bytes() == before
    assert list(tmp_path.iterdir()) == [settings]


@pytest.mark.parametrize(
    "platform, relative", [("darwin", "Library/Application Support"), ("linux", ".config")]
)
def test_preferences_use_the_platform_user_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, platform: str, relative: str
) -> None:
    namespace = runpy.run_path(str(SCRIPT))
    monkeypatch.delenv("XDG_CONFIG_HOME")
    monkeypatch.setattr(sys, "platform", platform)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert namespace["_settings_path"]() == (
        tmp_path / relative / "agent-plugin-forge" / "settings.json"
    )


def test_preferences_use_windows_appdata(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    namespace = runpy.run_path(str(SCRIPT))
    monkeypatch.delenv("XDG_CONFIG_HOME")
    monkeypatch.setenv("APPDATA", str(tmp_path / "roaming"))
    monkeypatch.setattr(sys, "platform", "win32")
    assert namespace["_settings_path"]() == (
        tmp_path / "roaming" / "agent-plugin-forge" / "settings.json"
    )
