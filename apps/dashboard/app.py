"""Streamlit dashboard over QC + aggregated statistics.

Reads through the ``analytics`` service so it inherits the same privacy rules as
the API; it never renders a subject pseudonym or a small group. Run with:

    streamlit run apps/dashboard/app.py
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from pucv_aq_qc import analytics
from pucv_aq_qc.config.settings import get_settings
from pucv_aq_qc.database.session import get_session

st.set_page_config(page_title="pucv-aq-qc", layout="wide")
st.title("pucv-aq-qc · Control de calidad y estadísticas")

settings = get_settings()

with get_session() as session:
    campaigns = analytics.list_campaigns(session)
    if not campaigns:
        st.warning("No hay campañas. Ejecuta `make demo` para generar datos sintéticos.")
        st.stop()

    labels = {f"{c.name} ({c.id[:12]}…)": c.id for c in campaigns}
    choice = st.selectbox("Campaña", list(labels))
    campaign_id = labels[choice]

    st.header("Control de calidad (Westgard / Levey-Jennings)")
    qc = analytics.qc_summary(session, campaign_id)
    qc_df = pd.DataFrame(qc)
    if not qc_df.empty:
        def _color(status: str) -> str:
            return {"rejected": "background-color:#fee2e2", "warning": "background-color:#fef9c3"}.get(
                status, "background-color:#dcfce7"
            )

        st.dataframe(
            qc_df.style.map(_color, subset=["run_status"]) if "run_status" in qc_df else qc_df,
            use_container_width=True,
        )

    analyte = st.selectbox("Analito (serie LJ)", sorted({r["analyte_code"] for r in qc}))
    series = analytics.qc_analyte_series(session, campaign_id, analyte)
    if series["series"]:
        s_df = pd.DataFrame(series["series"])
        st.line_chart(s_df.set_index("measured_at")["z"], height=240)
        for flag in series["flags"]:
            st.write(f"**{flag['severity'].upper()}** — {flag['message']}")

    st.header("Estadísticas agregadas (con supresión de grupos pequeños)")
    stats = analytics.stats_summary(
        session, campaign_id, group_by=["sex", "age_band"], min_group_size=settings.min_group_size
    )
    st.caption(
        f"min_group_size = {stats['min_group_size']} · "
        f"grupos suprimidos = {stats['suppressed_group_count']}"
    )
    st.dataframe(pd.DataFrame(stats["groups"]), use_container_width=True)
