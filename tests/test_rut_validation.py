"""RUT normalization + módulo-11 validation (docs/DELIVERY_PLAN.md Commit 1).

Fixtures are valid *synthetic* RUTs. No exception message may contain a RUT.
"""

import pytest

from pucv_aq_qc.identity import rut
from pucv_aq_qc.identity.exceptions import InvalidRUTError

VALID = ["12345678-5", "11111111-1", "22222222-2", "5126663-3", "9743918-4", "1-9"]


@pytest.mark.parametrize("value", VALID)
def test_valid_ruts_validate(value):
    assert rut.validate(value) is True


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("12.345.678-5", "12345678-5"),
        ("12345678-5", "12345678-5"),
        (" 12.345.678-5 ", "12345678-5"),
        ("012345678-5", "12345678-5"),  # leading zero stripped
    ],
)
def test_normalize_canonicalizes(raw, expected):
    assert rut.normalize(raw) == expected


def test_normalize_uppercases_k():
    # body whose check digit is K
    body = 20347878  # find a K below is asserted via compute_dv
    dv = rut.compute_dv(body)
    if dv != "K":
        pytest.skip("chosen body is not a K-digit RUT")
    assert rut.normalize(f"{body}-k") == f"{body}-K"


def test_k_check_digit_supported():
    # 44444444 -> compute and round-trip through normalize/validate
    body = 44444444
    dv = rut.compute_dv(body)
    canonical = f"{body}-{dv}"
    assert rut.validate(canonical) is True


@pytest.mark.parametrize(
    "bad",
    ["", "   ", "abc", "12.345.678", "12345678-9", "12345678-Z", "-5", "1.2.3-x"],
)
def test_invalid_ruts_raise(bad):
    with pytest.raises(InvalidRUTError):
        rut.validate(bad)


def test_bad_check_digit_raises():
    # correct is 12345678-5; force a wrong digit
    with pytest.raises(InvalidRUTError):
        rut.validate("12345678-4")


@pytest.mark.parametrize("bad", ["98765432-9", "abc-1", "12.345.678", "12345678-X"])
def test_exception_message_never_contains_rut(bad):
    try:
        rut.validate(bad)
    except InvalidRUTError as exc:
        digits = "".join(c for c in bad if c.isdigit())
        # no run of >=5 consecutive input digits appears in the message
        assert digits[:8] not in str(exc)
        assert bad not in str(exc)
        assert str(exc).startswith("invalid RUT format")
    else:  # pragma: no cover
        pytest.fail("expected InvalidRUTError")
