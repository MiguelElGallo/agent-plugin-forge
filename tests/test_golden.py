"""Test generated client marketplace files against reviewed golden files."""

from __future__ import annotations

import json
from pathlib import Path

from agent_plugin_forge.generator import render_marketplaces

from .test_importer import apply_reviewed


def test_fixture_client_outputs_match_reviewed_goldens(
    empty_forge: Path, skill_source: Path
) -> None:
    repo = Path(__file__).parents[1]
    golden = repo / "tests" / "golden"
    apply_reviewed(empty_forge, skill_source)
    rendered = render_marketplaces(empty_forge)
    assert (
        rendered[empty_forge / ".github" / "plugin" / "marketplace.json"]
        == (golden / "copilot-marketplace.json").read_bytes()
    )
    assert (
        rendered[empty_forge / ".agents" / "plugins" / "marketplace.json"]
        == (golden / "codex-marketplace.json").read_bytes()
    )


def test_rendered_versions_come_from_fixture_metadata(
    empty_forge: Path, skill_source: Path
) -> None:
    apply_reviewed(empty_forge, skill_source, version="4.5.6")
    catalog_path = empty_forge / "catalog" / "plugins.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    catalog["marketplace"]["version"] = "7.8.9"
    catalog_path.write_text(json.dumps(catalog), encoding="utf-8")

    rendered = render_marketplaces(empty_forge)
    copilot = json.loads(rendered[empty_forge / ".github" / "plugin" / "marketplace.json"])
    assert copilot["name"] == "test-forge"
    assert copilot["metadata"]["version"] == "7.8.9"
    assert copilot["plugins"][0]["name"] == "sample-skill"
    assert copilot["plugins"][0]["version"] == "4.5.6"
