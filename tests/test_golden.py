from __future__ import annotations

from pathlib import Path

from agent_plugin_forge.generator import render_marketplaces


def test_checked_in_client_outputs_match_reviewed_goldens() -> None:
    repo = Path(__file__).parents[1]
    golden = repo / "tests" / "golden"
    rendered = render_marketplaces(repo)
    assert (
        rendered[repo / ".github" / "plugin" / "marketplace.json"]
        == (golden / "copilot-marketplace.json").read_bytes()
    )
    assert (
        rendered[repo / ".agents" / "plugins" / "marketplace.json"]
        == (golden / "codex-marketplace.json").read_bytes()
    )
