from __future__ import annotations

from enum import Enum


class SectionType(str, Enum):
    PROFIT_AND_LOSS = "PROFIT_AND_LOSS"
    BALANCE_SHEET = "BALANCE_SHEET"
    CASH_FLOW = "CASH_FLOW"
    KPI_SUMMARY = "KPI_SUMMARY"
    RATIO_ANALYSIS = "RATIO_ANALYSIS"
    NARRATIVE = "NARRATIVE"
    FX_SUMMARY = "FX_SUMMARY"
    ENTITY_CONSOLIDATION = "ENTITY_CONSOLIDATION"


class PeriodType(str, Enum):
    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"
    ANNUAL = "ANNUAL"


class PackRunStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


class ExportFormat(str, Enum):
    PDF = "PDF"
    EXCEL = "EXCEL"


__all__ = [
    "ExportFormat",
    "PackRunStatus",
    "PeriodType",
    "SectionType",
]

