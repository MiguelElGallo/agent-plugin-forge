"""Test hash-bound planning and application of reviewed skill imports."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

import agent_plugin_forge.importer as importer_module
from agent_plugin_forge.common import ForgeError, load_json
from agent_plugin_forge.filesystem import tree_snapshot
from agent_plugin_forge.importer import (
    ImportRequest,
    _forge_repository_url,
    _manifest_repository_url,
    apply_import,
    plan_import,
)

from .conftest import git


def request(source: Path, **overrides: object) -> ImportRequest:
    license_file = source.parent / "LICENSE"
    license_file.write_text("Test license evidence\n", encoding="utf-8")
    values: dict[str, object] = {
        "source": source,
        "plugin": "sample-skill",
        "category": "Developer Tools",
        "version": "0.1.0",
        "description": "A sample plugin",
        "author": "Test Author",
        "license_id": "MIT",
        "license_file": license_file,
        "origin": "https://example.com/source",
        "revision": "0123456789abcdef0123456789abcdef01234567",
        "source_subpath": "skills/sample-skill",
        "imported_at": "2026-08-21",
    }
    values.update(overrides)
    return ImportRequest.model_validate(values)


def apply_reviewed(repo: Path, source: Path, **overrides: object):
    import_request = request(source, **overrides)
    plan = plan_import(repo, import_request)
    git(repo, "checkout", "-B", f"skill/{plan.plugin}/{plan.skill}")
    return apply_import(
        repo, import_request.model_copy(update={"expected_sha256": plan.plan_sha256})
    )


def test_plan_does_not_write(empty_forge: Path, skill_source: Path) -> None:
    plan = plan_import(empty_forge, request(skill_source))
    assert plan.creates_plugin
    assert not (empty_forge / "plugins" / "sample-skill").exists()


def test_hash_mismatch_explains_recovery_without_writes(
    empty_forge: Path, skill_source: Path
) -> None:
    import_request = request(skill_source)
    plan = plan_import(empty_forge, import_request)
    later = import_request.model_copy(
        update={"imported_at": date(2026, 8, 22), "expected_sha256": plan.plan_sha256}
    )
    before = tree_snapshot(empty_forge)
    with pytest.raises(ForgeError) as raised:
        apply_import(empty_forge, later)
    message = str(raised.value)
    assert "import date: 2026-08-22" in message
    assert "A hash alone cannot identify which input changed" in message
    assert "--imported-at YYYY-MM-DD" in message
    assert "do not simply replace the approved hash" in message
    assert tree_snapshot(empty_forge) == before


def test_apply_preserves_content_and_records_provenance(
    empty_forge: Path, skill_source: Path
) -> None:
    original = (skill_source / "SKILL.md").read_bytes()
    plan = apply_reviewed(empty_forge, skill_source)
    copied = empty_forge / "plugins" / plan.plugin / "skills" / plan.skill / "SKILL.md"
    assert copied.read_bytes() == original
    provenance = load_json(
        empty_forge / "plugins" / plan.plugin / "provenance" / f"{plan.skill}.json"
    )
    assert provenance["contentSha256"] == plan.content_sha256
    manifest = load_json(empty_forge / "plugins" / plan.plugin / "plugin.json")
    assert manifest["repository"] == plan.repository_url


def test_apply_creates_plugins_root_missing_from_a_fresh_clone(
    empty_forge: Path, skill_source: Path
) -> None:
    (empty_forge / "plugins").rmdir()

    plan = apply_reviewed(empty_forge, skill_source)

    assert (empty_forge / "plugins" / plan.plugin / "plugin.json").is_file()


def test_manifest_repository_url_supports_private_and_local_git_origins(tmp_path: Path) -> None:
    assert (
        _manifest_repository_url(
            "git@github.company.example:platform/agent-plugin-forge.git",
            repo=tmp_path,
        )
        == "ssh://git@github.company.example/platform/agent-plugin-forge.git"
    )
    assert (
        _manifest_repository_url("../forge.git", repo=tmp_path)
        == (tmp_path / "../forge.git").resolve().as_uri()
    )


def test_manifest_repository_url_rejects_embedded_http_credentials(tmp_path: Path) -> None:
    with pytest.raises(ForgeError, match="must not embed credentials"):
        _manifest_repository_url(
            "https://token@github.company.example/platform/forge.git",
            repo=tmp_path,
        )


def test_forge_repository_url_requires_git_origin(tmp_path: Path) -> None:
    with pytest.raises(ForgeError, match="Git worktree with an origin remote"):
        _forge_repository_url(tmp_path)


@pytest.mark.parametrize(
    "origin, message",
    [
        (
            "https://github.company.example/platform/forge.git?token=secret",
            "query or fragment",
        ),
        (
            "https://github.company.example/platform/forge.git#token=secret",
            "query or fragment",
        ),
        (
            "git@github.company.example:platform/forge.git?token=secret",
            "query or fragment",
        ),
        (
            "git@github.company.example:platform/forge.git#token=secret",
            "query or fragment",
        ),
        (
            "git?token@github.company.example:platform/forge.git",
            "query or fragment",
        ),
        (
            "git@github.company.example#token:platform/forge.git",
            "query or fragment",
        ),
        ("git@github.company.example:platform/forge.git\nsecret", "control characters"),
        ("git://github.company.example/platform/forge.git", "must use HTTPS"),
        ("ext::sh -c id", "remote-helper"),
    ],
)
def test_manifest_repository_url_rejects_unsafe_network_origins(
    tmp_path: Path, origin: str, message: str
) -> None:
    with pytest.raises(ForgeError, match=message):
        _manifest_repository_url(origin, repo=tmp_path)


def test_plan_binds_forge_repository_origin(empty_forge: Path, skill_source: Path) -> None:
    git(
        empty_forge,
        "remote",
        "set-url",
        "origin",
        "ssh://git@github.company.example/platform/forge.git",
    )
    import_request = request(skill_source)
    plan = plan_import(empty_forge, import_request)
    assert plan.repository_url == "ssh://git@github.company.example/platform/forge.git"

    git(
        empty_forge,
        "remote",
        "set-url",
        "origin",
        "ssh://git@other.company.example/platform/forge.git",
    )
    with pytest.raises(ForgeError, match="full-plan hash"):
        apply_import(
            empty_forge,
            import_request.model_copy(update={"expected_sha256": plan.plan_sha256}),
        )


@pytest.mark.parametrize(
    "origin, message",
    [
        ("https://token@private.example/repo.git", "must not embed credentials"),
        ("file://token@localhost/private/repo.git", "must not embed credentials"),
        ("https://private.example/repo.git?token=secret", "query or fragment"),
        ("https://private.example/repo.git#secret", "query or fragment"),
        ("git?secret@private.example:team/repo.git", "query or fragment"),
        ("git@private.example#secret:team/repo.git", "query or fragment"),
        ("ext::sh -c id", "remote-helper"),
        ("git://private.example/repo.git", "must use HTTPS"),
        ("../relative-source", "absolute path or a simple identifier"),
    ],
)
def test_import_rejects_unsafe_provenance_origins(
    skill_source: Path, origin: str, message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        request(skill_source, origin=origin)


def test_import_normalizes_source_origin_in_plan_and_provenance(
    empty_forge: Path, skill_source: Path
) -> None:
    import_request = request(
        skill_source,
        origin="git@github.company.example:team/source-skill.git",
    )
    assert import_request.origin == "ssh://git@github.company.example/team/source-skill.git"
    plan = plan_import(empty_forge, import_request)
    git(empty_forge, "checkout", "-B", f"skill/{plan.plugin}/{plan.skill}")
    applied = apply_import(
        empty_forge,
        import_request.model_copy(update={"expected_sha256": plan.plan_sha256}),
    )
    provenance = load_json(
        empty_forge / "plugins" / applied.plugin / "provenance" / f"{applied.skill}.json"
    )
    assert provenance["origin"] == import_request.origin

    local_request = request(skill_source, origin=str(skill_source.parent.resolve()))
    assert local_request.origin == skill_source.parent.resolve().as_uri()


def test_plan_binds_full_catalog_bytes(empty_forge: Path, skill_source: Path) -> None:
    import_request = request(skill_source)
    plan = plan_import(empty_forge, import_request)
    catalog_path = empty_forge / "catalog" / "plugins.json"
    catalog_path.write_text(
        catalog_path.read_text(encoding="utf-8").replace("Test marketplace", "Changed marketplace"),
        encoding="utf-8",
    )

    with pytest.raises(ForgeError, match="full-plan hash"):
        apply_import(
            empty_forge,
            import_request.model_copy(update={"expected_sha256": plan.plan_sha256}),
        )


def test_existing_bundle_requires_version_bump(empty_forge: Path, skill_source: Path) -> None:
    apply_reviewed(empty_forge, skill_source)
    second = skill_source.parent / "second-skill"
    second.mkdir()
    (second / "SKILL.md").write_text(
        "---\nname: second-skill\ndescription: Second skill.\n---\n\nDo another test.\n",
        encoding="utf-8",
    )
    with pytest.raises(ForgeError, match="higher --version"):
        plan_import(
            empty_forge,
            request(second, plugin="sample-skill", category=None, version="0.1.0"),
        )


@pytest.mark.parametrize("collision", ["license", "provenance"])
def test_existing_bundle_refuses_import_output_collisions(
    empty_forge: Path, skill_source: Path, collision: str
) -> None:
    apply_reviewed(empty_forge, skill_source)
    second = skill_source.parent / "second-skill"
    second.mkdir()
    (second / "SKILL.md").write_text(
        "---\nname: second-skill\ndescription: Second skill.\n---\n\nDo work.\n",
        encoding="utf-8",
    )
    plugin_root = empty_forge / "plugins" / "sample-skill"
    if collision == "license":
        target = plugin_root / "licenses" / "second-skill" / "LICENSE"
    else:
        target = plugin_root / "provenance" / "second-skill.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("must not be replaced\n", encoding="utf-8")

    with pytest.raises(ForgeError, match=f"{collision.title()} destination already exists"):
        plan_import(
            empty_forge,
            request(second, plugin="sample-skill", category=None, version="0.2.0"),
        )
    assert target.read_text(encoding="utf-8") == "must not be replaced\n"


def test_import_refuses_duplicate_skill_name_across_plugins(
    empty_forge: Path, skill_source: Path
) -> None:
    apply_reviewed(empty_forge, skill_source)
    with pytest.raises(ForgeError, match="repository-wide unique"):
        plan_import(empty_forge, request(skill_source, plugin="other-plugin"))


@pytest.mark.parametrize("field", ["category", "description", "author"])
def test_new_plugin_rejects_blank_required_metadata(skill_source: Path, field: str) -> None:
    with pytest.raises(ValidationError):
        request(skill_source, **{field: "   "})


def test_name_mismatch_is_not_rewritten(empty_forge: Path, skill_source: Path) -> None:
    (skill_source / "SKILL.md").write_text(
        "---\nname: other-name\ndescription: Mismatch.\n---\n\nDo work.\n",
        encoding="utf-8",
    )
    with pytest.raises(ForgeError, match="normalize it in a separate reviewed change"):
        plan_import(empty_forge, request(skill_source))


def test_apply_requires_reviewed_hash(empty_forge: Path, skill_source: Path) -> None:
    with pytest.raises(ForgeError, match="expected-sha256"):
        apply_import(empty_forge, request(skill_source))


def test_apply_rejects_license_changed_after_review(empty_forge: Path, skill_source: Path) -> None:
    import_request = request(skill_source)
    plan = plan_import(empty_forge, import_request)
    import_request.license_file.write_text("Changed license\n", encoding="utf-8")
    with pytest.raises(ForgeError, match="full-plan hash"):
        apply_import(
            empty_forge,
            import_request.model_copy(update={"expected_sha256": plan.plan_sha256}),
        )


def test_plan_binds_existing_bundle_license_destination(
    empty_forge: Path, skill_source: Path
) -> None:
    apply_reviewed(empty_forge, skill_source)
    second = skill_source.parent / "second-skill"
    second.mkdir()
    (second / "SKILL.md").write_text(
        "---\nname: second-skill\ndescription: Second skill.\n---\n\nDo work.\n",
        encoding="utf-8",
    )
    license_a = skill_source.parent / "LICENSE-A"
    license_b = skill_source.parent / "LICENSE-B"
    license_a.write_text("Same license bytes\n", encoding="utf-8")
    license_b.write_text("Same license bytes\n", encoding="utf-8")
    request_a = request(
        second,
        plugin="sample-skill",
        category=None,
        version="0.2.0",
        license_file=license_a,
    )
    plan_a = plan_import(empty_forge, request_a)
    request_b = request_a.model_copy(
        update={"license_file": license_b, "expected_sha256": plan_a.plan_sha256}
    )
    with pytest.raises(ForgeError, match="full-plan hash"):
        apply_import(empty_forge, request_b)


def test_plan_binds_existing_destination_state(empty_forge: Path, skill_source: Path) -> None:
    apply_reviewed(empty_forge, skill_source)
    second = skill_source.parent / "second-skill"
    second.mkdir()
    (second / "SKILL.md").write_text(
        "---\nname: second-skill\ndescription: Second skill.\n---\n\nDo work.\n",
        encoding="utf-8",
    )
    import_request = request(second, plugin="sample-skill", category=None, version="0.2.0")
    plan = plan_import(empty_forge, import_request)
    existing = (
        empty_forge / "plugins" / "sample-skill" / "skills" / "sample-skill" / "reference.txt"
    )
    existing.write_text("changed after review\n", encoding="utf-8")
    with pytest.raises(ForgeError, match="full-plan hash"):
        apply_import(
            empty_forge,
            import_request.model_copy(update={"expected_sha256": plan.plan_sha256}),
        )


def test_import_enforces_spdx_license_expressions(empty_forge: Path, skill_source: Path) -> None:
    with pytest.raises(ValidationError, match="valid SPDX"):
        request(skill_source, license_id="definitely not SPDX")
    plan = plan_import(empty_forge, request(skill_source, license_id="MIT OR Apache-2.0"))
    assert plan.skill == "sample-skill"


@pytest.mark.parametrize(
    "revision",
    ["a" * 39, "a" * 41, "a" * 63, "a" * 65, "sha256:" + "a" * 63],
)
def test_import_rejects_ambiguous_revision_lengths(skill_source: Path, revision: str) -> None:
    with pytest.raises(ValidationError, match="full commit/tree ID"):
        request(skill_source, revision=revision)


def test_rejects_version_downgrade(empty_forge: Path, skill_source: Path) -> None:
    apply_reviewed(empty_forge, skill_source, version="1.0.0")
    second = skill_source.parent / "second-skill"
    second.mkdir()
    (second / "SKILL.md").write_text(
        "---\nname: second-skill\ndescription: Second skill.\n---\n\nDo work.\n",
        encoding="utf-8",
    )
    with pytest.raises(ForgeError, match="higher --version"):
        plan_import(
            empty_forge, request(second, plugin="sample-skill", category=None, version="0.9.0")
        )


def test_imports_a_lone_skill_file(empty_forge: Path, skill_source: Path) -> None:
    skill_file = skill_source / "SKILL.md"
    import_request = request(skill_file)
    plan = plan_import(empty_forge, import_request)
    assert plan.source_kind == "skill-file"
    assert plan.files.keys() == {"SKILL.md"}
    git(empty_forge, "checkout", "-B", f"skill/{plan.plugin}/{plan.skill}")
    applied = apply_import(
        empty_forge,
        import_request.model_copy(update={"expected_sha256": plan.plan_sha256}),
    )
    destination = empty_forge / "plugins" / applied.plugin / "skills" / applied.skill
    assert sorted(path.name for path in destination.iterdir()) == ["SKILL.md"]


def test_existing_plugin_source_requires_selection_for_multiple_skills(
    empty_forge: Path, skill_source: Path
) -> None:
    source_plugin = skill_source.parent / "source-plugin"
    (source_plugin / "skills" / "first-skill").mkdir(parents=True)
    (source_plugin / "skills" / "second-skill").mkdir()
    (source_plugin / "plugin.json").write_text("{}\n", encoding="utf-8")
    for name in ("first-skill", "second-skill"):
        (source_plugin / "skills" / name / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: {name} instructions.\n---\n\nDo work.\n",
            encoding="utf-8",
        )
    with pytest.raises(ForgeError, match="require --source-skill"):
        plan_import(empty_forge, request(source_plugin))
    plan = plan_import(
        empty_forge,
        request(source_plugin, source_skill="second-skill"),
    )
    assert plan.source_kind == "plugin-skill"
    assert plan.skill == "second-skill"


@pytest.mark.skipif(os.name == "nt", reason="Windows does not preserve POSIX executable bits")
def test_plan_binds_executable_mode(empty_forge: Path, skill_source: Path) -> None:
    script = skill_source / "run.sh"
    script.write_text("#!/bin/sh\n", encoding="utf-8")
    script.chmod(0o644)
    import_request = request(skill_source)
    plan = plan_import(empty_forge, import_request)
    script.chmod(0o755)
    with pytest.raises(ForgeError, match="full-plan hash"):
        apply_import(
            empty_forge,
            import_request.model_copy(update={"expected_sha256": plan.plan_sha256}),
        )


def test_apply_rolls_back_plugin_and_catalog_on_publish_failure(
    empty_forge: Path,
    skill_source: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import_request = request(skill_source)
    plan = plan_import(empty_forge, import_request)
    reviewed = import_request.model_copy(update={"expected_sha256": plan.plan_sha256})
    git(empty_forge, "checkout", "-B", f"skill/{plan.plugin}/{plan.skill}")
    catalog_before = (empty_forge / "catalog" / "plugins.json").read_bytes()
    real_replace = importer_module.os.replace
    calls = 0

    def fail_catalog_publish(source: Path, destination: Path) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated catalog publish failure")
        real_replace(source, destination)

    monkeypatch.setattr(importer_module.os, "replace", fail_catalog_publish)
    with pytest.raises(OSError, match="simulated"):
        apply_import(empty_forge, reviewed)
    assert not (empty_forge / "plugins" / "sample-skill").exists()
    assert (empty_forge / "catalog" / "plugins.json").read_bytes() == catalog_before


@pytest.mark.parametrize(
    "existing_bundle, failure_step", [(False, 1), (False, 2), (True, 1), (True, 2), (True, 3)]
)
def test_apply_preserves_original_tree_at_each_publish_failure(
    empty_forge: Path, skill_source: Path, monkeypatch, existing_bundle: bool, failure_step: int
) -> None:
    if existing_bundle:
        apply_reviewed(empty_forge, skill_source)
        second = skill_source.parent / "second-skill"
        second.mkdir()
        (second / "SKILL.md").write_text(
            "---\nname: second-skill\ndescription: A second test skill.\n---\nTest.\n",
            encoding="utf-8",
        )
        import_request = request(second, version="0.2.0")
    else:
        import_request = request(skill_source)
    plan = plan_import(empty_forge, import_request)
    git(empty_forge, "checkout", "-B", f"skill/{plan.plugin}/{plan.skill}")
    before = tree_snapshot(empty_forge / "plugins")
    catalog_before = (empty_forge / "catalog" / "plugins.json").read_bytes()
    real_replace = importer_module.os.replace
    calls = 0

    def fail_once(source, destination):
        nonlocal calls
        calls += 1
        if calls == failure_step:
            raise OSError("simulated publish failure")
        real_replace(source, destination)

    monkeypatch.setattr(importer_module.os, "replace", fail_once)
    with pytest.raises(OSError, match="simulated publish failure"):
        apply_import(
            empty_forge, import_request.model_copy(update={"expected_sha256": plan.plan_sha256})
        )
    assert tree_snapshot(empty_forge / "plugins") == before
    assert (empty_forge / "catalog" / "plugins.json").read_bytes() == catalog_before
    assert not list(empty_forge.glob(".forge-import-*"))


@pytest.mark.parametrize("recovery_failure", ["cleanup", "restore"])
def test_failed_rollback_preserves_original_backup(
    empty_forge: Path, skill_source: Path, monkeypatch, recovery_failure: str
) -> None:
    apply_reviewed(empty_forge, skill_source)
    plugin = empty_forge / "plugins" / "sample-skill"
    before = tree_snapshot(plugin)
    catalog = empty_forge / "catalog" / "plugins.json"
    catalog_before = catalog.read_bytes()
    second = skill_source.parent / "second-skill"
    second.mkdir()
    (second / "SKILL.md").write_text(
        "---\nname: second-skill\ndescription: A second test skill.\n---\nTest.\n",
        encoding="utf-8",
    )
    import_request = request(second, version="0.2.0")
    plan = plan_import(empty_forge, import_request)
    git(empty_forge, "checkout", "-B", f"skill/{plan.plugin}/{plan.skill}")
    real_replace = importer_module.os.replace
    real_rmtree = importer_module.shutil.rmtree

    def fail_replace(source, destination):
        if destination == catalog:
            raise OSError("simulated catalog failure")
        if recovery_failure == "restore" and Path(source).name == "backup":
            raise OSError("simulated restore failure")
        real_replace(source, destination)

    def fail_cleanup(path, *args, **kwargs):
        if recovery_failure == "cleanup" and Path(path) == plugin:
            raise OSError("simulated cleanup failure")
        return real_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(importer_module.os, "replace", fail_replace)
    monkeypatch.setattr(importer_module.shutil, "rmtree", fail_cleanup)
    with pytest.raises(ForgeError, match="recovery files preserved") as error:
        apply_import(
            empty_forge, import_request.model_copy(update={"expected_sha256": plan.plan_sha256})
        )
    recovery_dirs = list(empty_forge.glob(".forge-import-*"))
    assert len(recovery_dirs) == 1
    assert str(recovery_dirs[0]) in str(error.value)
    assert tree_snapshot(recovery_dirs[0] / "backup") == before
    assert catalog.read_bytes() == catalog_before
