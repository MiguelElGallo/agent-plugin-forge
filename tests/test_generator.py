from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

import agent_plugin_forge.generator as generator_module
from agent_plugin_forge.common import ForgeError
from agent_plugin_forge.generator import generate, generation_drift, render_marketplaces

from .test_importer import apply_reviewed


def test_generation_is_idempotent(empty_forge: Path, skill_source: Path) -> None:
    apply_reviewed(empty_forge, skill_source)
    generate(empty_forge)
    first = (empty_forge / ".github" / "plugin" / "marketplace.json").read_bytes()
    generate(empty_forge)
    assert (empty_forge / ".github" / "plugin" / "marketplace.json").read_bytes() == first
    assert generation_drift(empty_forge) == []


def test_copilot_and_codex_outputs_are_distinct(empty_forge: Path, skill_source: Path) -> None:
    apply_reviewed(empty_forge, skill_source)
    generate(empty_forge)
    copilot = (empty_forge / ".github" / "plugin" / "marketplace.json").read_text()
    codex = (empty_forge / ".agents" / "plugins" / "marketplace.json").read_text()
    assert '"owner"' in copilot
    assert '"policy"' in codex
    assert '"owner"' not in codex
    assert '"path": "./plugins/sample-skill"' in codex


def test_catalog_traversal_is_rejected_before_io(empty_forge: Path) -> None:
    catalog_path = empty_forge / "catalog" / "plugins.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    catalog["plugins"] = [{"name": "../escape", "category": "Unsafe", "codexCompatibility": True}]
    catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
    with pytest.raises(ForgeError, match="Invalid plugin name"):
        render_marketplaces(empty_forge)
    assert not (empty_forge.parent / "escape").exists()


def test_marketplace_metadata_enforces_name_and_description_limits(empty_forge: Path) -> None:
    catalog_path = empty_forge / "catalog" / "plugins.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    catalog["marketplace"]["name"] = "Invalid Name"
    catalog["marketplace"]["description"] = "x" * 1025
    catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
    with pytest.raises(ForgeError, match="Invalid catalog"):
        render_marketplaces(empty_forge)


@pytest.mark.skipif(os.name == "nt", reason="Windows symlink creation requires extra privileges")
def test_generation_rejects_skill_symlink(empty_forge: Path, skill_source: Path) -> None:
    apply_reviewed(empty_forge, skill_source)
    copied = empty_forge / "plugins" / "sample-skill" / "skills" / "sample-skill"
    (copied / "unsafe-link").symlink_to(Path("/etc/hosts"))
    with pytest.raises(ForgeError, match="Links and junctions are not accepted"):
        generate(empty_forge)


@pytest.mark.skipif(os.name == "nt", reason="Windows symlink creation requires extra privileges")
def test_generation_refuses_symlinked_marketplace_output(
    empty_forge: Path, skill_source: Path, tmp_path: Path
) -> None:
    apply_reviewed(empty_forge, skill_source)
    generate(empty_forge)
    marketplace = empty_forge / ".github" / "plugin" / "marketplace.json"
    victim = tmp_path / "victim.json"
    victim.write_text("do not overwrite\n", encoding="utf-8")
    marketplace.unlink()
    marketplace.symlink_to(victim)
    with pytest.raises(ForgeError, match="symlink"):
        generate(empty_forge)
    assert victim.read_text(encoding="utf-8") == "do not overwrite\n"


def test_manifest_identity_cannot_change_generated_paths(
    empty_forge: Path, skill_source: Path
) -> None:
    apply_reviewed(empty_forge, skill_source)
    manifest_path = empty_forge / "plugins" / "sample-skill" / "plugin.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["name"] = "../../escape"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ForgeError, match="Invalid portable manifest|identity differ"):
        render_marketplaces(empty_forge)


def test_generation_rolls_back_every_output_on_publish_failure(
    empty_forge: Path,
    skill_source: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    apply_reviewed(empty_forge, skill_source)
    generate(empty_forge)
    paths = [
        empty_forge / ".github" / "plugin" / "marketplace.json",
        empty_forge / ".agents" / "plugins" / "marketplace.json",
    ]
    before = {path: path.read_bytes() for path in paths}
    manifest_path = empty_forge / "plugins" / "sample-skill" / "plugin.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["version"] = "0.2.0"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    real_replace = generator_module.os.replace
    calls = 0

    def fail_second_output(source: Path, destination: Path) -> None:
        nonlocal calls
        calls += 1
        if calls == 4:
            raise OSError("simulated generated-output publish failure")
        real_replace(source, destination)

    monkeypatch.setattr(generator_module.os, "replace", fail_second_output)
    with pytest.raises(OSError, match="simulated"):
        generate(empty_forge)
    assert {path: path.read_bytes() for path in paths} == before


def test_drift_rejects_obsolete_codex_wrapper_tree(empty_forge: Path, skill_source: Path) -> None:
    apply_reviewed(empty_forge, skill_source)
    generate(empty_forge)
    (empty_forge / "compat" / "codex").mkdir(parents=True)
    assert generation_drift(empty_forge) == [
        "Obsolete generated Codex wrapper tree remains at compat/codex"
    ]
