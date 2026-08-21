from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from agent_plugin_forge.common import ForgeError, load_json
from agent_plugin_forge.importer import ImportRequest, apply_import, plan_import


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
    return ImportRequest(**values)  # type: ignore[arg-type]


def apply_reviewed(repo: Path, source: Path, **overrides: object):
    import_request = request(source, **overrides)
    plan = plan_import(repo, import_request)
    return apply_import(repo, replace(import_request, expected_sha256=plan.plan_sha256))


def test_plan_does_not_write(empty_forge: Path, skill_source: Path) -> None:
    plan = plan_import(empty_forge, request(skill_source))
    assert plan.creates_plugin
    assert not (empty_forge / "plugins" / "sample-skill").exists()


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
        apply_import(empty_forge, replace(import_request, expected_sha256=plan.plan_sha256))


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
    request_b = replace(request_a, license_file=license_b, expected_sha256=plan_a.plan_sha256)
    with pytest.raises(ForgeError, match="full-plan hash"):
        apply_import(empty_forge, request_b)


def test_import_enforces_spdx_license_expressions(empty_forge: Path, skill_source: Path) -> None:
    with pytest.raises(ForgeError, match="valid SPDX"):
        plan_import(empty_forge, request(skill_source, license_id="definitely not SPDX"))
    plan = plan_import(empty_forge, request(skill_source, license_id="MIT OR Apache-2.0"))
    assert plan.skill == "sample-skill"


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
