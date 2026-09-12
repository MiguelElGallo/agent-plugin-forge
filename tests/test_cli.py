"""Test command-line parsing, planning, generation, and validation."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
from pathlib import Path

import pytest
from typer.testing import CliRunner

import agent_plugin_forge.cli as cli_module
from agent_plugin_forge.cli import app, run
from agent_plugin_forge.common import ForgeError, json_bytes

from .conftest import git
from .test_importer import apply_reviewed, request

runner = CliRunner()
ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def test_cli_json_plan_can_be_reviewed_and_applied(
    empty_forge: Path, skill_source: Path, monkeypatch
) -> None:
    license_file = skill_source.parent / "LICENSE"
    license_file.write_text("Test license\n", encoding="utf-8")
    monkeypatch.chdir(empty_forge)
    args = [
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
        "--imported-at",
        "2026-09-07",
        "--json",
    ]
    before = {path: path.read_bytes() for path in empty_forge.rglob("*") if path.is_file()}
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    plan = json.loads(result.output)
    payload = plan["review_payload"]
    assert hashlib.sha256(json_bytes(payload)).hexdigest() == plan["plan_sha256"]
    assert payload["description"] == "A sample plugin"
    assert payload["license"] == "MIT"
    assert payload["importedAt"] == "2026-09-07"
    assert payload["targetState"] is None
    assert (
        plan["files"]["SKILL.md"]
        == hashlib.sha256((skill_source / "SKILL.md").read_bytes()).hexdigest()
    )
    assert set(plan["file_modes"]) == set(plan["files"])
    assert {path: path.read_bytes() for path in empty_forge.rglob("*") if path.is_file()} == before
    git(empty_forge, "checkout", "-B", "skill/sample-skill/sample-skill")
    rejected = runner.invoke(app, [*args, "--apply", "--expected-sha256", "0" * 64])
    assert rejected.exit_code != 0
    assert not (empty_forge / "plugins" / "sample-skill").exists()
    applied = runner.invoke(app, [*args, "--apply", "--expected-sha256", plan["plan_sha256"]])
    assert applied.exit_code == 0, applied.output
    assert json.loads(applied.output) == plan
    copied = empty_forge / "plugins" / "sample-skill" / "skills" / "sample-skill" / "SKILL.md"
    assert copied.read_bytes() == (skill_source / "SKILL.md").read_bytes()


def plain_output(output: str) -> str:
    return ANSI_ESCAPE.sub("", output)


def test_cli_help_exposes_typed_typer_commands() -> None:
    result = runner.invoke(app, ["--help"])
    output = plain_output(result.output)

    assert result.exit_code == 0
    assert "Package Agent Skills and MCP servers safely" in output
    assert "--install-completion" in output
    for command in (
        "branch",
        "maintenance-branch",
        "plugin-branch",
        "branch-name",
        "pr-scope",
        "import",
        "generate",
        "check",
        "doctor",
    ):
        assert command in output


def test_cli_without_command_preserves_error_exit_code() -> None:
    result = runner.invoke(app)

    assert result.exit_code == 2
    assert "Usage: forge [OPTIONS] COMMAND [ARGS]..." in plain_output(result.output)


def test_cli_reports_missing_required_typed_option() -> None:
    result = runner.invoke(app, ["branch-name"])

    assert result.exit_code == 2
    assert "Missing option '--branch'" in plain_output(result.output)


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
    with pytest.raises(ForgeError, match=r"link|symlink"):
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


def test_printed_apply_command_preserves_review_across_days(
    empty_forge: Path, skill_source: Path, monkeypatch
) -> None:
    monkeypatch.chdir(empty_forge)
    monkeypatch.setattr(cli_module, "default_import_date", lambda: "2026-09-07")
    source_request = request(
        skill_source,
        description="-Draft 'notes' with $HOME and $(touch unexpected)",
        author='An "Author"',
        transformations=("Reviewed 'literal' $value", "Second note"),
    )
    tokens = shlex.split(cli_module._apply_command(source_request, "0" * 64))[3:]
    planning = [
        token
        for token in tokens
        if not token.startswith(("--expected-sha256=", "--imported-at=")) and token != "--apply"
    ]
    result = runner.invoke(app, planning)
    assert result.exit_code == 0, result.output
    command = next(line for line in result.output.splitlines() if line.startswith("uv run forge"))
    apply_args = shlex.split(command)[3:]
    assert "--imported-at=2026-09-07" in apply_args
    assert f"--description={source_request.description}" in apply_args
    assert not (empty_forge / "plugins" / "sample-skill").exists()

    monkeypatch.setattr(cli_module, "default_import_date", lambda: "2026-09-08")
    git(empty_forge, "checkout", "-B", "skill/sample-skill/sample-skill")
    applied = runner.invoke(app, [*apply_args, "--json"])
    assert applied.exit_code == 0, applied.output
    payload = json.loads(applied.output)["review_payload"]
    assert payload["importedAt"] == "2026-09-07"
    assert payload["description"] == source_request.description
    assert payload["transformations"] == list(source_request.transformations)


def test_doctor_json_and_text_report_issues_without_traceback(
    empty_forge: Path, monkeypatch
) -> None:
    monkeypatch.chdir(empty_forge)
    result = runner.invoke(app, ["doctor", "--json"])
    assert result.exit_code == 2
    report = json.loads(result.output)
    assert report["ready"] is False
    assert report["checks"]
    text_result = runner.invoke(app, ["doctor"])
    assert text_result.exit_code == 2
    assert "cached, not fetched" in text_result.output
    assert "Review the issues above" in text_result.output
