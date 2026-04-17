from __future__ import annotations

import uuid

from croniter import croniter
from pydantic import BaseModel, Field, field_validator

from financeops.modules.scheduled_delivery.domain.enums import (
    ChannelType,
    DeliveryExportFormat,
    ScheduleType,
)


class Recipient(BaseModel):
    type: ChannelType
    address: str

    @field_validator("address")
    @classmethod
    def _validate_address_not_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("recipient address is required")
        return cleaned

    @field_validator("address")
    @classmethod
    def _validate_address_format(cls, value: str, info) -> str:
        recipient_type = info.data.get("type")
        if recipient_type == ChannelType.EMAIL and "@" not in value:
            raise ValueError("email recipient address must contain '@'")
        if recipient_type == ChannelType.WEBHOOK and not (
            value.startswith("http://") or value.startswith("https://")
        ):
            raise ValueError("webhook recipient address must start with http:// or https://")
        return value


class ScheduleDefinitionSchema(BaseModel):
    name: str
    description: str | None = None
    schedule_type: ScheduleType
    source_definition_id: uuid.UUID
    cron_expression: str
    timezone: str = "UTC"
    recipients: list[Recipient]
    export_format: DeliveryExportFormat = DeliveryExportFormat.PDF
    config: dict = Field(default_factory=dict)

    @field_validator("recipients")
    @classmethod
    def _validate_recipients_non_empty(cls, value: list[Recipient]) -> list[Recipient]:
        if not value:
            raise ValueError("recipients must not be empty")
        return value

    @field_validator("cron_expression")
    @classmethod
    def _validate_cron_expression_fields(cls, value: str) -> str:
        if not croniter.is_valid(value):
            raise ValueError("cron_expression must be a valid 5-field cron expression")
        return value


__all__ = ["Recipient", "ScheduleDefinitionSchema"]
