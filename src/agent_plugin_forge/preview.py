"""Render bounded, terminal-safe update diffs from verified approval snapshots."""

from __future__ import annotations

import difflib
import hashlib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from .common import contained_child, json_bytes
from .errors import ForgeError, diagnostic_value
from .filesystem import FileSnapshot, snapshot_regular_file, snapshot_regular_tree
from .importer import _forge_repository_url, _read_catalog, _target_state
from .models import ImportPlan, ImportRequest, ProvenanceRecord
from .sources import resolve_skill_source

MAX_DIFF_FILE_BYTES = 64 * 1024
MAX_DIFF_LINES = 1000
MAX_DIFF_OUTPUT_CHARS = 128 * 1024
MAX_DIFF_TOTAL_BYTES = 1024 * 1024


@dataclass(frozen=True)
class _Difference:
    """Keep labels and verified before/after bytes together for one comparison."""

    title: str
    before_path: str
    after_path: str
    before: FileSnapshot | None
    after: FileSnapshot | None
    show_modes: bool = True


def _digest(content: bytes) -> str:
    """Return a stable fingerprint for displayed or omitted content."""

    return hashlib.sha256(content).hexdigest()


def _captured_file(files: dict[str, FileSnapshot], relative: str) -> FileSnapshot:
    """Find evidence in captured bytes, retaining supported unambiguous case aliases."""

    relative = PurePosixPath(relative).as_posix()
    if relative in files:
        return files[relative]
    matches = [value for name, value in files.items() if name.casefold() == relative.casefold()]
    if len(matches) == 1:
        return matches[0]
    raise ForgeError(f"Cannot resolve reviewed evidence path: {diagnostic_value(relative)}")


def _capture_differences(repo: Path, request: ImportRequest, plan: ImportPlan) -> list[_Difference]:
    """Verify all rendered inputs before constructing comparisons without further reads."""

    if plan.operation != "update":
        raise ForgeError("Diff previews require an update plan")
    source = resolve_skill_source(request.source, request.source_skill)
    if source.hashes() != plan.files or source.modes() != plan.file_modes:
        raise ForgeError("Source changed after planning; generate and review a fresh plan")
    license_snapshot = snapshot_regular_file(request.license_file, file_label="License file")
    if _digest(license_snapshot.content) != plan.license_sha256:
        raise ForgeError("License changed after planning; generate and review a fresh plan")
    _, catalog_sha256 = _read_catalog(repo)
    if catalog_sha256 != plan.catalog_sha256 or _forge_repository_url(repo) != plan.repository_url:
        raise ForgeError("Catalog or Forge origin changed after planning; review a fresh plan")
    root = contained_child(repo / "plugins", plan.plugin, kind="plugin")
    captured = snapshot_regular_tree(
        root, required_root_file="plugin.json", tree_label="Destination plugin"
    )
    target = plan.review_payload["targetState"]
    if _target_state(root, target["catalogEntry"], files=captured) != target:
        raise ForgeError("Destination changed after planning; generate and review a fresh plan")
    installed = {path.relative_to(root).as_posix(): snapshot for path, snapshot in captured.items()}
    proposed = {
        source.relative_path(path): snapshot
        for path, snapshot in zip(source.files, source.snapshots, strict=True)
    }
    prefix = f"skills/{plan.skill}/"
    differences = [
        _Difference(
            title=prefix + path,
            before_path=prefix + path,
            after_path=prefix + path,
            before=installed.get(prefix + path),
            after=proposed.get(path),
        )
        for path in sorted({path for paths in plan.changes.values() for path in paths})
    ]
    record = ProvenanceRecord.model_validate_json(
        _captured_file(installed, f"provenance/{plan.skill}.json").content
    )
    metadata_fields = ("origin", "revision", "sourceSubpath", "importedAt", "transformations")
    previous_metadata = record.model_dump(mode="json", by_alias=True)
    metadata_path = f"provenance/{plan.skill}.json (selected metadata fields)"
    differences.insert(
        0,
        _Difference(
            title="Provenance metadata comparison (previous record -> proposed record)",
            before_path=metadata_path,
            after_path=metadata_path,
            before=FileSnapshot(
                json_bytes({field: previous_metadata[field] for field in metadata_fields}), False
            ),
            after=FileSnapshot(
                json_bytes({field: plan.review_payload[field] for field in metadata_fields}), False
            ),
            show_modes=False,
        ),
    )
    previous_license = _captured_file(installed, record.license_evidence.path)
    if _digest(previous_license.content) != record.license_evidence.sha256:
        raise ForgeError("Previous license evidence does not match its reviewed provenance")
    differences.append(
        _Difference(
            title="License evidence comparison (previous evidence -> proposed evidence)",
            before_path=record.license_evidence.path,
            after_path=plan.license_destination,
            before=previous_license,
            after=license_snapshot,
            show_modes=False,
        )
    )
    return differences


