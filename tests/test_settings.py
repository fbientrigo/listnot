"""Config/secret-loading tests (docs/PRIVACY_MODEL.md §6, docs/DEPLOYMENT.md §5)."""

import base64

import pytest

from pucv_aq_qc.config.settings import MIN_SECRET_BYTES, SecretError, Settings


def _b64(nbytes: int) -> str:
    return base64.b64encode(b"x" * nbytes).decode()


def test_defaults_are_local_profile():
    s = Settings(PUCV_ID_SECRET_V1=_b64(32))
    assert s.env == "local"
    assert s.database_url.startswith("sqlite")
    assert s.min_group_size == 10
    assert s.active_key_version == "v1"


def test_missing_secret_fails_loudly_in_non_demo():
    s = Settings(PUCV_DEMO_MODE=False, PUCV_ID_SECRET_V1="")
    with pytest.raises(SecretError):
        _ = s.id_secret_v1


def test_short_secret_fails_loudly_in_non_demo():
    s = Settings(PUCV_DEMO_MODE=False, PUCV_ID_SECRET_V1=_b64(16))
    with pytest.raises(SecretError):
        _ = s.id_secret_v1


def test_demo_mode_tolerates_missing_secret_via_property():
    s = Settings(PUCV_DEMO_MODE=True, PUCV_ID_SECRET_V1="")
    # property does not raise in demo mode; require_secret still does
    assert s.id_secret_v1 == b""
    with pytest.raises(SecretError):
        s.require_secret()


def test_valid_secret_decodes_to_at_least_min_bytes():
    s = Settings(PUCV_ID_SECRET_V1=_b64(48))
    assert len(s.id_secret_v1) >= MIN_SECRET_BYTES


def test_settings_repr_never_contains_secret():
    secret_b64 = _b64(32)
    s = Settings(PUCV_ID_SECRET_V1=secret_b64)
    assert secret_b64 not in repr(s)
    assert "x" * 32 not in repr(s)
