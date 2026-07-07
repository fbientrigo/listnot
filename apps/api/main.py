"""FastAPI statistical service (docs/API_CONTRACT.md).

Hard rule enforced here and in test_api_stats: statistical/export responses
never contain rut/name/phone/address/person_uid_global/study_subject_uid or
small groups. Subject ids in exports are export_subject_uid only.
"""

from __future__ import annotations

import secrets as _secrets
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from pucv_aq_qc import analytics
from pucv_aq_qc.audit.logger import AuditLogger
from pucv_aq_qc.config.settings import get_settings
from pucv_aq_qc.database.init_db import init_db
from pucv_aq_qc.database.models import StatisticalExport
from pucv_aq_qc.database.session import get_session
from pucv_aq_qc.ingestion.validators import ValidationReport, validate_rows
from pucv_aq_qc.privacy.export_policy import DEFAULT_POLICY_NAME, rows_to_csv
from pucv_aq_qc.synthetic.generator import generate_world, persist_world

__version__ = "0.1.0"


# --- request models ---------------------------------------------------------


class DemoGenerateRequest(BaseModel):
    n_subjects: int = 120
    seed: int = 42


class IngestionValidateRequest(BaseModel):
    format: str = "csv"
    rows: list[dict]


class ExportRequestBody(BaseModel):
    export_id: str
    group_by: list[str] = ["sex", "age_band"]
    analytes: list[str] = ["glucose", "chol_total"]


# --- app factory ------------------------------------------------------------


def _resolve_secret() -> bytes:
    settings = get_settings()
    try:
        return settings.require_secret()
    except Exception:
        if settings.demo_mode:
            return _secrets.token_bytes(32)
        raise


def get_db() -> Session:
    session = get_session()
    try:
        yield session
    finally:
        session.close()


def _require_demo() -> None:
    if not get_settings().demo_mode:
        raise HTTPException(status_code=403, detail="demo endpoints disabled")


def create_app() -> FastAPI:
    app = FastAPI(title="pucv-aq-qc", version=__version__)
    settings = get_settings()
    init_db()

    @app.get("/health")
    def health() -> dict:
        return {
            "status": "ok",
            "env": settings.env,
            "demo_mode": settings.demo_mode,
            "version": __version__,
        }

    @app.post("/api/v1/demo/generate-synthetic", status_code=201)
    def demo_generate(body: DemoGenerateRequest, _: None = Depends(_require_demo)) -> dict:
        secret = _resolve_secret()
        world = generate_world(secret=secret, n_subjects=body.n_subjects, seed=body.seed)
        with get_session() as session:
            persist_world(world, session)
        return {
            "campaign_id": world.campaign.id,
            "counts": world.counts(),
            "rut_persisted": False,
        }

    @app.get("/api/v1/campaigns")
    def campaigns(db: Session = Depends(get_db)) -> dict:
        rows = analytics.list_campaigns(db)
        return {
            "campaigns": [
                {
                    "id": c.id,
                    "name": c.name,
                    "protocol_version": c.protocol_version,
                    "location_label": c.location_label,
                    "status": c.status,
                }
                for c in rows
            ]
        }

    @app.get("/api/v1/campaigns/{campaign_id}")
    def campaign_detail(campaign_id: str, db: Session = Depends(get_db)) -> dict:
        c = analytics.get_campaign(db, campaign_id)
        if c is None:
            raise HTTPException(status_code=404, detail="campaign not found")
        return {
            "id": c.id,
            "name": c.name,
            "protocol_version": c.protocol_version,
            "location_label": c.location_label,
            "start_date": c.start_date.isoformat(),
            "status": c.status,
            "synthetic": c.synthetic,
        }

    @app.post("/api/v1/ingestion/validate")
    def ingestion_validate(body: IngestionValidateRequest) -> ValidationReport:
        secret = _resolve_secret()
        return validate_rows(body.rows, secret=secret)

    @app.get("/api/v1/qc/{campaign_id}/summary")
    def qc_summary(campaign_id: str, db: Session = Depends(get_db)) -> dict:
        return {"campaign_id": campaign_id, "analytes": analytics.qc_summary(db, campaign_id)}

    @app.get("/api/v1/qc/{campaign_id}/analytes/{analyte_code}")
    def qc_analyte(campaign_id: str, analyte_code: str, db: Session = Depends(get_db)) -> dict:
        return analytics.qc_analyte_series(db, campaign_id, analyte_code)

    @app.get("/api/v1/stats/{campaign_id}/summary")
    def stats_summary(
        campaign_id: str,
        group_by: str = "sex,age_band",
        db: Session = Depends(get_db),
    ) -> dict:
        fields = [g.strip() for g in group_by.split(",") if g.strip()]
        return analytics.stats_summary(
            db, campaign_id, group_by=fields, min_group_size=settings.min_group_size
        )

    @app.get("/api/v1/stats/{campaign_id}/analytes/{analyte_code}")
    def stats_analyte(
        campaign_id: str,
        analyte_code: str,
        group_by: str = "comuna",
        db: Session = Depends(get_db),
    ) -> dict:
        fields = [g.strip() for g in group_by.split(",") if g.strip()]
        return analytics.stats_summary(
            db, campaign_id, group_by=fields, analytes=[analyte_code],
            min_group_size=settings.min_group_size,
        )

    @app.post("/api/v1/exports/{campaign_id}/aggregated", status_code=201)
    def export_aggregated(
        campaign_id: str,
        body: ExportRequestBody,
        db: Session = Depends(get_db),
    ) -> dict:
        result = analytics.aggregated_export(
            db,
            campaign_id,
            group_by=body.group_by,
            analytes=body.analytes,
            min_group_size=settings.min_group_size,
        )
        csv_text = rows_to_csv(result.rows, group_by=[g for g in body.group_by if g in analytics.ALLOWED_GROUP_FIELDS] or ["sex"])
        export_dir = Path("data/exports")
        export_dir.mkdir(parents=True, exist_ok=True)
        output_uri = str(export_dir / f"{body.export_id}.csv")
        Path(output_uri).write_text(csv_text, encoding="utf-8")

        # audit + provenance
        logger = AuditLogger(db)
        audit_row = logger.log(
            "export",
            actor="api",
            role="student",
            resource_type="export",
            resource_id=body.export_id,
            metadata={
                "min_group_size": result.min_group_size,
                "suppressed_cells": result.suppressed_cells,
                "policy": result.policy_name,
            },
            commit=False,
        )
        db.add(
            StatisticalExport(
                campaign_id=campaign_id,
                export_id=body.export_id,
                export_policy=DEFAULT_POLICY_NAME,
                min_group_size=result.min_group_size,
                created_by="api",
                output_uri=output_uri,
            )
        )
        db.commit()

        return {
            "export_id": body.export_id,
            "min_group_size": result.min_group_size,
            "output_uri": output_uri,
            "audit_id": audit_row.id,
            "subject_id_kind": "export_subject_uid",
            "suppressed_cells": result.suppressed_cells,
        }

    return app


app = create_app()
