"""Generate client marketplace files safely and detect generated-file drift."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from .errors import ForgeError
from .filesystem import generated_path_errors
from .marketplaces import render_marketplaces


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


def _publish_transactionally(repo: Path, staging: Path, targets: list[Path], backups: Path) -> None:
    """Publish staged outputs atomically and restore backups after failure."""

    replaced: list[tuple[Path, Path | None]] = []
    try:
        for target in targets:
            staged = staging / target.relative_to(repo)
            target.parent.mkdir(parents=True, exist_ok=True)
            backup: Path | None = None
            if target.exists():
                backup = backups / target.relative_to(repo)
                backup.parent.mkdir(parents=True, exist_ok=True)
                os.replace(target, backup)
            replaced.append((target, backup))
            os.replace(staged, target)
    except Exception:
        for target, backup in reversed(replaced):
            if target.is_dir():
                shutil.rmtree(target)
            elif target.exists() or target.is_symlink():
                target.unlink()
            if backup is not None and backup.exists():
                backup.parent.mkdir(parents=True, exist_ok=True)
                os.replace(backup, target)
        raise


def generate(repo: Path) -> None:
    """Regenerate all client outputs atomically after complete staging validation."""
    rendered = render_marketplaces(repo)
    safety_errors = _output_safety_errors(repo, list(rendered))
    if safety_errors:
        raise ForgeError("Unsafe generated output:\n- " + "\n- ".join(safety_errors))

    with tempfile.TemporaryDirectory(prefix=".forge-generate-", dir=repo) as temporary:
        temporary_root = Path(temporary)
        staging = temporary_root / "staging"
        _stage_outputs(repo, staging, rendered)
        _publish_transactionally(
            repo,
            staging,
            [*rendered],
            temporary_root / "backups",
        )


def generation_drift(repo: Path) -> list[str]:
    """Compare checked-in generated files, bytes, and executable bits with a fresh render."""
    errors: list[str] = []
    rendered = render_marketplaces(repo)
    safety_errors = _output_safety_errors(repo, list(rendered))
    if safety_errors:
        return safety_errors
    for path, expected in rendered.items():
        if not path.is_file() or path.read_bytes() != expected:
            errors.append(f"Generated marketplace is stale: {path.relative_to(repo)}")
    if (repo / "compat" / "codex").exists():
        errors.append("Obsolete generated Codex wrapper tree remains at compat/codex")
    return errors
