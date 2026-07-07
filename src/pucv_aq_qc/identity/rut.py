"""Chilean RUT normalization and módulo-11 validation.

Public interface (docs/DELIVERY_PLAN.md, Commit 1):

    normalize(raw)   -> canonical "NNNNNNNN-DV"  (no dots, uppercase K)
    validate(norm)   -> True, or raise InvalidRUTError
    compute_dv(body) -> the check digit "0".."9" or "K"

Invariant: no function raises an exception whose message contains the RUT
(docs/PRIVACY_MODEL.md §8).
"""

from __future__ import annotations

import re

from pucv_aq_qc.identity.exceptions import InvalidRUTError

# Canonical form: 1-8 body digits, a hyphen, and a check digit (0-9 or K).
_CANONICAL_RE = re.compile(r"^(\d{1,8})-([0-9K])$")


def compute_dv(body: int) -> str:
    """Return the módulo-11 check digit for a RUT body number.

    Weights 2..7 are applied cyclically to the body digits from right to left.
    """
    if body < 0:
        raise InvalidRUTError()
    total = 0
    weight = 2
    n = body
    if n == 0:
        # A zero body is not a real RUT; still compute deterministically.
        total = 0
    while n > 0:
        total += (n % 10) * weight
        n //= 10
        weight = 2 if weight == 7 else weight + 1
    remainder = 11 - (total % 11)
    if remainder == 11:
        return "0"
    if remainder == 10:
        return "K"
    return str(remainder)


def normalize(raw: str) -> str:
    """Strip dots/spaces, uppercase K, and return canonical ``NNNNNNNN-DV``.

    Raises InvalidRUTError on structurally malformed input. The message never
    contains the input value.
    """
    if not isinstance(raw, str):
        raise InvalidRUTError()
    # Remove dots, spaces and any surrounding whitespace; normalise the check
    # digit's letter form.
    cleaned = raw.strip().replace(".", "").replace(" ", "").upper()
    if not cleaned:
        raise InvalidRUTError()
    # Accept an existing hyphen or insert one before the last character.
    if "-" in cleaned:
        body_part, _, dv_part = cleaned.rpartition("-")
    else:
        body_part, dv_part = cleaned[:-1], cleaned[-1:]
    if not body_part or not dv_part:
        raise InvalidRUTError()
    if not body_part.isdigit():
        raise InvalidRUTError()
    if dv_part not in "0123456789K":
        raise InvalidRUTError()
    # Drop leading zeros in the body but keep at least one digit.
    body_int = int(body_part)
    canonical = f"{body_int}-{dv_part}"
    if not _CANONICAL_RE.match(canonical):
        raise InvalidRUTError()
    return canonical


def validate(normalized: str) -> bool:
    """Verify the módulo-11 check digit of a canonical RUT.

    Returns True on success; raises InvalidRUTError otherwise. Accepts either a
    canonical string or a still-messy one (it normalizes first).
    """
    match = _CANONICAL_RE.match(normalized)
    if not match:
        # Be forgiving: allow callers to pass a not-yet-normalized value.
        normalized = normalize(normalized)
        match = _CANONICAL_RE.match(normalized)
    if not match:  # pragma: no cover - normalize would have raised
        raise InvalidRUTError()
    body_str, dv = match.group(1), match.group(2)
    if compute_dv(int(body_str)) != dv:
        raise InvalidRUTError()
    return True
