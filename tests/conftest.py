from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def skill_source(tmp_path: Path) -> Path:
    skill = tmp_path / "sample-skill"
    skill.mkdir()
    (skill / "SKILL.md").write_text(
        "---\nname: sample-skill\ndescription: Demonstrate a test skill.\n---\n\nDo the test.\n",
        encoding="utf-8",
    )
    (skill / "reference.txt").write_text("evidence\n", encoding="utf-8")
    return skill


@pytest.fixture
def empty_forge(tmp_path: Path) -> Path:
    repo = tmp_path / "forge"
    (repo / "catalog").mkdir(parents=True)
    (repo / "plugins").mkdir()
    (repo / "catalog" / "plugins.json").write_text(
        json.dumps(
            {
                "marketplace": {
                    "name": "test-forge",
                    "displayName": "Test Forge",
                    "owner": {"name": "Test", "email": "test@example.com"},
                    "description": "Test marketplace",
                    "version": "0.1.0",
                },
                "plugins": [],
            }
        ),
        encoding="utf-8",
    )
    source_schemas = Path(__file__).parents[1] / "schemas" / "agent-plugins" / "1.0.0"
    shutil.copytree(
        source_schemas,
        repo / "schemas" / "agent-plugins" / "1.0.0",
    )
    git(repo, "init", "-b", "main")
    git(repo, "remote", "add", "origin", "https://github.com/Test/agent-plugin-forge.git")
    return repo


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()
