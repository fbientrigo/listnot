"""Shared enums for schemas, database models, and QC (docs/DATA_DICTIONARY.md)."""

from __future__ import annotations

from enum import StrEnum


class CampaignStatus(StrEnum):
    planned = "planned"
    active = "active"
    closed = "closed"


class ConsentStatus(StrEnum):
    unknown = "unknown"
    granted = "granted"
    withdrawn = "withdrawn"


class SampleType(StrEnum):
    serum = "serum"
    plasma = "plasma"
    whole_blood = "whole_blood"


class ControlLevel(StrEnum):
    L1 = "L1"
    L2 = "L2"


class PreanalyticalFlag(StrEnum):
    hemolysis_suspected = "hemolysis_suspected"
    insufficient_sample = "insufficient_sample"
    delayed_processing = "delayed_processing"
    missing_fasting_status = "missing_fasting_status"
    wrong_tube = "wrong_tube"
    sample_clotting = "sample_clotting"
    temperature_excursion = "temperature_excursion"
    missing_collection_time = "missing_collection_time"


class ResultFlag(StrEnum):
    below_ref = "below_ref"
    above_ref = "above_ref"
    critical = "critical"
    missing = "missing"


class RuleCode(StrEnum):
    r_1_2s = "1_2s"
    r_1_3s = "1_3s"
    r_2_2s = "2_2s"
    r_R_4s = "R_4s"
    r_4_1s = "4_1s"
    r_10x = "10x"


class Severity(StrEnum):
    info = "info"
    warning = "warning"
    reject = "reject"


class RunStatus(StrEnum):
    accepted = "accepted"
    warning = "warning"
    rejected = "rejected"


class EventType(StrEnum):
    access = "access"
    export = "export"
    ingestion = "ingestion"
    admin = "admin"
    key_rotation = "key_rotation"
