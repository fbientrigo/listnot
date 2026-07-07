"""Campaign contracts (docs/DATA_DICTIONARY.md §1)."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from pucv_aq_qc.schemas.enums import CampaignStatus


class CampaignIn(BaseModel):
    """Input to create a campaign. ``location_label`` is coarse only."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    protocol_version: str = Field(min_length=1)
    location_label: str = Field(min_length=1, description="Coarse comuna/región, never address/coords")
    start_date: date
    end_date: date | None = None
    status: CampaignStatus = CampaignStatus.planned
    synthetic: bool = True


class CampaignOut(CampaignIn):
    """Campaign as returned by metadata endpoints."""

    id: str
