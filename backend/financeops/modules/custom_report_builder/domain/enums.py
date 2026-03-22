from __future__ import annotations

from enum import Enum


class ReportRunStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


class ReportExportFormat(str, Enum):
    CSV = "CSV"
    EXCEL = "EXCEL"
    PDF = "PDF"


class FilterOperator(str, Enum):
    EQ = "EQ"
    NEQ = "NEQ"
    GT = "GT"
    GTE = "GTE"
    LT = "LT"
    LTE = "LTE"
    IN = "IN"
    BETWEEN = "BETWEEN"


class SortDirection(str, Enum):
    ASC = "ASC"
    DESC = "DESC"


__all__ = [
    "FilterOperator",
    "ReportExportFormat",
    "ReportRunStatus",
    "SortDirection",
]

