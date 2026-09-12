"""Inspect and copy package files while enforcing filesystem safety rules."""

from __future__ import annotations

import hashlib
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from .errors import ForgeError, diagnostic_value

SECRET_NAME_RE = re.compile(
    r"(^|/)(\.env(?:\..*)?|id_(?:rsa|dsa|ecdsa|ed25519)|.*\.(?:pem|p12|pfx|key))$",
    re.IGNORECASE,
)
SECRET_CONTENT_RES = (
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(rb"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(rb"AKIA[0-9A-Z]{16}"),
)
MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_TREE_BYTES = 50 * 1024 * 1024


@dataclass(frozen=True)
class FileSnapshot:
    """Keep safety-checked bytes and their executable mode together."""

    content: bytes
    executable: bool


def _file_identity(value: os.stat_result) -> tuple[int, ...]:
    """Compare stable metadata shared by path and descriptor stat APIs."""

    mode = value.st_mode
    timestamp = value.st_ctime_ns
    if os.name == "nt":
        # Windows lstat adds suffix-derived execute bits that fstat cannot infer.
        # CPython 3.12 lstat reports creation time in ctime, but fstat reports
        # metadata-change time. Compare birthtime across APIs when available.
        mode &= ~0o111
        timestamp = getattr(value, "st_birthtime_ns", value.st_ctime_ns)

    return (
        value.st_dev,
        value.st_ino,
        mode,
        value.st_size,
        value.st_mtime_ns,
        timestamp,
    )


def is_linklike(path: Path) -> bool:
    """Return whether a path is a symbolic link or platform junction."""

    junction_check = getattr(path, "is_junction", None)
    return path.is_symlink() or (junction_check is not None and junction_check())


def snapshot_regular_file(
    path: Path, *, file_label: str = "Source file", expected: os.stat_result | None = None
) -> FileSnapshot:
    """Read, scan, and capture a regular file through one verified descriptor."""

    try:
        before = path.lstat() if expected is None else expected
    except OSError as exc:
        raise ForgeError(
            f"Cannot inspect {diagnostic_value(file_label.lower())} {diagnostic_value(path)}: "
            f"{diagnostic_value(exc)}"
        ) from exc
    if stat.S_ISLNK(before.st_mode) or is_linklike(path) or not stat.S_ISREG(before.st_mode):
        raise ForgeError(
            f"{diagnostic_value(file_label)} must be a regular, non-symlink file: "
            f"{diagnostic_value(path)}"
        )
    if before.st_size > MAX_FILE_BYTES:
        raise ForgeError(
            f"{diagnostic_value(file_label)} exceeds {MAX_FILE_BYTES} bytes: "
            f"{diagnostic_value(path)}"
        )
    try:
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        descriptor = os.open(path, flags)
        try:
            opened = os.fstat(descriptor)
            if not stat.S_ISREG(opened.st_mode) or _file_identity(opened) != _file_identity(before):
                raise ForgeError(
                    f"{diagnostic_value(file_label)} changed while opening: "
                    f"{diagnostic_value(path)}"
                )
            chunks: list[bytes] = []
            remaining = MAX_FILE_BYTES + 1
            while remaining:
                chunk = os.read(descriptor, min(remaining, 1024 * 1024))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            data = b"".join(chunks)
            after = os.fstat(descriptor)
            if (
                _file_identity(after) != _file_identity(opened)
                or after.st_ctime_ns != opened.st_ctime_ns
                or _file_identity(path.lstat()) != _file_identity(opened)
                or is_linklike(path)
            ):
                raise ForgeError(
                    f"{diagnostic_value(file_label)} changed while reading: "
                    f"{diagnostic_value(path)}"
                )
        finally:
            os.close(descriptor)
    except OSError as exc:
        raise ForgeError(
            f"Cannot read {diagnostic_value(file_label.lower())} {diagnostic_value(path)}: "
            f"{diagnostic_value(exc)}"
        ) from exc
    if len(data) > MAX_FILE_BYTES:
        raise ForgeError(
            f"{diagnostic_value(file_label)} exceeds {MAX_FILE_BYTES} bytes: "
            f"{diagnostic_value(path)}"
        )
    if SECRET_NAME_RE.search(path.name):
        raise ForgeError(f"Possible secret file is not accepted: {diagnostic_value(path.name)}")
    if any(pattern.search(data) for pattern in SECRET_CONTENT_RES):
        raise ForgeError(f"Possible secret content is not accepted: {diagnostic_value(path.name)}")
    # Retain Windows' existing suffix-based executable convention. On POSIX,
    # before.st_mode has been verified equal to the descriptor's actual mode.
    return FileSnapshot(data, bool(before.st_mode & 0o111))


def inspect_regular_file(path: Path, *, file_label: str = "Source file") -> bytes:
    """Return the bytes captured by one bounded, safety-checked regular-file read."""

    return snapshot_regular_file(path, file_label=file_label).content


def snapshot_regular_tree(
    root: Path,
    *,
    required_root_file: str | None = None,
    tree_label: str = "Source",
) -> dict[Path, FileSnapshot]:
    """Capture regular file bytes and modes after checking tree safety and limits."""
    try:
        root_mode = root.lstat().st_mode
    except OSError as exc:
        raise ForgeError(
            f"Cannot inspect {diagnostic_value(tree_label.lower())} directory "
            f"{diagnostic_value(root)}: {diagnostic_value(exc)}"
        ) from exc
    if stat.S_ISLNK(root_mode) or is_linklike(root) or not stat.S_ISDIR(root_mode):
        raise ForgeError(
            f"{diagnostic_value(tree_label)} must be a real directory, not a link or special file: "
            f"{diagnostic_value(root)}"
        )

    files: dict[Path, FileSnapshot] = {}
    folded: dict[str, str] = {}
    total = 0
    resolved_root = root.resolve()
    try:
        paths = sorted(root.rglob("*"), key=lambda path: path.relative_to(root).as_posix())
        for path in paths:
            relative = path.relative_to(root)
            relative_text = relative.as_posix()
            folded_name = relative_text.casefold()
            previous = folded.get(folded_name)
            if previous is not None and previous != relative_text:
                raise ForgeError(
                    f"Case-fold path collision: {diagnostic_value(previous)} and "
                    f"{diagnostic_value(relative_text)}"
                )
            folded[folded_name] = relative_text
            entry = path.lstat()
            mode = entry.st_mode
            if stat.S_ISLNK(mode) or is_linklike(path):
                raise ForgeError(
                    f"Links and junctions are not accepted: {diagnostic_value(relative_text)}"
                )
            if not path.resolve().is_relative_to(resolved_root):
                raise ForgeError(f"Tree entry escapes its root: {diagnostic_value(relative_text)}")
            if stat.S_ISDIR(mode):
                continue
            if not stat.S_ISREG(mode):
                raise ForgeError(
                    f"Special files are not accepted: {diagnostic_value(relative_text)}"
                )
            size = entry.st_size
            if size > MAX_FILE_BYTES:
                raise ForgeError(
                    f"File exceeds {MAX_FILE_BYTES} bytes: {diagnostic_value(relative_text)}"
                )
            if total + size > MAX_TREE_BYTES:
                raise ForgeError(
                    f"{diagnostic_value(tree_label)} tree exceeds {MAX_TREE_BYTES} bytes"
                )
            if SECRET_NAME_RE.search(relative_text):
                raise ForgeError(
                    f"Possible secret file is not accepted: {diagnostic_value(relative_text)}"
                )
            captured = snapshot_regular_file(path, file_label="Source file", expected=entry)
            total += len(captured.content)
            if total > MAX_TREE_BYTES:
                raise ForgeError(
                    f"{diagnostic_value(tree_label)} tree exceeds {MAX_TREE_BYTES} bytes"
                )
            files[path] = captured
    except ForgeError:
        raise
    except (OSError, UnicodeError) as exc:
        raise ForgeError(
            f"Cannot safely inspect {diagnostic_value(tree_label.lower())} tree "
            f"{diagnostic_value(root)}: {diagnostic_value(exc)}"
        ) from exc

    if required_root_file is not None:
        required = root / required_root_file
        if required not in files:
            raise ForgeError(
                f"{diagnostic_value(tree_label)} does not contain "
                f"{diagnostic_value(required_root_file)} at its root: {diagnostic_value(root)}"
            )
    return files


def inspect_regular_tree(
    root: Path,
    *,
    required_root_file: str | None = None,
    tree_label: str = "Source",
) -> list[Path]:
    """Return the paths of a safely inspected tree without retaining its bytes."""

    return list(
        snapshot_regular_tree(root, required_root_file=required_root_file, tree_label=tree_label)
    )


def file_hashes(root: Path, *, required_root_file: str | None = None) -> dict[str, str]:
    """Hash every safe regular file in a tree by its relative path."""

    return {
        path.relative_to(root).as_posix(): hashlib.sha256(snapshot.content).hexdigest()
        for path, snapshot in snapshot_regular_tree(
            root, required_root_file=required_root_file
        ).items()
    }


def copy_regular_tree(
    source: Path,
    destination: Path,
    *,
    excluded: frozenset[PurePosixPath] = frozenset(),
) -> None:
    """Copy a pre-inspected tree without following links or overwriting staged files."""
    files = snapshot_regular_tree(source)
    for path, snapshot in files.items():
        relative = PurePosixPath(path.relative_to(source).as_posix())
        if any(relative == item or relative.is_relative_to(item) for item in excluded):
            continue
        target = destination.joinpath(*relative.parts)
        if target.exists() or target.is_symlink():
            raise ForgeError(f"Refusing to overwrite staged file: {diagnostic_value(target)}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(snapshot.content)
        target.chmod(0o755 if snapshot.executable else 0o644)


def tree_snapshot(root: Path) -> dict[str, tuple[bytes, bool]]:
    """Capture bytes and the portable executable bit for generated drift checks."""
    if not root.exists():
        return {}
    return {
        path.relative_to(root).as_posix(): (snapshot.content, snapshot.executable)
        for path, snapshot in snapshot_regular_tree(root, tree_label="Generated output").items()
    }


def generated_path_errors(repo: Path, path: Path, *, directory: bool) -> list[str]:
    """Return safety errors for a generated output path and its ancestors."""

    try:
        relative = path.relative_to(repo)
    except ValueError:
        return [f"Generated output escapes the repository: {diagnostic_value(path)}"]
    current = repo
    for index, part in enumerate(relative.parts):
        current /= part
        try:
            mode = current.lstat().st_mode
        except FileNotFoundError:
            break
        except OSError as exc:
            return [
                f"Cannot inspect generated output path {diagnostic_value(current)}: "
                f"{diagnostic_value(exc)}"
            ]
        if stat.S_ISLNK(mode) or is_linklike(current):
            return [
                f"Generated output path contains a symlink: "
                f"{diagnostic_value(current.relative_to(repo))}"
            ]
        is_target = index == len(relative.parts) - 1
        if not is_target and not stat.S_ISDIR(mode):
            return [
                f"Generated output parent is not a directory: "
                f"{diagnostic_value(current.relative_to(repo))}"
            ]
        if is_target:
            expected = stat.S_ISDIR(mode) if directory else stat.S_ISREG(mode)
            if not expected:
                kind = "directory" if directory else "regular file"
                return [f"Generated output must be a {kind}: {diagnostic_value(relative)}"]
    return []


def generated_tree_errors(repo: Path, root: Path) -> list[str]:
    """Return safety errors for every path in a generated output tree."""

    errors = generated_path_errors(repo, root, directory=True)
    if errors or not root.exists():
        return errors
    try:
        inspect_regular_tree(root, tree_label="Generated output")
    except ForgeError as exc:
        errors.append(str(exc))
    return errors
