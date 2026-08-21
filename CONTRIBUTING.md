# Contributing skills

Each skill change uses its own `skill/<plugin>/<skill>` branch and pull request. The seed commit on `main` is the one-time bootstrap exception required before protection can be enabled.

1. Install the locked environment with `uv sync --locked`.
2. From a clean and current `main`, run `uv run forge branch --plugin NAME --skill NAME`.
3. Stage remote content locally at an immutable revision. Inspect it; do not execute it.
4. Run `uv run forge import` without `--apply` and review the plan.
5. Repeat with `--apply --expected-sha256 HASH` and a reviewed `--license-file`, then run `uv run forge generate`.
6. Run `uv run forge check`, Ruff, ty, pytest, and strict Zensical build.
7. Review the full diff and open a pull request.

New plugins require a category, version, description, author, license, origin, and immutable revision. Adding a skill to a bundle inherits the bundle category and requires a version bump.

Imported content remains under its upstream license. This repository's MIT license does not replace third-party terms.
