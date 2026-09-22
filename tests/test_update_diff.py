"""Verify that update previews describe only approved captured bytes without writes."""

from __future__ import annotations

import hashlib
import os
from datetime import date
from pathlib import Path

import pytest

import agent_plugin_forge.preview as preview_module
from agent_plugin_forge.common import ForgeError
from agent_plugin_forge.filesystem import tree_snapshot
from agent_plugin_forge.importer import plan_update
from agent_plugin_forge.preview import render_update_diff

from .conftest import git
from .test_importer import apply_reviewed
from .test_updater import update_request


def test_update_diff_shows_all_changed_provenance_fields_when_skill_bytes_are_unchanged(
    empty_forge: Path, skill_source: Path
) -> None:
    apply_reviewed(empty_forge, skill_source, transformations=("Previous preparation",))
    request = update_request(
        skill_source,
        origin="https://example.com/reviewed-source",
        revision="abcdef0123456789abcdef0123456789abcdef01",
        source_subpath="reviewed/sample-skill",
        imported_at="2026-09-22",
        transformations=("Reviewed preparation", "Retained original instructions"),
    )
    plan = plan_update(empty_forge, request)
    original_plan = plan.model_dump(mode="json")
    before = tree_snapshot(empty_forge)

    output = render_update_diff(empty_forge, request, plan)

    assert not any(plan.changes.values())
    assert "Provenance metadata comparison" in output
    assert "provenance/sample-skill.json (selected metadata fields)" in output
    for old, new in (
        (
            '"origin": "https://example.com/source"',
            '"origin": "https://example.com/reviewed-source"',
        ),
        (
            '"revision": "0123456789abcdef0123456789abcdef01234567"',
            '"revision": "abcdef0123456789abcdef0123456789abcdef01"',
        ),
        ('"sourceSubpath": "skills/sample-skill"', '"sourceSubpath": "reviewed/sample-skill"'),
        ('"importedAt": "2026-08-21"', '"importedAt": "2026-09-22"'),
    ):
        assert f"-  {old}" in output
        assert f"+  {new}" in output
    assert '-    "Previous preparation"' in output
    assert '+    "Reviewed preparation"' in output
    assert '+    "Retained original instructions"' in output
    assert plan.model_dump(mode="json") == original_plan
    assert plan_update(empty_forge, request).plan_sha256 == plan.plan_sha256
    assert tree_snapshot(empty_forge) == before


def test_update_diff_reports_unchanged_provenance_metadata(
    empty_forge: Path, skill_source: Path
) -> None:
    apply_reviewed(empty_forge, skill_source)
    request = update_request(skill_source)
    plan = plan_update(empty_forge, request)

    output = render_update_diff(empty_forge, request, plan)

    metadata = output.split("Provenance metadata comparison", 1)[1].split("\nDiff:", 1)[0]
    assert "Content unchanged (identical bytes)." in metadata
    assert "--- a/" not in metadata


def test_update_diff_escapes_provenance_controls_and_distinguishes_literal_escapes(
    empty_forge: Path, skill_source: Path
) -> None:
    apply_reviewed(empty_forge, skill_source, transformations=("Tab:\tend",))
    request = update_request(
        skill_source,
        source_subpath="source\n\x1b[31m/sample-skill",
        transformations=("Tab:\\tend", "Changed\n\t\r\x1b[31m\x85metadata"),
    )
    plan = plan_update(empty_forge, request)

    output = render_update_diff(empty_forge, request, plan)

    assert '-    "Tab:\\tend"' in output
    assert '+    "Tab:\\\\tend"' in output
    assert '"sourceSubpath": "source\\n\\u001b[31m/sample-skill"' in output
    assert "Changed\\n\\t\\r\\u001b[31m\\x85metadata" in output
    assert not any(control in output for control in ("\t", "\r", "\x1b", "\x85"))


