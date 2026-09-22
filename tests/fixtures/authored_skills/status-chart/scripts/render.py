"""Render deterministic SVG and JSON artifacts for an authored Forge behavior fixture."""

from __future__ import annotations

import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

COLORS = ("#2563eb", "#7c3aed", "#d97706", "#64748b")


def single_line(value: object) -> bool:
    """Accept nonempty strings without line breaks or control characters."""

    return (
        isinstance(value, str)
        and bool(value.strip())
        and all(ord(character) >= 32 and ord(character) != 127 for character in value)
    )


def read_statuses(path: Path) -> tuple[str, list[dict[str, Any]]]:
    """Validate all labels and counts before creating any output files."""

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not single_line(data.get("title")):
        raise ValueError("Input requires a nonempty, single-line title.")
    statuses = data.get("statuses")
    if not isinstance(statuses, list) or not 1 <= len(statuses) <= 16:
        raise ValueError("Input requires between one and sixteen statuses.")
    labels: set[str] = set()
    for status in statuses:
        if not isinstance(status, dict) or not single_line(status.get("label")):
            raise ValueError("Every status requires a nonempty, single-line label.")
        label = status["label"]
        if label in labels:
            raise ValueError("Status labels must be unique.")
        labels.add(label)
        count = status.get("count")
        if isinstance(count, bool) or not isinstance(count, int) or not 0 <= count <= 1_000_000:
            raise ValueError("Status count must be an integer from zero to one million.")
    return data["title"], statuses


def render(title: str, statuses: list[dict[str, Any]]) -> tuple[str, str]:
    """Produce escaped SVG markup and an exact summary without external dependencies."""

    maximum = max(status["count"] for status in statuses)
    total = sum(status["count"] for status in statuses)
    height = 90 + 48 * len(statuses)
    root = ET.Element(
        "svg",
        {
            "xmlns": "http://www.w3.org/2000/svg",
            "viewBox": f"0 0 720 {height}",
            "role": "img",
            "aria-labelledby": "chart-title chart-description",
        },
    )
    ET.SubElement(root, "title", {"id": "chart-title"}).text = title
    ET.SubElement(
        root, "desc", {"id": "chart-description"}
    ).text = (
        f"{len(statuses)} categories; total {total}. Bars preserve the supplied category order."
    )
    ET.SubElement(root, "rect", {"width": "720", "height": str(height), "fill": "#ffffff"})
    ET.SubElement(root, "text", {"x": "24", "y": "32", "font-size": "18"}).text = title
    for index, status in enumerate(statuses):
        y = 60 + 48 * index
        label, count = status["label"], status["count"]
        ET.SubElement(root, "text", {"x": "24", "y": str(y + 20), "font-size": "14"}).text = label
        ET.SubElement(
            root,
            "rect",
            {
                "x": "210",
                "y": str(y),
                "width": str(count * 420 // maximum if maximum else 0),
                "height": "28",
                "fill": COLORS[index % len(COLORS)],
                "data-label": label,
                "data-count": str(count),
            },
        )
        ET.SubElement(root, "text", {"x": "650", "y": str(y + 20), "font-size": "14"}).text = str(
            count
        )
    ET.indent(root, space="  ")
    summary = {
        "schema_version": 1,
        "title": title,
        "statuses": [{"label": item["label"], "count": item["count"]} for item in statuses],
        "total": total,
        "max_count": maximum,
    }
    return (
        ET.tostring(root, encoding="unicode") + "\n",
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )


def main() -> None:
    """Write both artifacts into a new output directory without overwriting existing work."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    arguments = parser.parse_args()
    try:
        title, statuses = read_statuses(arguments.input)
        svg, summary = render(title, statuses)
        arguments.output_dir.mkdir()
        (arguments.output_dir / "status.svg").write_text(svg, encoding="utf-8", newline="\n")
        (arguments.output_dir / "status-summary.json").write_text(
            summary, encoding="utf-8", newline="\n"
        )
    except (OSError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
