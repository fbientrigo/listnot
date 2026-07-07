"""Sample contract (docs/DATA_DICTIONARY.md §4)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from pucv_aq_qc.schemas.enums import PreanalyticalFlag, SampleType


class SampleIn(BaseModel):
    """A biological sample collected from a study subject."""

    model_config = ConfigDict(extra="forbid")

    campaign_id: str
    study_subject_id: str
    sample_uid: str
    sample_type: SampleType
    collected_at: datetime | None = None  # None -> missing_collection_time
    preanalytical_flags: list[PreanalyticalFlag] = Field(default_factory=list)
