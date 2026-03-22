from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from financeops.modules.scheduled_delivery.domain.enums import (
    ChannelType,
    ScheduleType,
)
from financeops.modules.scheduled_delivery.domain.schedule_definition import (
    Recipient,
    ScheduleDefinitionSchema,
)


def _base_payload() -> dict:
    return {
        "name": "Morning Delivery",
        "schedule_type": ScheduleType.BOARD_PACK,
        "source_definition_id": uuid.uuid4(),
        "cron_expression": "0 8 * * 1",
        "timezone": "UTC",
        "recipients": [Recipient(type=ChannelType.EMAIL, address="ops@example.com")],
        "config": {},
    }


@pytest.mark.unit
def test_t_201_schedule_definition_rejects_empty_recipients() -> None:
    payload = _base_payload()
    payload["recipients"] = []
    with pytest.raises(ValidationError):
        ScheduleDefinitionSchema(**payload)


@pytest.mark.unit
def test_t_202_schedule_definition_rejects_four_field_cron_expression() -> None:
    payload = _base_payload()
    payload["cron_expression"] = "0 8 * *"
    with pytest.raises(ValidationError):
        ScheduleDefinitionSchema(**payload)


@pytest.mark.unit
def test_t_203_schedule_definition_accepts_five_field_cron_expression() -> None:
    payload = _base_payload()
    payload["cron_expression"] = "15 10 * * 2"
    model = ScheduleDefinitionSchema(**payload)
    assert model.cron_expression == "15 10 * * 2"


@pytest.mark.unit
def test_t_204_email_recipient_without_at_is_invalid() -> None:
    with pytest.raises(ValidationError):
        Recipient(type=ChannelType.EMAIL, address="invalid-email")


@pytest.mark.unit
def test_t_205_webhook_recipient_without_http_is_invalid() -> None:
    with pytest.raises(ValidationError):
        Recipient(type=ChannelType.WEBHOOK, address="hooks.example.com/path")


@pytest.mark.unit
def test_t_206_schedule_definition_accepts_email_and_webhook_recipients() -> None:
    payload = _base_payload()
    payload["recipients"] = [
        Recipient(type=ChannelType.EMAIL, address="ops@example.com"),
        Recipient(type=ChannelType.WEBHOOK, address="https://hooks.example.com/delivery"),
    ]
    model = ScheduleDefinitionSchema(**payload)
    assert len(model.recipients) == 2
    assert model.recipients[0].type == ChannelType.EMAIL
    assert model.recipients[1].type == ChannelType.WEBHOOK
