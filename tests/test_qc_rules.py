"""QC engine tests (docs/DELIVERY_PLAN.md Commit 6, QC_MODEL.md).

Each Westgard rule is fired on a crafted ground-truth series and checked silent
on a clean one. z-score / mean / SD / CV and run-status logic are verified.
"""

from datetime import UTC, datetime, timedelta

import pytest

from pucv_aq_qc.qc.levey_jennings import band_for_z, lj_series
from pucv_aq_qc.qc.metrics import control_stats
from pucv_aq_qc.qc.summary import run_status_from_hits, summarize_series
from pucv_aq_qc.qc.westgard import Severity, WestgardConfig, evaluate
from pucv_aq_qc.schemas.enums import RunStatus

MEAN, SD = 100.0, 5.0
T0 = datetime(2026, 3, 1, 9, tzinfo=UTC)


class M:
    """Lightweight measurement stub (duck-types MeasurementLike)."""

    def __init__(self, z, i, mean=MEAN, sd=SD, analyte="glucose", level="L1", lot="L23A"):
        self.id = f"p{i}"
        self.measured_at = T0 + timedelta(hours=i)
        self.value = mean + z * sd
        self.target_mean = mean
        self.target_sd = sd
        self.analyte_code = analyte
        self.control_level = level
        self.reagent_lot = lot


def series_from_z(zs):
    return lj_series([M(z, i) for i, z in enumerate(zs)])


def rule_codes(hits):
    return {h.rule_code for h in hits}


# --- z-score, bands, metrics ------------------------------------------------


def test_zscore_and_bands():
    s = series_from_z([0.0, 1.5, 2.5, 3.5])
    assert s.points[0].z == pytest.approx(0.0)
    assert s.points[0].band == "in_1sd"
    assert s.points[1].band == "1_2sd"
    assert s.points[2].band == "2_3sd"
    assert s.points[3].band == "beyond_3sd"


def test_band_for_z_boundaries():
    assert band_for_z(0.99) == "in_1sd"
    assert band_for_z(1.0) == "1_2sd"
    assert band_for_z(2.0) == "2_3sd"
    assert band_for_z(3.0) == "beyond_3sd"


def test_metrics_mean_sd_cv():
    stats = control_stats([100.0, 102.0, 98.0, 100.0])
    assert stats.n == 4
    assert stats.mean == pytest.approx(100.0)
    assert stats.sd == pytest.approx(1.632993, rel=1e-4)
    assert stats.cv_percent == pytest.approx(1.632993, rel=1e-4)


def test_metrics_guards():
    assert control_stats([]).sd is None
    assert control_stats([5.0]).sd is None
    zero_mean = control_stats([-1.0, 1.0])
    assert zero_mean.mean == 0.0
    assert zero_mean.cv_percent is None  # mean == 0


def test_target_sd_zero_is_invalid_not_divide_by_zero():
    s = lj_series([M(0.0, 0, sd=0.0)])
    assert s.points[0].z is None
    assert s.points[0].valid is False
    assert s.points[0].band == "invalid"


# --- individual Westgard rules ----------------------------------------------


def test_1_3s_fires_on_point_beyond_3sd():
    hits = evaluate(series_from_z([0.1, 0.2, 3.4, -0.1]))
    assert "1_3s" in rule_codes(hits)
    assert run_status_from_hits(hits) is RunStatus.rejected


def test_1_2s_warns_but_not_rejects():
    hits = evaluate(series_from_z([0.1, 2.3, 0.2]))
    assert "1_2s" in rule_codes(hits)
    assert "1_3s" not in rule_codes(hits)
    assert run_status_from_hits(hits) is RunStatus.warning


def test_2_2s_fires_on_two_consecutive_same_side_beyond_2sd():
    hits = evaluate(series_from_z([0.1, 2.3, 2.4, 0.0]))
    assert "2_2s" in rule_codes(hits)
    assert run_status_from_hits(hits) is RunStatus.rejected


def test_2_2s_silent_when_opposite_sides():
    hits = evaluate(series_from_z([2.3, -2.4]))
    assert "2_2s" not in rule_codes(hits)


def test_R_4s_fires_on_large_range():
    hits = evaluate(series_from_z([2.5, -2.0]))  # range 4.5 SD
    assert "R_4s" in rule_codes(hits)
    assert run_status_from_hits(hits) is RunStatus.rejected


def test_4_1s_fires_on_four_consecutive_same_side_beyond_1sd():
    hits = evaluate(series_from_z([1.2, 1.3, 1.4, 1.5]))
    codes = rule_codes(hits)
    assert "4_1s" in codes
    # default severity is warning
    h = next(h for h in hits if h.rule_code == "4_1s")
    assert h.severity == Severity.warning


def test_4_1s_severity_configurable_to_reject():
    cfg = WestgardConfig(severity_4_1s=Severity.reject)
    hits = evaluate(series_from_z([1.2, 1.3, 1.4, 1.5]), cfg)
    h = next(h for h in hits if h.rule_code == "4_1s")
    assert h.severity == Severity.reject
    assert run_status_from_hits(hits) is RunStatus.rejected


def test_10x_fires_on_ten_same_side():
    hits = evaluate(series_from_z([0.2] * 10))
    assert "10x" in rule_codes(hits)
    assert run_status_from_hits(hits) is RunStatus.warning


def test_10x_silent_when_crossing_mean():
    zs = [0.2, -0.2] * 5
    hits = evaluate(series_from_z(zs))
    assert "10x" not in rule_codes(hits)


def test_clean_series_is_accepted_and_silent():
    zs = [0.1, -0.2, 0.3, -0.1, 0.2, -0.3, 0.1, -0.2]
    hits = evaluate(series_from_z(zs))
    assert hits == []
    assert run_status_from_hits(hits) is RunStatus.accepted


# --- messages + summary -----------------------------------------------------


def test_messages_are_spanish_and_name_analyte_without_identifiers():
    hits = evaluate(series_from_z([3.4]))
    msg = hits[0].message
    assert "Glicemia" in msg
    assert "Nivel L1" in msg
    assert "Rechazo" in msg
    # never a patient identifier
    assert "puid_" not in msg and "12345678" not in msg


def test_summary_run_status_is_most_severe():
    # one warning (1_2s) and one reject (1_3s) -> rejected
    summary = summarize_series([M(2.3, 0), M(3.4, 1)])
    assert summary.run_status is RunStatus.rejected
    assert summary.stats.n == 2


def test_summary_cv_exceeded_escalates_to_warning():
    # clean (accepted) rules but CV over the allowable limit -> warning
    measurements = [M(0.0, i) for i in range(6)]
    # give them scatter so CV is measurable but rules stay silent
    for i, m in enumerate(measurements):
        m.value = MEAN + (1.0 if i % 2 else -1.0) * 3.0  # ~3% CV, within ±1SD
    summary = summarize_series(measurements, allowable_cv=1.0)
    assert summary.cv_exceeded is True
    assert summary.run_status is RunStatus.warning
