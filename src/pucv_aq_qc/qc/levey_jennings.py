"""Levey-Jennings series construction (docs/QC_MODEL.md §2-3).

Builds an ordered series of points (by ``measured_at``) with a z-score and a
band per point, plus the ±1/2/3 SD limits. A ``target_sd <= 0`` is a data error:
the point's z is undefined and it is marked invalid rather than dividing by zero.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

BAND_IN_1SD = "in_1sd"
BAND_1_2SD = "1_2sd"
BAND_2_3SD = "2_3sd"
BAND_BEYOND_3SD = "beyond_3sd"
BAND_INVALID = "invalid"


class MeasurementLike(Protocol):
    measured_at: datetime
    value: float
    target_mean: float
    target_sd: float


@dataclass(frozen=True, slots=True)
class LJPoint:
    point_id: str
    measured_at: datetime
    value: float
    z: float | None  # None when target_sd <= 0
    band: str
    valid: bool = True


@dataclass(slots=True)
class LJSeries:
    analyte_code: str
    control_level: str
    reagent_lot: str | None
    target_mean: float
    target_sd: float
    points: list[LJPoint] = field(default_factory=list)

    @property
    def limits(self) -> dict[str, float]:
        m, s = self.target_mean, self.target_sd
        return {
            "mean": m,
            "plus_1sd": m + s,
            "minus_1sd": m - s,
            "plus_2sd": m + 2 * s,
            "minus_2sd": m - 2 * s,
            "plus_3sd": m + 3 * s,
            "minus_3sd": m - 3 * s,
        }


def band_for_z(z: float) -> str:
    az = abs(z)
    if az < 1:
        return BAND_IN_1SD
    if az < 2:
        return BAND_1_2SD
    if az < 3:
        return BAND_2_3SD
    return BAND_BEYOND_3SD


def _point_id(measurement: MeasurementLike, index: int) -> str:
    return str(getattr(measurement, "id", None) or f"idx_{index}")


def lj_series(measurements: list[MeasurementLike]) -> LJSeries:
    """Build an LJSeries from measurements of one (analyte, level, lot).

    Assumes the caller has grouped by (analyte_code, control_level, reagent_lot);
    targets are taken from the first measurement. Points are ordered by
    ``measured_at``.
    """
    if not measurements:
        raise ValueError("lj_series requires at least one measurement")

    ordered = sorted(enumerate(measurements), key=lambda pair: pair[1].measured_at)
    first = measurements[0]
    series = LJSeries(
        analyte_code=getattr(first, "analyte_code", ""),
        control_level=getattr(first, "control_level", ""),
        reagent_lot=getattr(first, "reagent_lot", None),
        target_mean=first.target_mean,
        target_sd=first.target_sd,
    )
    for original_index, m in ordered:
        if m.target_sd is None or m.target_sd <= 0:
            series.points.append(
                LJPoint(
                    point_id=_point_id(m, original_index),
                    measured_at=m.measured_at,
                    value=m.value,
                    z=None,
                    band=BAND_INVALID,
                    valid=False,
                )
            )
            continue
        z = (m.value - m.target_mean) / m.target_sd
        series.points.append(
            LJPoint(
                point_id=_point_id(m, original_index),
                measured_at=m.measured_at,
                value=m.value,
                z=z,
                band=band_for_z(z),
            )
        )
    return series
