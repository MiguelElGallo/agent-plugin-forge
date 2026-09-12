"""Generate client marketplace files safely and detect generated-file drift."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from .errors import ForgeError, diagnostic_value
from .filesystem import generated_path_errors
from .marketplaces import render_marketplaces


class _GenerationRecoveryError(ForgeError):
    """Signal incomplete rollback whose staged files and backups must be retained."""


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
    installed: set[Path] = set()
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
            installed.add(target)
    except Exception as publish_error:
        recovery_errors: list[str] = []
        for target, backup in reversed(replaced):
            try:
                if target in installed:
                    if target.is_dir():
                        shutil.rmtree(target)
                    elif target.exists() or target.is_symlink():
                        target.unlink()
                if backup is not None:
                    os.replace(backup, target)
            except Exception as recovery_error:
                recovery_errors.append(
                    f"{diagnostic_value(target.relative_to(repo).as_posix())}: "
                    f"{diagnostic_value(recovery_error)}"
                )
        if recovery_errors:
            raise _GenerationRecoveryError(
                f"Generation rollback failed; recovery files preserved at "
                f"{diagnostic_value(backups.parent)}. "
                "Inspect the affected outputs and restore any remaining backups "
                "before regenerating.\n- " + "\n- ".join(recovery_errors)
            ) from publish_error
        raise


def generate(repo: Path) -> None:
    """Regenerate all client outputs atomically after complete staging validation."""
    rendered = render_marketplaces(repo)
    safety_errors = _output_safety_errors(repo, list(rendered))
    if safety_errors:
        raise ForgeError("Unsafe generated output:\n- " + "\n- ".join(safety_errors))

    temporary_root = Path(tempfile.mkdtemp(prefix=".forge-generate-", dir=repo))
    preserve_recovery = False
    try:
        staging = temporary_root / "staging"
        _stage_outputs(repo, staging, rendered)
        _publish_transactionally(
            repo,
            staging,
            [*rendered],
            temporary_root / "backups",
        )
    except _GenerationRecoveryError:
        preserve_recovery = True
        raise
    finally:
        if not preserve_recovery:
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
