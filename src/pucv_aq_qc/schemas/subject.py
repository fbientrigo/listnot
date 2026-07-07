"""Subject / StudySubject contracts (docs/DATA_DICTIONARY.md §2-3).

No RUT/name/phone/address field exists here — by construction, not by policy.
``person_uid_global`` is operational-zone only and must never be serialized to
students/public (docs/PRIVACY_MODEL.md §4-5); it is therefore NOT part of any
``*Out`` schema returned by the API.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from pucv_aq_qc.schemas.enums import ConsentStatus


class SubjectOut(BaseModel):
    """A pseudonymous subject as exposed within the operational zone only.

    Note: this schema intentionally omits ``person_uid_global``; the operational
    identifier never leaves the operational zone in a response body.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    key_version: str
    synthetic: bool
    created_at: datetime


class StudySubjectOut(BaseModel):
    """A subject's participation within one campaign (carries ``suid_…``)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    campaign_id: str
    subject_id: str
    study_subject_uid: str
    consent_status: ConsentStatus
    created_at: datetime
