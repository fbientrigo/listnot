"""Synthetic-data generation (ADR-0003). Never importable in a production data path.

Produces campaigns, valid synthetic Chilean RUTs, subjects, samples, analyte
results, and QC controls with injectable error scenarios so the QC engine fires
realistically. RUTs are used only to derive pseudonyms and are then discarded —
no raw RUT is persisted.
"""

from pucv_aq_qc.synthetic.generator import SyntheticWorld, generate_world, persist_world
from pucv_aq_qc.synthetic.scenarios import Scenario

__all__ = ["SyntheticWorld", "generate_world", "persist_world", "Scenario"]
