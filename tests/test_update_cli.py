"""Exercise the public reviewed-update command and replay its printed approval command."""

from __future__ import annotations

import json
import shlex
from pathlib import Path

from typer.testing import CliRunner

from agent_plugin_forge.cli import app
from agent_plugin_forge.common import load_json
from agent_plugin_forge.filesystem import tree_snapshot
from agent_plugin_forge.generator import generate
from agent_plugin_forge.validator import assert_valid_repository

from .test_cli import plain_output
from .test_importer import apply_reviewed

runner = CliRunner()


def update_arguments(source: Path, license_file: Path) -> list[str]:
    return [
        "update",
        "--source",
        str(source),
        "--plugin",
        "sample-skill",
        "--version",
        "0.2.0",
        "--license",
        "MIT",
        "--license-file",
        str(license_file),
        "--origin",
        "https://example.com/source",
        "--revision",
        "b" * 40,
        "--imported-at",
        "2026-09-21",
        "--source-subpath",
        "skills/sample-skill",
    ]


def test_update_json_review_apply_and_validate(empty_forge: Path, skill_source: Path, monkeypatch):
    apply_reviewed(empty_forge, skill_source)
    (skill_source / "reference.txt").unlink()
    (skill_source / "new.txt").write_text("New reviewed material.\n")
    license_file = skill_source.parent / "LICENSE"
    args = update_arguments(skill_source, license_file)
    monkeypatch.chdir(empty_forge)
    before = tree_snapshot(empty_forge / "plugins")
    catalog_before = (empty_forge / "catalog/plugins.json").read_bytes()
    result = runner.invoke(app, [*args, "--json"])
    assert result.exit_code == 0, result.output
    plan = json.loads(result.output)
    assert plan["operation"] == plan["review_payload"]["operation"] == "update"
    assert plan["changes"]["added"] == ["new.txt"]
    assert plan["changes"]["removed"] == ["reference.txt"]
    assert plan["update_metadata"]["previousVersion"] == "0.1.0"
    assert tree_snapshot(empty_forge / "plugins") == before
    assert (empty_forge / "catalog/plugins.json").read_bytes() == catalog_before
    applied = runner.invoke(
        app, [*args, "--apply", "--expected-sha256", plan["plan_sha256"], "--json"]
    )
    assert applied.exit_code == 0, applied.output
    assert json.loads(applied.output) == plan
    generate(empty_forge)
    assert_valid_repository(empty_forge)


def test_update_printed_command_preserves_quoted_paths_and_review_date(
    empty_forge: Path, skill_source: Path, tmp_path: Path, monkeypatch
):
    apply_reviewed(empty_forge, skill_source)
    parent = tmp_path / "reviewer's source"
    parent.mkdir()
    source = parent / "sample-skill"
    skill_source.rename(source)
    (source / "reference.txt").write_text("Reviewed replacement.\n")
    license_file = parent / "author's LICENSE"
    license_file.write_text("Reviewed license evidence.\n")
    monkeypatch.chdir(empty_forge)
    result = runner.invoke(app, update_arguments(source, license_file))
    assert result.exit_code == 0, result.output
    assert "Skill modified (1):" in result.output
    assert "Plugin version: 0.1.0 -> 0.2.0" in result.output
    assert "Rewrite provenance: provenance/sample-skill.json" in result.output
    assert "License evidence (add): licenses/sample-skill/LICENSE" in result.output
    command = shlex.split(result.output.splitlines()[-1])
    assert command[:4] == ["uv", "run", "forge", "update"]
    assert "--imported-at=2026-09-21" in command
    applied = runner.invoke(app, command[3:])
    assert applied.exit_code == 0, applied.output
    record = load_json(empty_forge / "plugins/sample-skill/provenance/sample-skill.json")
    assert record["importedAt"] == "2026-09-21"
    assert (
        empty_forge / "plugins/sample-skill/skills/sample-skill/reference.txt"
    ).read_bytes() == (source / "reference.txt").read_bytes()


def test_update_requires_explicit_destination_and_version():
    result = runner.invoke(app, ["update", "--help"], color=True)
    assert result.exit_code == 0
    output = plain_output(result.output)
    assert "--plugin" in output and "--version" in output
    result = runner.invoke(app, ["update", "--source", "/unused"])
    assert result.exit_code == 2


def test_update_does_not_expose_shared_metadata_options():
    result = runner.invoke(app, ["update", "--author", "Someone"])
    assert result.exit_code == 2
    assert "No such option" in result.output