@pytest.mark.parametrize(
    ("transformation", "limit"),
    [("x" * (128 * 1024), "byte limit"), ("\x85" * 20000, "output limit")],
    ids=["oversized-metadata", "escaped-output-expansion"],
)
def test_update_diff_bounds_provenance_metadata_and_reports_omissions(
    empty_forge: Path, skill_source: Path, transformation: str, limit: str
) -> None:
    apply_reviewed(empty_forge, skill_source, transformations=(transformation + "previous",))
    request = update_request(skill_source, transformations=(transformation + "proposed",))
    plan = plan_update(empty_forge, request)

    output = render_update_diff(empty_forge, request, plan)

    assert len(output) <= preview_module.MAX_DIFF_OUTPUT_CHARS
    assert limit in output
    assert "omitted" in output
    assert "review" in output.lower()
    assert transformation not in output


def test_update_diff_provenance_uses_reviewed_plan_after_request_metadata_changes(
    empty_forge: Path, skill_source: Path
) -> None:
    apply_reviewed(empty_forge, skill_source)
    request = update_request(
        skill_source,
        origin="https://example.com/reviewed-source",
        revision="abcdef0123456789abcdef0123456789abcdef01",
        source_subpath="reviewed/source-path",
        imported_at="2026-09-22",
        transformations=("Reviewed transformation",),
    )
    plan = plan_update(empty_forge, request)
    original_plan = plan.model_dump(mode="json")
    changed = request.model_copy(
        update={
            "origin": "https://unreviewed.example/source",
            "revision": "f" * 40,
            "source_subpath": "unreviewed/path",
            "imported_at": date(2099, 1, 1),
            "transformations": ("Unreviewed transformation",),
        }
    )

    output = render_update_diff(empty_forge, changed, plan)

    assert "https://example.com/reviewed-source" in output
    assert "abcdef0123456789abcdef0123456789abcdef01" in output
    assert "reviewed/source-path" in output
    assert "2026-09-22" in output
    assert "Reviewed transformation" in output
    for unreviewed in (
        "unreviewed.example",
        "f" * 40,
        "unreviewed/path",
        "2099-01-01",
        "Unreviewed",
    ):
        assert unreviewed not in output
    assert plan.model_dump(mode="json") == original_plan


def test_update_diff_shows_changed_added_removed_and_empty_files_without_writes(
    empty_forge: Path, skill_source: Path
) -> None:
    (skill_source / "removed.txt").write_bytes(b"old removed instruction\n")
    (skill_source / "removed-empty.txt").write_bytes(b"")
    apply_reviewed(empty_forge, skill_source)
    (skill_source / "reference.txt").write_bytes(b"new reviewed instruction\n")
    (skill_source / "added.txt").write_bytes(b"new added instruction\n")
    (skill_source / "added-empty.txt").write_bytes(b"")
    (skill_source / "removed.txt").unlink()
    (skill_source / "removed-empty.txt").unlink()
    request = update_request(skill_source)
    plan = plan_update(empty_forge, request)
    original_plan = plan.model_dump(mode="json")
    before = tree_snapshot(empty_forge)
    source_before = tree_snapshot(skill_source)

    output = render_update_diff(empty_forge, request, plan)

    for filename in (
        "reference.txt",
        "removed.txt",
        "removed-empty.txt",
        "added.txt",
        "added-empty.txt",
    ):
        assert filename in output
    assert "-evidence" in output
    assert "+new reviewed instruction" in output
    assert "-old removed instruction" in output
    assert "+new added instruction" in output
    assert "added" in output.lower() and "removed" in output.lower()
    assert plan.model_dump(mode="json") == original_plan
    assert plan_update(empty_forge, request).plan_sha256 == plan.plan_sha256
    assert tree_snapshot(empty_forge) == before
    assert tree_snapshot(skill_source) == source_before


