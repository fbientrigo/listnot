#!/usr/bin/env python3
"""Generate a strong HMAC identity secret (docs/DEPLOYMENT.md §5).

Emits a >= 32-byte cryptographically random secret, base64-encoded.

    python scripts/generate_secret.py            # print to stdout
    python scripts/generate_secret.py --write    # write into .env — DEMO MODE ONLY

``--write`` edits ``.env`` only when ``PUCV_DEMO_MODE=true`` in the environment
or in the existing ``.env``; otherwise it refuses and prints to stdout so the
operator can place the secret manually. The secret is never committed.
"""

from __future__ import annotations

import argparse
import base64
import os
import secrets
import sys
from pathlib import Path

DEFAULT_BYTES = 48  # > 32-byte minimum, with margin
ENV_KEY = "PUCV_ID_SECRET_V1"


def generate(nbytes: int = DEFAULT_BYTES) -> str:
    if nbytes < 32:
        raise ValueError("secret must be >= 32 bytes")
    return base64.b64encode(secrets.token_bytes(nbytes)).decode("ascii")


def _demo_mode_enabled(env_path: Path) -> bool:
    if os.environ.get("PUCV_DEMO_MODE", "").lower() in {"1", "true", "yes"}:
        return True
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.strip().startswith("PUCV_DEMO_MODE="):
                return line.split("=", 1)[1].strip().lower() in {"1", "true", "yes"}
    return False


def _write_env(env_path: Path, secret: str) -> None:
    lines: list[str] = []
    replaced = False
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.strip().startswith(f"{ENV_KEY}="):
                lines.append(f"{ENV_KEY}={secret}")
                replaced = True
            else:
                lines.append(line)
    if not replaced:
        lines.append(f"{ENV_KEY}={secret}")
    env_path.write_text("\n".join(lines) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write into .env (demo mode only)")
    parser.add_argument("--bytes", type=int, default=DEFAULT_BYTES, help="secret length in bytes")
    parser.add_argument("--env-file", default=".env", help="path to .env (default: .env)")
    args = parser.parse_args(argv)

    secret = generate(args.bytes)

    if not args.write:
        print(secret)
        return 0

    env_path = Path(args.env_file)
    if not _demo_mode_enabled(env_path):
        print(
            "Refusing to --write: PUCV_DEMO_MODE is not true. "
            "Place this secret manually in your secret store:",
            file=sys.stderr,
        )
        print(secret)
        return 1

    _write_env(env_path, secret)
    print(f"Wrote {ENV_KEY} into {env_path} (demo mode).", file=sys.stderr)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
