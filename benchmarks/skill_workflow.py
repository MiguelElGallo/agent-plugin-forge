"""Benchmark the shipped skill's deterministic local workflow with synthetic fixtures."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path
from time import perf_counter

from agent_plugin_forge import __version__
from agent_plugin_forge.common import tree_hash
from agent_plugin_forge.filesystem import file_hashes

REPO = Path(__file__).resolve().parents[1]
BOOTSTRAP = (
    REPO / "plugins/agent-plugin-forge/skills/package-agent-skill/scripts/bootstrap_forge.py"
)


def command(args: list[str], cwd: Path, environment: dict[str, str], expected: int = 0) -> str:
    """Run a bounded fixture command and fail on unexpected status."""

    result = subprocess.run(
        args, cwd=cwd, env=environment, capture_output=True, text=True, timeout=120, check=False
    )
    if result.returncode != expected:
        raise RuntimeError(f"{args[0:3]} exited {result.returncode}: {result.stderr}")
    return result.stdout


def git(cwd: Path, environment: dict[str, str], *args: str) -> str:
    """Run Git against a local benchmark fixture without inherited user configuration."""

    return command(["git", *args], cwd, environment).strip()


def fixture(root: Path, file_count: int, environment: dict[str, str]) -> tuple[Path, Path]:
    """Create a local bare remote and an inert skill with the requested file count."""

    seed = root / "seed"
    seed.mkdir()
    (seed / "catalog").mkdir()
    (seed / "plugins").mkdir()
    shutil.copytree(REPO / "schemas", seed / "schemas")
    catalog = {
        "marketplace": {
            "name": "benchmark-forge",
            "displayName": "Benchmark Forge",
            "owner": {"name": "Benchmark", "email": "benchmark@example.invalid"},
            "description": "Synthetic local benchmark",
            "version": "0.1.0",
        },
        "plugins": [],
    }
    (seed / "catalog/plugins.json").write_text(json.dumps(catalog), encoding="utf-8")
    (seed / "pyproject.toml").write_text("[project]\nname='benchmark'\n", encoding="utf-8")
    git(seed, environment, "init", "-b", "main")
    git(seed, environment, "add", ".")
    git(seed, environment, "commit", "-m", "seed")
    remote = root / "remote.git"
    git(root, environment, "init", "--bare", "-b", "main", str(remote))
    git(seed, environment, "remote", "add", "origin", str(remote))
    git(seed, environment, "push", "origin", "main")
    source = root / "sample-skill"
    source.mkdir()
    (source / "SKILL.md").write_text(
        "---\nname: sample-skill\ndescription: Inert benchmark skill.\n---\n\nReply OK.\n",
        encoding="utf-8",
    )
    for index in range(file_count - 1):
        (source / f"asset-{index:05d}.txt").write_text("synthetic asset\n" * 64, encoding="utf-8")
    shutil.copyfile(REPO / "LICENSE", root / "LICENSE")
    return remote, source


def sample(root: Path, file_count: int, environment: dict[str, str]) -> dict[str, float]:
    """Measure a fresh local workflow and assert review, drift, and duplicate protections."""

    root.mkdir()
    remote, source = fixture(root, file_count, environment)
    checkout = root / "review"
    timings: dict[str, float] = {}

    def timed(name: str, args: list[str], cwd: Path, expected: int = 0) -> str:
        """Measure one complete process, including interpreter and CLI startup."""

        started = perf_counter()
        output = command(args, cwd, environment, expected)
        timings[name] = round((perf_counter() - started) * 1000, 3)
        return output

    bootstrap = [
        sys.executable,
        str(BOOTSTRAP),
        "--config",
        str(root / "forge-settings.json"),
        "--origin",
        str(remote),
        "--destination",
        str(checkout),
    ]
    fresh = json.loads(timed("bootstrap_fresh", bootstrap, root))
    reused = json.loads(timed("bootstrap_reuse", [*bootstrap, "--reuse"], root))
    assert fresh == reused and fresh["host"] == "local"
    cli = [sys.executable, "-m", "agent_plugin_forge.cli"]
    timed(
        "branch", [*cli, "branch", "--plugin", "sample-skill", "--skill", "sample-skill"], checkout
    )
    args = [
        *cli,
        "import",
        "--source",
        str(source),
        "--plugin",
        "sample-skill",
        "--category",
        "Developer Tools",
        "--version",
        "0.1.0",
        "--description",
        "Synthetic benchmark plugin",
        "--author",
        "Benchmark",
        "--license",
        "MIT",
        "--license-file",
        str(root / "LICENSE"),
        "--origin",
        str(remote),
        "--revision",
        f"sha256:{tree_hash(file_hashes(source, required_root_file='SKILL.md'))}",
        "--source-subpath",
        ".",
        "--imported-at",
        "2026-09-11",
    ]
    before = git(checkout, environment, "status", "--porcelain")
    first = json.loads(timed("plan", [*args, "--json"], checkout))
    repeat = json.loads(command([*args, "--json"], checkout, environment))
    assert first == repeat and first["file_count"] == file_count
    assert git(checkout, environment, "status", "--porcelain") == before
    assert first["repository_url"] == remote.as_uri()
    source_file = source / "SKILL.md"
    content = source_file.read_bytes()
    source_file.write_bytes(content + b"\nChanged after review.\n")
    approved = [*args, "--apply", "--expected-sha256", first["plan_sha256"]]
    timed("reject_changed_source", approved, checkout, expected=2)
    assert not (checkout / "plugins/sample-skill").exists()
    source_file.write_bytes(content)
    timed("apply", approved, checkout)
    copied = checkout / "plugins/sample-skill/skills/sample-skill"
    assert {p.name: p.read_bytes() for p in source.iterdir()} == {
        p.name: p.read_bytes() for p in copied.iterdir()
    }
    timed("generate", [*cli, "generate"], checkout)
    timed("check", [*cli, "check"], checkout)
    timed("reject_duplicate", [*args, "--json"], checkout, expected=2)
    git(checkout, environment, "add", ".")
    git(checkout, environment, "commit", "-m", "add reviewed skill")
    timed(
        "pr_scope",
        [*cli, "pr-scope", "--branch", "skill/sample-skill/sample-skill", "--base", "main"],
        checkout,
    )
    return timings


def main() -> None:
    """Write raw samples and median timings without imposing machine-dependent CI thresholds."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--sizes", type=int, nargs="+", default=[1, 100, 1000])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= args.runs <= 20 or any(not 1 <= size <= 10000 for size in args.sizes):
        parser.error("Use 1-20 runs and sizes of 1-10000 files")
    environment: dict[str, str] = {
        **os.environ,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_AUTHOR_NAME": "Benchmark",
        "GIT_AUTHOR_EMAIL": "benchmark@example.invalid",
        "GIT_COMMITTER_NAME": "Benchmark",
        "GIT_COMMITTER_EMAIL": "benchmark@example.invalid",
        "PYTHONPATH": str(REPO / "src"),
    }
    for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        environment.pop(key, None)
    results = {}
    with tempfile.TemporaryDirectory(prefix="forge-benchmark-") as temporary:
        for size in args.sizes:
            samples = [
                sample(Path(temporary) / f"size-{size}-run-{run}", size, environment)
                for run in range(args.runs)
            ]
            medians = {
                stage: round(statistics.median(row[stage] for row in samples), 3)
                for stage in samples[0]
            }
            results[str(size)] = {"samples_ms": samples, "median_ms": medians}
            print(json.dumps({"files": size, "median_ms": medians}), flush=True)
    report = {
        "forge_version": __version__,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "runs_per_size": args.runs,
        "method": (
            "Complete CLI process timings; fresh fixtures; "
            "warm dependency and OS caches; local Git only."
        ),
        "excludes": [
            "network",
            "LLM reasoning",
            "human review",
            "client install",
            "full test suite",
        ],
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