@pytest.mark.skipif(os.name == "nt", reason="Windows does not preserve POSIX executable bits")
def test_update_diff_reports_mode_only_changes(empty_forge: Path, skill_source: Path) -> None:
    script = skill_source / "helper.sh"
    script.write_bytes(b"# reviewed helper; never executed\n")
    script.chmod(0o644)
    apply_reviewed(empty_forge, skill_source)
    script.chmod(0o755)
    request = update_request(skill_source)
    plan = plan_update(empty_forge, request)

    output = render_update_diff(empty_forge, request, plan)

    assert "helper.sh" in output
    assert "executable" in output.lower() or "mode" in output.lower()
    assert plan.changes["mode_changed"] == ["helper.sh"]
    assert plan.changes["modified"] == []
    assert "-# reviewed helper" not in output
    assert "+# reviewed helper" not in output


@pytest.mark.parametrize(
    ("old", "new"),
    [
        (b"old\x00binary\n", b"new\x00binary\n"),
        (b"old\xffbytes\n", b"new\xfebytes\n"),
    ],
)
def test_update_diff_summarizes_binary_and_non_utf8_changes(
    empty_forge: Path, skill_source: Path, old: bytes, new: bytes
) -> None:
    asset = skill_source / "asset.bin"
    asset.write_bytes(old)
    apply_reviewed(empty_forge, skill_source)
    asset.write_bytes(new)
    request = update_request(skill_source)
    plan = plan_update(empty_forge, request)

    output = render_update_diff(empty_forge, request, plan)

    assert "asset.bin" in output
    assert hashlib.sha256(old).hexdigest() in output
    assert hashlib.sha256(new).hexdigest() in output
    assert str(len(old)) in output and str(len(new)) in output
    assert "bytes" in output.lower()
    assert "\x00" not in output
    assert "\ufffd" not in output


def test_update_diff_preserves_crlf_and_missing_final_newline_differences(
    empty_forge: Path, skill_source: Path
) -> None:
    text = skill_source / "line-endings.txt"
    text.write_bytes(b"first\r\nlast\r\n")
    apply_reviewed(empty_forge, skill_source)
    text.write_bytes(b"first\nlast")
    request = update_request(skill_source)
    plan = plan_update(empty_forge, request)

    output = render_update_diff(empty_forge, request, plan)

    assert "line-endings.txt" in output
    assert "-first" in output and "+first" in output
    assert "-last" in output and "+last" in output
    assert "\\r" in output or "CRLF" in output
    assert "newline" in output.lower()
    assert "\r" not in output


@pytest.mark.skipif(os.name == "nt", reason="Windows disallows controls in filenames")
def test_update_diff_escapes_hostile_filenames_and_content(
    empty_forge: Path, skill_source: Path
) -> None:
    filename = "note\n\x1b[31m\t.txt"
    text = skill_source / filename
    text.write_bytes(b"old\tcontent\x1b[31m\r\n")
    apply_reviewed(empty_forge, skill_source)
    text.write_bytes(b"new\tcontent\x1b[32m\r\n")
    request = update_request(skill_source)
    plan = plan_update(empty_forge, request)

    output = render_update_diff(empty_forge, request, plan)

    assert "note\\n" in output
    assert "\\x1b" in output
    assert "\\t" in output
    assert "old" in output and "new" in output
    assert "\x1b" not in output and "\t" not in output and "\r" not in output
    assert filename not in output


def test_update_diff_compares_before_escaping_content(
    empty_forge: Path, skill_source: Path
) -> None:
    text = skill_source / "escaped-text.txt"
    text.write_bytes(b"tab:\tend\n")
    apply_reviewed(empty_forge, skill_source)
    text.write_bytes(b"tab:\\tend\n")
    request = update_request(skill_source)
    plan = plan_update(empty_forge, request)

    output = render_update_diff(empty_forge, request, plan)

    assert "-tab:" in output
    assert "+tab:" in output
    assert "\t" not in output


