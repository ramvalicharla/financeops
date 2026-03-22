from __future__ import annotations

from enum import Enum


class ScheduleType(str, Enum):
    BOARD_PACK = "BOARD_PACK"
    REPORT = "REPORT"


class ChannelType(str, Enum):
    EMAIL = "EMAIL"
    WEBHOOK = "WEBHOOK"


class DeliveryStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"


class DeliveryExportFormat(str, Enum):
    PDF = "PDF"
    EXCEL = "EXCEL"
    CSV = "CSV"


__all__ = [
    "ChannelType",
    "DeliveryExportFormat",
    "DeliveryStatus",
    "ScheduleType",
]
