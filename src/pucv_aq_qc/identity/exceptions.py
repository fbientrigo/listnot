"""Identity errors — messages are generic and never contain a RUT.

docs/PRIVACY_MODEL.md §8: identity errors carry a generic message plus an
optional non-identifying correlation id; they must not echo the offending value.
"""

from __future__ import annotations


class IdentityError(Exception):
    """Base class for identity-layer errors."""


class InvalidRUTError(IdentityError):
    """Raised when a RUT is malformed or its check digit is wrong.

    The message is deliberately generic ("invalid RUT format") and MUST NOT
    contain the offending value. An optional non-identifying ``correlation_id``
    can be attached for log correlation.
    """

    def __init__(self, correlation_id: str | None = None) -> None:
        self.correlation_id = correlation_id
        message = "invalid RUT format"
        if correlation_id:
            message = f"{message} (ref={correlation_id})"
        super().__init__(message)


class MissingSecretError(IdentityError):
    """Raised when an HMAC derivation is attempted without a usable secret.

    Never falls back to an insecure default (docs/PRIVACY_MODEL.md §3).
    """

    def __init__(self, message: str = "HMAC secret is missing or empty") -> None:
        super().__init__(message)
