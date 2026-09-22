"""Build both archives and exercise the installed Forge CLI in a fresh environment."""

from __future__ import annotations

import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import tomllib
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


def smoke_skill_workflow(forge: Path, repo: Path, temporary: Path, env: dict[str, str]) -> None:
    """Exercise reviewed imports and an update using only the installed CLI."""

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
    source = sources / "sample-skill"
    companion = sources / "companion"
    (source / "scripts").mkdir(parents=True)
    companion.mkdir()
    for path in (source, companion):
        (path / "SKILL.md").write_bytes(
            f"---\nname: {path.name}\ndescription: Authored smoke fixture.\n---\n\n"
            "Read the supplied text. Never execute the fixture scripts.\n".encode()
        )
    (source / "changed.txt").write_bytes(b"Original content.\n")
    (source / "removed.txt").write_bytes(b"Obsolete content.\n")
    (source / "kept.txt").write_bytes(b"Preserved content.\n")
    helper = source / "scripts/helper.py"
    helper.write_bytes(b'raise RuntimeError("Smoke fixture scripts must never execute")\n')
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
                "--- a/skills/sample-skill/SKILL.md",
                "+++ b/skills/sample-skill/SKILL.md",
                "-Read the supplied text. Never execute the fixture scripts.",
                "+Read the revised text. Never execute the fixture scripts.",
                "License evidence comparison (previous evidence -> proposed evidence)",
                "+++ b/licenses/sample-skill/LICENSE",
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

    review_and_apply("import", source, "0.1.0")
    finish_branch(source.name)
    review_and_apply("import", companion, "0.2.0")
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
    (source / "SKILL.md").write_bytes(
        b"---\nname: sample-skill\ndescription: Revised authored smoke fixture.\n---\n\n"
        b"Read the revised text. Never execute the fixture scripts.\n"
    )
    (source / "changed.txt").write_bytes(b"Revised content.\n")
    (source / "removed.txt").unlink()
    (source / "references").mkdir()
    (source / "references/added.txt").write_bytes(b"New supporting content.\n")
    if os.name != "nt":
        helper.chmod(0o755)
    license_file.write_bytes(
        original_license + b"\nAdditional fixture author: Update smoke test.\n"
    )
    plan = review_and_apply("update", source, "0.3.0")
    expected_changes = {
        "added": ["references/added.txt"],
        "removed": ["removed.txt"],
        "modified": ["SKILL.md", "changed.txt"],
        "mode_changed": ["scripts/helper.py"] if os.name != "nt" else [],
    }
    if plan["changes"] != expected_changes:
        raise RuntimeError(f"Unexpected installed update review: {plan['changes']}")
    after = snapshot(plugin)
    for path, value in before.items():
        if path.startswith("skills/sample-skill/") or path in {
            "plugin.json",
            "provenance/sample-skill.json",
        }:
            continue
        if after.get(path) != value:
            raise RuntimeError(f"Update changed an unrelated plugin path: {path}")
    if (fixture / "catalog/plugins.json").read_bytes() != catalog_before:
        raise RuntimeError("The update changed shared catalog metadata.")
    manifest = json.loads((plugin / "plugin.json").read_bytes())
    if manifest != {**manifest_before, "version": "0.3.0"}:
        raise RuntimeError("The update changed manifest fields beyond its version.")
    record = json.loads((plugin / "provenance/sample-skill.json").read_bytes())
    if (
        record["files"] != plan["files"]
        or record["fileModes"] != plan["file_modes"]
        or record["contentSha256"] != plan["content_sha256"]
        or record["revision"] != plan["review_payload"]["revision"]
        or record["licenseEvidence"]
        != {
            "path": "licenses/sample-skill/LICENSE",
            "sha256": hashlib.sha256(license_file.read_bytes()).hexdigest(),
        }
        or (plugin / "licenses/sample-skill/LICENSE").read_bytes() != license_file.read_bytes()
    ):
        raise RuntimeError("The update did not refresh the reviewed provenance and license bytes.")


def main() -> None:
    """Build through the source distribution and smoke-test an isolated wheel install."""

    repo = Path(__file__).resolve().parents[1]
    uv = shutil.which("uv")
    if uv is None:
        raise RuntimeError("Install uv before running the distribution smoke check.")
    env = dict(os.environ)
    for name in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"):
        env.pop(name, None)
    with tempfile.TemporaryDirectory(prefix="forge-wheel-smoke-") as directory:
        temporary = Path(directory).resolve()
        distributions = temporary / "dist"
        # uv build creates an sdist, then builds the wheel from that sdist.
        run([uv, "build", "--out-dir", str(distributions)], cwd=repo, env=env)
        wheels = list(distributions.glob("*.whl"))
        sources = list(distributions.glob("*.tar.gz"))
        if len(wheels) != 1 or len(sources) != 1:
            raise RuntimeError("Expected exactly one wheel and one source distribution.")
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
        smoke_skill_workflow(forge, repo, temporary, env)
    print("Built sdist and wheel; installed import, update, and repository checks passed.")


if __name__ == "__main__":
    main()