def test_update_diff_compares_license_evidence_without_removing_shared_license(
    empty_forge: Path, skill_source: Path
) -> None:
    apply_reviewed(empty_forge, skill_source)
    plugin = empty_forge / "plugins" / "sample-skill"
    original_license = (plugin / "LICENSE").read_bytes()
    request = update_request(skill_source)
    request.license_file.write_bytes(b"New reviewed license evidence\n")
    plan = plan_update(empty_forge, request)
    before = tree_snapshot(plugin)

    output = render_update_diff(empty_forge, request, plan)

    assert "LICENSE" in output
    assert plan.license_destination in output
    assert "-Test license evidence" in output
    assert "+New reviewed license evidence" in output
    assert any(text in output.lower() for text in ("preserv", "retain", "does not imply removal"))
    assert (plugin / "LICENSE").read_bytes() == original_license
    assert not (plugin / plan.license_destination).exists()
    assert tree_snapshot(plugin) == before


def test_update_diff_reports_license_path_when_evidence_bytes_are_unchanged(
    empty_forge: Path, skill_source: Path
) -> None:
    apply_reviewed(empty_forge, skill_source)
    request = update_request(skill_source)
    plan = plan_update(empty_forge, request)

    output = render_update_diff(empty_forge, request, plan)

    assert "LICENSE" in output
    assert plan.license_destination in output
    assert "unchanged" in output.lower() or "identical" in output.lower()


@pytest.mark.parametrize(
    "drift",
    [
        "source-content",
        "source-paths",
        "license",
        "destination-content",
        "destination-directory",
        "catalog",
        "origin",
        pytest.param(
            "source-mode",
            marks=pytest.mark.skipif(os.name == "nt", reason="POSIX executable mode required"),
        ),
        pytest.param(
            "destination-mode",
            marks=pytest.mark.skipif(os.name == "nt", reason="POSIX executable mode required"),
        ),
    ],
)
def test_update_diff_rejects_drift_without_rendering_unverified_bytes(
    empty_forge: Path, skill_source: Path, drift: str, capsys: pytest.CaptureFixture[str]
) -> None:
    apply_reviewed(empty_forge, skill_source)
    request = update_request(skill_source)
    plan = plan_update(empty_forge, request)
    plugin = empty_forge / "plugins" / "sample-skill"
    marker = b"unreviewed content must not appear\n"
    if drift == "source-content":
        (skill_source / "reference.txt").write_bytes(marker)
    elif drift == "source-paths":
        (skill_source / "unexpected.txt").write_bytes(marker)
    elif drift == "source-mode":
        (skill_source / "reference.txt").chmod(0o755)
    elif drift == "license":
        request.license_file.write_bytes(marker)
    elif drift == "destination-content":
        (plugin / "shared.txt").write_bytes(marker)
    elif drift == "destination-directory":
        (plugin / "empty-shared-directory").mkdir()
    elif drift == "catalog":
        catalog = empty_forge / "catalog" / "plugins.json"
        catalog.write_bytes(catalog.read_bytes() + b"\n")
    elif drift == "origin":
        git(empty_forge, "remote", "set-url", "origin", "https://example.com/other-forge.git")
    else:
        (plugin / "skills" / "sample-skill" / "reference.txt").chmod(0o755)
    before = tree_snapshot(empty_forge)

    with pytest.raises(ForgeError) as error:
        render_update_diff(empty_forge, request, plan)

    assert marker.decode().strip() not in str(error.value)
    assert capsys.readouterr().out == ""
    assert tree_snapshot(empty_forge) == before


