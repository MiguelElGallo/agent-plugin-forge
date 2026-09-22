"""Replace staged paths with cancellation-aware rollback and retained recovery data."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from .errors import ForgeError, diagnostic_value
from .filesystem import is_linklike


@dataclass(frozen=True)
class Replacement:
    """Describe one validated stage, destination, and private backup path."""

    staged: Path
    target: Path
    backup: Path
    copy_backup: bool = False


def _exists(path: Path) -> bool:
    """Include dangling links when deciding whether a path can be removed."""

    return path.exists() or path.is_symlink()


def _remove(path: Path) -> None:
    """Remove an installed path without following a link into another tree."""

    if path.is_dir() and not is_linklike(path):
        shutil.rmtree(path)
    elif _exists(path):
        path.unlink()


def _restore(replacement: Replacement, had_original: bool) -> None:
    """Infer completed moves from disk, including an interrupted successful rename."""

    staged, target, backup = replacement.staged, replacement.target, replacement.backup
    stage_remains = _exists(staged)
    target_exists = _exists(target)
    backup_exists = _exists(backup)
    if not had_original:
        if stage_remains and target_exists:
            raise ForgeError("Unexpected destination appeared before installation")
        if not stage_remains:
            _remove(target)
        return
    # A copied catalog backup leaves the original in place until installation.
    # If the stage remains, an interrupted backup copy is never used for recovery.
    if replacement.copy_backup and stage_remains:
        if not target_exists:
            raise ForgeError("Original destination disappeared before installation")
        return
    if backup_exists:
        if stage_remains and target_exists:
            raise ForgeError("Destination and backup both exist before installation")
        _remove(target)
        os.replace(backup, target)
    elif not (stage_remains and target_exists):
        raise ForgeError("Cannot establish the original destination; retain recovery files")


class ReplacementTransaction:
    """Keep backups until every replacement or every rollback is known to be complete."""

    def __init__(self, recovery_root: Path, label: str) -> None:
        """Initialize cleanup permission before any destructive operation starts."""

        self.recovery_root = recovery_root
        self.label = label
        self.preserve_recovery = False

    def publish(self, replacements: list[Replacement]) -> None:
        """Publish validated paths, restoring originals on errors or ordinary cancellation."""

        journal: list[tuple[Replacement, bool]] = []
        # Default to retention throughout publication and recovery. Signals between
        # Python statements must not permit callers to delete the only backup.
        self.preserve_recovery = True
        try:
            for replacement in replacements:
                had_original = _exists(replacement.target)
                journal.append((replacement, had_original))
                replacement.target.parent.mkdir(parents=True, exist_ok=True)
                if had_original:
                    replacement.backup.parent.mkdir(parents=True, exist_ok=True)
                    if replacement.copy_backup:
                        shutil.copy2(replacement.target, replacement.backup)
                    else:
                        os.replace(replacement.target, replacement.backup)
                os.replace(replacement.staged, replacement.target)
        except BaseException as publish_error:
            recovery_errors: list[str] = []
            for replacement, had_original in reversed(journal):
                try:
                    _restore(replacement, had_original)
                except BaseException as recovery_error:
                    recovery_errors.append(
                        f"{diagnostic_value(replacement.target.as_posix())}: "
                        f"{type(recovery_error).__name__}: {diagnostic_value(recovery_error)}"
                    )
            if recovery_errors:
                raise ForgeError(
                    f"{self.label} rollback failed; recovery files preserved at "
                    f"{diagnostic_value(self.recovery_root)}. "
                    "Restore remaining backups before retrying.\n- " + "\n- ".join(recovery_errors)
                ) from publish_error
            self.preserve_recovery = False
            raise
        self.preserve_recovery = False
