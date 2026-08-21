from __future__ import annotations

import os
from pathlib import Path

import pytest

from agent_plugin_forge.common import (
    ForgeError,
    inspect_tree,
    parse_semver,
    parse_skill_frontmatter,
)


def test_parse_skill_frontmatter(skill_source: Path) -> None:
    metadata = parse_skill_frontmatter(skill_source / "SKILL.md")
    assert metadata["name"] == "sample-skill"


def test_frontmatter_allows_separator_inside_quoted_value(skill_source: Path) -> None:
    (skill_source / "SKILL.md").write_text(
        '---\nname: sample-skill\ndescription: "Valid --- description"\n---\n\nWork.\n',
        encoding="utf-8",
    )
    assert (
        parse_skill_frontmatter(skill_source / "SKILL.md")["description"] == "Valid --- description"
    )


@pytest.mark.parametrize("value", ["1.0.0-01", "1.0.0-alpha..1"])
def test_strict_semver_rejects_invalid_values(value: str) -> None:
    with pytest.raises(ForgeError, match="Semantic Versioning"):
        parse_semver(value, label="Version")


def test_strict_semver_accepts_prerelease_with_build() -> None:
    assert str(parse_semver("1.0.0-alpha+build", label="Version")) == "1.0.0-alpha+build"


def test_rejects_nested_secret_file(skill_source: Path) -> None:
    (skill_source / ".env.local").write_text("SAFE=still-not-imported\n", encoding="utf-8")
    with pytest.raises(ForgeError, match="Possible secret file"):
        inspect_tree(skill_source)


def test_rejects_private_key_content(skill_source: Path) -> None:
    (skill_source / "notes.txt").write_text("-----BEGIN PRIVATE KEY-----\n", encoding="utf-8")
    with pytest.raises(ForgeError, match="Possible secret content"):
        inspect_tree(skill_source)


@pytest.mark.parametrize(
    ("frontmatter", "message"),
    [
        ("name: dotted.skill\ndescription: Invalid name.", "Invalid skill name"),
        (f"name: sample-skill\ndescription: {'x' * 1025}", "description exceeds"),
        (
            "name: sample-skill\ndescription: Invalid metadata.\nmetadata:\n  count: 1",
            "metadata must map strings to strings",
        ),
        (
            f"name: sample-skill\ndescription: Long compatibility.\ncompatibility: {'x' * 501}",
            "compatibility must be",
        ),
        (
            "name: sample-skill\ndescription: Invalid tools.\nallowed-tools:\n  - Read",
            "allowed-tools must be",
        ),
    ],
)
def test_agent_skills_frontmatter_contract(
    skill_source: Path, frontmatter: str, message: str
) -> None:
    (skill_source / "SKILL.md").write_text(
        f"---\n{frontmatter}\n---\n\nInstructions.\n", encoding="utf-8"
    )
    with pytest.raises(ForgeError, match=message):
        parse_skill_frontmatter(skill_source / "SKILL.md")


@pytest.mark.skipif(os.name == "nt", reason="Windows symlink creation requires extra privileges")
def test_rejects_symlink(skill_source: Path) -> None:
    (skill_source / "link").symlink_to(skill_source / "SKILL.md")
    with pytest.raises(ForgeError, match="Symlinks"):
        inspect_tree(skill_source)
