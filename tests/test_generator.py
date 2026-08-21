from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

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
    assert (empty_forge / "compat" / "codex" / "plugins" / "sample-skill" / "LICENSE").is_file()


def test_catalog_traversal_is_rejected_before_io(empty_forge: Path) -> None:
    catalog_path = empty_forge / "catalog" / "plugins.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    catalog["plugins"] = [{"name": "../escape", "category": "Unsafe", "codexCompatibility": True}]
    catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
    with pytest.raises(ForgeError, match="Invalid plugin name"):
        render_marketplaces(empty_forge)
    assert not (empty_forge.parent / "escape").exists()


@pytest.mark.skipif(os.name == "nt", reason="Windows symlink creation requires extra privileges")
def test_generation_rejects_skill_symlink(empty_forge: Path, skill_source: Path) -> None:
    apply_reviewed(empty_forge, skill_source)
    copied = empty_forge / "plugins" / "sample-skill" / "skills" / "sample-skill"
    (copied / "unsafe-link").symlink_to(Path("/etc/hosts"))
    with pytest.raises(ForgeError, match="Unsafe file"):
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


@pytest.mark.skipif(os.name == "nt", reason="Windows symlink creation requires extra privileges")
def test_drift_rejects_symlinked_wrapper_file(empty_forge: Path, skill_source: Path) -> None:
    apply_reviewed(empty_forge, skill_source)
    generate(empty_forge)
    wrapper_skill = (
        empty_forge
        / "compat"
        / "codex"
        / "plugins"
        / "sample-skill"
        / "skills"
        / "sample-skill"
        / "SKILL.md"
    )
    portable_skill = (
        empty_forge / "plugins" / "sample-skill" / "skills" / "sample-skill" / "SKILL.md"
    )
    wrapper_skill.unlink()
    wrapper_skill.symlink_to(portable_skill)
    assert any("symlink" in error for error in generation_drift(empty_forge))


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


def test_codex_compatibility_requires_rich_identity(empty_forge: Path, skill_source: Path) -> None:
    apply_reviewed(empty_forge, skill_source)
    manifest_path = empty_forge / "plugins" / "sample-skill" / "plugin.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    del manifest["description"]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ForgeError, match="requires description"):
        render_marketplaces(empty_forge)


def test_codex_compatibility_rejects_non_https_urls(empty_forge: Path, skill_source: Path) -> None:
    apply_reviewed(empty_forge, skill_source)
    manifest_path = empty_forge / "plugins" / "sample-skill" / "plugin.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["author"]["url"] = "http://example.com"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ForgeError, match="Invalid generated Codex manifest"):
        generate(empty_forge)


def test_codex_compatibility_rejects_todo_markers(empty_forge: Path, skill_source: Path) -> None:
    apply_reviewed(empty_forge, skill_source)
    manifest_path = empty_forge / "plugins" / "sample-skill" / "plugin.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["description"] = "[TODO: replace me]"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ForgeError, match=r"\[TODO:"):
        generate(empty_forge)
