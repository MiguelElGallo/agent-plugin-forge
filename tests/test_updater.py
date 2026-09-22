"""Test reviewed replacement of installed skills without changing unrelated package files."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path

import pytest

import agent_plugin_forge.importer as importer_module
import agent_plugin_forge.transactions as transactions_module
from agent_plugin_forge.common import ForgeError, json_bytes, load_json
from agent_plugin_forge.filesystem import tree_snapshot
from agent_plugin_forge.importer import apply_update, plan_import, plan_update
from agent_plugin_forge.models import ImportRequest

from .conftest import git
from .test_importer import apply_reviewed, request
from .test_mcp import write_mcp


def update_request(source: Path, **overrides: object) -> ImportRequest:
    values: dict[str, object] = {
        "version": "0.2.0",
        "category": None,
        "description": None,
        "author": None,
    }
    values.update(overrides)
    return request(source, **values)


def second_source(source: Path) -> Path:
    second = source.parent / "second-skill"
    second.mkdir()
    (second / "SKILL.md").write_text(
        "---\nname: second-skill\ndescription: Another reviewed skill.\n---\n\nDo work.\n",
        encoding="utf-8",
    )
    return second


def reviewed_update(repo: Path, update: ImportRequest):
    plan = plan_update(repo, update)
    git(repo, "checkout", "-B", f"skill/{plan.plugin}/{plan.skill}")
    return apply_update(repo, update.model_copy(update={"expected_sha256": plan.plan_sha256}))


def test_update_plan_is_deterministic_and_does_not_write(
    empty_forge: Path, skill_source: Path
) -> None:
    apply_reviewed(empty_forge, skill_source)
    update = update_request(skill_source)
    before = tree_snapshot(empty_forge)

    first = plan_update(empty_forge, update)
    second = plan_update(empty_forge, update)

    assert first == second
    assert first.operation == "update"
    assert first.review_payload["operation"] == "update"
    assert first.review_payload["changes"] == first.changes
    assert first.review_payload["updateMetadata"] == first.update_metadata
    assert first.update_metadata == {
        "previousVersion": "0.1.0",
        "version": "0.2.0",
        "manifestPath": "plugin.json",
        "provenancePath": "provenance/sample-skill.json",
        "licensePath": "licenses/sample-skill/LICENSE",
        "licenseAction": "add",
        "preservesSharedLicense": True,
    }
    assert not first.creates_plugin
    assert tree_snapshot(empty_forge) == before
    with pytest.raises(ForgeError, match="already exists"):
        plan_import(empty_forge, update)


def test_update_replaces_files_and_refreshes_provenance_and_version(
    empty_forge: Path, skill_source: Path
) -> None:
    apply_reviewed(empty_forge, skill_source)
    plugin = empty_forge / "plugins" / "sample-skill"
    old_root_license = (plugin / "LICENSE").read_bytes()
    (skill_source / "reference.txt").unlink()
    (skill_source / "SKILL.md").write_text(
        "---\nname: sample-skill\ndescription: Revised reviewed instructions.\n---\n\nNew work.\n",
        encoding="utf-8",
    )
    (skill_source / "new.txt").write_text("new supporting content\n", encoding="utf-8")
    update = update_request(skill_source, revision="a" * 40, transformations=("Reviewed revision",))
    update.license_file.write_text("Updated MIT evidence\n", encoding="utf-8")

    plan = reviewed_update(empty_forge, update)

    assert plan.changes == {
        "added": ["new.txt"],
        "removed": ["reference.txt"],
        "modified": ["SKILL.md"],
        "mode_changed": [],
    }
    assert tree_snapshot(plugin / "skills" / "sample-skill") == tree_snapshot(skill_source)
    manifest = load_json(plugin / "plugin.json")
    assert manifest["version"] == "0.2.0"
    record = load_json(plugin / "provenance" / "sample-skill.json")
    assert record["revision"] == "a" * 40
    assert record["files"] == plan.files
    assert record["fileModes"] == plan.file_modes
    assert record["contentSha256"] == plan.content_sha256
    assert record["transformations"] == ["Reviewed revision"]
    assert record["licenseEvidence"]["path"] == "licenses/sample-skill/LICENSE"
    assert (
        record["licenseEvidence"]["sha256"]
        == hashlib.sha256(update.license_file.read_bytes()).hexdigest()
    )
    assert (plugin / record["licenseEvidence"]["path"]).read_bytes() == (
        update.license_file.read_bytes()
    )
    assert (plugin / "LICENSE").read_bytes() == old_root_license


@pytest.mark.skipif(os.name == "nt", reason="Windows does not preserve POSIX executable bits")
def test_update_reports_and_applies_mode_only_changes(
    empty_forge: Path, skill_source: Path
) -> None:
    script = skill_source / "run.sh"
    script.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    script.chmod(0o644)
    apply_reviewed(empty_forge, skill_source)
    script.chmod(0o755)

    plan = reviewed_update(empty_forge, update_request(skill_source))

    assert plan.changes["mode_changed"] == ["run.sh"]
    assert plan.changes["modified"] == []
    installed = empty_forge / "plugins" / "sample-skill" / "skills" / "sample-skill" / "run.sh"
    assert installed.stat().st_mode & 0o111


def test_update_preserves_other_skill_and_mcp_files(empty_forge: Path, skill_source: Path) -> None:
    apply_reviewed(empty_forge, skill_source)
    second = second_source(skill_source)
    apply_reviewed(empty_forge, second, version="0.2.0")
    plugin = empty_forge / "plugins" / "sample-skill"
    write_mcp(plugin, {"type": "stdio", "command": "python3", "args": ["server.py"]})
    (plugin / "server.py").write_text("raise SystemExit('must not run')\n", encoding="utf-8")
    (plugin / "server.py").chmod(0o755)
    (plugin / "asset.txt").write_text("shared asset\n", encoding="utf-8")
    before = tree_snapshot(plugin)
    catalog_before = (empty_forge / "catalog" / "plugins.json").read_bytes()
    manifest_before = load_json(plugin / "plugin.json")
    (skill_source / "reference.txt").write_text("updated evidence\n", encoding="utf-8")

    reviewed_update(empty_forge, update_request(skill_source, version="0.3.0"))

    after = tree_snapshot(plugin)
    expected_changes = {
        "skills/sample-skill/reference.txt",
        "plugin.json",
        "provenance/sample-skill.json",
        "licenses/sample-skill/LICENSE",
    }
    for path, previous in before.items():
        if path not in expected_changes:
            assert after[path] == previous
    assert set(after) - set(before) == {"licenses/sample-skill/LICENSE"}
    assert (empty_forge / "catalog" / "plugins.json").read_bytes() == catalog_before
    manifest_after = load_json(plugin / "plugin.json")
    assert manifest_after == {**manifest_before, "version": "0.3.0"}


def test_update_preserves_reformatted_catalog_bytes(empty_forge: Path, skill_source: Path) -> None:
    apply_reviewed(empty_forge, skill_source)
    catalog = empty_forge / "catalog" / "plugins.json"
    catalog.write_bytes(
        (json.dumps(load_json(catalog), ensure_ascii=False, separators=(",", ":")) + "\n").encode()
    )
    original = catalog.read_bytes()
    assert b"\n  " not in original

    (skill_source / "reference.txt").write_text("Reviewed update.\n", encoding="utf-8")
    reviewed_update(empty_forge, update_request(skill_source))

    assert catalog.read_bytes() == original


@pytest.mark.parametrize("version", [None, "0.1.0", "0.0.9"])
def test_update_requires_higher_version(
    empty_forge: Path, skill_source: Path, version: str | None
) -> None:
    apply_reviewed(empty_forge, skill_source)
    before = tree_snapshot(empty_forge)
    with pytest.raises(ForgeError):
        plan_update(empty_forge, update_request(skill_source, version=version))
    assert tree_snapshot(empty_forge) == before


def test_update_requires_installed_plugin(empty_forge: Path, skill_source: Path) -> None:
    before = tree_snapshot(empty_forge)
    with pytest.raises(ForgeError):
        plan_update(empty_forge, update_request(skill_source))
    assert tree_snapshot(empty_forge) == before


def test_update_does_not_add_a_missing_skill(empty_forge: Path, skill_source: Path) -> None:
    apply_reviewed(empty_forge, skill_source)
    before = tree_snapshot(empty_forge)
    with pytest.raises(ForgeError):
        plan_update(empty_forge, update_request(second_source(skill_source)))
    assert tree_snapshot(empty_forge) == before


@pytest.mark.parametrize("drift", ["missing", "identity", "content", "license"])
def test_update_rejects_unrecorded_or_drifted_installed_skill(
    empty_forge: Path, skill_source: Path, drift: str
) -> None:
    apply_reviewed(empty_forge, skill_source)
    plugin = empty_forge / "plugins" / "sample-skill"
    provenance = plugin / "provenance" / "sample-skill.json"
    if drift == "missing":
        provenance.unlink()
    elif drift == "identity":
        record = load_json(provenance)
        record["skill"] = "other-skill"
        provenance.write_bytes(json_bytes(record))
    elif drift == "content":
        (plugin / "skills" / "sample-skill" / "reference.txt").write_text(
            "unrecorded edit\n", encoding="utf-8"
        )
    else:
        (plugin / "LICENSE").write_text("unrecorded license\n", encoding="utf-8")
    before = tree_snapshot(empty_forge)

    with pytest.raises(ForgeError):
        plan_update(empty_forge, update_request(skill_source))

    assert tree_snapshot(empty_forge) == before


@pytest.mark.skipif(os.name == "nt", reason="Windows does not preserve POSIX executable bits")
def test_update_rejects_installed_mode_drift(empty_forge: Path, skill_source: Path) -> None:
    apply_reviewed(empty_forge, skill_source)
    installed = empty_forge / "plugins" / "sample-skill" / "skills" / "sample-skill"
    (installed / "reference.txt").chmod(0o755)
    before = tree_snapshot(empty_forge)
    with pytest.raises(ForgeError):
        plan_update(empty_forge, update_request(skill_source))
    assert tree_snapshot(empty_forge) == before


def test_update_validates_other_skills_provenance(empty_forge: Path, skill_source: Path) -> None:
    apply_reviewed(empty_forge, skill_source)
    second = second_source(skill_source)
    apply_reviewed(empty_forge, second, version="0.2.0")
    (empty_forge / "plugins" / "sample-skill" / "provenance" / "second-skill.json").unlink()
    before = tree_snapshot(empty_forge)

    with pytest.raises(ForgeError):
        plan_update(empty_forge, update_request(skill_source, version="0.3.0"))

    assert tree_snapshot(empty_forge) == before


@pytest.mark.parametrize("drift", ["source", "license", "catalog", "origin", "shared-file"])
def test_update_rejects_changed_review_inputs(
    empty_forge: Path, skill_source: Path, drift: str
) -> None:
    apply_reviewed(empty_forge, skill_source)
    update = update_request(skill_source)
    plan = plan_update(empty_forge, update)
    if drift == "source":
        (skill_source / "reference.txt").write_text("changed after review\n", encoding="utf-8")
    elif drift == "license":
        update.license_file.write_text("changed after review\n", encoding="utf-8")
    elif drift == "catalog":
        catalog = empty_forge / "catalog" / "plugins.json"
        catalog.write_bytes(catalog.read_bytes() + b"\n")
    elif drift == "origin":
        git(empty_forge, "remote", "set-url", "origin", "https://example.com/other-forge.git")
    else:
        (empty_forge / "plugins" / "sample-skill" / "shared.txt").write_text(
            "new unrelated file\n", encoding="utf-8"
        )
    before = tree_snapshot(empty_forge)

    with pytest.raises(ForgeError, match="full-plan hash"):
        apply_update(empty_forge, update.model_copy(update={"expected_sha256": plan.plan_sha256}))

    assert tree_snapshot(empty_forge) == before


def test_update_requires_reviewed_hash_and_scoped_branch(
    empty_forge: Path, skill_source: Path
) -> None:
    apply_reviewed(empty_forge, skill_source)
    update = update_request(skill_source)
    plan = plan_update(empty_forge, update)
    with pytest.raises(ForgeError, match="expected-sha256"):
        apply_update(empty_forge, update)
    git(empty_forge, "checkout", "-B", "forge/wrong-scope")
    before = tree_snapshot(empty_forge)
    with pytest.raises(ForgeError, match="skill/sample-skill/sample-skill"):
        apply_update(empty_forge, update.model_copy(update={"expected_sha256": plan.plan_sha256}))
    assert tree_snapshot(empty_forge) == before


@pytest.mark.skipif(os.name == "nt", reason="Windows does not preserve POSIX executable bits")
def test_update_rejects_source_mode_changed_after_review(
    empty_forge: Path, skill_source: Path
) -> None:
    apply_reviewed(empty_forge, skill_source)
    update = update_request(skill_source)
    plan = plan_update(empty_forge, update)
    (skill_source / "reference.txt").chmod(0o755)
    before = tree_snapshot(empty_forge)

    with pytest.raises(ForgeError, match="full-plan hash"):
        apply_update(empty_forge, update.model_copy(update={"expected_sha256": plan.plan_sha256}))

    assert tree_snapshot(empty_forge) == before


@pytest.mark.parametrize("drift", ["destination", "catalog", "origin"])
def test_update_preserves_edits_made_while_staging(
    empty_forge: Path, skill_source: Path, monkeypatch: pytest.MonkeyPatch, drift: str
) -> None:
    apply_reviewed(empty_forge, skill_source)
    update = update_request(skill_source)
    plan = plan_update(empty_forge, update)
    plugin = empty_forge / "plugins" / "sample-skill"
    catalog = empty_forge / "catalog" / "plugins.json"
    before = tree_snapshot(plugin)
    catalog_before = catalog.read_bytes()
    real_copy = importer_module._copy_regular_tree

    def copy_then_edit(source: Path, destination: Path) -> None:
        real_copy(source, destination)
        if drift == "destination":
            (plugin / "concurrent.txt").write_bytes(b"preserve this edit\n")
        elif drift == "catalog":
            catalog.write_bytes(catalog_before + b"\n")
        else:
            git(empty_forge, "remote", "set-url", "origin", "https://example.com/new-forge.git")

    monkeypatch.setattr(importer_module, "_copy_regular_tree", copy_then_edit)

    with pytest.raises(ForgeError, match="changed while staging"):
        apply_update(empty_forge, update.model_copy(update={"expected_sha256": plan.plan_sha256}))

    expected = dict(before)
    if drift == "destination":
        expected["concurrent.txt"] = (b"preserve this edit\n", False)
    assert tree_snapshot(plugin) == expected
    assert catalog.read_bytes() == catalog_before + (b"\n" if drift == "catalog" else b"")
    if drift == "origin":
        assert (
            git(empty_forge, "remote", "get-url", "origin") == "https://example.com/new-forge.git"
        )
    assert not list(empty_forge.glob(".forge-import-*"))


def test_update_rejects_destination_edits_copied_during_staging(
    empty_forge: Path, skill_source: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    apply_reviewed(empty_forge, skill_source)
    update = update_request(skill_source)
    plan = plan_update(empty_forge, update)
    plugin = empty_forge / "plugins" / "sample-skill"
    before = tree_snapshot(plugin)
    real_copy = importer_module._copy_regular_tree

    def edit_then_copy(source: Path, destination: Path) -> None:
        (plugin / "concurrent.txt").write_bytes(b"preserve this edit\n")
        real_copy(source, destination)

    monkeypatch.setattr(importer_module, "_copy_regular_tree", edit_then_copy)

    with pytest.raises(ForgeError, match="changed while staging"):
        apply_update(empty_forge, update.model_copy(update={"expected_sha256": plan.plan_sha256}))

    assert tree_snapshot(plugin) == {**before, "concurrent.txt": (b"preserve this edit\n", False)}
    assert not list(empty_forge.glob(".forge-import-*"))


def test_update_rejects_license_expression_change(empty_forge: Path, skill_source: Path) -> None:
    apply_reviewed(empty_forge, skill_source)
    before = tree_snapshot(empty_forge)
    with pytest.raises(ForgeError):
        plan_update(empty_forge, update_request(skill_source, license_id="Apache-2.0"))
    assert tree_snapshot(empty_forge) == before


@pytest.mark.parametrize(
    "existing_path", ["licenses/sample-skill/LICENSE", "LICENSES/SAMPLE-SKILL/license"]
)
def test_update_rejects_unowned_license_destination(
    empty_forge: Path, skill_source: Path, existing_path: str
) -> None:
    apply_reviewed(empty_forge, skill_source)
    occupied = empty_forge / "plugins" / "sample-skill" / existing_path
    occupied.parent.mkdir(parents=True)
    occupied.write_text("existing unrelated evidence\n", encoding="utf-8")
    before = tree_snapshot(empty_forge)
    with pytest.raises(ForgeError):
        plan_update(empty_forge, update_request(skill_source))
    assert tree_snapshot(empty_forge) == before


def test_update_can_replace_its_own_license_evidence(empty_forge: Path, skill_source: Path) -> None:
    apply_reviewed(empty_forge, skill_source)
    root_license = empty_forge / "plugins" / "sample-skill" / "LICENSE"
    original_shared_license = root_license.read_bytes()
    reviewed_update(empty_forge, update_request(skill_source))
    update = update_request(skill_source, version="0.3.0")
    update.license_file.write_text("new reviewed evidence\n", encoding="utf-8")

    plan = reviewed_update(empty_forge, update)

    evidence = empty_forge / "plugins" / "sample-skill" / plan.license_destination
    assert evidence.read_bytes() == update.license_file.read_bytes()
    assert plan.update_metadata["licenseAction"] == "replace"
    assert root_license.read_bytes() == original_shared_license


@pytest.mark.parametrize(
    "existing_path",
    ["LICENSES/MIT.txt", "LICENSES/SAMPLE-SKILL/license", "licenses/SAMPLE-SKILL/LICENSE"],
)
def test_update_preserves_actual_license_path_spelling(
    empty_forge: Path, skill_source: Path, existing_path: str
) -> None:
    from agent_plugin_forge.generator import generate
    from agent_plugin_forge.validator import assert_valid_repository

    apply_reviewed(empty_forge, skill_source)
    plugin = empty_forge / "plugins" / "sample-skill"
    evidence = plugin / existing_path
    evidence.parent.mkdir(parents=True)
    evidence.write_bytes((plugin / "LICENSE").read_bytes())
    # A lowercase licenses/ directory alone does not satisfy the package license contract.
    if existing_path.startswith("LICENSES/"):
        (plugin / "LICENSE").unlink()
    provenance = plugin / "provenance" / "sample-skill.json"
    record = load_json(provenance)
    record["licenseEvidence"]["path"] = existing_path
    provenance.write_bytes(json_bytes(record))
    generate(empty_forge)
    assert_valid_repository(empty_forge)

    plan = reviewed_update(empty_forge, update_request(skill_source))

    expected = (
        "LICENSES/sample-skill/LICENSE" if existing_path == "LICENSES/MIT.txt" else existing_path
    )
    assert plan.license_destination == expected
    assert plan.update_metadata["licensePath"] == expected
    assert load_json(provenance)["licenseEvidence"]["path"] == expected
    assert expected in tree_snapshot(plugin)
    assert existing_path in tree_snapshot(plugin)
    generate(empty_forge)
    assert_valid_repository(empty_forge)


@pytest.mark.parametrize(
    "aliases",
    [
        ["licenses", "LICENSES"],
        ["licenses/sample-skill", "licenses/SAMPLE-SKILL"],
        ["licenses/sample-skill/LICENSE", "licenses/sample-skill/license"],
    ],
)
def test_update_rejects_ambiguous_license_case_aliases_on_every_host(aliases: list[str]) -> None:
    # A captured Linux tree can contain aliases that cannot coexist on this host.
    with pytest.raises(ForgeError, match="ambiguous case aliases"):
        importer_module._canonical_output_path(
            "licenses/sample-skill/LICENSE", {"files": dict.fromkeys(aliases), "directories": []}
        )


@pytest.mark.parametrize(
    "evidence_path",
    [
        "licenses/sample-skill/LICENSE",
        "./licenses/sample-skill/LICENSE",
        "licenses//sample-skill/LICENSE",
    ],
)
def test_update_does_not_overwrite_evidence_referenced_by_another_skill(
    empty_forge: Path, skill_source: Path, evidence_path: str
) -> None:
    apply_reviewed(empty_forge, skill_source)
    reviewed_update(empty_forge, update_request(skill_source))
    second = second_source(skill_source)
    apply_reviewed(empty_forge, second, version="0.3.0")
    plugin = empty_forge / "plugins" / "sample-skill"
    own_record = load_json(plugin / "provenance" / "sample-skill.json")
    other_provenance = plugin / "provenance" / "second-skill.json"
    record = load_json(other_provenance)
    record["licenseEvidence"] = {**own_record["licenseEvidence"], "path": evidence_path}
    other_provenance.write_bytes(json_bytes(record))
    before = tree_snapshot(empty_forge)

    with pytest.raises(ForgeError):
        plan_update(empty_forge, update_request(skill_source, version="0.4.0"))

    assert tree_snapshot(empty_forge) == before


@pytest.mark.parametrize(
    ("evidence_path", "change"),
    [
        ("skills/sample-skill/LICENSE", "replace"),
        ("skills/sample-skill/LICENSE", "remove"),
        ("plugin.json", "metadata"),
        ("provenance/sample-skill.json", "metadata"),
    ],
)
def test_update_preserves_other_skills_evidence_in_changed_paths(
    empty_forge: Path, skill_source: Path, evidence_path: str, change: str
) -> None:
    source_evidence = skill_source / "LICENSE"
    source_evidence.write_text("Test license evidence\n", encoding="utf-8")
    apply_reviewed(empty_forge, skill_source)
    second = second_source(skill_source)
    apply_reviewed(empty_forge, second, version="0.2.0")
    plugin = empty_forge / "plugins" / "sample-skill"
    other_provenance = plugin / "provenance" / "second-skill.json"
    record = load_json(other_provenance)
    record["licenseEvidence"] = {
        "path": evidence_path,
        "sha256": hashlib.sha256((plugin / evidence_path).read_bytes()).hexdigest(),
    }
    other_provenance.write_bytes(json_bytes(record))
    if change == "replace":
        source_evidence.write_text("New license evidence\n", encoding="utf-8")
    elif change == "remove":
        source_evidence.unlink()
    before = tree_snapshot(empty_forge)

    with pytest.raises(ForgeError):
        plan_update(empty_forge, update_request(skill_source, version="0.3.0"))

    assert tree_snapshot(empty_forge) == before


@pytest.mark.parametrize("failure", ["backup", "install", "catalog"])
def test_update_restores_original_package_at_each_publish_failure(
    empty_forge: Path, skill_source: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    apply_reviewed(empty_forge, skill_source)
    update = update_request(skill_source)
    (skill_source / "reference.txt").write_text("new revision\n", encoding="utf-8")
    plan = plan_update(empty_forge, update)
    plugin = empty_forge / "plugins" / "sample-skill"
    catalog = empty_forge / "catalog" / "plugins.json"
    before = tree_snapshot(plugin)
    catalog_before = catalog.read_bytes()
    real_replace = transactions_module.os.replace
    failed = False

    def fail_once(source: Path, destination: Path) -> None:
        nonlocal failed
        selected = (
            (failure == "backup" and source == plugin)
            or (failure == "install" and destination == plugin)
            or (failure == "catalog" and destination == catalog)
        )
        if not failed and selected:
            failed = True
            raise OSError("simulated update publish failure")
        real_replace(source, destination)

    monkeypatch.setattr(transactions_module.os, "replace", fail_once)

    with pytest.raises(OSError, match="simulated update publish failure"):
        apply_update(empty_forge, update.model_copy(update={"expected_sha256": plan.plan_sha256}))

    assert failed
    assert tree_snapshot(plugin) == before
    assert catalog.read_bytes() == catalog_before
    assert not list(empty_forge.glob(".forge-import-*"))
    assert not list(empty_forge.glob(".forge-update-*"))


@pytest.mark.parametrize("failure", ["cleanup", "restore"])
def test_update_preserves_backup_when_rollback_fails(
    empty_forge: Path, skill_source: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    apply_reviewed(empty_forge, skill_source)
    update = update_request(skill_source)
    (skill_source / "reference.txt").write_text("new revision\n", encoding="utf-8")
    plan = plan_update(empty_forge, update)
    plugin = empty_forge / "plugins" / "sample-skill"
    catalog = empty_forge / "catalog" / "plugins.json"
    before = tree_snapshot(plugin)
    catalog_before = catalog.read_bytes()
    real_replace = transactions_module.os.replace
    real_rmtree = importer_module.shutil.rmtree

    def fail_replace(source: Path, destination: Path) -> None:
        if destination == catalog:
            raise OSError("simulated catalog failure")
        if failure == "restore" and source.name == "backup":
            raise OSError("simulated restore failure")
        real_replace(source, destination)

    def fail_cleanup(path: Path, *args, **kwargs) -> None:
        if failure == "cleanup" and path == plugin:
            raise OSError("simulated cleanup failure")
        real_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(transactions_module.os, "replace", fail_replace)
    monkeypatch.setattr(importer_module.shutil, "rmtree", fail_cleanup)

    with pytest.raises(ForgeError, match="recovery files preserved") as raised:
        apply_update(empty_forge, update.model_copy(update={"expected_sha256": plan.plan_sha256}))

    recovery = list(empty_forge.glob(".forge-import-*"))
    assert len(recovery) == 1
    assert str(recovery[0]) in str(raised.value)
    assert tree_snapshot(recovery[0] / "backup") == before
    assert catalog.read_bytes() == catalog_before


def test_update_refuses_to_remove_a_packaged_mcp_command(
    empty_forge: Path, skill_source: Path
) -> None:
    from agent_plugin_forge.generator import generate
    from agent_plugin_forge.validator import assert_valid_repository

    command = skill_source / "run.sh"
    command.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    command.chmod(0o755)
    apply_reviewed(empty_forge, skill_source)
    plugin = empty_forge / "plugins" / "sample-skill"
    write_mcp(plugin, {"type": "stdio", "command": "./skills/sample-skill/run.sh"})
    generate(empty_forge)
    assert_valid_repository(empty_forge)
    before = tree_snapshot(empty_forge)
    command.unlink()
    update = update_request(skill_source)
    plan = plan_update(empty_forge, update)

    with pytest.raises(ForgeError, match="command does not exist"):
        apply_update(empty_forge, update.model_copy(update={"expected_sha256": plan.plan_sha256}))

    assert tree_snapshot(empty_forge) == before
    assert not list(empty_forge.glob(".forge-import-*"))
    assert_valid_repository(empty_forge)


@pytest.mark.parametrize(
    "argument",
    [
        "${PLUGIN_ROOT}/skills/sample-skill/server.py",
        "${PLUGIN_ROOT}//skills/sample-skill/server.py",
        "--script=${PLUGIN_ROOT}/skills/sample-skill/server.py",
        "-s=${PLUGIN_ROOT}/skills/sample-skill/server.py",
        "${PLUGIN_ROOT}/skills/./sample-skill/server.py",
        "${PLUGIN_ROOT}/skills/sample-skill/../sample-skill/server.py",
    ],
)
@pytest.mark.parametrize("replacement", ["missing", "directory"])
def test_update_refuses_to_remove_or_change_mcp_argument_file(
    empty_forge: Path, skill_source: Path, argument: str, replacement: str
) -> None:
    from agent_plugin_forge.generator import generate
    from agent_plugin_forge.validator import assert_valid_repository

    script = skill_source / "server.py"
    script.write_text("raise SystemExit('must not run')\n", encoding="utf-8")
    apply_reviewed(empty_forge, skill_source)
    plugin = empty_forge / "plugins" / "sample-skill"
    write_mcp(plugin, {"type": "stdio", "command": "python3", "args": [argument]})
    generate(empty_forge)
    assert_valid_repository(empty_forge)
    before = tree_snapshot(empty_forge)
    script.unlink()
    if replacement == "directory":
        script.mkdir()
        (script / "content.txt").write_text("directory contents\n", encoding="utf-8")

    with pytest.raises(ForgeError, match=r"MCP server .* argument path"):
        reviewed_update(empty_forge, update_request(skill_source))

    assert tree_snapshot(empty_forge) == before
    assert not list(empty_forge.glob(".forge-import-*"))
    assert_valid_repository(empty_forge)


@pytest.mark.parametrize("replacement", ["missing", "file", "empty"])
def test_update_refuses_to_remove_or_change_mcp_argument_directory(
    empty_forge: Path, skill_source: Path, replacement: str
) -> None:
    directory = skill_source / "server data"
    directory.mkdir()
    (directory / "data.json").write_text("{}\n", encoding="utf-8")
    apply_reviewed(empty_forge, skill_source)
    plugin = empty_forge / "plugins" / "sample-skill"
    write_mcp(
        plugin,
        {
            "type": "stdio",
            "command": "python3",
            "args": ["--data=${PLUGIN_ROOT}/skills/sample-skill/server data/"],
        },
    )
    before = tree_snapshot(empty_forge)
    shutil.rmtree(directory)
    if replacement == "file":
        directory.write_text("file contents\n", encoding="utf-8")
    elif replacement == "empty":
        directory.mkdir()

    with pytest.raises(ForgeError, match=r"MCP server .* argument path"):
        reviewed_update(empty_forge, update_request(skill_source))

    assert tree_snapshot(empty_forge) == before


@pytest.mark.skipif(os.name == "nt", reason="Windows disallows newlines in filenames")
def test_update_protects_mcp_argument_paths_containing_newlines(
    empty_forge: Path, skill_source: Path
) -> None:
    script = skill_source / "server\nname.py"
    script.write_text("raise SystemExit('must not run')\n", encoding="utf-8")
    apply_reviewed(empty_forge, skill_source)
    plugin = empty_forge / "plugins" / "sample-skill"
    write_mcp(
        plugin,
        {
            "type": "stdio",
            "command": "python3",
            "args": ["${PLUGIN_ROOT}/skills/sample-skill/server\nname.py"],
        },
    )
    before = tree_snapshot(empty_forge)
    script.unlink()

    with pytest.raises(ForgeError, match=r"MCP server .* argument path"):
        reviewed_update(empty_forge, update_request(skill_source))

    assert tree_snapshot(empty_forge) == before


def test_update_preserves_mcp_arguments_and_allows_uncreated_output_paths(
    empty_forge: Path, skill_source: Path
) -> None:
    from agent_plugin_forge.generator import generate
    from agent_plugin_forge.validator import assert_valid_repository

    directory = skill_source / "server data"
    directory.mkdir()
    data = directory / "data.json"
    data.write_text("{}\n", encoding="utf-8")
    apply_reviewed(empty_forge, skill_source)
    second = second_source(skill_source)
    apply_reviewed(empty_forge, second, version="0.2.0")
    plugin = empty_forge / "plugins" / "sample-skill"
    write_mcp(
        plugin,
        {
            "type": "stdio",
            "command": "python3",
            "args": [
                "${PLUGIN_ROOT}/skills/sample-skill/server data/data.json",
                "--data=${PLUGIN_ROOT}/skills/sample-skill/server data",
                "${PLUGIN_ROOT}/skills/sample-skill",
                "${PLUGIN_ROOT}/skills/sample-skill/../second-skill/SKILL.md",
                "--output=${PLUGIN_ROOT}/skills/sample-skill/new.json",
                "--output=${PLUGIN_ROOT}/skills/sample-skill/missing/../reference.txt",
                "${PLUGIN_DATA}/output.json",
                "--verbose",
            ],
        },
    )
    mcp_before = (plugin / "mcp.json").read_bytes()
    data.write_text('{"updated": true}\n', encoding="utf-8")
    (skill_source / "reference.txt").unlink()

    reviewed_update(empty_forge, update_request(skill_source, version="0.3.0"))

    assert (plugin / "mcp.json").read_bytes() == mcp_before
    assert not (plugin / "skills" / "sample-skill" / "new.json").exists()
    generate(empty_forge)
    assert_valid_repository(empty_forge)


@pytest.mark.parametrize(
    "argument",
    [
        "${PLUGIN_ROOT}/skills/sample-skill/data/../reference.txt",
        "${PLUGIN_ROOT}/skills/sample-skill/data/../../../plugin.json",
    ],
)
def test_update_preserves_mcp_argument_traversal_directories(
    empty_forge: Path, skill_source: Path, argument: str
) -> None:
    directory = skill_source / "data"
    directory.mkdir()
    (directory / "data.json").write_text("{}\n", encoding="utf-8")
    apply_reviewed(empty_forge, skill_source)
    plugin = empty_forge / "plugins" / "sample-skill"
    write_mcp(plugin, {"type": "stdio", "command": "python3", "args": [argument]})
    before = tree_snapshot(empty_forge)
    shutil.rmtree(directory)

    with pytest.raises(ForgeError, match=r"MCP server .* argument path"):
        reviewed_update(empty_forge, update_request(skill_source))

    assert tree_snapshot(empty_forge) == before


def test_update_preserves_empty_shared_mcp_working_directory(
    empty_forge: Path, skill_source: Path
) -> None:
    from agent_plugin_forge.generator import generate
    from agent_plugin_forge.validator import assert_valid_repository

    apply_reviewed(empty_forge, skill_source)
    plugin = empty_forge / "plugins" / "sample-skill"
    working_directory = plugin / "data" / "empty"
    working_directory.mkdir(parents=True)
    write_mcp(plugin, {"type": "stdio", "command": "python3", "cwd": "./data/empty"})
    generate(empty_forge)
    assert_valid_repository(empty_forge)
    original_mcp = (plugin / "mcp.json").read_bytes()
    (skill_source / "reference.txt").write_text("Reviewed update.\n", encoding="utf-8")

    plan = reviewed_update(empty_forge, update_request(skill_source))

    assert "data/empty" in plan.review_payload["targetState"]["directories"]
    assert working_directory.is_dir()
    assert list(working_directory.iterdir()) == []
    assert (plugin / "mcp.json").read_bytes() == original_mcp
    generate(empty_forge)
    assert_valid_repository(empty_forge)
