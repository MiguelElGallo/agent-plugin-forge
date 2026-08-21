from __future__ import annotations

from pathlib import Path

from agent_plugin_forge.common import file_hashes, load_json, tree_hash
from agent_plugin_forge.validator import _provenance_errors, _schema_errors, validate_repository


def test_closed_manifest_rejects_legacy_fields() -> None:
    repo = Path(__file__).parents[1]
    schema = load_json(repo / "schemas" / "agent-plugins" / "1.0.0" / "plugin.schema.json")
    errors = _schema_errors(
        {
            "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
            "name": "sample",
            "skills": "./skills/",
        },
        schema,
        "plugin.json",
    )
    assert any("Additional properties" in error for error in errors)


def test_provenance_requires_immutable_revision_and_license_evidence(
    tmp_path: Path, skill_source: Path
) -> None:
    plugin = tmp_path / "plugin"
    plugin.mkdir()
    hashes = file_hashes(skill_source)
    errors = _provenance_errors(
        plugin,
        "sample-skill",
        {
            "skill": "sample-skill",
            "origin": "local",
            "revision": "moving-main",
            "sourceSubpath": "../escape",
            "importedAt": "2026-08-21",
            "license": "MIT",
            "licenseEvidence": {"path": "../LICENSE", "sha256": "0" * 64},
            "files": hashes,
            "contentSha256": tree_hash(hashes),
            "transformations": [],
        },
        hashes,
    )
    assert any("not immutable" in error for error in errors)
    assert any("License evidence path is unsafe" in error for error in errors)


def test_checked_in_repository_is_valid() -> None:
    repo = Path(__file__).parents[1]
    assert validate_repository(repo) == []
