"""Test visible control-character escaping at diagnostic display boundaries."""

import io
import os
from pathlib import Path

import pytest
import typer

from agent_plugin_forge.errors import diagnostic_value, terminal_text


@pytest.mark.parametrize("codepoint", [0xD800, 0xDC00, 0xDC80, 0xDC9B, 0xDCFF, 0xDFFF])
def test_diagnostic_values_escape_lone_surrogates(codepoint: int) -> None:
    value = f"before{chr(codepoint)}after"
    expected = f"before\\u{codepoint:04x}after"
    assert diagnostic_value(value) == expected
    assert terminal_text(value) == expected


@pytest.mark.skipif(os.name == "nt", reason="POSIX filenames use surrogateescape")
def test_surrogateescape_does_not_restore_raw_c1_controls_on_stdout() -> None:
    value = os.fsdecode(b"/tmp/source-\x9b2J/SKILL.md")
    stream = io.BytesIO()
    stdout = io.TextIOWrapper(stream, encoding="utf-8", errors="surrogateescape")
    typer.echo(diagnostic_value(value), file=stdout)
    stdout.flush()
    assert stream.getvalue() == b"/tmp/source-\\udc9b2J/SKILL.md\n"


@pytest.mark.parametrize("codepoint", [*range(32), *range(127, 160)])
def test_diagnostic_values_escape_every_terminal_control(codepoint: int) -> None:
    control = chr(codepoint)
    rendered = diagnostic_value(f"before{control}after")

    assert control not in rendered
    assert rendered.startswith("before\\")
    assert rendered.endswith("after")
    assert diagnostic_value(rendered) == rendered


def test_diagnostic_values_keep_unicode_paths_readable() -> None:
    path = Path("資料") / "café-Åland-🧪.txt"

    assert diagnostic_value(path) == str(path)
    assert diagnostic_value("line\nreturn\rtab\tdelete\x7fCSI\x9b") == (
        r"line\nreturn\rtab\tdelete\x7fCSI\x9b"
    )


def test_terminal_guard_preserves_only_trusted_newlines() -> None:
    value = diagnostic_value("untrusted\nforged success\x1b[2J\x9b0m")
    message = f"First issue:\n  {value}\nSecond issue:\tbad\rvalue\x00"

    assert terminal_text(message) == (
        "First issue:\n  untrusted\\nforged success\\x1b[2J\\x9b0m\n"
        "Second issue:\\tbad\\rvalue\\x00"
    )
