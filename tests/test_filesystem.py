"""Exercise filesystem inspection and copy failure boundaries."""

from __future__ import annotations

import os
from pathlib import Path, PurePosixPath

import pytest

from agent_plugin_forge import filesystem
from agent_plugin_forge.errors import ForgeError


def test_copy_preserves_existing_destination(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "data.txt").write_bytes(b"new")
    (target / "data.txt").write_bytes(b"original")
    with pytest.raises(ForgeError, match="overwrite"):
        filesystem.copy_regular_tree(source, target)
    assert (target / "data.txt").read_bytes() == b"original"
    assert (source / "data.txt").read_bytes() == b"new"


def test_copy_excludes_nested_subtree_and_preserves_bytes(tmp_path: Path) -> None:
    source = tmp_path / "source"
    (source / "excluded" / "nested").mkdir(parents=True)
    (source / "excluded" / "nested" / "data.txt").write_bytes(b"excluded")
    (source / "script.sh").write_bytes(b"echo example\n")
    (source / "script.sh").chmod(0o755)
    target = tmp_path / "target"
    filesystem.copy_regular_tree(source, target, excluded=frozenset({PurePosixPath("excluded")}))
    assert (target / "script.sh").read_bytes() == b"echo example\n"
    assert not (target / "excluded").exists()
    if os.name != "nt":
        assert (target / "script.sh").stat().st_mode & 0o111


def test_copy_write_failure_preserves_source(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "data.txt").write_bytes(b"original")
    target = tmp_path / "target"
    before = filesystem.tree_snapshot(source)
    real_write = Path.write_bytes

    def fail_write(path, data):
        if path.is_relative_to(target):
            raise OSError("simulated disk full")
        return real_write(path, data)

    monkeypatch.setattr(Path, "write_bytes", fail_write)
    with pytest.raises(OSError, match="disk full"):
        filesystem.copy_regular_tree(source, target)
    assert filesystem.tree_snapshot(source) == before
    assert not (target / "data.txt").exists()


@pytest.mark.skipif(os.name == "nt", reason="Windows symlinks require privileges")
def test_linked_source_rejected_before_copy(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"original")
    (source / "linked.txt").symlink_to(outside)
    with pytest.raises(ForgeError, match="Links"):
        filesystem.copy_regular_tree(source, tmp_path / "target")
    assert not (tmp_path / "target").exists()
    assert outside.read_bytes() == b"original"


@pytest.mark.parametrize(
    "name,data,match",
    [
        (".env", b"example", "secret file"),
        ("data.txt", b"-----BEGIN PRIVATE KEY-----", "secret content"),
        ("large.txt", b"12345", "exceeds"),
    ],
)
def test_file_inspection_rejects_secrets_and_oversize(
    tmp_path: Path, monkeypatch, name, data, match
) -> None:
    path = tmp_path / name
    path.write_bytes(data)
    monkeypatch.setattr(filesystem, "MAX_FILE_BYTES", 4 if name == "large.txt" else 100)
    with pytest.raises(ForgeError, match=match):
        filesystem.inspect_regular_file(path)


def test_tree_total_size_limit(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "one.txt").write_bytes(b"123")
    (tmp_path / "two.txt").write_bytes(b"456")
    monkeypatch.setattr(filesystem, "MAX_TREE_BYTES", 5)
    with pytest.raises(ForgeError, match="tree exceeds"):
        filesystem.inspect_regular_tree(tmp_path)


def test_read_failure_reports_context(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "data.txt"
    path.write_bytes(b"original")

    def fail_open(*args, **kwargs):
        raise PermissionError("simulated unreadable file")

    monkeypatch.setattr(os, "open", fail_open)
    with pytest.raises(ForgeError, match="Cannot read source file"):
        filesystem.inspect_regular_file(path)
    with pytest.raises(ForgeError, match="Cannot read source file"):
        filesystem.inspect_regular_tree(tmp_path)


def test_snapshot_rejects_replacement_between_inspect_and_open(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "source.txt"
    replacement = tmp_path / "replacement.txt"
    path.write_bytes(b"reviewed")
    replacement.write_bytes(b"unreviewed")
    real_open = os.open

    def replace_then_open(file, flags):
        replacement.replace(path)
        return real_open(file, flags)

    monkeypatch.setattr(os, "open", replace_then_open)
    with pytest.raises(ForgeError, match="changed while opening"):
        filesystem.snapshot_regular_file(path)


def test_snapshot_rejects_modification_during_read(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "source.txt"
    path.write_bytes(b"reviewed")
    real_read = os.read
    changed = False

    def change_during_read(descriptor, size):
        nonlocal changed
        if not changed:
            changed = True
            path.write_bytes(b"unreviewed bytes")
        return real_read(descriptor, size)

    monkeypatch.setattr(os, "read", change_during_read)
    with pytest.raises(ForgeError, match="changed while reading"):
        filesystem.snapshot_regular_file(path)


def test_snapshot_bounds_reads_even_if_the_file_grows(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "source.txt"
    path.write_bytes(b"a")
    monkeypatch.setattr(filesystem, "MAX_FILE_BYTES", 8)
    requested = []

    def growing_read(descriptor, size):
        requested.append(size)
        return b"a" * size

    monkeypatch.setattr(os, "read", growing_read)
    with pytest.raises(ForgeError, match="exceeds"):
        filesystem.snapshot_regular_file(path)
    assert sum(requested) == 9


def test_snapshot_works_without_optional_open_flags(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "source.txt"
    path.write_bytes(b"reviewed")
    for flag in ("O_NOFOLLOW", "O_NONBLOCK"):
        monkeypatch.delattr(os, flag, raising=False)
    snapshot = filesystem.snapshot_regular_file(path)
    assert snapshot.content == b"reviewed"


def test_copy_uses_scanned_bytes_after_source_mutation(tmp_path: Path, monkeypatch) -> None:
    source, target = tmp_path / "source", tmp_path / "target"
    source.mkdir()
    path = source / "resource.txt"
    path.write_bytes(b"reviewed")
    inspect = filesystem.snapshot_regular_tree

    def change_after_scan(root, **kwargs):
        snapshot = inspect(root, **kwargs)
        path.write_bytes(b"unreviewed")
        return snapshot

    monkeypatch.setattr(filesystem, "snapshot_regular_tree", change_after_scan)
    filesystem.copy_regular_tree(source, target)
    assert (target / "resource.txt").read_bytes() == b"reviewed"


def test_generated_output_rejects_escape_and_wrong_path_types(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    file = repo / "file"
    file.write_bytes(b"original")
    assert (
        "escapes"
        in filesystem.generated_path_errors(repo, tmp_path / "outside", directory=False)[0]
    )
    assert (
        "parent is not a directory"
        in filesystem.generated_path_errors(repo, file / "child", directory=False)[0]
    )
    assert "must be a directory" in filesystem.generated_path_errors(repo, file, directory=True)[0]
    directory = repo / "directory"
    directory.mkdir()
    assert (
        "must be a regular file"
        in filesystem.generated_path_errors(repo, directory, directory=False)[0]
    )
    assert file.read_bytes() == b"original"


@pytest.mark.skipif(os.name == "nt", reason="Windows symlinks require privileges")
def test_generated_tree_rejects_linked_parent_and_contents(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    repo = tmp_path / "repo"
    repo.mkdir()
    linked = repo / "linked"
    linked.symlink_to(outside, target_is_directory=True)
    assert (
        "symlink"
        in filesystem.generated_path_errors(repo, linked / "index.json", directory=False)[0]
    )
    assert "Links" in filesystem.generated_tree_errors(tmp_path, repo)[0]