@pytest.mark.parametrize("capture", ["source", "destination", "license"])
def test_update_diff_uses_verified_snapshots_after_files_change_on_disk(
    empty_forge: Path,
    skill_source: Path,
    capture: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    reference = skill_source / "reference.txt"
    reference.write_bytes(b"old captured instruction\n")
    apply_reviewed(empty_forge, skill_source)
    reference.write_bytes(b"new captured instruction\n")
    request = update_request(skill_source)
    request.license_file.write_bytes(b"new captured license\n")
    plan = plan_update(empty_forge, request)
    plugin = empty_forge / "plugins" / "sample-skill"
    marker = b"unverified post-capture replacement\n"
    mutated = False

    if capture == "source":
        real_resolve = preview_module.resolve_skill_source

        def resolve_then_change(*args, **kwargs):
            nonlocal mutated
            snapshot = real_resolve(*args, **kwargs)
            reference.write_bytes(marker)
            mutated = True
            return snapshot

        monkeypatch.setattr(preview_module, "resolve_skill_source", resolve_then_change)
    elif capture == "destination":
        real_tree = preview_module.snapshot_regular_tree

        def snapshot_then_change(*args, **kwargs):
            nonlocal mutated
            snapshot = real_tree(*args, **kwargs)
            (plugin / "skills" / "sample-skill" / "reference.txt").write_bytes(marker)
            (plugin / "LICENSE").write_bytes(marker)
            (plugin / "provenance" / "sample-skill.json").write_bytes(marker)
            mutated = True
            return snapshot

        monkeypatch.setattr(preview_module, "snapshot_regular_tree", snapshot_then_change)
    else:
        real_file = preview_module.snapshot_regular_file

        def license_then_change(*args, **kwargs):
            nonlocal mutated
            snapshot = real_file(*args, **kwargs)
            request.license_file.write_bytes(marker)
            mutated = True
            return snapshot

        monkeypatch.setattr(preview_module, "snapshot_regular_file", license_then_change)

    output = render_update_diff(empty_forge, request, plan)

    assert mutated
    assert "-old captured instruction" in output
    assert "+new captured instruction" in output
    assert "-Test license evidence" in output
    assert "+new captured license" in output
    assert marker.decode().strip() not in output
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize(
    ("limit", "value", "old", "new"),
    [
        ("MAX_DIFF_FILE_BYTES", 8, b"old bounding payload\n", b"new bounding payload\n"),
        ("MAX_DIFF_LINES", 1, b"old first\nold second\n", b"new first\nnew second\n"),
        ("MAX_DIFF_TOTAL_BYTES", 8, b"old bounding payload\n", b"new bounding payload\n"),
    ],
)
def test_update_diff_marks_resource_limited_comparisons_with_hashes_and_sizes(
    empty_forge: Path,
    skill_source: Path,
    monkeypatch: pytest.MonkeyPatch,
    limit: str,
    value: int,
    old: bytes,
    new: bytes,
) -> None:
    text = skill_source / "bounded.txt"
    text.write_bytes(old)
    apply_reviewed(empty_forge, skill_source)
    text.write_bytes(new)
    request = update_request(skill_source)
    plan = plan_update(empty_forge, request)
    monkeypatch.setattr(preview_module, limit, value)

    output = render_update_diff(empty_forge, request, plan)

    assert "bounded.txt" in output
    assert "omitted" in output.lower() and "limit" in output.lower()
    assert hashlib.sha256(old).hexdigest() in output
    assert hashlib.sha256(new).hexdigest() in output
    assert str(len(old)) in output and str(len(new)) in output
    assert "bytes" in output.lower()
    assert "-old bounding payload" not in output
    assert "+new bounding payload" not in output
    assert "-old first" not in output
    assert "+new first" not in output


def test_update_diff_caps_total_output_and_reports_omitted_comparisons(
    empty_forge: Path, skill_source: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for index in range(5):
        (skill_source / f"content-{index}.txt").write_bytes(b"old content\n")
    apply_reviewed(empty_forge, skill_source)
    for index in range(5):
        (skill_source / f"content-{index}.txt").write_bytes(b"new content\n")
    request = update_request(skill_source)
    plan = plan_update(empty_forge, request)
    monkeypatch.setattr(preview_module, "MAX_DIFF_OUTPUT_CHARS", 1024)

    output = render_update_diff(empty_forge, request, plan)

    assert len(output) <= 1024
    assert "output limit" in output.lower()
    assert "omitted" in output.lower()
    assert "review" in output.lower()
