#!/usr/bin/env python3
"""Create a clean, current Agent Plugin Forge checkout for a review session."""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
from pathlib import Path, PureWindowsPath
from urllib.parse import urlsplit

DEFAULT_ORIGIN = "https://github.com/MiguelElGallo/agent-plugin-forge.git"
SCP_ORIGIN_RE = re.compile(r"(?:(?P<user>[^@/:]+)@)?(?P<host>[^/:]+):(?P<path>.+)")


class BootstrapError(RuntimeError):
    """A safe Forge checkout could not be created."""


def _validate_origin(origin: str) -> None:
    """Reject unsafe, credential-bearing, or unsupported forge origins."""

    if not origin:
        raise BootstrapError("Forge origin is empty")
    if any(ord(character) < 32 or ord(character) == 127 for character in origin):
        raise BootstrapError("Forge origin must not contain control characters")
    if "://" not in origin:
        if "::" in origin:
            raise BootstrapError("Git remote-helper origins are not supported")
        local = Path(origin).expanduser()
        if local.is_absolute() or PureWindowsPath(origin).is_absolute():
            return
        scp = SCP_ORIGIN_RE.fullmatch(origin)
        if scp and ("?" in origin or "#" in origin):
            raise BootstrapError("Forge origin must not include a query or fragment")
        return

    parsed = urlsplit(origin)
    if parsed.scheme not in {"https", "ssh", "file"}:
        raise BootstrapError("Forge origin must use HTTPS, SSH, scp-style SSH, or a local path")
    if parsed.password is not None or (
        parsed.scheme in {"https", "file"} and parsed.username is not None
    ):
        raise BootstrapError("Forge origin URL must not embed credentials")
    if parsed.query or parsed.fragment:
        raise BootstrapError("Forge origin URL must not include a query or fragment")
    if parsed.scheme in {"https", "ssh"} and not parsed.hostname:
        raise BootstrapError("Forge network origin must include a host")


def _normalize_origin(origin: str) -> str:
    """Validate an origin and normalize relative local paths to absolute paths."""

    _validate_origin(origin)
    if "://" in origin:
        return origin
    local = Path(origin).expanduser()
    if local.is_absolute():
        return str(local.resolve())
    if SCP_ORIGIN_RE.fullmatch(origin):
        return origin
    return str(local.resolve())


def _run(command: list[str], *, cwd: Path | None = None) -> str:
    """Run a required command and return its stripped standard output."""

    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as error:
        raise BootstrapError(f"Required command is unavailable: {command[0]}") from error
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or "command failed"
        raise BootstrapError(f"{command[0]} failed: {detail}")
    return result.stdout.strip()


def _git(arguments: list[str], *, hooks_path: Path, cwd: Path | None = None) -> str:
    """Run Git with repository hooks, fsmonitor, and line conversion disabled."""

    return _run(
        [
            "git",
            "-c",
            f"core.hooksPath={hooks_path}",
            "-c",
            "core.fsmonitor=false",
            "-c",
            "core.autocrlf=false",
            *arguments,
        ],
        cwd=cwd,
    )


def _is_link_like(path: Path) -> bool:
    """Return whether a path is a symlink, junction, or Windows reparse point."""

    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)
    if callable(is_junction) and is_junction():
        return True
    if os.name == "nt":
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
        return bool(attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)
    return False


def _destination(value: str | None, *, reuse: bool) -> tuple[Path, bool]:
    """Resolve a new or explicitly reusable checkout destination."""

    if reuse and value is None:
        raise BootstrapError("--reuse requires --destination")
    if value is None:
        parent = Path(tempfile.mkdtemp(prefix="agent-plugin-forge-review-"))
        return parent / "agent-plugin-forge", False

    destination = Path(value).expanduser().absolute()
    if os.path.lexists(destination):
        if not reuse:
            raise BootstrapError(f"Destination already exists: {destination}")
        if _is_link_like(destination) or not destination.is_dir():
            raise BootstrapError(f"Reusable destination is not a regular directory: {destination}")
        return destination, True
    destination.parent.mkdir(parents=True, exist_ok=True)
    return destination, False