def _summary(side: str, path: str, snapshot: FileSnapshot | None, *, show_modes: bool) -> str:
    """Describe a comparison side, including byte count and digest for omitted text."""

    if snapshot is None:
        return f"{side}: absent\n"
    mode = f", executable {str(snapshot.executable).lower()}" if show_modes else ""
    return (
        f"{side}: {diagnostic_value(path)} "
        f"({len(snapshot.content)} bytes, sha256 {_digest(snapshot.content)}{mode})\n"
    )


def _text_lines(content: bytes) -> list[str] | None:
    """Decode UTF-8 while preserving LF, CRLF, and missing final newline distinctions."""

    if b"\x00" in content:
        return None
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        return None
    # splitlines() also splits CR and Unicode control characters, hiding byte changes.
    parts = text.split("\n")
    return [part + "\n" for part in parts[:-1]] + ([parts[-1]] if parts[-1] else [])


def _render_difference(difference: _Difference, remaining_bytes: int) -> tuple[str, int]:
    """Render one verified comparison with explicit binary and size-limit summaries."""

    before, after = difference.before, difference.after
    output = f"\nDiff: {diagnostic_value(difference.title)}\n"
    output += _summary("Before", difference.before_path, before, show_modes=difference.show_modes)
    output += _summary("After", difference.after_path, after, show_modes=difference.show_modes)
    if before is None:
        output += "File added.\n"
    elif after is None:
        output += "File removed.\n"
    if (
        difference.show_modes
        and before is not None
        and after is not None
        and before.executable != after.executable
    ):
        output += (
            f"Executable mode: {str(before.executable).lower()} -> "
            f"{str(after.executable).lower()}\n"
        )
    old = before.content if before is not None else b""
    new = after.content if after is not None else b""
    if old == new:
        return output + "Content unchanged (identical bytes).\n", 0
    size = len(old) + len(new)
    if max(len(old), len(new)) > MAX_DIFF_FILE_BYTES or size > remaining_bytes:
        return output + "Text diff omitted: byte limit reached; review the full files.\n", 0
    old_lines, new_lines = _text_lines(old), _text_lines(new)
    if old_lines is None or new_lines is None:
        return output + "Binary or non-UTF-8 content; text diff omitted.\n", size
    if max(len(old_lines), len(new_lines)) > MAX_DIFF_LINES:
        return output + "Text diff omitted: line limit reached; review the full files.\n", size
    lines = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile="a/" + difference.before_path if before is not None else "/dev/null",
        tofile="b/" + difference.after_path if after is not None else "/dev/null",
    )
    for line in lines:
        has_newline = line.endswith("\n")
        output += diagnostic_value(line[:-1] if has_newline else line) + "\n"
        if not has_newline:
            output += "\\ No newline at end of file\n"
    return output, size


def render_update_diff(repo: Path, request: ImportRequest, plan: ImportPlan) -> str:
    """Return a bounded, read-only preview whose displayed bytes match the approved plan."""

    differences = _capture_differences(repo, request, plan)
    output = (
        "Update diff preview (display only; plan hash unchanged).\n"
        "Controls are escaped; CRLF is shown as \\r and missing final LF is marked.\n"
        "License comparison does not imply removal of the previous evidence path.\n"
    )
    remaining_bytes = MAX_DIFF_TOTAL_BYTES
    for index, difference in enumerate(differences):
        rendered, used_bytes = _render_difference(difference, remaining_bytes)
        remaining_bytes -= used_bytes
        # Reserve room for a clear notice, never silently cut a hunk or escape sequence.
        if len(output) + len(rendered) > MAX_DIFF_OUTPUT_CHARS - 200:
            output += (
                f"\nDiff output limit reached: {len(differences) - index} comparisons omitted. "
                "Review the full files, provenance metadata, and license before approving.\n"
            )
            break
        output += rendered
    return output
