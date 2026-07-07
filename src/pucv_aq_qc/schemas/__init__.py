"""Pydantic v2 data contracts — the shapes the whole system agrees on.

These are the wire + internal contracts (docs/DATA_DICTIONARY.md). Persisted
operational models (database/) mirror these and, like them, contain **no**
``rut``/``name``/``phone``/``address`` field — enforced by test_schemas.
"""

from pucv_aq_qc.schemas.campaign import CampaignIn, CampaignOut
from pucv_aq_qc.schemas.export import ExportRequest, ExportResult
from pucv_aq_qc.schemas.qc import QCFlagOut, QCMeasurementIn
from pucv_aq_qc.schemas.result import AnalyteResultIn
from pucv_aq_qc.schemas.sample import SampleIn
from pucv_aq_qc.schemas.subject import StudySubjectOut, SubjectOut

__all__ = [
    "CampaignIn",
    "CampaignOut",
    "SubjectOut",
    "StudySubjectOut",
    "SampleIn",
    "AnalyteResultIn",
    "QCMeasurementIn",
    "QCFlagOut",
    "ExportRequest",
    "ExportResult",
]