def _origin_host(origin: str) -> str:
    """Return a safe host label for a network origin or ``local`` otherwise."""

    if "://" not in origin:
        if Path(origin).is_absolute() or PureWindowsPath(origin).is_absolute():
            return "local"
        scp = SCP_ORIGIN_RE.fullmatch(origin)
        return scp.group("host") if scp else "local"

    parsed = urlsplit(origin)
    if parsed.scheme in {"https", "ssh"} and parsed.hostname:
        return parsed.hostname
    return "local"


def bootstrap(origin: str, destination: Path, *, reuse: bool) -> dict[str, str]:
    """Create or refresh a verified, clean checkout of current origin/main."""

    def verify(checkout: Path, hooks_path: Path) -> str:
        """Update a checkout and return its verified origin/main revision."""

        _git(["pull", "--ff-only", "origin", "main"], hooks_path=hooks_path, cwd=checkout)
        revision = _git(["rev-parse", "HEAD"], hooks_path=hooks_path, cwd=checkout)
        remote_line = _git(
            ["ls-remote", "--exit-code", "origin", "refs/heads/main"],
            hooks_path=hooks_path,
            cwd=checkout,
        )
        remote_revision = remote_line.split()[0]
        if revision != remote_revision:
            raise BootstrapError("Checkout is not aligned with the current origin/main revision")
        if _git(["branch", "--show-current"], hooks_path=hooks_path, cwd=checkout) != "main":
            raise BootstrapError("Checkout did not select the main branch")
        if _git(["status", "--porcelain"], hooks_path=hooks_path, cwd=checkout):
            raise BootstrapError("Checkout is unexpectedly dirty")
        return revision

    with tempfile.TemporaryDirectory(prefix="agent-plugin-forge-hooks-") as hooks_directory:
        hooks_path = Path(hooks_directory)
        if reuse:
            configured_origin = _git(
                ["remote", "get-url", "origin"], hooks_path=hooks_path, cwd=destination
            )
            if configured_origin != origin:
                detail = f"expected {origin!r}, found {configured_origin!r}"
                raise BootstrapError(f"Reusable checkout origin differs: {detail}")
            if _git(["branch", "--show-current"], hooks_path=hooks_path, cwd=destination) != "main":
                raise BootstrapError("Reusable checkout must be on the main branch")
            if _git(["status", "--porcelain"], hooks_path=hooks_path, cwd=destination):
                raise BootstrapError("Reusable checkout is dirty")
            revision = verify(destination, hooks_path)
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(
                prefix=f".{destination.name}-clone-", dir=destination.parent
            ) as staging_directory:
                checkout = Path(staging_directory) / "checkout"
                _git(
                    [
                        "clone",
                        "--branch",
                        "main",
                        "--single-branch",
                        "--no-tags",
                        "--",
                        origin,
                        str(checkout),
                    ],
                    hooks_path=hooks_path,
                )
                revision = verify(checkout, hooks_path)
                try:
                    os.replace(checkout, destination)
                except OSError as error:
                    raise BootstrapError(
                        f"Could not publish verified checkout at {destination}: {error}"
                    ) from error

    return {
        "checkout": str(destination),
        "host": _origin_host(origin),
        "origin": origin,
        "revision": revision,
        "branch": "main",
    }


def _parser() -> argparse.ArgumentParser:
    """Build the standalone bootstrap script's argument parser."""

    parser = argparse.ArgumentParser(
        description="Clone a clean, current Agent Plugin Forge review checkout."
    )
    parser.add_argument(
        "--origin",
        default=os.environ.get("AGENT_PLUGIN_FORGE_ORIGIN", DEFAULT_ORIGIN),
    )
    parser.add_argument("--destination")
    parser.add_argument(
        "--reuse",
        action="store_true",
        help="Update an existing clean main checkout at --destination.",
    )
    return parser


def main() -> int:
    """Run the bootstrap CLI and return a process exit status."""

    args = _parser().parse_args()
    try:
        origin = _normalize_origin(args.origin)
        destination, reuse = _destination(args.destination, reuse=args.reuse)
        payload = bootstrap(origin, destination, reuse=reuse)
    except BootstrapError as error:
        print(f"bootstrap failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
