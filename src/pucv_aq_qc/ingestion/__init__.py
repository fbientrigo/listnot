"""Ingestion zone: parse → validate → identity gateway → internal models.

The raw input contract (``contracts.IngestionRow``) is the ONLY schema in the
system permitted to carry a RUT, and only in memory. Everything downstream
receives pseudonymous IDs (docs/SDD.md §3-5).
"""
