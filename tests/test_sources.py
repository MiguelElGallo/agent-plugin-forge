from __future__ import annotations

import os
from pathlib import Path

import pytest

from agent_plugin_forge.common import ForgeError
from agent_plugin_forge.sources import resolve_skill_source


def test_lone_source_file_must_be_named_skill_md(tmp_path: Path) -> None:
    source = tmp_path / "skill.md"
    source.write_text(
        "---\nname: sample-skill\ndescription: Sample.\n---\n\nWork.\n",
        encoding="utf-8",
    )
    with pytest.raises(ForgeError, match="must be named SKILL.md"):
        resolve_skill_source(source)


def test_source_directory_must_have_skill_or_plugin_manifest(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    with pytest.raises(ForgeError, match="skill directory.*existing plugin"):
        resolve_skill_source(source)


def test_requested_skill_must_match_directory_skill(skill_source: Path) -> None:
    with pytest.raises(ForgeError, match="does not match"):
        resolve_skill_source(skill_source, "other-skill")


def test_existing_plugin_rejects_unknown_selected_skill(tmp_path: Path) -> None:
    plugin = tmp_path / "plugin"
    skill = plugin / "skills" / "known-skill"
    skill.mkdir(parents=True)
    (plugin / "plugin.json").write_text("{}\n", encoding="utf-8")
    (skill / "SKILL.md").write_text(
        "---\nname: known-skill\ndescription: Known.\n---\n\nWork.\n",
        encoding="utf-8",
    )
    with pytest.raises(ForgeError, match="choose one of"):
        resolve_skill_source(plugin, "missing-skill")


@pytest.mark.skipif(os.name == "nt", reason="Windows symlink creation requires extra privileges")
def test_source_root_symlink_is_rejected(skill_source: Path, tmp_path: Path) -> None:
    link = tmp_path / "linked-skill"
    link.symlink_to(skill_source, target_is_directory=True)
    with pytest.raises(ForgeError, match="link or junction"):
        resolve_skill_source(link)
