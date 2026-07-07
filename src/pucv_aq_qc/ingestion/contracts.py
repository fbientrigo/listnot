"""Raw ingestion row contract — the only schema allowed to carry a RUT.

A ``RawIngestionRow`` exists only in memory inside the ingestion zone. The
identity gateway consumes its ``rut``, derives a pseudonym, and discards the
RUT; nothing downstream ever sees this type (docs/SDD.md §5, PRIVACY_MODEL §5).

This type is deliberately kept OUT of ``schemas/`` so that the operational
schema package can be asserted RUT-free.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class RawIngestionRow(BaseModel):
    """A single row from a CSV/Excel/form import, pre-pseudonymization.

    Its ``__repr__`` is customized to never print the RUT
    (docs/PRIVACY_MODEL.md §8).
    """

    model_config = ConfigDict(extra="ignore")

    rut: str = Field(repr=False)
    analyte_code: str
    value: float | None = None
    unit: str
    campaign_id: str | None = None
    reagent_lot: str | None = None
    method: str | None = None
    instrument_id: str | None = None

    def __repr__(self) -> str:  # pragma: no cover - defensive, never logs RUT
        return (
            f"RawIngestionRow(rut=<redacted>, analyte_code={self.analyte_code!r}, "
            f"value={self.value!r}, unit={self.unit!r})"
        )

    __str__ = __repr__
