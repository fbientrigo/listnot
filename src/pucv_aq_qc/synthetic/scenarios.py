"""Injectable QC/pre-analytical error scenarios (ADR-0003).

These deliberately introduce ground-truth faults so the QC engine's rules fire
in a testable, explainable way:

- ``bias``        — constant systematic offset on a control series (→ 2_2s/10x)
- ``drift``       — gradually increasing offset across a series (→ 4_1s/1_2s)
- ``imprecision`` — inflated random scatter (→ high CV%, occasional 1_2s/1_3s)
- ``outliers``    — isolated points pushed beyond ±3SD (→ 1_3s)
- ``missing``     — missing analyte values / collection times on results
- ``preanalytical`` — pre-analytical flags on a fraction of samples
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import StrEnum


class Scenario(StrEnum):
    bias = "bias"
    drift = "drift"
    imprecision = "imprecision"
    outliers = "outliers"
    missing = "missing"
    preanalytical = "preanalytical"


ALL_SCENARIOS: list[Scenario] = list(Scenario)


@dataclass
class ScenarioConfig:
    """Parameters controlling injected-fault magnitude. Defaults are 'obvious'
    faults so demo QC clearly triggers; tests may tighten these."""

    enabled: set[Scenario] = field(default_factory=lambda: set(ALL_SCENARIOS))
    bias_sd: float = 2.2  # offset in units of target SD
    drift_sd_per_point: float = 0.35  # per-point slope in target SD
    imprecision_factor: float = 3.0  # scatter multiplier
    outlier_sd: float = 3.6  # magnitude of an injected outlier in target SD
    outlier_rate: float = 0.06
    missing_rate: float = 0.05
    preanalytical_rate: float = 0.12

    def __contains__(self, scenario: Scenario) -> bool:
        return scenario in self.enabled


def qc_series_values(
    target_mean: float,
    target_sd: float,
    n: int,
    rng: random.Random,
    cfg: ScenarioConfig,
    *,
    inject_bias: bool = False,
    inject_drift: bool = False,
    inject_imprecision: bool = False,
    inject_outliers: bool = False,
) -> list[float]:
    """Produce ``n`` QC control values around ``target_mean`` with optional faults.

    Which faults apply to a given series is decided by the caller (so the demo
    can assign different scenarios to different analytes/levels).
    """
    scatter = target_sd
    if inject_imprecision and Scenario.imprecision in cfg:
        scatter *= cfg.imprecision_factor

    bias = cfg.bias_sd * target_sd if (inject_bias and Scenario.bias in cfg) else 0.0

    values: list[float] = []
    for i in range(n):
        drift = 0.0
        if inject_drift and Scenario.drift in cfg:
            drift = cfg.drift_sd_per_point * i * target_sd
        value = rng.gauss(target_mean + bias + drift, scatter)
        if inject_outliers and Scenario.outliers in cfg and rng.random() < cfg.outlier_rate:
            sign = 1.0 if rng.random() < 0.5 else -1.0
            value = target_mean + sign * cfg.outlier_sd * target_sd
        values.append(round(value, 3))
    return values
