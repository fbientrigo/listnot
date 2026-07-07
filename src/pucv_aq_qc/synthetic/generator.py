"""Orchestrate synthetic-world generation end-to-end (ADR-0003).

Builds a deterministic, seeded campaign with subjects/samples/results/QC. The
identity gateway sequence is honoured per subject: a synthetic RUT is
normalized → validated → converted to ``person_uid_global`` (and
``study_subject_uid``), then the RUT local is discarded. No model instance in
the returned world holds a RUT.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

from sqlmodel import Session

from pucv_aq_qc.database.models import (
    AnalyteResult,
    Campaign,
    QCMeasurement,
    Sample,
    StudySubject,
    Subject,
)
from pucv_aq_qc.identity import hmac_id, rut
from pucv_aq_qc.synthetic.analytes import ANALYTES, AnalyteSpec
from pucv_aq_qc.synthetic.rut_generator import generate_unique_ruts
from pucv_aq_qc.synthetic.scenarios import Scenario, ScenarioConfig, qc_series_values

# Deterministic assignment of an injected fault to a specific analyte/level so
# the demo QC engine fires explainable, ground-truth flags.
_QC_FAULT_PLAN: dict[tuple[str, str], str] = {
    ("glucose", "L1"): "bias",
    ("ast", "L2"): "outliers",
    ("creatinine", "L1"): "drift",
    ("urea", "L2"): "imprecision",
}

_SAMPLE_TYPES = ["serum", "plasma", "whole_blood"]
_PREANALYTICAL = [
    "hemolysis_suspected",
    "delayed_processing",
    "wrong_tube",
    "sample_clotting",
    "temperature_excursion",
]
_QC_POINTS_PER_SERIES = 24


@dataclass
class SyntheticWorld:
    """In-memory bundle of generated ORM instances (not yet persisted).

    Holds only pseudonymous identifiers — never a RUT.
    """

    campaign: Campaign
    subjects: list[Subject] = field(default_factory=list)
    study_subjects: list[StudySubject] = field(default_factory=list)
    samples: list[Sample] = field(default_factory=list)
    results: list[AnalyteResult] = field(default_factory=list)
    qc_measurements: list[QCMeasurement] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        return {
            "subjects": len(self.subjects),
            "samples": len(self.samples),
            "results": len(self.results),
            "qc_measurements": len(self.qc_measurements),
        }


def _result_flags(spec: AnalyteSpec, value: float | None) -> list[str]:
    if value is None:
        return ["missing"]
    flags: list[str] = []
    if spec.ref_low is not None and value < spec.ref_low:
        flags.append("below_ref")
    if spec.ref_high is not None and value > spec.ref_high:
        flags.append("above_ref")
    return flags


def _generate_results(
    sample: Sample, rng: random.Random, cfg: ScenarioConfig
) -> list[AnalyteResult]:
    results: list[AnalyteResult] = []
    for spec in ANALYTES.values():
        value: float | None = round(rng.gauss(spec.pop_mean, spec.pop_sd), 3)
        if Scenario.missing in cfg and rng.random() < cfg.missing_rate:
            value = None
        results.append(
            AnalyteResult(
                sample_id=sample.id,
                analyte_code=spec.code,
                value=value,
                unit=spec.unit,
                method="enzymatic",
                instrument_id="inst_A",
                reagent_lot="R-2026A",
                reference_low=spec.ref_low,
                reference_high=spec.ref_high,
                result_flags=_result_flags(spec, value),
            )
        )
    return results


def _generate_qc(
    campaign_id: str, start: datetime, rng: random.Random, cfg: ScenarioConfig
) -> list[QCMeasurement]:
    measurements: list[QCMeasurement] = []
    for spec in ANALYTES.values():
        for level in ("L1", "L2"):
            mean = spec.qc_l1_mean if level == "L1" else spec.qc_l2_mean
            sd = spec.qc_l1_sd if level == "L1" else spec.qc_l2_sd
            fault = _QC_FAULT_PLAN.get((spec.code, level))
            values = qc_series_values(
                mean,
                sd,
                _QC_POINTS_PER_SERIES,
                rng,
                cfg,
                inject_bias=fault == "bias",
                inject_drift=fault == "drift",
                inject_imprecision=fault == "imprecision",
                inject_outliers=fault == "outliers",
            )
            for i, value in enumerate(values):
                measurements.append(
                    QCMeasurement(
                        campaign_id=campaign_id,
                        analyte_code=spec.code,
                        control_level=level,
                        value=value,
                        target_mean=mean,
                        target_sd=sd,
                        unit=spec.unit,
                        instrument_id="inst_A",
                        reagent_lot="L23A" if level == "L1" else "C11B",
                        measured_at=start + timedelta(hours=i),
                    )
                )
    return measurements


def generate_world(
    *,
    secret: bytes,
    n_subjects: int = 120,
    seed: int = 42,
    key_version: str = "v1",
    scenarios: ScenarioConfig | None = None,
    campaign_name: str = "Screening comunitario Valparaíso 2026-Q1",
    location_label: str = "Valparaíso",
) -> SyntheticWorld:
    """Generate a deterministic synthetic campaign. RUTs are discarded post-ID."""
    cfg = scenarios or ScenarioConfig()
    rng = random.Random(seed)

    campaign = Campaign(
        name=campaign_name,
        protocol_version="v1.0",
        location_label=location_label,
        start_date=date(2026, 3, 1),
        status="active",
        synthetic=True,
    )
    world = SyntheticWorld(campaign=campaign)
    qc_start = datetime(2026, 3, 1, 9, tzinfo=UTC)

    for raw_rut in generate_unique_ruts(n_subjects, rng):
        # --- identity gateway: RUT lives only here, in memory ---
        normalized = rut.normalize(raw_rut)
        rut.validate(normalized)
        puid = hmac_id.person_uid_global(normalized, secret, key_version)
        suid = hmac_id.study_subject_uid(puid, campaign.id, secret, key_version)
        del raw_rut, normalized  # discard the RUT; never persisted
        # ---------------------------------------------------------

        subject = Subject(person_uid_global=puid, key_version=key_version, synthetic=True)
        study = StudySubject(
            campaign_id=campaign.id,
            subject_id=subject.id,
            study_subject_uid=suid,
            consent_status="granted",
        )
        world.subjects.append(subject)
        world.study_subjects.append(study)

        n_samples = rng.randint(1, 2)
        for _ in range(n_samples):
            collected_at: datetime | None = qc_start + timedelta(
                days=rng.randint(0, 20), hours=rng.randint(0, 8)
            )
            flags: list[str] = []
            if Scenario.preanalytical in cfg and rng.random() < cfg.preanalytical_rate:
                flags.append(rng.choice(_PREANALYTICAL))
            if Scenario.missing in cfg and rng.random() < cfg.missing_rate / 2:
                collected_at = None
                flags.append("missing_collection_time")
            sample = Sample(
                campaign_id=campaign.id,
                study_subject_id=study.id,
                sample_uid=f"smp_{len(world.samples):06d}",
                sample_type=rng.choice(_SAMPLE_TYPES),
                collected_at=collected_at,
                preanalytical_flags=flags,
            )
            world.samples.append(sample)
            world.results.extend(_generate_results(sample, rng, cfg))

    world.qc_measurements = _generate_qc(campaign.id, qc_start, rng, cfg)
    return world


def persist_world(world: SyntheticWorld, session: Session) -> None:
    """Persist a generated world in FK-safe order and commit."""
    session.add(world.campaign)
    session.add_all(world.subjects)
    session.add_all(world.study_subjects)
    session.add_all(world.samples)
    session.add_all(world.results)
    session.add_all(world.qc_measurements)
    session.commit()
