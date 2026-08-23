"""Test command-line parsing, planning, generation, and validation."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from agent_plugin_forge.cli import app, run
from agent_plugin_forge.common import ForgeError

from .test_importer import apply_reviewed

runner = CliRunner()


def test_cli_help_exposes_typed_typer_commands() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "Package Agent Skills and MCP servers safely" in result.output
    assert "--install-completion" in result.output
    for command in (
        "branch",
        "maintenance-branch",
        "plugin-branch",
        "branch-name",
        "pr-scope",
        "import",
        "generate",
        "check",
    ):
        assert command in result.output


def test_cli_reports_missing_required_typed_option() -> None:
    result = runner.invoke(app, ["branch-name"])

    assert result.exit_code == 2
    assert "Missing option '--branch'" in result.output


def test_cli_plans_without_writing(
    empty_forge: Path, skill_source: Path, monkeypatch, capsys
) -> None:
    license_file = skill_source.parent / "LICENSE"
    license_file.write_text("Test license\n", encoding="utf-8")
    monkeypatch.chdir(empty_forge)
    result = run(
        [
            "import",
            "--source",
            str(skill_source),
            "--category",
            "Developer Tools",
            "--version",
            "0.1.0",
            "--description",
            "A sample plugin",
            "--author",
            "Test Author",
            "--license",
            "MIT",
            "--license-file",
            str(license_file),
            "--origin",
            "https://example.com/source",
            "--revision",
            "0123456789abcdef0123456789abcdef01234567",
        ]
    )
    assert result == 0
    assert "No files changed" in capsys.readouterr().out
    assert not (empty_forge / "plugins" / "sample-skill").exists()


def test_cli_infers_plugin_name_from_lone_skill_file(
    empty_forge: Path, skill_source: Path, monkeypatch, capsys
) -> None:
    license_file = skill_source.parent / "LICENSE"
    license_file.write_text("Test license\n", encoding="utf-8")
    monkeypatch.chdir(empty_forge)
    result = run(
        [
            "import",
            "--source",
            str(skill_source / "SKILL.md"),
            "--category",
            "Developer Tools",
            "--version",
            "0.1.0",
            "--description",
            "A sample plugin",
            "--author",
            "Test Author",
            "--license",
            "MIT",
            "--license-file",
            str(license_file),
            "--origin",
            "https://example.com/source",
            "--revision",
            "0123456789abcdef0123456789abcdef01234567",
        ]
    )
    assert result == 0
    assert "sample-skill -> plugins/sample-skill/skills/sample-skill" in capsys.readouterr().out


@pytest.mark.skipif(os.name == "nt", reason="Windows symlink creation requires extra privileges")
@pytest.mark.parametrize("linked_input", ["source", "license"])
def test_cli_rejects_linked_intake_roots(
    empty_forge: Path, skill_source: Path, tmp_path: Path, monkeypatch, linked_input: str
) -> None:
    license_file = tmp_path / "LICENSE"
    license_file.write_text("Test license\n", encoding="utf-8")
    source = skill_source
    if linked_input == "source":
        source = tmp_path / "linked-skill"
        source.symlink_to(skill_source, target_is_directory=True)
    else:
        linked_license = tmp_path / "LINKED-LICENSE"
        linked_license.symlink_to(license_file)
        license_file = linked_license
    monkeypatch.chdir(empty_forge)
    with pytest.raises(ForgeError, match="link|symlink"):
        run(
            [
                "import",
                "--source",
                str(source),
                "--plugin",
                "sample-skill",
                "--category",
                "Developer Tools",
                "--version",
                "0.1.0",
                "--description",
                "A sample plugin",
                "--author",
                "Test Author",
                "--license",
                "MIT",
                "--license-file",
                str(license_file),
                "--origin",
                "https://example.com/source",
                "--revision",
                "0123456789abcdef0123456789abcdef01234567",
            ]
        )


def test_cli_validates_branch_name(empty_forge: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(empty_forge)
    assert run(["branch-name", "--branch", "skill/sample-plugin/sample-skill"]) == 0
    assert "Valid skill branch" in capsys.readouterr().out


def test_cli_validates_plugin_and_maintenance_branch_names(
    empty_forge: Path, monkeypatch, capsys
) -> None:
    monkeypatch.chdir(empty_forge)
    assert run(["branch-name", "--branch", "plugin/sample-plugin/add-mcp"]) == 0
    assert "Valid plugin branch" in capsys.readouterr().out
    assert run(["branch-name", "--branch", "forge/validator-hardening"]) == 0
    assert "Valid maintenance branch" in capsys.readouterr().out


def test_cli_generates_checks_drift_and_validates_repository(
    empty_forge: Path, skill_source: Path, monkeypatch, capsys
) -> None:
    apply_reviewed(empty_forge, skill_source)
    monkeypatch.chdir(empty_forge)
    assert run(["generate"]) == 0
    assert run(["generate", "--check"]) == 0
    assert run(["check"]) == 0
    assert "checks passed" in capsys.readouterr().out
