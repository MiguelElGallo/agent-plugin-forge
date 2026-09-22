"""Build both archives and exercise the installed Forge CLI in a fresh environment."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


def run(
    command: list[str], *, cwd: Path, env: dict[str, str], expected: int = 0
) -> subprocess.CompletedProcess[str]:
    """Run a bounded smoke command and report unexpected output on failure."""

    result = subprocess.run(
        command, cwd=cwd, env=env, capture_output=True, text=True, check=False, timeout=180
    )
    if result.returncode != expected:
        raise RuntimeError(
            f"Command {command!r} returned {result.returncode}, expected {expected}.\n"
            f"{result.stdout}{result.stderr}"
        )
    return result


def snapshot(root: Path) -> dict[str, tuple[bytes | None, bool]]:
    """Capture fixture directories, bytes, and executable flags without Git internals."""

    result: dict[str, tuple[bytes | None, bool]] = {}
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if ".git" in relative.parts:
            continue
        result[relative.as_posix()] = (
            (None, False)
            if path.is_dir()
            else (path.read_bytes(), bool(path.stat().st_mode & 0o111))
        )
    return result


def fixture_revision(root: Path) -> str:
    """Hash every authored source file, path, and executable flag for its declared revision."""

    files = {
        path: {"sha256": hashlib.sha256(content).hexdigest(), "executable": executable}
        for path, (content, executable) in snapshot(root).items()
        if content is not None
    }
    digest = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
    return f"sha256:{digest}"


def smoke_skill_workflow(
    forge: Path, repo: Path, temporary: Path, env: dict[str, str]
) -> tuple[Path, dict[str, str]]:
    """Exercise reviewed imports, an update, and authored skill artifact rendering."""

    git = shutil.which("git")
    if git is None:
        raise RuntimeError("Install Git before running the installed workflow smoke check.")
    fixture = temporary / "forge checkout"
    origin = temporary / "local origin.git"
    templates = temporary / "empty git templates"
    templates.mkdir()
    fixture_env = {name: value for name, value in env.items() if not name.startswith("GIT_")}
    fixture_env.update(
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_CONFIG_NOSYSTEM="1",
        GIT_TEMPLATE_DIR=str(templates),
        GIT_TERMINAL_PROMPT="0",
    )

    def git_command(*arguments: str) -> subprocess.CompletedProcess[str]:
        """Run Git only inside the authored fixture and its local bare origin."""

        return run([git, *arguments], cwd=fixture, env=fixture_env)

    def forge_command(*arguments: str, expected: int = 0) -> subprocess.CompletedProcess[str]:
        """Invoke the installed executable against the disposable Forge checkout."""

        return run([str(forge), *arguments], cwd=fixture, env=fixture_env, expected=expected)

    def finish_branch(skill: str) -> None:
        """Advance the fixture's local main and origin before the next reviewed operation."""

        branch = f"skill/wheel-smoke/{skill}"
        git_command("add", ".")
        git_command("commit", "-m", f"Import authored {skill} fixture")
        git_command("switch", "main")
        git_command("merge", "--ff-only", branch)
        git_command("branch", "-d", branch)
        git_command("push", "--quiet", "origin", "main")

    (fixture / "catalog").mkdir(parents=True)
    (fixture / "plugins").mkdir()
    (fixture / "catalog/plugins.json").write_text(
        json.dumps(
            {
                "marketplace": {
                    "name": "wheel-smoke",
                    "displayName": "Installed wheel smoke fixture",
                    "owner": {"name": "Smoke Test", "email": "smoke@example.invalid"},
                    "description": "An authored, disposable marketplace fixture.",
                    "version": "0.1.0",
                },
                "plugins": [],
            }
        ),
        encoding="utf-8",
    )
    shutil.copytree(repo / "schemas", fixture / "schemas")
    git_command("init", "--bare", "-b", "main", str(origin))
    git_command("init", "-b", "main")
    git_command("config", "user.name", "Forge Wheel Smoke")
    git_command("config", "user.email", "smoke@example.invalid")
    git_command("config", "core.autocrlf", "false")
    git_command("config", "commit.gpgsign", "false")
    git_command("remote", "add", "origin", str(origin))
    forge_command("generate")
    forge_command("check")
    git_command("add", ".")
    git_command("commit", "-m", "Seed empty authored Forge fixture")
    git_command("push", "--quiet", "-u", "origin", "main")

    sources = temporary / "authored sources"
    authored = repo / "tests/fixtures/authored_skills"
    source = sources / "release-digest"
    companion = sources / "status-chart"
    shutil.copytree(authored / source.name, source)
    shutil.copytree(authored / companion.name, companion)
    (source / "changed.txt").write_bytes(b"Original content.\n")
    (source / "removed.txt").write_bytes(b"Obsolete content.\n")
    (source / "kept.txt").write_bytes(b"Preserved content.\n")
    helper = source / "scripts/render.py"
    helper.chmod(0o644)
    license_file = sources / "LICENSE"
    original_license = (repo / "LICENSE").read_bytes()
    license_file.write_bytes(original_license)
    plugin = fixture / "plugins/wheel-smoke"

    def review_and_apply(operation: str, selected: Path, version: str) -> dict[str, Any]:
        """Review an inert fixture, reject a wrong hash, and apply its exact JSON plan."""

        forge_command("branch", "--plugin", "wheel-smoke", "--skill", selected.name)
        arguments = [
            operation,
            "--source",
            str(selected),
            "--plugin",
            "wheel-smoke",
            "--version",
            version,
            "--license",
            "MIT",
            "--license-file",
            str(license_file),
            "--origin",
            sources.as_uri(),
            "--revision",
            fixture_revision(selected),
            "--source-subpath",
            selected.name,
            "--imported-at",
            "2026-09-22",
        ]
        if not plugin.exists():
            arguments.extend(
                [
                    "--category",
                    "Developer Tools",
                    "--description",
                    "An authored installed-wheel fixture.",
                    "--author",
                    "Smoke Test",
                ]
            )
        before = snapshot(fixture)
        plan = json.loads(forge_command(*arguments, "--json").stdout)
        if plan["operation"] != operation or snapshot(fixture) != before:
            raise RuntimeError("Review returned the wrong operation or changed the fixture.")
        apply_arguments = [*arguments, "--apply", "--expected-sha256", plan["plan_sha256"]]
        if operation == "update":
            sources_before = snapshot(sources)
            preview = forge_command(*arguments, "--diff").stdout
            if snapshot(fixture) != before or snapshot(sources) != sources_before:
                raise RuntimeError("The installed diff preview changed the fixture or its source.")
            expected_preview = (
                f"review plan sha256 {plan['plan_sha256']}",
                "--- a/skills/release-digest/SKILL.md",
                "+++ b/skills/release-digest/SKILL.md",
                "-Use this authored test fixture when asked",
                "+Use this revised authored test fixture when asked",
                "License evidence comparison (previous evidence -> proposed evidence)",
                "+++ b/licenses/release-digest/LICENSE",
                "+Additional fixture author: Update smoke test.",
            )
            if any(text not in preview for text in expected_preview):
                raise RuntimeError("The installed diff omitted the approved hash or reviewed text.")
            replay = shlex.split(preview.splitlines()[-1])
            if (
                replay[:4] != ["uv", "run", "forge", "update"]
                or "--apply" not in replay
                or f"--expected-sha256={plan['plan_sha256']}" not in replay
                or any(argument.split("=", 1)[0] == "--diff" for argument in replay)
            ):
                raise RuntimeError("The diff preview did not emit a valid approved apply command.")
            apply_arguments = replay[3:]
        forge_command(*arguments, "--apply", "--expected-sha256", "0" * 64, expected=2)
        if snapshot(fixture) != before:
            raise RuntimeError("Refusing an unapproved hash changed the fixture.")
        source_file = selected / "SKILL.md"
        reviewed_bytes = source_file.read_bytes()
        try:
            source_file.write_bytes(reviewed_bytes + b"\nUnreviewed fixture change.\n")
            forge_command(*apply_arguments, expected=2)
            if snapshot(fixture) != before:
                raise RuntimeError("Refusing a stale source plan changed the fixture.")
        finally:
            source_file.write_bytes(reviewed_bytes)
        applied = json.loads(forge_command(*apply_arguments, "--json").stdout)
        if applied != plan:
            raise RuntimeError("The installed CLI applied a different plan from the reviewed one.")
        if snapshot(plugin / "skills" / selected.name) != snapshot(selected):
            raise RuntimeError("Installed skill bytes, paths, or modes differ from their source.")
        forge_command("generate")
        forge_command("generate", "--check")
        forge_command("check")
        return plan

    validated_artifacts: dict[str, str] = {}

    def render_fixture_skill(skill: str, run_name: str) -> None:
        """Run a reviewed helper only after import validation, then inspect exact artifacts."""

        installed = plugin / "skills" / skill
        output = artifact_root / run_name
        command = [
            sys.executable,
            "-I",
            str(installed / "scripts/render.py"),
            "--input",
            str(installed / "assets/input.json"),
            "--output-dir",
            str(output),
        ]
        checkout_before = snapshot(fixture)
        run(command, cwd=installed, env=fixture_env)
        expected = installed / "assets/expected"
        output_before = snapshot(output)
        if output_before != snapshot(expected):
            raise RuntimeError(f"Installed {skill} artifacts differ from reviewed expected bytes.")
        validated_artifacts.update(
            {
                f"{run_name}/{name}": hashlib.sha256(content).hexdigest()
                for name, (content, _) in output_before.items()
                if content is not None
            }
        )
        run(command, cwd=installed, env=fixture_env, expected=2)
        if snapshot(output) != output_before or snapshot(fixture) != checkout_before:
            raise RuntimeError(f"Installed {skill} renderer overwrote artifacts or checkout files.")
        if skill == "release-digest":
            index = json.loads((output / "release-index.json").read_bytes())
            notes = (output / "release-notes.md").read_text(encoding="utf-8")
            if (
                index["version"] != "2.4.0"
                or index["change_count"] != 4
                or index["reference_ids"] != ["#17", "#18", "PR-42"]
                or "café/報告.md" not in notes
            ):
                raise RuntimeError("Installed release-digest produced the wrong release evidence.")
        else:
            summary = json.loads((output / "status-summary.json").read_bytes())
            chart = ET.parse(output / "status.svg").getroot()
            title = chart.find("{http://www.w3.org/2000/svg}title")
            bars = [
                element
                for element in chart.findall("{http://www.w3.org/2000/svg}rect")
                if "data-label" in element.attrib
            ]
            if (
                summary["total"] != 12
                or summary["max_count"] != 8
                or [bar.attrib["width"] for bar in bars] != ["420", "157", "52", "0"]
                or title is None
                or title.text != "Review status <Q3> & delivery"
            ):
                raise RuntimeError("Installed status-chart produced the wrong chart evidence.")

    artifact_root = temporary / "fixture artifacts"
    artifact_root.mkdir()
    review_and_apply("import", source, "0.1.0")
    render_fixture_skill(source.name, "release-digest-initial")
    finish_branch(source.name)
    review_and_apply("import", companion, "0.2.0")
    render_fixture_skill(companion.name, "status-chart")
    (plugin / "shared/work").mkdir(parents=True)
    (plugin / "shared/asset.txt").write_bytes(b"Shared plugin asset.\n")
    (plugin / "shared/server.py").write_bytes(
        b'raise RuntimeError("Smoke fixture MCP servers must never execute")\n'
    )
    (plugin / "mcp.json").write_text(
        json.dumps(
            {
                "$schema": "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json",
                "mcpServers": {
                    "inert-fixture": {
                        "type": "stdio",
                        "command": "python",
                        "args": ["${PLUGIN_ROOT}/shared/server.py"],
                        "cwd": "./shared/work",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    forge_command("check")
    finish_branch(companion.name)
    before = snapshot(plugin)
    catalog_before = (fixture / "catalog/plugins.json").read_bytes()
    manifest_before = json.loads((plugin / "plugin.json").read_bytes())
    (source / "SKILL.md").write_text(
        (source / "SKILL.md")
        .read_text(encoding="utf-8")
        .replace(
            "Use this authored test fixture when asked",
            "Use this revised authored test fixture when asked",
        ),
        encoding="utf-8",
        newline="\n",
    )
    (source / "changed.txt").write_bytes(b"Revised content.\n")
    (source / "removed.txt").unlink()
    (source / "references/added.txt").write_bytes(b"New supporting content.\n")
    if os.name != "nt":
        helper.chmod(0o755)
    license_file.write_bytes(
        original_license + b"\nAdditional fixture author: Update smoke test.\n"
    )
    plan = review_and_apply("update", source, "0.3.0")
    render_fixture_skill(source.name, "release-digest-updated")
    expected_changes = {
        "added": ["references/added.txt"],
        "removed": ["removed.txt"],
        "modified": ["SKILL.md", "changed.txt"],
        "mode_changed": ["scripts/render.py"] if os.name != "nt" else [],
    }
    if plan["changes"] != expected_changes:
        raise RuntimeError(f"Unexpected installed update review: {plan['changes']}")
    after = snapshot(plugin)
    for path, value in before.items():
        if path.startswith("skills/release-digest/") or path in {
            "plugin.json",
            "provenance/release-digest.json",
        }:
            continue
        if after.get(path) != value:
            raise RuntimeError(f"Update changed an unrelated plugin path: {path}")
    if (fixture / "catalog/plugins.json").read_bytes() != catalog_before:
        raise RuntimeError("The update changed shared catalog metadata.")
    manifest = json.loads((plugin / "plugin.json").read_bytes())
    if manifest != {**manifest_before, "version": "0.3.0"}:
        raise RuntimeError("The update changed manifest fields beyond its version.")
    record = json.loads((plugin / "provenance/release-digest.json").read_bytes())
    if (
        record["files"] != plan["files"]
        or record["fileModes"] != plan["file_modes"]
        or record["contentSha256"] != plan["content_sha256"]
        or record["revision"] != plan["review_payload"]["revision"]
        or record["licenseEvidence"]
        != {
            "path": "licenses/release-digest/LICENSE",
            "sha256": hashlib.sha256(license_file.read_bytes()).hexdigest(),
        }
        or (plugin / "licenses/release-digest/LICENSE").read_bytes() != license_file.read_bytes()
    ):
        raise RuntimeError("The update did not refresh the reviewed provenance and license bytes.")
    artifacts = capture_fixture_artifacts(artifact_root)
    final_hashes = {
        name: hashlib.sha256(content).hexdigest() for name, content in artifacts.items()
    }
    if final_hashes != validated_artifacts:
        raise RuntimeError("Fixture artifacts changed after installed skill validation.")
    return artifact_root, validated_artifacts


def archive_hashes(archives: list[Path]) -> dict[str, str]:
    """Hash the archive bytes built for and installed during qualification."""

    return {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in archives}


def is_linklike(path: Path) -> bool:
    """Reject symbolic links and Windows reparse points without following their targets."""

    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return False
    return stat.S_ISLNK(metadata.st_mode) or bool(
        getattr(metadata, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
    )


def read_regular_bytes(path: Path) -> tuple[bytes, int]:
    """Open a regular file without following POSIX links or blocking on FIFOs."""

    before = path.lstat()
    if is_linklike(path) or not stat.S_ISREG(before.st_mode):
        raise RuntimeError(f"Cannot read a linked or non-regular file: {path}")
    flags = (
        os.O_RDONLY
        | getattr(os, "O_BINARY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    with os.fdopen(os.open(path, flags), "rb") as file:
        opened = os.fstat(file.fileno())
        if not stat.S_ISREG(opened.st_mode) or (
            os.name != "nt" and (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino)
        ):
            raise RuntimeError(f"File changed type or identity before reading: {path}")
        return file.read(), opened.st_mode


def capture_fixture_artifacts(root: Path) -> dict[str, bytes]:
    """Read only regular fixture files, retaining their exact relative paths and bytes."""

    if is_linklike(root):
        raise RuntimeError(f"Cannot retain a linked fixture directory: {root}")
    captured: dict[str, bytes] = {}
    for path in sorted(root.rglob("*")):
        if is_linklike(path):
            raise RuntimeError(f"Cannot retain a linked fixture artifact: {path}")
        if path.is_dir():
            continue
        if not stat.S_ISREG(path.lstat().st_mode):
            raise RuntimeError(f"Cannot retain a non-regular fixture artifact: {path}")
        captured[path.relative_to(root).as_posix()] = read_regular_bytes(path)[0]
    return captured


def source_state(repo: Path, env: dict[str, str]) -> dict[str, Any]:
    """Bind visible source bytes and modes to the actual committed Git tree."""

    def git(*arguments: str) -> bytes:
        """Read raw Git output without changing NUL-delimited path bytes."""

        git_env = {key: value for key, value in env.items() if not key.startswith("GIT_")}
        git_env["GIT_NO_REPLACE_OBJECTS"] = "1"
        result = subprocess.run(
            ["git", *arguments],
            cwd=repo,
            env=git_env,
            capture_output=True,
            check=False,
            timeout=180,
        )
        if result.returncode:
            raise RuntimeError(
                f"Git {arguments!r} returned {result.returncode}: "
                f"{result.stderr.decode(errors='backslashreplace')}"
            )
        return result.stdout

    commit = git("rev-parse", "HEAD").decode("ascii").strip()
    status = git("status", "--porcelain=v1", "-z", "--untracked-files=all")
    paths = git("ls-files", "--cached", "--others", "--exclude-standard", "-z")
    committed: dict[str, tuple[str, str]] = {}
    for entry in git("ls-tree", "-r", "-z", "HEAD").split(b"\0"):
        if not entry:
            continue
        metadata, raw_path = entry.split(b"\t", 1)
        mode, kind, object_id = metadata.decode("ascii").split(" ")
        if kind != "blob" or mode not in {"100644", "100755"}:
            raise RuntimeError(f"Cannot verify a non-regular Git file: {os.fsdecode(raw_path)!r}")
        committed[os.fsdecode(raw_path)] = (mode, object_id)
    files: dict[str, Any] = {}
    mismatched = set(committed)
    for relative in sorted({os.fsdecode(path) for path in paths.split(b"\0") if path}):
        path = repo / relative
        if any(is_linklike(parent) for parent in (path, *path.parents)):
            raise RuntimeError(
                f"Cannot bind source through a symlink or reparse point: {relative!r}"
            )
        try:
            content, mode = read_regular_bytes(path)
        except FileNotFoundError:
            files[relative] = None
            continue
        files[relative] = {
            "sha256": hashlib.sha256(content).hexdigest(),
            "executable": bool(mode & 0o111),
        }
        previous = committed.get(relative)
        if previous is None:
            mismatched.add(relative)
            continue
        committed_mode, object_id = previous
        committed_bytes = git("cat-file", "blob", object_id)
        mode_matches = (
            committed_mode == "100644"
            if os.name == "nt"
            else (bool(mode & 0o111) == (committed_mode == "100755"))
        )
        if content == committed_bytes and mode_matches:
            mismatched.discard(relative)
    status_entries = [os.fsdecode(entry) for entry in status.split(b"\0") if entry]
    matches_commit = not status_entries and not mismatched
    return {
        "commit": commit,
        "dirty": not matches_commit,
        "git_status_dirty": bool(status_entries),
        "matches_commit": matches_commit,
        "commit_mismatch_paths": sorted(mismatched),
        "status_porcelain_v1": status_entries,
        "tree_sha256": hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest(),
        "tree_scope": "Git tracked and unignored untracked paths, raw bytes, and executable flags",
    }


def output_destination(value: Path) -> Path:
    """Require a fresh output path beneath an existing parent without symlink components."""

    destination = Path(os.path.abspath(value))
    if any(is_linklike(path) for path in (destination, *destination.parents)):
        raise RuntimeError("The retained output path must not contain symlinks or reparse points.")
    if destination.exists():
        raise RuntimeError(f"The retained output path already exists: {destination}")
    if not destination.parent.is_dir():
        raise RuntimeError("The retained output parent must be an existing directory.")
    return destination


def retain_archives(
    destination: Path,
    archives: list[Path],
    hashes: dict[str, str],
    source: dict[str, Any],
    env: dict[str, str],
    fixture_artifacts: tuple[Path, dict[str, str]] | None = None,
) -> None:
    """Export tested archives, authored skill artifacts, and a verified report."""

    destination = output_destination(destination)
    with tempfile.TemporaryDirectory(prefix=".forge-release-", dir=destination.parent) as directory:
        staged = Path(directory) / "artifacts"
        staged.mkdir()
        for archive in archives:
            content = archive.read_bytes()
            if hashlib.sha256(content).hexdigest() != hashes[archive.name]:
                raise RuntimeError(f"Tested archive changed before retention: {archive.name}")
            (staged / archive.name).write_bytes(content)
        fixture_hashes: dict[str, str] = {}
        if fixture_artifacts is not None:
            root, tested_hashes = fixture_artifacts
            captured = capture_fixture_artifacts(root)
            fixture_hashes = {
                name: hashlib.sha256(content).hexdigest() for name, content in captured.items()
            }
            if fixture_hashes != tested_hashes:
                raise RuntimeError("Fixture artifacts changed after installed skill validation.")
            for relative, content in captured.items():
                target = staged / "fixtures" / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
        checksums = "".join(f"{value}  {name}\n" for name, value in sorted(hashes.items()))
        (staged / "SHA256SUMS").write_text(checksums, encoding="utf-8", newline="\n")
        report = {
            "schema_version": 2,
            "smoke_passed": True,
            "source": source,
            "archives": hashes,
            "fixture_artifacts": fixture_hashes,
            "python": platform.python_version(),
            "platform": platform.platform(),
            "ci": {
                key: env[key]
                for key in (
                    "GITHUB_REPOSITORY",
                    "GITHUB_REF",
                    "GITHUB_SHA",
                    "GITHUB_RUN_ID",
                    "GITHUB_RUN_ATTEMPT",
                    "FORGE_PR_HEAD_SHA",
                )
                if env.get(key)
            },
        }
        (staged / "smoke-report.json").write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
        )
        # Reserve without replacement before moving files; failed exports remove only our directory.
        output_destination(destination)
        destination.mkdir()
        try:
            names = [archive.name for archive in archives]
            if fixture_artifacts is not None:
                names.append("fixtures")
            names.extend(["SHA256SUMS", "smoke-report.json"])
            # A hard interruption can leave an incomplete directory, but never a success report
            # ahead of the archives and their checksums.
            for name in names:
                (staged / name).replace(destination / name)
        except BaseException:
            shutil.rmtree(destination)
            raise


def build_and_smoke(
    repo: Path, temporary: Path, uv: str, env: dict[str, str]
) -> tuple[list[Path], dict[str, str], tuple[Path, dict[str, str]]]:
    """Build through an sdist and qualify the wheel's isolated installed workflow."""

    distributions = temporary / "dist"
    # uv build creates an sdist, then builds the wheel from that sdist.
    run([uv, "build", "--out-dir", str(distributions)], cwd=repo, env=env)
    wheels = list(distributions.glob("*.whl"))
    sources = list(distributions.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sources) != 1:
        raise RuntimeError("Expected exactly one wheel and one source distribution.")
    archives = [wheels[0], sources[0]]
    hashes = archive_hashes(archives)
    environment = temporary / "environment"
    run([uv, "venv", "--python", sys.executable, str(environment)], cwd=temporary, env=env)
    binaries = environment / ("Scripts" if os.name == "nt" else "bin")
    python = binaries / ("python.exe" if os.name == "nt" else "python")
    forge = binaries / ("forge.exe" if os.name == "nt" else "forge")
    run(
        [uv, "pip", "install", "--python", str(python), str(wheels[0])],
        cwd=temporary,
        env=env,
    )
    probe = run(
        [
            str(python),
            "-I",
            "-c",
            "import json, sys, agent_plugin_forge; "
            "print(json.dumps([sys.prefix, agent_plugin_forge.__file__]))",
        ],
        cwd=temporary,
        env=env,
    )
    prefix, module = (Path(value).resolve() for value in json.loads(probe.stdout))
    if prefix != environment or not module.is_relative_to(environment):
        raise RuntimeError(f"Forge was not imported from the isolated environment: {module}")
    if "site-packages" not in module.parts:
        raise RuntimeError(f"Forge was not loaded from installed site-packages: {module}")
    metadata = tomllib.loads((repo / "pyproject.toml").read_text(encoding="utf-8"))
    version = run([str(forge), "--version"], cwd=temporary, env=env)
    if version.stdout.strip() != f"agent-plugin-forge {metadata['project']['version']}":
        raise RuntimeError(f"Installed Forge reported an unexpected version: {version.stdout}")
    run([str(forge), "branch-name", "--branch", "forge/wheel-smoke"], cwd=temporary, env=env)
    diagnosis = run([str(forge), "doctor", "--json"], cwd=temporary, env=env, expected=2)
    report = json.loads(diagnosis.stdout)
    checkout = next(check for check in report["checks"] if check["name"] == "checkout")
    if report["ready"] or checkout["status"] != "error" or diagnosis.stderr:
        raise RuntimeError("Doctor did not return a clean JSON checkout failure.")
    run([str(forge), "check"], cwd=repo, env=env)
    fixture_artifacts = smoke_skill_workflow(forge, repo, temporary, env)
    if archive_hashes(archives) != hashes:
        raise RuntimeError("Distribution bytes changed during smoke qualification.")
    return archives, hashes, fixture_artifacts


def main(argv: list[str] | None = None) -> None:
    """Smoke-test an isolated wheel, optionally retaining the exact successful archives."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Retain successful archives, checksums, and report in a new directory.",
    )
    arguments = parser.parse_args(argv)
    destination = output_destination(arguments.output_dir) if arguments.output_dir else None
    repo = Path(__file__).resolve().parents[1]
    uv = shutil.which("uv")
    if uv is None:
        raise RuntimeError("Install uv before running the distribution smoke check.")
    env = dict(os.environ)
    for name in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"):
        env.pop(name, None)
    before = source_state(repo, env) if destination else None
    with tempfile.TemporaryDirectory(prefix="forge-wheel-smoke-") as directory:
        temporary = Path(directory).resolve()
        archives, hashes, fixture_artifacts = build_and_smoke(repo, temporary, uv, env)
        if destination is not None and before is not None:
            if source_state(repo, env) != before:
                raise RuntimeError(
                    "Source checkout changed during qualification; no archives retained."
                )
            retain_archives(destination, archives, hashes, before, env, fixture_artifacts)
            print(f"Retained tested archives, skill artifacts, and smoke report in {destination}")
    print(
        "Built sdist and wheel; installed import, update, artifact, and repository checks passed."
    )


if __name__ == "__main__":
    main()
