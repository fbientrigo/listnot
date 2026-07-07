#!/usr/bin/env python3
"""Fail if any RUT-shaped / forbidden identifier appears in generated artifacts.

Scans data/ (DB, staging, exports, reports) by default. Exit code 1 on any
match; used by ``make demo`` and CI (docs/PRIVACY_MODEL.md §8).

    python scripts/scan_for_forbidden_identifiers.py [PATH ...]
"""

from __future__ import annotations

import sys

from pucv_aq_qc.privacy import forbidden

DEFAULT_PATHS = ["data"]


def main(argv: list[str] | None = None) -> int:
    paths = argv if argv else DEFAULT_PATHS
    matches = forbidden.scan_paths(paths)
    if matches:
        print(f"FORBIDDEN IDENTIFIER SCAN FAILED: {len(matches)} match(es)", file=sys.stderr)
        for m in matches[:20]:
            # print redacted only; never the real value
            print(f"  {m.source}: {m.redacted}", file=sys.stderr)
        return 1
    print(f"forbidden-identifier scan clean over: {', '.join(paths)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
