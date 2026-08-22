from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

from .conftest import git


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


def initialize_remote(repo: Path, tmp_path: Path) -> None:
    remote = tmp_path / "tutorial-remote.git"
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.email", "tutorial@example.com")
    git(repo, "config", "user.name", "Tutorial")
    (repo / "pyproject.toml").write_text("[project]\nname='tutorial'\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "seed tutorial checkout")
    git(tmp_path, "init", "--bare", str(remote))
    git(repo, "remote", "add", "origin", str(remote))
    git(repo, "push", "-u", "origin", "main")


def test_first_skill_tutorial_runs_through_the_real_cli(
    empty_forge: Path,
    skill_source: Path,
    tmp_path: Path,
) -> None:
    initialize_remote(empty_forge, tmp_path)
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
        empty_forge,
        "branch",
        "--plugin",
        "sample-skill",
        "--skill",
        "sample-skill",
    )
    assert "skill/sample-skill/sample-skill" in branch.stdout
    plan = forge(empty_forge, *common_args)
    match = re.search(r"review plan sha256 ([0-9a-f]{64})", plan.stdout)
    assert match is not None
    forge(
        empty_forge,
        *common_args,
        "--expected-sha256",
        match.group(1),
        "--apply",
    )
    forge(empty_forge, "generate")
    checked = forge(empty_forge, "check")
    assert "checks passed" in checked.stdout
    assert (
        empty_forge / "plugins" / "sample-skill" / "skills" / "sample-skill" / "SKILL.md"
    ).is_file()
