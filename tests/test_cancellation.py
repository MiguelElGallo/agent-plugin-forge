"""Exercise interruption before and after publication moves, including recovery itself."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import agent_plugin_forge.transactions as transactions_module
from agent_plugin_forge.common import ForgeError
from agent_plugin_forge.filesystem import tree_snapshot
from agent_plugin_forge.generator import generate, render_marketplaces
from agent_plugin_forge.importer import apply_import, apply_update, plan_import, plan_update

from .conftest import git
from .test_importer import apply_reviewed, request
from .test_updater import update_request


@pytest.mark.parametrize("interrupt", [KeyboardInterrupt, SystemExit])
@pytest.mark.parametrize("after_move", [False, True])
@pytest.mark.parametrize("phase", ["backup", "install", "catalog"])
def test_update_cancellation_restores_plugin_and_catalog(
    empty_forge: Path,
    skill_source: Path,
    monkeypatch: pytest.MonkeyPatch,
    interrupt: type[BaseException],
    after_move: bool,
    phase: str,
) -> None:
    apply_reviewed(empty_forge, skill_source)
    (skill_source / "reference.txt").write_bytes(b"Reviewed changed content\n")
    update = update_request(skill_source)
    plan = plan_update(empty_forge, update)
    plugin = empty_forge / "plugins/sample-skill"
    catalog = empty_forge / "catalog/plugins.json"
    before = tree_snapshot(empty_forge)
    real_replace = transactions_module.os.replace
    interrupted = False

    def cancel_once(source: Path, destination: Path) -> None:
        nonlocal interrupted
        selected = (
            (phase == "backup" and source == plugin)
            or (phase == "install" and destination == plugin)
            or (phase == "catalog" and destination == catalog)
        )
        if selected and not interrupted:
            interrupted = True
            if after_move:
                real_replace(source, destination)
            raise interrupt("simulated cancellation")
        real_replace(source, destination)

    monkeypatch.setattr(transactions_module.os, "replace", cancel_once)
    with pytest.raises(interrupt, match="simulated cancellation"):
        apply_update(empty_forge, update.model_copy(update={"expected_sha256": plan.plan_sha256}))

    assert interrupted
    assert tree_snapshot(empty_forge) == before
    assert not list(empty_forge.glob(".forge-import-*"))


@pytest.mark.parametrize("after_move", [False, True])
@pytest.mark.parametrize("phase", ["install", "catalog"])
def test_new_import_cancellation_restores_catalog_and_removes_new_plugin(
    empty_forge: Path,
    skill_source: Path,
    monkeypatch: pytest.MonkeyPatch,
    after_move: bool,
    phase: str,
) -> None:
    importing = request(skill_source)
    plan = plan_import(empty_forge, importing)
    git(empty_forge, "checkout", "-B", "skill/sample-skill/sample-skill")
    before = tree_snapshot(empty_forge)
    target = empty_forge / (
        "plugins/sample-skill" if phase == "install" else "catalog/plugins.json"
    )
    real_replace = transactions_module.os.replace
    interrupted = False

    def cancel_once(source: Path, destination: Path) -> None:
        nonlocal interrupted
        if destination == target and not interrupted:
            interrupted = True
            if after_move:
                real_replace(source, destination)
            raise KeyboardInterrupt
        real_replace(source, destination)

    monkeypatch.setattr(transactions_module.os, "replace", cancel_once)
    with pytest.raises(KeyboardInterrupt):
        apply_import(
            empty_forge, importing.model_copy(update={"expected_sha256": plan.plan_sha256})
        )
    assert interrupted
    assert tree_snapshot(empty_forge) == before
    assert not list(empty_forge.glob(".forge-import-*"))


@pytest.mark.parametrize("after_copy", [False, True])
def test_cancellation_during_catalog_backup_keeps_original_catalog(
    empty_forge: Path, skill_source: Path, monkeypatch: pytest.MonkeyPatch, after_copy: bool
) -> None:
    apply_reviewed(empty_forge, skill_source)
    update = update_request(skill_source)
    plan = plan_update(empty_forge, update)
    before = tree_snapshot(empty_forge)
    real_copy = transactions_module.shutil.copy2

    def cancel_catalog_copy(source: Path, destination: Path, **kwargs) -> None:
        if destination.name == "catalog-backup.json":
            if after_copy:
                real_copy(source, destination, **kwargs)
            else:
                destination.write_bytes(b"partial backup")
            raise KeyboardInterrupt
        real_copy(source, destination, **kwargs)

    monkeypatch.setattr(transactions_module.shutil, "copy2", cancel_catalog_copy)
    with pytest.raises(KeyboardInterrupt):
        apply_update(empty_forge, update.model_copy(update={"expected_sha256": plan.plan_sha256}))
    assert tree_snapshot(empty_forge) == before
    assert not list(empty_forge.glob(".forge-import-*"))


@pytest.mark.parametrize("after_move", [False, True])
@pytest.mark.parametrize("interrupt_at", [1, 2, 3, 4])
@pytest.mark.parametrize("interrupt", [KeyboardInterrupt, SystemExit])
def test_generation_cancellation_restores_every_original_output(
    empty_forge: Path,
    skill_source: Path,
    monkeypatch: pytest.MonkeyPatch,
    after_move: bool,
    interrupt_at: int,
    interrupt: type[BaseException],
) -> None:
    apply_reviewed(empty_forge, skill_source)
    generate(empty_forge)
    manifest = empty_forge / "plugins/sample-skill/plugin.json"
    metadata = json.loads(manifest.read_bytes())
    metadata["version"] = "0.2.0"
    manifest.write_text(json.dumps(metadata), encoding="utf-8")
    paths = list(render_marketplaces(empty_forge))
    before = {path: path.read_bytes() for path in paths}
    real_replace = transactions_module.os.replace
    calls = 0

    def cancel_once(source: Path, destination: Path) -> None:
        nonlocal calls
        calls += 1
        if calls == interrupt_at:
            if after_move:
                real_replace(source, destination)
            raise interrupt
        real_replace(source, destination)

    monkeypatch.setattr(transactions_module.os, "replace", cancel_once)
    with pytest.raises(interrupt):
        generate(empty_forge)
    assert calls >= interrupt_at
    assert {path: path.read_bytes() for path in paths} == before
    assert not list(empty_forge.glob(".forge-generate-*"))


@pytest.mark.parametrize("after_move", [False, True])
@pytest.mark.parametrize("interrupt_at", [1, 2])
def test_generation_cancellation_removes_new_outputs(
    empty_forge: Path,
    monkeypatch: pytest.MonkeyPatch,
    after_move: bool,
    interrupt_at: int,
) -> None:
    paths = list(render_marketplaces(empty_forge))
    real_replace = transactions_module.os.replace
    calls = 0

    def cancel_once(source: Path, destination: Path) -> None:
        nonlocal calls
        calls += 1
        if calls == interrupt_at:
            if after_move:
                real_replace(source, destination)
            raise KeyboardInterrupt
        real_replace(source, destination)

    monkeypatch.setattr(transactions_module.os, "replace", cancel_once)
    with pytest.raises(KeyboardInterrupt):
        generate(empty_forge)
    assert all(not path.exists() for path in paths)
    assert not list(empty_forge.glob(".forge-generate-*"))


@pytest.mark.parametrize("after_restore", [False, True])
def test_second_cancellation_preserves_recovery_and_restores_other_targets(
    empty_forge: Path,
    skill_source: Path,
    monkeypatch: pytest.MonkeyPatch,
    after_restore: bool,
) -> None:
    apply_reviewed(empty_forge, skill_source)
    generate(empty_forge)
    paths = list(render_marketplaces(empty_forge))
    before = {path: path.read_bytes() for path in paths}
    real_replace = transactions_module.os.replace

    def cancel_publish_and_recovery(source: Path, destination: Path) -> None:
        if destination == paths[1] and "staging" in source.parts:
            real_replace(source, destination)
            raise KeyboardInterrupt("publish cancellation")
        if destination == paths[1] and "backups" in source.parts:
            if after_restore:
                real_replace(source, destination)
            raise KeyboardInterrupt("recovery cancellation")
        real_replace(source, destination)

    monkeypatch.setattr(transactions_module.os, "replace", cancel_publish_and_recovery)
    with pytest.raises(ForgeError, match="recovery files preserved") as error:
        generate(empty_forge)
    (recovery,) = empty_forge.glob(".forge-generate-*")
    assert str(recovery) in str(error.value)
    assert paths[0].read_bytes() == before[paths[0]]
    original = (
        paths[1] if after_restore else recovery / "backups" / paths[1].relative_to(empty_forge)
    )
    assert original.read_bytes() == before[paths[1]]


@pytest.mark.parametrize("after_restore", [False, True])
def test_update_second_cancellation_preserves_plugin_and_catalog_recovery(
    empty_forge: Path,
    skill_source: Path,
    monkeypatch: pytest.MonkeyPatch,
    after_restore: bool,
) -> None:
    apply_reviewed(empty_forge, skill_source)
    update = update_request(skill_source)
    plan = plan_update(empty_forge, update)
    plugin = empty_forge / "plugins/sample-skill"
    catalog = empty_forge / "catalog/plugins.json"
    before = tree_snapshot(plugin)
    catalog_before = catalog.read_bytes()
    real_replace = transactions_module.os.replace

    def cancel_publish_and_recovery(source: Path, destination: Path) -> None:
        if source.name == "catalog.json" and destination == catalog:
            real_replace(source, destination)
            raise KeyboardInterrupt("publish cancellation")
        if source.name == "backup" and destination == plugin:
            if after_restore:
                real_replace(source, destination)
            raise KeyboardInterrupt("recovery cancellation")
        real_replace(source, destination)

    monkeypatch.setattr(transactions_module.os, "replace", cancel_publish_and_recovery)
    with pytest.raises(ForgeError, match="recovery files preserved") as error:
        apply_update(empty_forge, update.model_copy(update={"expected_sha256": plan.plan_sha256}))
    (recovery,) = empty_forge.glob(".forge-import-*")
    assert str(recovery) in str(error.value)
    assert catalog.read_bytes() == catalog_before
    assert tree_snapshot(plugin if after_restore else recovery / "backup") == before
