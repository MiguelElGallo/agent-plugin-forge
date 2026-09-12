"""Test the first-skill tutorial against the real forge command-line flow."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from .conftest import git

BOOTSTRAP = (
    Path(__file__).parents[1]
    / "plugins"
    / "agent-plugin-forge"
    / "skills"
    / "package-agent-skill"
    / "scripts"
    / "bootstrap_forge.py"
)


def forge(repo: Path, *args: str, expect: int = 0) -> subprocess.CompletedProcess[str]:
    source_root = Path(__file__).parents[1] / "src"
    environment = {**os.environ, "PYTHONPATH": str(source_root)}
    result = subprocess.run(
        [sys.executable, "-m", "agent_plugin_forge.cli", *args],
        cwd=repo,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == expect, result.stderr
    return result


def initialize_remote(repo: Path, tmp_path: Path) -> Path:
    remote = tmp_path / "tutorial-remote.git"
    git(repo, "config", "user.email", "tutorial@example.com")
    git(repo, "config", "user.name", "Tutorial")
    (repo / "pyproject.toml").write_text("[project]\nname='tutorial'\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "seed tutorial checkout")
    git(tmp_path, "init", "--bare", str(remote))
    git(repo, "remote", "set-url", "origin", str(remote))
    git(repo, "push", "-u", "origin", "main")
    return remote


def test_real_cli_translates_forge_errors(empty_forge: Path) -> None:
    result = forge(empty_forge, "branch-name", "--branch", "invalid", expect=2)

    assert result.stdout == ""
    assert result.stderr == "forge: Skill branches must use skill/<plugin>/<skill>\n"


@pytest.mark.parametrize("remember_destination", [False, True])
def test_first_skill_tutorial_runs_through_the_real_cli(
    empty_forge: Path,
    skill_source: Path,
    tmp_path: Path,
    remember_destination: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AGENT_PLUGIN_FORGE_ORIGIN", raising=False)
    remote = initialize_remote(empty_forge, tmp_path)
    review_checkout = tmp_path / "review-checkout"
    helper = [sys.executable, str(BOOTSTRAP), "--config", str(tmp_path / "preferences.json")]
    origin_args = ["--origin", str(remote)]
    if remember_destination:
        subprocess.run(
            [*helper, *origin_args, "--remember-origin"],
            cwd=skill_source,
            check=True,
            capture_output=True,
            text=True,
        )
        origin_args = []
    bootstrapped = subprocess.run(
        [*helper, *origin_args, "--destination", str(review_checkout)],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(bootstrapped.stdout)["origin_source"] == (
        "saved" if remember_destination else "argument"
    )
    license_file = skill_source.parent / "LICENSE"
    license_file.write_text("Test license\n", encoding="utf-8")
    revision = "0123456789abcdef0123456789abcdef01234567"
    common_args = (
        "import",
        "--source",
        str(skill_source),
        "--plugin",
        "sample-skill",
        "--category",
        "Developer Tools",
        "--version",
        "0.1.0",
        "--description",
        "A sample plugin",
        "--author",
        "Tutorial Author",
        "--license",
        "MIT",
        "--license-file",
        str(license_file),
        "--origin",
        "https://example.com/tutorial",
        "--revision",
        revision,
        "--source-subpath",
        "examples/sample-skill",
        "--imported-at",
        "2026-08-21",
    )

    branch = forge(
        review_checkout,
        "branch",
        "--plugin",
        "sample-skill",
        "--skill",
        "sample-skill",
    )
    assert "skill/sample-skill/sample-skill" in branch.stdout
    plan = forge(review_checkout, *common_args)
    assert f"repository {remote.as_uri()}" in plan.stdout
    match = re.search(r"review plan sha256 ([0-9a-f]{64})", plan.stdout)
    assert match is not None
    forge(
        review_checkout,
        *common_args,
        "--expected-sha256",
        match.group(1),
        "--apply",
    )
    forge(review_checkout, "generate")
    checked = forge(review_checkout, "check")
    assert "checks passed" in checked.stdout
    assert (
        review_checkout / "plugins" / "sample-skill" / "skills" / "sample-skill" / "SKILL.md"
    ).is_file()
    manifest = json.loads(
        (review_checkout / "plugins" / "sample-skill" / "plugin.json").read_text(encoding="utf-8")
    )
    assert manifest["repository"] == remote.as_uri()
