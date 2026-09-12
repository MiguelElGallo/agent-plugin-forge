"""Test installed version reporting and repository release metadata consistency."""

from __future__ import annotations

import json
import tomllib
from importlib.metadata import version
from pathlib import Path

from typer.testing import CliRunner

from agent_plugin_forge import __version__
from agent_plugin_forge.cli import app


def test_release_versions_agree() -> None:
    repo = Path(__file__).parents[1]
    project = tomllib.loads((repo / "pyproject.toml").read_text(encoding="utf-8"))
    manifest = json.loads(
        (repo / "plugins/agent-plugin-forge/plugin.json").read_text(encoding="utf-8")
    )
    catalog = json.loads((repo / "catalog/plugins.json").read_text(encoding="utf-8"))
    lock = tomllib.loads((repo / "uv.lock").read_text(encoding="utf-8"))
    locked_project = next(p for p in lock["package"] if p["name"] == "agent-plugin-forge")
    assert (
        __version__
        == version("agent-plugin-forge")
        == project["project"]["version"]
        == manifest["version"]
        == catalog["marketplace"]["version"]
        == locked_project["version"]
    )


def test_cli_version_works_outside_a_forge(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(app, ["--version"])
    assert result.exit_code == 0, result.output
    assert result.output == f"agent-plugin-forge {__version__}\n"


def test_cli_without_arguments_still_shows_help() -> None:
    result = CliRunner().invoke(app, [])
    assert result.exit_code == 2
    assert "Usage:" in result.output
    assert "Commands" in result.output
