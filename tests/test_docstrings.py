"""Test complete docstring coverage in shipped Python code."""

from __future__ import annotations

import ast
from pathlib import Path


def test_non_test_python_definitions_have_docstrings() -> None:
    repo = Path(__file__).parents[1]
    missing: list[str] = []
    for source_root in (repo / "src", repo / "plugins", repo / "examples"):
        for path in sorted(source_root.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            if ast.get_docstring(tree) is None:
                missing.append(f"{path.relative_to(repo)}:1: module")
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef) and (
                    ast.get_docstring(node) is None
                ):
                    missing.append(f"{path.relative_to(repo)}:{node.lineno}: {node.name}")
    assert not missing, "Missing docstrings:\n" + "\n".join(missing)
