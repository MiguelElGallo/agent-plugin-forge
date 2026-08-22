"""Inspect and copy package files while enforcing filesystem safety rules."""

from __future__ import annotations

import hashlib
import re
import stat
from pathlib import Path, PurePosixPath

from .errors import ForgeError

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


def is_linklike(path: Path) -> bool:
    """Return whether a path is a symbolic link or platform junction."""

    junction_check = getattr(path, "is_junction", None)
    return path.is_symlink() or (junction_check is not None and junction_check())


def inspect_regular_file(path: Path, *, file_label: str = "Source file") -> bytes:
    """Read one bounded regular file after rejecting links and likely secrets."""

    try:
        mode = path.lstat().st_mode
    except OSError as exc:
        raise ForgeError(f"Cannot inspect {file_label.lower()} {path}: {exc}") from exc
    if stat.S_ISLNK(mode) or is_linklike(path) or not stat.S_ISREG(mode):
        raise ForgeError(f"{file_label} must be a regular, non-symlink file: {path}")
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise ForgeError(f"Cannot read {file_label.lower()} {path}: {exc}") from exc
    if size > MAX_FILE_BYTES:
        raise ForgeError(f"{file_label} exceeds {MAX_FILE_BYTES} bytes: {path}")
    try:
        with path.open("rb") as handle:
            data = handle.read(MAX_FILE_BYTES + 1)
    except OSError as exc:
        raise ForgeError(f"Cannot read {file_label.lower()} {path}: {exc}") from exc
    if len(data) > MAX_FILE_BYTES:
        raise ForgeError(f"{file_label} exceeds {MAX_FILE_BYTES} bytes: {path}")
    if SECRET_NAME_RE.search(path.name):
        raise ForgeError(f"Possible secret file is not accepted: {path.name}")
    if any(pattern.search(data) for pattern in SECRET_CONTENT_RES):
        raise ForgeError(f"Possible secret content is not accepted: {path.name}")
    return data


def inspect_regular_tree(
    root: Path,
    *,
    required_root_file: str | None = None,
    tree_label: str = "Source",
) -> list[Path]:
    """Return regular files after rejecting package escape and supply-chain hazards."""
    try:
        root_mode = root.lstat().st_mode
    except OSError as exc:
        raise ForgeError(f"Cannot inspect {tree_label.lower()} directory {root}: {exc}") from exc
    if stat.S_ISLNK(root_mode) or is_linklike(root) or not stat.S_ISDIR(root_mode):
        raise ForgeError(
            f"{tree_label} must be a real directory, not a link or special file: {root}"
        )

    files: list[Path] = []
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
                raise ForgeError(f"Case-fold path collision: {previous} and {relative_text}")
            folded[folded_name] = relative_text
            mode = path.lstat().st_mode
            if stat.S_ISLNK(mode) or is_linklike(path):
                raise ForgeError(f"Links and junctions are not accepted: {relative_text}")
            if not path.resolve().is_relative_to(resolved_root):
                raise ForgeError(f"Tree entry escapes its root: {relative_text}")
            if stat.S_ISDIR(mode):
                continue
            if not stat.S_ISREG(mode):
                raise ForgeError(f"Special files are not accepted: {relative_text}")
            size = path.stat().st_size
            if size > MAX_FILE_BYTES:
                raise ForgeError(f"File exceeds {MAX_FILE_BYTES} bytes: {relative_text}")
            total += size
            if total > MAX_TREE_BYTES:
                raise ForgeError(f"{tree_label} tree exceeds {MAX_TREE_BYTES} bytes")
            if SECRET_NAME_RE.search(relative_text):
                raise ForgeError(f"Possible secret file is not accepted: {relative_text}")
            data = path.read_bytes()
            if any(pattern.search(data) for pattern in SECRET_CONTENT_RES):
                raise ForgeError(f"Possible secret content is not accepted: {relative_text}")
            files.append(path)
    except ForgeError:
        raise
    except (OSError, UnicodeError) as exc:
        raise ForgeError(f"Cannot safely inspect {tree_label.lower()} tree {root}: {exc}") from exc

    if required_root_file is not None:
        required = root / required_root_file
        if required not in files:
            raise ForgeError(
                f"{tree_label} does not contain {required_root_file} at its root: {root}"
            )
    return files


def file_hashes(root: Path, *, required_root_file: str | None = None) -> dict[str, str]:
    """Hash every safe regular file in a tree by its relative path."""

    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in inspect_regular_tree(root, required_root_file=required_root_file)
    }


def copy_regular_tree(
    source: Path,
    destination: Path,
    *,
    excluded: frozenset[PurePosixPath] = frozenset(),
) -> None:
    """Copy a pre-inspected tree without following links or overwriting staged files."""
    files = inspect_regular_tree(source)
    for path in files:
        relative = PurePosixPath(path.relative_to(source).as_posix())
        if any(relative == item or relative.is_relative_to(item) for item in excluded):
            continue
        target = destination.joinpath(*relative.parts)
        if target.exists() or target.is_symlink():
            raise ForgeError(f"Refusing to overwrite staged file: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())
        executable = bool(path.stat().st_mode & 0o111)
        target.chmod(0o755 if executable else 0o644)


def tree_snapshot(root: Path) -> dict[str, tuple[bytes, bool]]:
    """Capture bytes and the portable executable bit for generated drift checks."""
    if not root.exists():
        return {}
    return {
        path.relative_to(root).as_posix(): (path.read_bytes(), bool(path.stat().st_mode & 0o111))
        for path in inspect_regular_tree(root, tree_label="Generated output")
    }


def generated_path_errors(repo: Path, path: Path, *, directory: bool) -> list[str]:
    """Return safety errors for a generated output path and its ancestors."""

    try:
        relative = path.relative_to(repo)
    except ValueError:
        return [f"Generated output escapes the repository: {path}"]
    current = repo
    for index, part in enumerate(relative.parts):
        current /= part
        try:
            mode = current.lstat().st_mode
        except FileNotFoundError:
            break
        except OSError as exc:
            return [f"Cannot inspect generated output path {current}: {exc}"]
        if stat.S_ISLNK(mode) or is_linklike(current):
            return [f"Generated output path contains a symlink: {current.relative_to(repo)}"]
        is_target = index == len(relative.parts) - 1
        if not is_target and not stat.S_ISDIR(mode):
            return [f"Generated output parent is not a directory: {current.relative_to(repo)}"]
        if is_target:
            expected = stat.S_ISDIR(mode) if directory else stat.S_ISREG(mode)
            if not expected:
                kind = "directory" if directory else "regular file"
                return [f"Generated output must be a {kind}: {relative}"]
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
