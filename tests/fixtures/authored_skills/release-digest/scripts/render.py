"""Render deterministic release artifacts for an authored Forge behavior fixture."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SECTIONS = {
    "highlights": "Highlights",
    "changes": "Changes",
    "upgrade_notes": "Upgrade notes",
}


def single_line(value: object) -> bool:
    """Accept nonempty strings without line breaks or control characters."""

    return (
        isinstance(value, str)
        and bool(value.strip())
        and all(ord(character) >= 32 and ord(character) != 127 for character in value)
    )


def read_changes(path: Path) -> tuple[str, list[dict[str, Any]]]:
    """Validate the complete input before creating the requested output directory."""

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not single_line(data.get("version")):
        raise ValueError("Input requires a nonempty, single-line version.")
    changes = data.get("changes")
    if not isinstance(changes, list) or not changes:
        raise ValueError("Input requires a nonempty changes array.")
    for change in changes:
        if not isinstance(change, dict):
            raise ValueError("Every change must be an object.")
        section = change.get("section")
        if not isinstance(section, str) or section not in SECTIONS:
            raise ValueError("Change section must be highlights, changes, or upgrade_notes.")
        if not single_line(change.get("text")):
            raise ValueError("Change text must be a nonempty, single-line string.")
        references = change.get("references")
        if not isinstance(references, list) or not all(single_line(item) for item in references):
            raise ValueError("Change references must be an array of single-line strings.")
    return data["version"], changes


def render(version: str, changes: list[dict[str, Any]]) -> tuple[str, str]:
    """Preserve supplied text while producing stable Markdown and a machine-readable index."""

    lines = [f"# Release {version}", ""]
    counts = dict.fromkeys(SECTIONS, 0)
    references: list[str] = []
    for section, title in SECTIONS.items():
        selected = [change for change in changes if change["section"] == section]
        counts[section] = len(selected)
        if selected:
            lines.extend([f"## {title}", ""])
            for change in selected:
                suffix = f" ({', '.join(change['references'])})" if change["references"] else ""
                lines.append(f"- {change['text']}{suffix}")
            lines.append("")
    for change in changes:
        for reference in change["references"]:
            if reference not in references:
                references.append(reference)
    index = {
        "schema_version": 1,
        "version": version,
        "change_count": len(changes),
        "section_counts": counts,
        "reference_ids": references,
    }
    return "\n".join(lines), json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> None:
    """Write artifacts only into a new directory selected by the caller."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    arguments = parser.parse_args()
    try:
        version, changes = read_changes(arguments.input)
        markdown, index = render(version, changes)
        arguments.output_dir.mkdir()
        (arguments.output_dir / "release-notes.md").write_text(
            markdown, encoding="utf-8", newline="\n"
        )
        (arguments.output_dir / "release-index.json").write_text(
            index, encoding="utf-8", newline="\n"
        )
    except (OSError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
