"""Provide the Typer command-line interface for Agent Plugin Forge workflows."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError

from .common import ForgeError, repository_root
from .generator import generate as generate_repository
from .generator import generation_drift
from .gitflow import (
    create_maintenance_branch,
    create_plugin_branch,
    create_skill_branch,
    validate_maintenance_branch,
    validate_plugin_branch,
    validate_pr_scope,
    validate_skill_branch,
)
from .importer import ImportRequest, apply_import, default_import_date, plan_import
from .sources import resolve_skill_source
from .validator import assert_valid_repository

app = typer.Typer(
    name="forge",
    help="Package Agent Skills and MCP servers safely.",
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
)


@app.command("branch", help="Create a collision-safe branch for one skill.")
def branch_command(
    plugin: Annotated[str, typer.Option(help="Destination plugin name.")],
    skill: Annotated[str, typer.Option(help="Skill name.")],
    base: Annotated[str, typer.Option(help="Local and remote base branch.")] = "main",
) -> None:
    """Create a skill-scoped branch from the current remote base."""

    repo = repository_root()
    typer.echo(f"Created {create_skill_branch(repo, plugin, skill, base)}")


@app.command("maintenance-branch", help="Create a collision-safe branch for forge changes.")
def maintenance_branch_command(
    topic: Annotated[str, typer.Option(help="Maintenance topic used in the branch name.")],
    base: Annotated[str, typer.Option(help="Local and remote base branch.")] = "main",
) -> None:
    """Create a forge-maintenance branch from the current remote base."""

    repo = repository_root()
    typer.echo(f"Created {create_maintenance_branch(repo, topic, base)}")


@app.command("plugin-branch", help="Create a scoped branch for MCP or plugin-wide changes.")
def plugin_branch_command(
    plugin: Annotated[str, typer.Option(help="Plugin name.")],
    topic: Annotated[str, typer.Option(help="Plugin-wide change topic.")],
    base: Annotated[str, typer.Option(help="Local and remote base branch.")] = "main",
) -> None:
    """Create a plugin-scoped branch from the current remote base."""

    repo = repository_root()
    typer.echo(f"Created {create_plugin_branch(repo, plugin, topic, base)}")


@app.command("branch-name", help="Validate a pull-request branch name.")
def branch_name_command(
    branch: Annotated[str, typer.Option(help="Branch name to validate.")],
) -> None:
    """Validate one supported scoped branch name."""

    if branch.startswith("forge/"):
        typer.echo(f"Valid maintenance branch for {validate_maintenance_branch(branch)}")
    elif branch.startswith("plugin/"):
        plugin, topic = validate_plugin_branch(branch)
        typer.echo(f"Valid plugin branch for {plugin}/{topic}")
    else:
        plugin, skill = validate_skill_branch(branch)
        typer.echo(f"Valid skill branch for {plugin}/{skill}")


@app.command("pr-scope", help="Validate a pull-request diff against its branch scope.")
def pr_scope_command(
    branch: Annotated[str, typer.Option(help="Scoped pull-request branch name.")],
    base: Annotated[str, typer.Option(help="Pull-request base branch.")],
) -> None:
    """Validate changed paths against the scope encoded by a branch name."""

    changed = validate_pr_scope(repository_root(), branch, base)
    typer.echo(f"Valid PR scope ({len(changed)} changed paths)")


def _import_request(
    *,
    source: Path,
    source_skill: str | None,
    plugin: str | None,
    category: str | None,
    version: str | None,
    description: str | None,
    author: str | None,
    license_id: str,
    license_file: Path,
    origin: str,
    revision: str,
    source_subpath: str,
    imported_at: str,
    expected_sha256: str | None,
    transformations: list[str] | None,
) -> ImportRequest:
    """Build a validated import request from typed command options."""

    absolute_source = source.absolute()
    plugin_name = plugin or resolve_skill_source(absolute_source, source_skill).name
    try:
        import_date = date.fromisoformat(imported_at)
    except ValueError as exc:
        raise ForgeError("--imported-at must use the YYYY-MM-DD date form") from exc
    return ImportRequest(
        source=absolute_source,
        source_skill=source_skill,
        plugin=plugin_name,
        category=category,
        version=version,
        description=description,
        author=author,
        license_id=license_id,
        license_file=license_file.absolute(),
        origin=origin,
        revision=revision,
        source_subpath=source_subpath,
        imported_at=import_date,
        expected_sha256=expected_sha256,
        transformations=tuple(transformations or ()),
    )


@app.command("import", help="Plan or apply a local skill import.")
def import_command(
    source: Annotated[Path, typer.Option(help="Skill, SKILL.md, or plugin source path.")],
    license_id: Annotated[str, typer.Option("--license", help="SPDX license expression.")],
    license_file: Annotated[Path, typer.Option(help="Source license file to review and copy.")],
    origin: Annotated[str, typer.Option(help="Canonical source repository URL.")],
    revision: Annotated[str, typer.Option(help="Immutable source revision.")],
    source_skill: Annotated[
        str | None,
        typer.Option(help="Immediate skill to select from a source plugin."),
    ] = None,
    plugin: Annotated[str | None, typer.Option(help="Destination plugin name.")] = None,
    category: Annotated[str | None, typer.Option(help="Marketplace category.")] = None,
    version: Annotated[str | None, typer.Option(help="Destination plugin version.")] = None,
    description: Annotated[str | None, typer.Option(help="Destination plugin description.")] = None,
    author: Annotated[str | None, typer.Option(help="Destination plugin author.")] = None,
    source_subpath: Annotated[str, typer.Option(help="Path within the source repository.")] = ".",
    imported_at: Annotated[str, typer.Option(help="Import date in YYYY-MM-DD form.")] = (
        default_import_date()
    ),
    transformation: Annotated[
        list[str] | None,
        typer.Option(help="Reviewed transformation; repeat for multiple entries."),
    ] = None,
    expected_sha256: Annotated[
        str | None,
        typer.Option(help="Previously reviewed plan SHA-256 required by --apply."),
    ] = None,
    apply: Annotated[
        bool,
        typer.Option("--apply", help="Apply the reviewed import plan."),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Print the complete review plan as JSON only."),
    ] = False,
) -> None:
    """Plan an import by default, or apply an exact reviewed plan."""

    request = _import_request(
        source=source,
        source_skill=source_skill,
        plugin=plugin,
        category=category,
        version=version,
        description=description,
        author=author,
        license_id=license_id,
        license_file=license_file,
        origin=origin,
        revision=revision,
        source_subpath=source_subpath,
        imported_at=imported_at,
        expected_sha256=expected_sha256,
        transformations=transformation,
    )
    repo = repository_root()
    plan = apply_import(repo, request) if apply else plan_import(repo, request)
    if json_output:
        typer.echo(plan.model_dump_json(indent=2))
        return
    action = "Imported" if apply else "Plan"
    typer.echo(
        f"{action}: {plan.skill} -> plugins/{plan.plugin}/skills/{plan.skill} "
        f"({plan.file_count} files, repository {plan.repository_url}, "
        f"content sha256 {plan.content_sha256}, "
        f"review plan sha256 {plan.plan_sha256})"
    )
    if not apply:
        typer.echo("No files changed. Review the source and repeat with --apply.")


@app.command("generate", help="Generate client distribution files.")
def generate_command(
    check: Annotated[
        bool,
        typer.Option(
            "--check",
            help="Report generated-file drift without writing.",
        ),
    ] = False,
) -> None:
    """Generate client indexes or verify that committed output is current."""

    repo = repository_root()
    if check:
        errors = generation_drift(repo)
        if errors:
            raise ForgeError("\n".join(errors))
    else:
        generate_repository(repo)


@app.command("check", help="Validate the complete repository.")
def check_command() -> None:
    """Validate all authoritative and generated repository content."""

    assert_valid_repository(repository_root())
    typer.echo("Agent Plugin Forge checks passed")


def run(argv: list[str] | None = None) -> int:
    """Invoke the Typer app programmatically and return a successful status."""

    app(args=argv, prog_name="forge", standalone_mode=False)
    return 0


def main() -> None:
    """Run the CLI entry point and translate expected errors into exit code 2."""

    try:
        app(prog_name="forge")
    except (ForgeError, ValidationError) as exc:
        typer.echo(f"forge: {exc}", err=True)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
