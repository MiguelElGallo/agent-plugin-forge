"""Generate client marketplace files safely and detect generated-file drift."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from .errors import ForgeError, diagnostic_value
from .filesystem import generated_path_errors
from .marketplaces import render_marketplaces
from .transactions import Replacement, ReplacementTransaction


def _output_safety_errors(repo: Path, marketplace_paths: list[Path]) -> list[str]:
    """Collect safety errors for generated marketplace output paths."""

    return [
        error
        for path in marketplace_paths
        for error in generated_path_errors(repo, path, directory=False)
    ]


def _stage_outputs(repo: Path, staging: Path, rendered: dict[Path, bytes]) -> None:
    """Write rendered marketplace files into a temporary staging tree."""

    for path, content in rendered.items():
        staged = staging / path.relative_to(repo)
        staged.parent.mkdir(parents=True, exist_ok=True)
        staged.write_bytes(content)


def generate(repo: Path) -> None:
    """Regenerate staged client outputs with rollback and cancellation recovery."""
    rendered = render_marketplaces(repo)
    safety_errors = _output_safety_errors(repo, list(rendered))
    if safety_errors:
        raise ForgeError("Unsafe generated output:\n- " + "\n- ".join(safety_errors))

    temporary_root = Path(tempfile.mkdtemp(prefix=".forge-generate-", dir=repo))
    transaction = ReplacementTransaction(temporary_root, "Generation")
    try:
        staging = temporary_root / "staging"
        _stage_outputs(repo, staging, rendered)
        transaction.publish(
            [
                Replacement(
                    staging / target.relative_to(repo),
                    target,
                    temporary_root / "backups" / target.relative_to(repo),
                )
                for target in rendered
            ]
        )
    finally:
        if not transaction.preserve_recovery:
            shutil.rmtree(temporary_root)


def generation_drift(repo: Path) -> list[str]:
    """Compare checked-in generated files, bytes, and executable bits with a fresh render."""
    errors: list[str] = []
    rendered = render_marketplaces(repo)
    safety_errors = _output_safety_errors(repo, list(rendered))
    if safety_errors:
        return safety_errors
    for path, expected in rendered.items():
        if not path.is_file() or path.read_bytes() != expected:
            errors.append(
                f"Generated marketplace is stale: {diagnostic_value(path.relative_to(repo))}"
            )
    if (repo / "compat" / "codex").exists():
        errors.append("Obsolete generated Codex wrapper tree remains at compat/codex")
    return errors
