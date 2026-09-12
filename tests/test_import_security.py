"""Exercise the reviewed-byte boundary with deterministic source mutations."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

import agent_plugin_forge.importer as importer
from agent_plugin_forge.common import ForgeError, tree_hash
from agent_plugin_forge.sources import SkillSource, resolve_skill_source

from .conftest import git
from .test_importer import request


def test_apply_cannot_mix_hashes_from_different_source_reads(
    empty_forge: Path, skill_source: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_file = skill_source / "reference.txt"
    approved_bytes = source_file.read_bytes()
    unreviewed_bytes = b"Unreviewed instructions.\n"
    import_request = request(skill_source)
    approved = importer.plan_import(empty_forge, import_request)
    git(empty_forge, "switch", "-c", f"skill/{approved.plugin}/{approved.skill}")
    original_hashes = SkillSource.hashes
    calls = 0

    def change_between_hashes(source: SkillSource) -> dict[str, str]:
        nonlocal calls
        if source.root == skill_source:
            calls += 1
            source_file.write_bytes(unreviewed_bytes if calls == 1 else approved_bytes)
        return original_hashes(source)

    enforce_branch = importer._enforce_branch

    def change_after_authorization(repo: Path, plugin: str, skill: str) -> None:
        enforce_branch(repo, plugin, skill)
        source_file.write_bytes(unreviewed_bytes)

    monkeypatch.setattr(SkillSource, "hashes", change_between_hashes)
    monkeypatch.setattr(importer, "_enforce_branch", change_after_authorization)
    try:
        importer.apply_import(
            empty_forge,
            import_request.model_copy(update={"expected_sha256": approved.plan_sha256}),
        )
    except ForgeError:
        assert not approved.destination.exists()
    else:
        assert (approved.destination / "reference.txt").read_bytes() == approved_bytes


def test_plan_binds_the_exact_file_map(empty_forge: Path, skill_source: Path) -> None:
    plan = importer.plan_import(empty_forge, request(skill_source))
    assert plan.review_payload["files"] == plan.files
    assert plan.content_sha256 == tree_hash(plan.files)


def test_license_digest_uses_safety_inspected_bytes(
    empty_forge: Path, skill_source: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import_request = request(skill_source)
    safe_bytes = import_request.license_file.read_bytes()
    inspect = importer.inspect_regular_file

    def replace_after_inspection(path: Path, *, file_label: str = "Source file") -> bytes:
        result = inspect(path, file_label=file_label)
        if path == import_request.license_file:
            path.write_bytes(b"-----BEGIN PRIVATE KEY-----\nsynthetic regression fixture\n")
        return result

    monkeypatch.setattr(importer, "inspect_regular_file", replace_after_inspection)
    plan = importer.plan_import(empty_forge, import_request)
    assert plan.license_sha256 == hashlib.sha256(safe_bytes).hexdigest()


def test_resolved_source_is_an_immutable_byte_snapshot(skill_source: Path) -> None:
    source = resolve_skill_source(skill_source)
    hashes, modes = source.hashes(), source.modes()
    (skill_source / "reference.txt").write_bytes(b"changed after inspection")
    assert source.hashes() == hashes
    assert source.modes() == modes
    assert source.content_sha256() == tree_hash(hashes)


@pytest.mark.parametrize("newline", [b"\r\n", b"\r"])
def test_snapshot_metadata_preserves_universal_newlines(skill_source: Path, newline: bytes) -> None:
    path = skill_source / "SKILL.md"
    content = path.read_bytes().replace(b"\n", newline)
    path.write_bytes(content)
    source = resolve_skill_source(skill_source)
    assert source.name == skill_source.name
    assert source.hashes()["SKILL.md"] == hashlib.sha256(content).hexdigest()


def test_copy_rejects_added_source_paths_before_creating_destination(
    skill_source: Path, tmp_path: Path
) -> None:
    reviewed = resolve_skill_source(skill_source)
    (skill_source / "added.txt").write_bytes(b"new resource")
    destination = tmp_path / "copied"
    with pytest.raises(ForgeError, match="changed before apply"):
        importer._copy_reviewed_skill(
            resolve_skill_source(skill_source), destination, reviewed.hashes(), reviewed.modes()
        )
    assert not destination.exists()
