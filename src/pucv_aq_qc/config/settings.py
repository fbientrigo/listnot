"""Environment/profile configuration and secret loading (12-factor).

Loads configuration from the process environment (see docs/DEPLOYMENT.md §4).
The HMAC identity secret is the crown jewel (docs/PRIVACY_MODEL.md §6):

- It is read only from the environment — never from the DB, code, or a report.
- In non-demo profiles the application **fails to start** if the secret is
  missing or shorter than 32 bytes. There is no insecure fallback.

Nothing in this module ever logs or echoes a secret value.
"""

from __future__ import annotations

import base64
import binascii
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

MIN_SECRET_BYTES = 32

DeploymentEnv = Literal["local", "server", "cloud"]
StorageBackend = Literal["local", "s3", "gcs", "azure"]


class SecretError(RuntimeError):
    """Raised when the identity secret is missing or too weak in a non-demo profile.

    The message never contains any secret material.
    """


def _decode_secret(raw: str) -> bytes:
    """Decode a base64 secret to bytes; fall back to raw UTF-8 bytes.

    Accepts either a base64-encoded value (as produced by
    ``scripts/generate_secret.py``) or a plain string. Never raises with the
    secret in the message.
    """
    raw = raw.strip()
    if not raw:
        return b""
    try:
        decoded = base64.b64decode(raw, validate=True)
        # A short/odd string may decode to garbage; prefer it only if it is at
        # least as long as the raw text would be, otherwise treat as raw bytes.
        if decoded:
            return decoded
    except (binascii.Error, ValueError):
        pass
    return raw.encode("utf-8")


class Settings(BaseSettings):
    """Runtime settings resolved from environment variables.

    See docs/DEPLOYMENT.md §4 for the full variable table.
    """

    model_config = SettingsConfigDict(
        env_file=None,  # env is the source of truth; .env is loaded by the shell/tooling
        env_prefix="",
        extra="ignore",
        case_sensitive=False,
    )

    env: DeploymentEnv = Field(default="local", alias="PUCV_AQ_ENV")
    database_url: str = Field(default="sqlite:///data/pucv.db", alias="DATABASE_URL")
    active_key_version: str = Field(default="v1", alias="PUCV_ACTIVE_KEY_VERSION")
    min_group_size: int = Field(default=10, alias="PUCV_MIN_GROUP_SIZE")
    storage_backend: StorageBackend = Field(default="local", alias="PUCV_STORAGE_BACKEND")
    demo_mode: bool = Field(default=False, alias="PUCV_DEMO_MODE")

    # Raw secret material; validated lazily below. Never logged (repr=False).
    id_secret_v1_raw: str = Field(default="", alias="PUCV_ID_SECRET_V1", repr=False)

    @field_validator("min_group_size")
    @classmethod
    def _min_group_size_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("PUCV_MIN_GROUP_SIZE must be >= 1")
        return v

    @property
    def id_secret_v1(self) -> bytes:
        """The active HMAC secret as bytes.

        Fails loudly in non-demo profiles if the secret is missing or < 32 bytes
        (docs/PRIVACY_MODEL.md §6). In demo mode an empty secret is tolerated so
        callers can auto-generate one; callers that require a secret must check.
        """
        secret = _decode_secret(self.id_secret_v1_raw)
        if len(secret) < MIN_SECRET_BYTES and not self.demo_mode:
            raise SecretError(
                "PUCV_ID_SECRET_V1 is missing or shorter than "
                f"{MIN_SECRET_BYTES} bytes; refusing to start in a non-demo profile. "
                "Generate one with scripts/generate_secret.py."
            )
        return secret

    def require_secret(self) -> bytes:
        """Return the secret, raising SecretError if it is unusable (any profile)."""
        secret = _decode_secret(self.id_secret_v1_raw)
        if len(secret) < MIN_SECRET_BYTES:
            raise SecretError(
                "PUCV_ID_SECRET_V1 is missing or shorter than "
                f"{MIN_SECRET_BYTES} bytes."
            )
        return secret


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return process-wide settings (cached). Reads the current environment."""
    return Settings()
