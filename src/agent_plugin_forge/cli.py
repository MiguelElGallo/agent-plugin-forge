"""Provide the command-line interface for Agent Plugin Forge workflows."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pydantic import ValidationError

from .common import ForgeError, repository_root
from .generator import generate, generation_drift
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


def _parser() -> argparse.ArgumentParser:
    """Build the top-level command-line parser and its subcommands."""

    parser = argparse.ArgumentParser(
        prog="forge", description="Package Agent Skills and MCP servers safely"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    branch = subparsers.add_parser("branch", help="Create a collision-safe branch for one skill")
    branch.add_argument("--plugin", required=True)
    branch.add_argument("--skill", required=True)
    branch.add_argument("--base", default="main")

    maintenance = subparsers.add_parser(
        "maintenance-branch", help="Create a collision-safe branch for forge changes"
    )
    maintenance.add_argument("--topic", required=True)
    maintenance.add_argument("--base", default="main")

    plugin_branch = subparsers.add_parser(
        "plugin-branch", help="Create a scoped branch for MCP or plugin-wide changes"
    )
    plugin_branch.add_argument("--plugin", required=True)
    plugin_branch.add_argument("--topic", required=True)
    plugin_branch.add_argument("--base", default="main")

    branch_name = subparsers.add_parser("branch-name", help="Validate a PR branch name")
    branch_name.add_argument("--branch", required=True)

    pr_scope = subparsers.add_parser("pr-scope", help="Validate a PR diff against its branch scope")
    pr_scope.add_argument("--branch", required=True)
    pr_scope.add_argument("--base", required=True)

    import_parser = subparsers.add_parser("import", help="Plan or apply a local skill import")
    import_parser.add_argument("--source", type=Path, required=True)
    import_parser.add_argument(
        "--source-skill", help="Select one immediate skill when --source is an existing plugin"
    )
    import_parser.add_argument("--plugin")
    import_parser.add_argument("--category")
    import_parser.add_argument("--version")
    import_parser.add_argument("--description")
    import_parser.add_argument("--author")
    import_parser.add_argument("--license", dest="license_id", required=True)
    import_parser.add_argument("--license-file", type=Path, required=True)
    import_parser.add_argument("--origin", required=True)
    import_parser.add_argument("--revision", required=True)
    import_parser.add_argument("--source-subpath", default=".")
    import_parser.add_argument("--imported-at", default=default_import_date())
    import_parser.add_argument("--transformation", action="append", default=[])
    import_parser.add_argument("--expected-sha256")
    import_parser.add_argument("--apply", action="store_true")

    generate_parser = subparsers.add_parser("generate", help="Generate client distribution files")
    generate_parser.add_argument("--check", action="store_true")
    subparsers.add_parser("check", help="Validate the complete repository")
    return parser


def _request(args: argparse.Namespace) -> ImportRequest:
    """Convert parsed import arguments into a validated import request."""

    source = args.source.absolute()
    plugin = args.plugin or resolve_skill_source(source, args.source_skill).name
    return ImportRequest(
        source=source,
        source_skill=args.source_skill,
        plugin=plugin,
        category=args.category,
        version=args.version,
        description=args.description,
        author=args.author,
        license_id=args.license_id,
        license_file=args.license_file.absolute(),
        origin=args.origin,
        revision=args.revision,
        source_subpath=args.source_subpath,
        imported_at=args.imported_at,
        expected_sha256=args.expected_sha256,
        transformations=tuple(args.transformation),
    )


def run(argv: list[str] | None = None) -> int:
    """Run one forge command and return its process exit status."""

    args = _parser().parse_args(argv)
    repo = repository_root()
    if args.command == "branch":
        print(f"Created {create_skill_branch(repo, args.plugin, args.skill, args.base)}")
        return 0
    if args.command == "maintenance-branch":
        print(f"Created {create_maintenance_branch(repo, args.topic, args.base)}")
        return 0
    if args.command == "plugin-branch":
        print(f"Created {create_plugin_branch(repo, args.plugin, args.topic, args.base)}")
        return 0
    if args.command == "branch-name":
        if args.branch.startswith("forge/"):
            print(f"Valid maintenance branch for {validate_maintenance_branch(args.branch)}")
        elif args.branch.startswith("plugin/"):
            plugin, topic = validate_plugin_branch(args.branch)
            print(f"Valid plugin branch for {plugin}/{topic}")
        else:
            plugin, skill = validate_skill_branch(args.branch)
            print(f"Valid skill branch for {plugin}/{skill}")
        return 0
    if args.command == "pr-scope":
        changed = validate_pr_scope(repo, args.branch, args.base)
        print(f"Valid PR scope ({len(changed)} changed paths)")
        return 0
    if args.command == "import":
        request = _request(args)
        plan = apply_import(repo, request) if args.apply else plan_import(repo, request)
        action = "Imported" if args.apply else "Plan"
        print(
            f"{action}: {plan.skill} -> plugins/{plan.plugin}/skills/{plan.skill} "
            f"({plan.file_count} files, repository {plan.repository_url}, "
            f"content sha256 {plan.content_sha256}, "
            f"review plan sha256 {plan.plan_sha256})"
        )
        if not args.apply:
            print("No files changed. Review the source and repeat with --apply.")
        return 0
    if args.command == "generate":
        if args.check:
            errors = generation_drift(repo)
            if errors:
                raise ForgeError("\n".join(errors))
        else:
            generate(repo)
        return 0
    if args.command == "check":
        assert_valid_repository(repo)
        print("Agent Plugin Forge checks passed")
        return 0
    raise AssertionError(args.command)


def main() -> None:
    """Run the CLI entry point and translate expected errors into exit code 2."""

    try:
        raise SystemExit(run())
    except (ForgeError, ValidationError) as exc:
        print(f"forge: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
