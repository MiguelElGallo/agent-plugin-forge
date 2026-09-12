"""Define user-correctable errors and safe human-readable diagnostic rendering."""

_CONTROL_ESCAPES = {
    codepoint: f"\\x{codepoint:02x}" for codepoint in (*range(32), *range(127, 160))
}
_CONTROL_ESCAPES.update({ord("\t"): "\\t", ord("\n"): "\\n", ord("\r"): "\\r"})
# POSIX surrogateescape can encode these back into raw terminal-control bytes.
# Escape all lone surrogates for safe display under any stdout error handler.
_CONTROL_ESCAPES.update({codepoint: f"\\u{codepoint:04x}" for codepoint in range(0xD800, 0xE000)})
_TERMINAL_ESCAPES = {
    codepoint: replacement
    for codepoint, replacement in _CONTROL_ESCAPES.items()
    if codepoint != ord("\n")
}


def diagnostic_value(value: object) -> str:
    """Make controls visible in an untrusted value while preserving Unicode text.

    Apply this to paths, names, and external error details before interpolating
    them into a diagnostic. Newlines in values are escaped so only the calling
    formatter can introduce new output lines. This is for display, not storage.
    """

    return str(value).translate(_CONTROL_ESCAPES)


def terminal_text(value: object) -> str:
    """Neutralize remaining terminal controls while preserving trusted line breaks.

    Untrusted values must first pass through ``diagnostic_value`` so their line
    breaks cannot be confused with the formatter's deliberate layout.
    """

    return str(value).translate(_TERMINAL_ESCAPES)


class ForgeError(ValueError):
    """A user-correctable forge error with an actionable message."""
