"""HMAC pseudonym derivation (docs/PRIVACY_MODEL.md §3-4, ADR-0002)."""

import pytest

from pucv_aq_qc.identity import hmac_id
from pucv_aq_qc.identity.exceptions import MissingSecretError

SECRET_A = b"0" * 32
SECRET_B = b"1" * 32
RUT = "12345678-5"


def test_same_rut_same_secret_is_deterministic():
    a = hmac_id.person_uid_global(RUT, SECRET_A)
    b = hmac_id.person_uid_global(RUT, SECRET_A)
    assert a == b


def test_same_rut_different_secret_differs():
    a = hmac_id.person_uid_global(RUT, SECRET_A)
    b = hmac_id.person_uid_global(RUT, SECRET_B)
    assert a != b


def test_layer_prefixes():
    puid = hmac_id.person_uid_global(RUT, SECRET_A)
    suid = hmac_id.study_subject_uid(puid, "camp_1", SECRET_A)
    euid = hmac_id.export_subject_uid(suid, "exp_1", SECRET_A)
    assert puid.startswith("puid_")
    assert suid.startswith("suid_")
    assert euid.startswith("euid_")


def test_export_uid_is_per_export_namespaced():
    puid = hmac_id.person_uid_global(RUT, SECRET_A)
    suid = hmac_id.study_subject_uid(puid, "camp_1", SECRET_A)
    e1 = hmac_id.export_subject_uid(suid, "exp_1", SECRET_A)
    e2 = hmac_id.export_subject_uid(suid, "exp_2", SECRET_A)
    assert e1 != e2  # cross-export linkage blocked


def test_study_uid_is_per_campaign_namespaced():
    puid = hmac_id.person_uid_global(RUT, SECRET_A)
    s1 = hmac_id.study_subject_uid(puid, "camp_1", SECRET_A)
    s2 = hmac_id.study_subject_uid(puid, "camp_2", SECRET_A)
    assert s1 != s2


def test_key_version_changes_output():
    v1 = hmac_id.person_uid_global(RUT, SECRET_A, key_version="v1")
    v2 = hmac_id.person_uid_global(RUT, SECRET_A, key_version="v2")
    assert v1 != v2


def test_empty_secret_raises():
    with pytest.raises(MissingSecretError):
        hmac_id.person_uid_global(RUT, b"")


def test_full_width_base32_not_truncated():
    # full HMAC-SHA256 is 32 bytes -> 52 base32 chars (unpadded), plus prefix
    puid = hmac_id.person_uid_global(RUT, SECRET_A)
    body = puid[len("puid_"):]
    assert len(body) == 52


def test_raw_rut_never_in_return_value():
    puid = hmac_id.person_uid_global(RUT, SECRET_A)
    suid = hmac_id.study_subject_uid(puid, "camp_1", SECRET_A)
    euid = hmac_id.export_subject_uid(suid, "exp_1", SECRET_A)
    for out in (puid, suid, euid):
        assert RUT not in out
        assert "12345678" not in out
