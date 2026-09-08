"""Low-level Verilog text helpers for the ISCAS parser."""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator

_IDENTIFIER = re.compile(r"^[A-Za-z_]\w*$")


class ParseError(ValueError):
    """Raised when Verilog text cannot be parsed."""


def strip_comment_lines(lines: Iterable[str]) -> Iterator[str]:
    """Yield lines that are not full-line // comments."""
    for line in lines:
        if line.strip().startswith("//"):
            continue
        yield line.rstrip("\n")


def split_identifiers(text: str) -> list[str]:
    """Split a comma-separated identifier list, preserving order."""
    normalized = " ".join(text.split())
    if not normalized:
        return []
    names = [part.strip() for part in normalized.split(",")]
    names = [name for name in names if name]
    for name in names:
        if not _IDENTIFIER.match(name):
            raise ParseError(f"invalid Verilog identifier: {name!r}")
    return names


_ENDMODULE_WITH_SEMICOLON_RE = re.compile(r"^\s*endmodule\s*;\s*$", re.IGNORECASE)


def _reject_endmodule_with_semicolon(statement: str) -> None:
    if _ENDMODULE_WITH_SEMICOLON_RE.match(statement):
        raise ParseError("endmodule must not be terminated with a semicolon")


def iter_statements(lines: Iterable[str]) -> Iterator[str]:
    """Join physical lines into statements.

    Most statements end with ';'. ``endmodule`` is a standalone keyword and
    must not include a trailing semicolon.
    """
    buffer = ""
    for line in strip_comment_lines(lines):
        chunk = line.strip()
        if not chunk:
            continue
        buffer = f"{buffer} {chunk}".strip() if buffer else chunk
        while ";" in buffer:
            semicolon = buffer.index(";")
            statement = buffer[: semicolon + 1].strip()
            buffer = buffer[semicolon + 1 :].strip()
            if statement:
                _reject_endmodule_with_semicolon(statement)
                yield statement
    if buffer:
        leftover = buffer.strip()
        if leftover.lower() == "endmodule":
            yield "endmodule"
        else:
            raise ParseError(f"unterminated statement: {buffer!r}")
