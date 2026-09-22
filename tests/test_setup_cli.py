"""Exercise structured diagnostics before a Forge checkout is available."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from agent_plugin_forge.cli import app

from .conftest import git


@pytest.mark.parametrize("ordinary_git_repo", [False, True])
def test_doctor_json_outside_forge_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ordinary_git_repo: bool
) -> None:
    if ordinary_git_repo:
        git(tmp_path, "init", "-b", "main")
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(app, ["doctor", "--json"])
    assert result.exit_code == 2
    assert not result.stderr
    report = json.loads(result.stdout)
    assert report["ready"] is False
    assert {item["name"] for item in report["checks"]} == {"python", "git", "uv", "gh", "checkout"}
    assert (
        next(item for item in report["checks"] if item["name"] == "checkout")["status"] == "error"
    )
