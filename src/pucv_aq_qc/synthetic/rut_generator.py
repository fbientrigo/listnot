"""Deterministic generation of valid synthetic Chilean RUTs.

Every produced RUT passes ``identity.rut.validate``. Generation is seeded, so
``make demo`` regenerates the same world (ADR-0003). These are synthetic values;
they are still never persisted (they are consumed to derive pseudonyms).
"""

from __future__ import annotations

import random
from collections.abc import Iterator

from pucv_aq_qc.identity import rut

# Plausible natural-person RUT body range (avoids tiny/company-like numbers).
_BODY_MIN = 5_000_000
_BODY_MAX = 25_000_000


def generate_rut(rng: random.Random) -> str:
    """Return one valid canonical RUT ``NNNNNNNN-DV`` using ``rng``."""
    body = rng.randint(_BODY_MIN, _BODY_MAX)
    dv = rut.compute_dv(body)
    return f"{body}-{dv}"


def generate_unique_ruts(n: int, rng: random.Random) -> Iterator[str]:
    """Yield ``n`` distinct valid RUTs deterministically from ``rng``."""
    seen: set[str] = set()
    while len(seen) < n:
        candidate = generate_rut(rng)
        if candidate in seen:
            continue
        seen.add(candidate)
        yield candidate
