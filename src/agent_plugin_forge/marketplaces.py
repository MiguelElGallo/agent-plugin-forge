"""Render client-specific marketplaces from the portable package catalog."""

from __future__ import annotations

from pathlib import Path

from .common import json_bytes
from .models import CodexMarketplace, CopilotMarketplace
from .packages import load_packages


def render_marketplaces(repo: Path) -> dict[Path, bytes]:
    """Render client-specific marketplace schemas from one validated catalog."""
    catalog, packages = load_packages(repo)
    copilot = CopilotMarketplace.model_validate(
        {
            "name": catalog.marketplace.name,
            "owner": catalog.marketplace.owner.model_dump(),
            "metadata": {
                "description": catalog.marketplace.description,
                "version": catalog.marketplace.version,
            },
            "plugins": [
                {
                    "name": package.manifest.name,
                    "description": package.manifest.description,
                    "version": package.manifest.version,
                    "source": f"./plugins/{package.entry.name}",
                }
                for package in packages
            ],
        }
    )
    codex = CodexMarketplace.model_validate(
        {
            "name": catalog.marketplace.name,
            "interface": {"displayName": catalog.marketplace.display_name},
            "plugins": [
                {
                    "name": package.entry.name,
                    "source": {
                        "source": "local",
                        "path": f"./plugins/{package.entry.name}",
                    },
                    "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
                    "category": package.entry.category,
                }
                for package in packages
                if package.entry.codex_compatibility
            ],
        }
    )
    return {
        repo / ".github" / "plugin" / "marketplace.json": json_bytes(
            copilot.model_dump(mode="json", by_alias=True)
        ),
        repo / ".agents" / "plugins" / "marketplace.json": json_bytes(
            codex.model_dump(mode="json", by_alias=True)
        ),
    }
