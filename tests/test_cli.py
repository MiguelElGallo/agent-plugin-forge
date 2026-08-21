from __future__ import annotations

from pathlib import Path

from agent_plugin_forge.cli import run


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


def test_cli_validates_branch_name(empty_forge: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(empty_forge)
    assert run(["branch-name", "--branch", "skill/sample-plugin/sample-skill"]) == 0
    assert "Valid skill branch" in capsys.readouterr().out
