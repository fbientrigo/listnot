"""Detect RUT-shaped / forbidden-identifier patterns in text and files.

Used by the no-RUT-persistence test and by
``scripts/scan_for_forbidden_identifiers.py`` (docs/PRIVACY_MODEL.md §8).

This is a *defensive* scanner: it is intentionally broad (it may flag some
non-RUT digit strings), because a false positive is cheap and a leaked RUT is
not. Detection is best-effort — the real guarantee is that the code paths never
produce a RUT; this catches regressions.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

# RUT shapes we treat as forbidden if written to any artifact:
#   dotted:   12.345.678-5   /   1.234.567-8
#   plain:    12345678-5     /   1234567-8
_RUT_PATTERNS = [
    re.compile(r"\b\d{1,3}(?:\.\d{3})+-[\dkK]\b"),  # dotted body + check digit
    re.compile(r"\b\d{7,8}-[\dkK]\b"),  # plain 7-8 digit body + check digit
]

# Text file extensions worth scanning (DB files/exports are scanned as raw text too).
_TEXT_SUFFIXES = {
    ".txt", ".csv", ".json", ".md", ".html", ".log", ".db", ".sql", ".ndjson", "",
}


@dataclass(frozen=True)
class Match:
    """A forbidden-pattern match. ``value`` is redacted before storage/return."""

    source: str  # file path or logical label
    redacted: str  # e.g. "1XXXXXXX-X" — never the real value


def _redact(value: str) -> str:
    return re.sub(r"\d", "X", value)


def scan_text(text: str, source: str = "<text>") -> list[Match]:
    """Return redacted matches of RUT-shaped patterns in ``text``."""
    found: list[Match] = []
    for pattern in _RUT_PATTERNS:
        for m in pattern.finditer(text):
            found.append(Match(source=source, redacted=_redact(m.group(0))))
    return found


def scan_file(path: str | Path) -> list[Match]:
    """Scan a single file's bytes (decoded leniently) for RUT-shaped patterns."""
    p = Path(path)
    try:
        data = p.read_bytes()
    except OSError:
        return []
    text = data.decode("utf-8", errors="ignore")
    return scan_text(text, source=str(p))


def scan_paths(paths: Iterable[str | Path]) -> list[Match]:
    """Recursively scan files under the given paths for RUT-shaped patterns."""
    matches: list[Match] = []
    for raw in paths:
        base = Path(raw)
        if base.is_dir():
            for child in base.rglob("*"):
                if child.is_file() and child.suffix.lower() in _TEXT_SUFFIXES:
                    matches.extend(scan_file(child))
        elif base.is_file():
            matches.extend(scan_file(base))
    return matches


def contains_forbidden(text: str) -> bool:
    """True if ``text`` contains any RUT-shaped pattern."""
    return bool(scan_text(text))
