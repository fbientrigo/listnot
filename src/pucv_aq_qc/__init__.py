"""pucv-aq-qc — reproducible data-quality, pseudonymization and QC layer.

A downstream, identity-safe mirror of PUCV / Centro de Bioanálisis Clínico
lab-campaign data. It is NOT a LIS/EHR: it exists to run QC, produce
reproducible statistics, and enforce a hard privacy boundary in which a
Chilean RUT is never persisted, logged, exported, or returned.

See docs/SDD.md and docs/PRIVACY_MODEL.md.
"""

__version__ = "0.1.0"
