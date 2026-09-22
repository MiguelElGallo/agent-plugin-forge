"""Build both archives and exercise the installed Forge CLI in a fresh environment."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path


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
    print("Built sdist and wheel; isolated installed CLI and repository checks passed.")


if __name__ == "__main__":
    main()
