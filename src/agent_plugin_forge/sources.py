"""Resolve supported Agent Skill intake sources without mutating them."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .common import parse_skill_frontmatter, tree_hash, validate_name
from .errors import ForgeError, diagnostic_value
from .filesystem import FileSnapshot, is_linklike, snapshot_regular_file, snapshot_regular_tree

SourceKind = Literal["skill-directory", "skill-file", "plugin-skill"]


@dataclass(frozen=True)
class SkillSource:
    """Describe an inspected local Agent Skill source and its safe files."""

    kind: SourceKind
    name: str
    root: Path | None
    skill_md: Path
    files: tuple[Path, ...]
    snapshots: tuple[FileSnapshot, ...]

    def relative_path(self, path: Path) -> str:
        """Return a source file's portable relative path."""

        return "SKILL.md" if self.root is None else path.relative_to(self.root).as_posix()

    def hashes(self) -> dict[str, str]:
        """Return SHA-256 hashes for every inspected source file."""

        return {
            self.relative_path(path): hashlib.sha256(snapshot.content).hexdigest()
            for path, snapshot in zip(self.files, self.snapshots, strict=True)
        }

    def modes(self) -> dict[str, bool]:
        """Return portable executable-bit metadata for every source file."""

        return {
            self.relative_path(path): snapshot.executable
            for path, snapshot in zip(self.files, self.snapshots, strict=True)
        }

    def content_sha256(self) -> str:
        """Return the deterministic aggregate hash of the source content."""

        return tree_hash(self.hashes())

    def path_for(self, relative: str) -> Path:
        """Resolve a portable relative source path to its local path."""

        return self.skill_md if self.root is None else self.root / relative


def _directory_source(root: Path, kind: SourceKind) -> SkillSource:
    """Inspect a skill directory and build its immutable source description."""

    captured = snapshot_regular_tree(root, required_root_file="SKILL.md", tree_label="Skill source")
    skill_md = root / "SKILL.md"
    metadata = parse_skill_frontmatter(skill_md, content=captured[skill_md].content)
    name = str(metadata["name"])
    if root.name != name:
        raise ForgeError(
            f"Source directory {root.name!r} must match SKILL.md name {name!r}; "
            "normalize it in a separate reviewed change"
        )
    return SkillSource(kind, name, root, skill_md, tuple(captured), tuple(captured.values()))


def _plugin_source(root: Path, requested_skill: str | None) -> SkillSource:
    """Select one immediate skill from an existing plugin source."""

    skills_root = root / "skills"
    if not skills_root.is_dir() or skills_root.is_symlink():
        raise ForgeError(
            f"Existing plugin source has no safe skills/ directory: {diagnostic_value(root)}"
        )
    candidates = sorted(
        path.name for path in skills_root.iterdir() if path.is_dir() and not path.is_symlink()
    )
    if requested_skill is None:
        if len(candidates) != 1:
            raise ForgeError(
                "Existing plugin sources with zero or multiple skills require --source-skill; "
                f"found {candidates}"
            )
        requested_skill = candidates[0]
    validate_name(requested_skill, kind="skill")
    if requested_skill not in candidates:
        raise ForgeError(
            f"Skill {requested_skill!r} is not an immediate skill in source plugin; "
            f"choose one of {candidates}"
        )
    return _directory_source(skills_root / requested_skill, "plugin-skill")


def resolve_skill_source(source: Path, requested_skill: str | None = None) -> SkillSource:
    """Resolve the three supported local intake shapes without staging or executing content."""
    if is_linklike(source):
        raise ForgeError(f"Skill source cannot be a link or junction: {diagnostic_value(source)}")
    if source.is_file():
        if source.name != "SKILL.md":
            raise ForgeError("A lone skill file must be named SKILL.md")
        captured = snapshot_regular_file(source, file_label="Skill source")
        metadata = parse_skill_frontmatter(source, content=captured.content)
        name = str(metadata["name"])
        if requested_skill is not None and requested_skill != name:
            raise ForgeError(f"--source-skill {requested_skill!r} does not match {name!r}")
        return SkillSource("skill-file", name, None, source, (source,), (captured,))
    if not source.is_dir():
        raise ForgeError(
            f"Skill source does not exist or is unsupported: {diagnostic_value(source)}"
        )
    if (source / "SKILL.md").is_file():
        resolved = _directory_source(source, "skill-directory")
        if requested_skill is not None and requested_skill != resolved.name:
            raise ForgeError(f"--source-skill {requested_skill!r} does not match {resolved.name!r}")
        return resolved
    if (source / "plugin.json").is_file():
        return _plugin_source(source, requested_skill)
    raise ForgeError(
        "Source must be a skill directory, a lone SKILL.md, or an existing plugin directory"
    )
