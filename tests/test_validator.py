"""Test repository validation across schemas, packages, and provenance."""

from __future__ import annotations

import json
from pathlib import Path

from agent_plugin_forge.common import file_hashes, load_json, tree_hash
from agent_plugin_forge.validator import _provenance_errors, _schema_errors, validate_repository

from .test_importer import apply_reviewed


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
    assert any("revision" in error for error in errors)
    assert any("license evidence path" in error for error in errors)


def test_checked_in_repository_is_valid() -> None:
    repo = Path(__file__).parents[1]
    assert validate_repository(repo) == []


def test_validator_reports_invalid_mcp_without_crashing(
    empty_forge: Path, skill_source: Path
) -> None:
    apply_reviewed(empty_forge, skill_source)
    mcp_path = empty_forge / "plugins" / "sample-skill" / "mcp.json"
    mcp_path.write_text(
        json.dumps(
            {
                "$schema": "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json",
                "mcpServers": {
                    "unsafe": {
                        "type": "streamable-http",
                        "url": "http://example.com/mcp",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    errors = validate_repository(empty_forge)
    assert any("non-loopback MCP endpoints must use HTTPS" in error for error in errors)


def test_validator_reports_non_utf8_skill_without_crashing(
    empty_forge: Path, skill_source: Path
) -> None:
    apply_reviewed(empty_forge, skill_source)
    skill_md = empty_forge / "plugins" / "sample-skill" / "skills" / "sample-skill" / "SKILL.md"
    skill_md.write_bytes(b"\xff")
    errors = validate_repository(empty_forge)
    assert any("Cannot read Agent Skill metadata" in error for error in errors)


def test_validator_reports_non_utf8_json_without_crashing(
    empty_forge: Path, skill_source: Path
) -> None:
    apply_reviewed(empty_forge, skill_source)
    manifest = empty_forge / "plugins" / "sample-skill" / "plugin.json"
    manifest.write_bytes(b"\xff")
    errors = validate_repository(empty_forge)
    assert any("Cannot read JSON" in error for error in errors)


def test_validator_reports_duplicate_skill_names_across_plugins(
    empty_forge: Path, skill_source: Path
) -> None:
    apply_reviewed(empty_forge, skill_source)
    other_source = skill_source.parent / "other-skill"
    other_source.mkdir()
    (other_source / "SKILL.md").write_text(
        "---\nname: other-skill\ndescription: Other skill.\n---\n\nDo work.\n",
        encoding="utf-8",
    )
    apply_reviewed(empty_forge, other_source, plugin="other-plugin")
    duplicate = empty_forge / "plugins" / "other-plugin" / "skills" / "sample-skill"
    duplicate.mkdir()
    (duplicate / "SKILL.md").write_bytes((skill_source / "SKILL.md").read_bytes())
    errors = validate_repository(empty_forge)
    assert any("Duplicate skill name 'sample-skill'" in error for error in errors)


def test_validator_reports_provenance_mode_drift(empty_forge: Path, skill_source: Path) -> None:
    apply_reviewed(empty_forge, skill_source)
    provenance_path = empty_forge / "plugins" / "sample-skill" / "provenance" / "sample-skill.json"
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    provenance["fileModes"]["SKILL.md"] = True
    provenance_path.write_text(json.dumps(provenance), encoding="utf-8")
    assert any("executable-mode drift" in error for error in validate_repository(empty_forge))


def test_validator_reports_catalog_directory_drift(empty_forge: Path) -> None:
    (empty_forge / "plugins" / "uncatalogued").mkdir()
    errors = validate_repository(empty_forge)
    assert any("Catalog/plugin directory drift" in error for error in errors)


def test_validator_reports_malformed_schema_checksum_file(empty_forge: Path) -> None:
    checksum_path = empty_forge / "schemas" / "agent-plugins" / "1.0.0" / "SHA256SUMS"
    checksum_path.write_text("not-a-checksum-line\n", encoding="utf-8")
    errors = validate_repository(empty_forge)
    assert any("Invalid schema checksum entry" in error for error in errors)


def test_validator_requires_complete_schema_checksum_coverage(empty_forge: Path) -> None:
    checksum_path = empty_forge / "schemas" / "agent-plugins" / "1.0.0" / "SHA256SUMS"
    checksum_path.write_text(checksum_path.read_text().splitlines()[0] + "\n", encoding="utf-8")
    errors = validate_repository(empty_forge)
    assert any("checksum coverage differs" in error for error in errors)


def test_validator_rejects_checksum_path_traversal(empty_forge: Path) -> None:
    checksum_path = empty_forge / "schemas" / "agent-plugins" / "1.0.0" / "SHA256SUMS"
    checksum_path.write_text(f"{'0' * 64}  ../outside.json\n", encoding="utf-8")
    errors = validate_repository(empty_forge)
    assert any("Invalid schema checksum entry" in error for error in errors)


def test_validator_reports_non_utf8_schema_checksums(empty_forge: Path) -> None:
    checksum_path = empty_forge / "schemas" / "agent-plugins" / "1.0.0" / "SHA256SUMS"
    checksum_path.write_bytes(b"\xff")
    errors = validate_repository(empty_forge)
    assert any("Cannot read schema checksums" in error for error in errors)


def test_validator_rejects_empty_licenses_directory(empty_forge: Path, skill_source: Path) -> None:
    apply_reviewed(empty_forge, skill_source)
    plugin = empty_forge / "plugins" / "sample-skill"
    (plugin / "LICENSE").unlink()
    (plugin / "LICENSES").mkdir()
    errors = validate_repository(empty_forge)
    assert any("must distribute its declared license" in error for error in errors)
