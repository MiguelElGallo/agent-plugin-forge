"""Verify retained release archives and their qualification evidence."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from scripts import smoke_wheel as smoke

from .conftest import git


@pytest.fixture
def archives(tmp_path: Path) -> list[Path]:
    paths = [tmp_path / "forge-1.0.whl", tmp_path / "forge-1.0.tar.gz"]
    for path in paths:
        path.write_bytes(path.name.encode() + b"\x00archive bytes\n")
    return paths


def test_retains_exact_tested_bytes_hashes_and_honest_source_report(
    tmp_path: Path, archives: list[Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / "retained"
    before = {path.name: path.read_bytes() for path in archives}
    hashes = {name: hashlib.sha256(content).hexdigest() for name, content in before.items()}
    source = {"commit": "merge-commit", "dirty": True, "tree_sha256": "source-tree"}
    env = {"GITHUB_SHA": "merge-commit", "FORGE_PR_HEAD_SHA": "pr-head", "SECRET": "omit"}
    fixture_outputs = tmp_path / "fixture-outputs"
    (fixture_outputs / "release-digest").mkdir(parents=True)
    (fixture_outputs / "release-digest/release-notes.md").write_bytes(b"# Release 2.4.0\n")
    fixture_hashes = {
        "release-digest/release-notes.md": hashlib.sha256(b"# Release 2.4.0\n").hexdigest()
    }

    moves: list[str] = []
    replace = Path.replace

    def record_move(path: Path, target: Path) -> Path:
        moves.append(path.name)
        if path.name == "smoke-report.json":
            assert all((destination / name).is_file() for name in (*before, "SHA256SUMS"))
        return replace(path, target)

    monkeypatch.setattr(Path, "replace", record_move)
    smoke.retain_archives(
        destination, archives, hashes, source, env, (fixture_outputs, fixture_hashes)
    )

    assert moves[-1] == "smoke-report.json"
    assert set(path.name for path in destination.iterdir()) == {
        *before,
        "fixtures",
        "SHA256SUMS",
        "smoke-report.json",
    }
    for name, content in before.items():
        assert (destination / name).read_bytes() == content
    assert (destination / "fixtures/release-digest/release-notes.md").read_bytes() == (
        fixture_outputs / "release-digest/release-notes.md"
    ).read_bytes()
    assert (destination / "SHA256SUMS").read_bytes() == "".join(
        f"{value}  {name}\n" for name, value in sorted(hashes.items())
    ).encode()
    report = json.loads((destination / "smoke-report.json").read_bytes())
    assert report["schema_version"] == 2
    assert report["smoke_passed"] is True
    assert report["source"] == source
    assert report["archives"] == hashes
    assert report["fixture_artifacts"] == fixture_hashes
    assert report["ci"] == {"GITHUB_SHA": "merge-commit", "FORGE_PR_HEAD_SHA": "pr-head"}
    assert not list(tmp_path.glob(".forge-release-*"))


def test_changed_tested_archive_is_not_retained(tmp_path: Path, archives: list[Path]) -> None:
    hashes = smoke.archive_hashes(archives)
    archives[-1].write_bytes(b"changed after testing")
    destination = tmp_path / "retained"

    with pytest.raises(RuntimeError, match="Tested archive changed"):
        smoke.retain_archives(destination, archives, hashes, {}, {})

    assert not destination.exists()
    assert not list(tmp_path.glob(".forge-release-*"))


@pytest.mark.parametrize("mutation", ["changed", "added"])
def test_fixture_artifacts_must_match_validated_set_and_bytes(
    tmp_path: Path, archives: list[Path], mutation: str
) -> None:
    fixture_outputs = tmp_path / "fixture-outputs"
    fixture_outputs.mkdir()
    original = fixture_outputs / "release-notes.md"
    original.write_bytes(b"reviewed\n")
    tested = {"release-notes.md": hashlib.sha256(original.read_bytes()).hexdigest()}
    if mutation == "changed":
        original.write_bytes(b"unreviewed\n")
    else:
        (fixture_outputs / "late.txt").write_bytes(b"late unreviewed file\n")
    destination = tmp_path / "retained"

    with pytest.raises(RuntimeError, match="Fixture artifacts changed"):
        smoke.retain_archives(
            destination,
            archives,
            smoke.archive_hashes(archives),
            {},
            {},
            (fixture_outputs, tested),
        )
    assert not destination.exists()


def test_retention_exports_only_validated_fixture_snapshot(
    tmp_path: Path, archives: list[Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture_outputs = tmp_path / "fixture-outputs"
    fixture_outputs.mkdir()
    (fixture_outputs / "reviewed.txt").write_bytes(b"reviewed\n")
    tested = {"reviewed.txt": hashlib.sha256(b"reviewed\n").hexdigest()}
    capture = smoke.capture_fixture_artifacts

    def add_after_capture(root: Path) -> dict[str, bytes]:
        files = capture(root)
        (root / "late-unreviewed.txt").write_bytes(b"late\n")
        return files

    monkeypatch.setattr(smoke, "capture_fixture_artifacts", add_after_capture)
    destination = tmp_path / "retained"
    smoke.retain_archives(
        destination,
        archives,
        smoke.archive_hashes(archives),
        {},
        {},
        (fixture_outputs, tested),
    )
    assert (destination / "fixtures/reviewed.txt").read_bytes() == b"reviewed\n"
    assert not (destination / "fixtures/late-unreviewed.txt").exists()
    report = json.loads((destination / "smoke-report.json").read_bytes())
    assert report["fixture_artifacts"] == tested


@pytest.mark.skipif(os.name == "nt", reason="Windows has no POSIX FIFO")
def test_fixture_snapshot_rejects_fifo_without_opening_it(tmp_path: Path) -> None:
    artifact_root = tmp_path / "fixture-outputs"
    artifact_root.mkdir()
    os.mkfifo(artifact_root / "blocked.fifo")
    with pytest.raises(RuntimeError, match="non-regular fixture artifact"):
        smoke.capture_fixture_artifacts(artifact_root)


def test_workflow_rejects_artifact_changed_after_renderer_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = Path(__file__).resolve().parents[1]
    forge = Path(sys.executable).parent / ("forge.exe" if os.name == "nt" else "forge")
    capture = smoke.capture_fixture_artifacts

    def change_before_final_capture(root: Path) -> dict[str, bytes]:
        (root / "release-digest-initial/release-index.json").write_bytes(
            b"changed after validation\n"
        )
        return capture(root)

    monkeypatch.setattr(smoke, "capture_fixture_artifacts", change_before_final_capture)
    with pytest.raises(
        RuntimeError, match="Fixture artifacts changed after installed skill validation"
    ):
        smoke.smoke_skill_workflow(forge, repo, tmp_path, dict(os.environ))


@pytest.mark.parametrize("occupied", ["directory", "file"])
def test_retention_never_overwrites_existing_output(
    tmp_path: Path, archives: list[Path], occupied: str
) -> None:
    destination = tmp_path / "retained"
    if occupied == "directory":
        destination.mkdir()
    else:
        destination.write_bytes(b"user data")

    with pytest.raises(RuntimeError, match="already exists"):
        smoke.retain_archives(destination, archives, smoke.archive_hashes(archives), {}, {})

    assert (
        destination.is_dir()
        if occupied == "directory"
        else destination.read_bytes() == b"user data"
    )


def test_output_parent_must_exist(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="existing directory"):
        smoke.output_destination(tmp_path / "missing" / "output")
    assert not (tmp_path / "missing").exists()


@pytest.mark.parametrize("link_at", ["destination", "parent"])
def test_retention_refuses_symlinks(tmp_path: Path, archives: list[Path], link_at: str) -> None:
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    try:
        link.symlink_to(real, target_is_directory=True)
    except OSError:
        pytest.skip("Creating symlinks requires platform privileges")
    destination = link if link_at == "destination" else link / "retained"

    with pytest.raises(RuntimeError, match="symlinks"):
        smoke.retain_archives(destination, archives, smoke.archive_hashes(archives), {}, {})

    assert list(real.iterdir()) == []
    assert link.is_symlink()


@pytest.mark.parametrize("failure", [OSError, KeyboardInterrupt])
def test_partial_export_is_removed_after_error_or_cancellation(
    tmp_path: Path,
    archives: list[Path],
    monkeypatch: pytest.MonkeyPatch,
    failure: type[BaseException],
) -> None:
    destination = tmp_path / "retained"
    replace = Path.replace
    count = 0

    def interrupted_move(path: Path, target: Path) -> Path:
        nonlocal count
        count += 1
        if count == 2:
            raise failure("injected export failure")
        return replace(path, target)

    monkeypatch.setattr(Path, "replace", interrupted_move)
    with pytest.raises(failure, match="injected"):
        smoke.retain_archives(destination, archives, smoke.archive_hashes(archives), {}, {})

    assert not destination.exists()
    assert all(path.exists() for path in archives)
    assert not list(tmp_path.glob(".forge-release-*"))


def test_competing_output_creation_is_preserved(
    tmp_path: Path, archives: list[Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / "retained"
    mkdir = Path.mkdir

    def competing_mkdir(path: Path, *args: Any, **kwargs: Any) -> None:
        if path == destination:
            mkdir(path)
            (path / "user.txt").write_bytes(b"concurrent user data")
        mkdir(path, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", competing_mkdir)
    with pytest.raises(FileExistsError):
        smoke.retain_archives(destination, archives, smoke.archive_hashes(archives), {}, {})

    assert (destination / "user.txt").read_bytes() == b"concurrent user data"
    assert not list(tmp_path.glob(".forge-release-*"))


@pytest.fixture
def source_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "source"
    repo.mkdir()
    (repo / "code.py").write_bytes(b"original\n")
    (repo / ".gitignore").write_bytes(b"ignored\n")
    git(repo, "init", "-b", "main")
    git(repo, "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "add", ".")
    git(
        repo,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.invalid",
        "-c",
        "commit.gpgsign=false",
        "commit",
        "-m",
        "Authored source",
    )
    return repo


def test_source_report_binds_already_dirty_bytes_and_untracked_files(source_repo: Path) -> None:
    clean = smoke.source_state(source_repo, {})
    assert clean["dirty"] is False
    assert clean["matches_commit"] is True
    assert clean["commit"] == git(source_repo, "rev-parse", "HEAD")
    (source_repo / "code.py").write_bytes(b"first edit\n")
    first = smoke.source_state(source_repo, {})
    (source_repo / "code.py").write_bytes(b"second edit\n")
    second = smoke.source_state(source_repo, {})
    assert first["dirty"] is second["dirty"] is True
    assert first["status_porcelain_v1"] == second["status_porcelain_v1"]
    assert first["tree_sha256"] != second["tree_sha256"]
    (source_repo / "extra.py").write_bytes(b"untracked\n")
    untracked = smoke.source_state(source_repo, {})
    assert untracked["tree_sha256"] != second["tree_sha256"]
    (source_repo / "ignored").write_bytes(b"excluded from Git-visible scope\n")
    assert smoke.source_state(source_repo, {}) == untracked
    (source_repo / "code.py").unlink()
    deleted = smoke.source_state(source_repo, {})
    assert deleted["tree_sha256"] != untracked["tree_sha256"]


@pytest.mark.parametrize("flag", ["--assume-unchanged", "--skip-worktree"])
def test_hidden_index_flags_cannot_mark_changed_source_clean(source_repo: Path, flag: str) -> None:
    git(source_repo, "update-index", flag, "code.py")
    index_before = subprocess.run(
        ["git", "ls-files", "-v", "-z"],
        cwd=source_repo,
        capture_output=True,
        check=True,
    ).stdout
    (source_repo / "code.py").write_bytes(b"modified bytes hidden from Git status\n")
    assert git(source_repo, "status", "--porcelain") == ""

    report = smoke.source_state(source_repo, {})

    assert report["git_status_dirty"] is False
    assert report["dirty"] is True
    assert report["matches_commit"] is False
    assert report["commit_mismatch_paths"] == ["code.py"]
    assert (
        subprocess.run(
            ["git", "ls-files", "-v", "-z"],
            cwd=source_repo,
            capture_output=True,
            check=True,
        ).stdout
        == index_before
    )


@pytest.mark.skipif(os.name == "nt", reason="Windows filenames cannot contain CR or LF")
def test_source_report_preserves_distinct_cr_and_lf_filenames(source_repo: Path) -> None:
    carriage = source_repo / "report\rname.txt"
    newline = source_repo / "report\nname.txt"
    carriage.write_bytes(b"carriage v1\n")
    newline.write_bytes(b"newline v1\n")
    git(source_repo, "add", "--", carriage.name, newline.name)
    git(
        source_repo,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.invalid",
        "-c",
        "commit.gpgsign=false",
        "commit",
        "-m",
        "Add distinct unusual filenames",
    )
    clean = smoke.source_state(source_repo, {})
    assert clean["matches_commit"] is True
    carriage.write_bytes(b"carriage v2\n")
    changed = smoke.source_state(source_repo, {})
    assert changed["matches_commit"] is False
    assert changed["commit_mismatch_paths"] == [carriage.name]
    assert changed["tree_sha256"] != clean["tree_sha256"]
    carriage.write_bytes(b"carriage v1\n")
    newline.write_bytes(b"newline v2\n")
    assert smoke.source_state(source_repo, {})["tree_sha256"] != clean["tree_sha256"]


@pytest.mark.skipif(os.name == "nt", reason="Windows filenames cannot contain raw non-UTF-8 bytes")
def test_source_report_preserves_non_utf8_filename(source_repo: Path) -> None:
    unusual = source_repo / os.fsdecode(b"source-\xff.txt")
    try:
        unusual.write_bytes(b"one\n")
    except OSError:
        pytest.skip("This filesystem does not accept non-UTF-8 filenames")
    first = smoke.source_state(source_repo, {})
    unusual.write_bytes(b"two\n")
    second = smoke.source_state(source_repo, {})
    assert first["tree_sha256"] != second["tree_sha256"]
    assert unusual.name in second["commit_mismatch_paths"]


@pytest.mark.skipif(os.name == "nt", reason="POSIX executable bits")
def test_source_report_binds_executable_modes(source_repo: Path) -> None:
    before = smoke.source_state(source_repo, {})
    (source_repo / "code.py").chmod(0o755)
    assert smoke.source_state(source_repo, {})["tree_sha256"] != before["tree_sha256"]


@pytest.mark.skipif(os.name == "nt", reason="POSIX executable bits")
def test_source_verification_detects_mode_change_when_git_ignores_it(source_repo: Path) -> None:
    git(source_repo, "config", "core.filemode", "false")
    (source_repo / "code.py").chmod(0o755)
    assert git(source_repo, "status", "--porcelain") == ""
    report = smoke.source_state(source_repo, {})
    assert report["matches_commit"] is False
    assert report["commit_mismatch_paths"] == ["code.py"]


def test_source_symlink_is_refused_without_reading_target(
    source_repo: Path, tmp_path: Path
) -> None:
    link = source_repo / "external"
    try:
        link.symlink_to(tmp_path / "nonexistent-secret")
    except OSError:
        pytest.skip("Creating symlinks requires platform privileges")
    with pytest.raises(RuntimeError, match="source through a symlink"):
        smoke.source_state(source_repo, {})


@pytest.mark.skipif(os.name == "nt", reason="Windows symlink creation requires privileges")
def test_committed_symlink_replaced_by_hidden_regular_file_is_refused(source_repo: Path) -> None:
    link = source_repo / "link.txt"
    link.symlink_to("code.py")
    git(source_repo, "add", "link.txt")
    git(
        source_repo,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.invalid",
        "-c",
        "commit.gpgsign=false",
        "commit",
        "-m",
        "Record authored symlink",
    )
    link.unlink()
    link.write_bytes(b"code.py")
    git(source_repo, "update-index", "--assume-unchanged", "link.txt")

    with pytest.raises(RuntimeError, match="non-regular Git file"):
        smoke.source_state(source_repo, {})


@pytest.mark.parametrize("failure", ["smoke", "source-change"])
def test_main_does_not_retain_failed_or_changed_source_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    destination = tmp_path / "retained"
    captures = iter([{"commit": "before"}, {"commit": "after"}])
    monkeypatch.setattr(smoke, "source_state", lambda *_: next(captures))
    monkeypatch.setattr(smoke.shutil, "which", lambda _: "uv")

    def fake_smoke(*_: Any) -> tuple[list[Path], dict[str, str], tuple[Path, dict[str, str]]]:
        if failure == "smoke":
            raise RuntimeError("smoke failure")
        return [], {}, (tmp_path, {})

    monkeypatch.setattr(smoke, "build_and_smoke", fake_smoke)
    with pytest.raises(RuntimeError, match=r"smoke failure|Source checkout changed"):
        smoke.main(["--output-dir", str(destination)])
    assert not destination.exists()


@pytest.mark.parametrize("scope", ["source", "output"])
def test_windows_reparse_points_are_refused_without_following_targets(
    source_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, scope: str
) -> None:
    reparse = source_repo / "code.py" if scope == "source" else tmp_path / "junction"
    if scope == "output":
        reparse.mkdir()
    lstat = Path.lstat

    def reparse_stat(path: Path, *args: Any, **kwargs: Any) -> Any:
        value = lstat(path, *args, **kwargs)
        if path == reparse:
            return SimpleNamespace(
                st_mode=value.st_mode, st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT
            )
        return value

    monkeypatch.setattr(Path, "lstat", reparse_stat)
    with pytest.raises(RuntimeError, match="reparse point"):
        if scope == "source":
            smoke.source_state(source_repo, {})
        else:
            smoke.output_destination(reparse / "retained")
