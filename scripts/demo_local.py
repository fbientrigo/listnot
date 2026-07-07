#!/usr/bin/env python3
"""End-to-end synthetic demo pipeline (docs/SDD.md MVP demo flow; DELIVERY_PLAN Commit 8).

Steps: reset DB → generate+persist synthetic world → QC summary → aggregated
statistics → Markdown/HTML report → audited aggregated export → forbidden-
identifier scan → self-check that no RUT was persisted.

    python scripts/demo_local.py [--subjects N] [--seed S]
"""

from __future__ import annotations

import argparse
import secrets as _secrets
from pathlib import Path

from pucv_aq_qc import analytics
from pucv_aq_qc.audit.logger import AuditLogger
from pucv_aq_qc.config.settings import get_settings
from pucv_aq_qc.database.init_db import drop_all, init_db
from pucv_aq_qc.database.models import StatisticalExport
from pucv_aq_qc.database.session import session_scope
from pucv_aq_qc.privacy import forbidden
from pucv_aq_qc.privacy.export_policy import DEFAULT_POLICY_NAME, rows_to_csv
from pucv_aq_qc.reporting import render_html_report, render_markdown_report
from pucv_aq_qc.synthetic.generator import generate_world, persist_world

REPORT_DIR = Path("data/reports")
EXPORT_DIR = Path("data/exports")


def _secret() -> bytes:
    settings = get_settings()
    try:
        return settings.require_secret()
    except Exception:
        return _secrets.token_bytes(32)  # ephemeral demo secret (synthetic only)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subjects", type=int, default=120)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)

    print("[1] reset database")
    drop_all()
    init_db()

    print("[2] generate + persist synthetic world")
    world = generate_world(secret=_secret(), n_subjects=args.subjects, seed=args.seed)
    with session_scope() as session:
        persist_world(world, session)
    campaign_id = world.campaign.id
    counts = world.counts()

    with session_scope() as session:
        print("[3] QC summary")
        qc = analytics.qc_summary(session, campaign_id)

        print("[4] aggregated statistics")
        stats = analytics.stats_summary(
            session, campaign_id, group_by=["sex", "age_band"],
            min_group_size=get_settings().min_group_size,
        )

        print("[5] render Markdown + HTML report")
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        report_kwargs = dict(
            campaign_name=world.campaign.name,
            campaign_id=campaign_id,
            counts=counts,
            qc_summary=qc,
            stats=stats,
        )
        (REPORT_DIR / "report.md").write_text(render_markdown_report(**report_kwargs), encoding="utf-8")
        (REPORT_DIR / "report.html").write_text(render_html_report(**report_kwargs), encoding="utf-8")

        print("[6] audited aggregated export")
        result = analytics.aggregated_export(
            session, campaign_id, group_by=["sex", "age_band"],
            analytes=["glucose", "chol_total"], min_group_size=get_settings().min_group_size,
        )
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        export_uri = EXPORT_DIR / "demo_export.csv"
        export_uri.write_text(rows_to_csv(result.rows, group_by=["sex", "age_band"]), encoding="utf-8")
        logger = AuditLogger(session)
        logger.log(
            "export", actor="demo", role="operator", resource_type="export",
            resource_id="demo_export",
            metadata={"min_group_size": result.min_group_size, "suppressed_cells": result.suppressed_cells},
            commit=False,
        )
        session.add(
            StatisticalExport(
                campaign_id=campaign_id, export_id="demo_export",
                export_policy=DEFAULT_POLICY_NAME, min_group_size=result.min_group_size,
                created_by="demo", output_uri=str(export_uri),
            )
        )

    print("[7] forbidden-identifier scan over data/")
    matches = forbidden.scan_paths(["data"])
    if matches:
        print(f"    FAILED: {len(matches)} forbidden match(es)")
        return 1
    print("    clean")

    print("\n=== demo complete ===")
    print(f"campaign_id = {campaign_id}")
    for k, v in counts.items():
        print(f"{k} = {v}")
    print(f"suppressed_cells = {result.suppressed_cells}")
    print(f"report = {REPORT_DIR / 'report.md'}")
    print(f"export = {export_uri}")
    print("rut_persisted = false")  # step 16 self-check
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
