"""Read/analytics service layer over the operational DB.

Shared by the API, dashboard, and reporting so they all enforce the same
privacy rules. Nothing here selects ``person_uid_global`` or
``study_subject_uid`` into a returned structure — statistical outputs are
aggregated and suppressed (docs/PRIVACY_MODEL.md §5,§10).
"""

from __future__ import annotations

from sqlmodel import Session, select

from pucv_aq_qc.database.models import (
    AnalyteResult,
    Campaign,
    QCMeasurement,
    Sample,
    StudySubject,
)
from pucv_aq_qc.privacy.aggregation import aggregate
from pucv_aq_qc.privacy.export_policy import (
    ExportResultData,
    build_aggregated_export,
)
from pucv_aq_qc.privacy.suppression import DEFAULT_MIN_GROUP_SIZE, suppress
from pucv_aq_qc.qc.summary import summarize_campaign
from pucv_aq_qc.synthetic.analytes import ANALYTES

# Group dimensions the statistical layer allows (coarse, non-identifying).
ALLOWED_GROUP_FIELDS = {"sex", "age_band", "sample_type"}


def list_campaigns(session: Session) -> list[Campaign]:
    return list(session.exec(select(Campaign)).all())


def get_campaign(session: Session, campaign_id: str) -> Campaign | None:
    return session.get(Campaign, campaign_id)


def qc_measurements(session: Session, campaign_id: str) -> list[QCMeasurement]:
    return list(
        session.exec(
            select(QCMeasurement).where(QCMeasurement.campaign_id == campaign_id)
        ).all()
    )


def qc_summary(session: Session, campaign_id: str) -> list[dict]:
    """Per (analyte, level, lot) QC summary dicts. Contains no subject linkage."""
    allowable_cv = {code: spec.allowable_cv for code, spec in ANALYTES.items()}
    summaries = summarize_campaign(qc_measurements(session, campaign_id), allowable_cv=allowable_cv)
    return [s.as_dict() for s in summaries]


def qc_analyte_series(session: Session, campaign_id: str, analyte_code: str) -> dict:
    """LJ series + flags for one analyte (first matching level/lot)."""
    from pucv_aq_qc.qc.levey_jennings import lj_series
    from pucv_aq_qc.qc.westgard import evaluate

    measurements = [
        m for m in qc_measurements(session, campaign_id) if m.analyte_code == analyte_code
    ]
    if not measurements:
        return {"analyte_code": analyte_code, "series": [], "flags": []}
    series = lj_series(measurements)
    hits = evaluate(series)
    return {
        "analyte_code": series.analyte_code,
        "control_level": series.control_level,
        "reagent_lot": series.reagent_lot,
        "target_mean": series.target_mean,
        "target_sd": series.target_sd,
        "series": [
            {
                "measured_at": p.measured_at.isoformat(),
                "value": p.value,
                "z": round(p.z, 4) if p.z is not None else None,
                "band": p.band,
            }
            for p in series.points
        ],
        "flags": [
            {"rule_code": h.rule_code, "severity": h.severity, "message": h.message}
            for h in hits
        ],
    }


def build_observations(
    session: Session, campaign_id: str, analytes: list[str] | None = None
) -> list[dict]:
    """Join results → sample → study_subject into aggregation-ready observations.

    Each observation carries only coarse group fields + analyte + value — never
    a subject pseudonym.
    """
    stmt = (
        select(
            AnalyteResult.analyte_code,
            AnalyteResult.value,
            Sample.sample_type,
            StudySubject.sex,
            StudySubject.age_band,
        )
        .join(Sample, Sample.id == AnalyteResult.sample_id)
        .join(StudySubject, StudySubject.id == Sample.study_subject_id)
        .where(Sample.campaign_id == campaign_id)
    )
    if analytes:
        stmt = stmt.where(AnalyteResult.analyte_code.in_(analytes))

    observations: list[dict] = []
    for analyte_code, value, sample_type, sex, age_band in session.exec(stmt).all():
        observations.append(
            {
                "analyte_code": analyte_code,
                "value": value,
                "sample_type": sample_type,
                "sex": sex,
                "age_band": age_band,
            }
        )
    return observations


def stats_summary(
    session: Session,
    campaign_id: str,
    group_by: list[str],
    analytes: list[str] | None = None,
    min_group_size: int = DEFAULT_MIN_GROUP_SIZE,
) -> dict:
    """Aggregated, suppression-enforced statistics grouped by ``group_by``."""
    safe_group_by = [g for g in group_by if g in ALLOWED_GROUP_FIELDS] or ["sex"]
    codes = analytes or list(ANALYTES)
    observations = build_observations(session, campaign_id, codes)

    groups: list[dict] = []
    total_suppressed = 0
    for analyte in codes:
        obs_a = [o for o in observations if o["analyte_code"] == analyte]
        cells = aggregate(obs_a, safe_group_by)
        result = suppress(cells, min_group_size)
        total_suppressed += result.suppressed_count
        for cell in result.cells:
            entry = cell.as_dict()
            entry["analyte_code"] = analyte
            groups.append(entry)

    return {
        "campaign_id": campaign_id,
        "min_group_size": min_group_size,
        "group_by": safe_group_by,
        "groups": groups,
        "suppressed_group_count": total_suppressed,
        "all_groups_suppressed": bool(groups) and all(g.get("status") == "suppressed" for g in groups),
    }


def aggregated_export(
    session: Session,
    campaign_id: str,
    group_by: list[str],
    analytes: list[str],
    min_group_size: int = DEFAULT_MIN_GROUP_SIZE,
) -> ExportResultData:
    """Produce a privacy-enforced aggregated export dataset (rows + suppression)."""
    safe_group_by = [g for g in group_by if g in ALLOWED_GROUP_FIELDS] or ["sex"]
    observations = build_observations(session, campaign_id, analytes)
    return build_aggregated_export(
        observations,
        group_by=safe_group_by,
        analytes=analytes,
        min_group_size=min_group_size,
    )
