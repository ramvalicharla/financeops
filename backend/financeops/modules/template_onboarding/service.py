from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.modules.board_pack_generator.domain.enums import PeriodType, SectionType
from financeops.modules.board_pack_generator.domain.pack_definition import (
    PackDefinitionSchema,
    SectionConfig,
)
from financeops.modules.board_pack_generator.infrastructure.repository import (
    BoardPackRepository,
)
from financeops.modules.custom_report_builder.domain.enums import ReportExportFormat
from financeops.modules.custom_report_builder.domain.filter_dsl import (
    FilterConfig,
    ReportDefinitionSchema,
)
from financeops.modules.custom_report_builder.infrastructure.repository import (
    ReportRepository,
)
from financeops.modules.scheduled_delivery.domain.enums import (
    ChannelType,
    DeliveryExportFormat,
    ScheduleType,
)
from financeops.modules.scheduled_delivery.domain.schedule_definition import (
    Recipient,
    ScheduleDefinitionSchema,
)
from financeops.modules.scheduled_delivery.infrastructure.repository import (
    DeliveryRepository,
)
from financeops.modules.template_onboarding.models import OnboardingState
from financeops.modules.template_onboarding.templates import get_template


class TemplateAlreadyAppliedError(RuntimeError):
    pass


async def get_or_create_onboarding_state(
    session: AsyncSession,
    tenant_id: uuid.UUID,
) -> OnboardingState:
    row = (
        await session.execute(
            select(OnboardingState).where(OnboardingState.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if row is not None:
        return row

    now = datetime.now(UTC)
    row = OnboardingState(
        tenant_id=tenant_id,
        current_step=1,
        template_applied=False,
        erp_connected=False,
        completed=False,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    await session.flush()
    return row


async def update_onboarding_step(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    step: int,
    **kwargs: Any,
) -> OnboardingState:
    if int(step) < 1 or int(step) > 5:
        raise ValueError("current_step must be between 1 and 5")

    row = await get_or_create_onboarding_state(session=session, tenant_id=tenant_id)
    row.current_step = int(step)

    for field in (
        "industry",
        "template_applied",
        "template_applied_at",
        "template_id",
        "erp_connected",
        "completed",
        "completed_at",
    ):
        if field in kwargs and kwargs[field] is not None:
            setattr(row, field, kwargs[field])

    row.updated_at = datetime.now(UTC)
    await session.flush()
    return row


async def apply_template(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    template_id: str,
    user_id: uuid.UUID,
) -> dict[str, Any]:
    template = get_template(template_id)
    if template is None:
        raise ValueError("Template not found")

    state = await get_or_create_onboarding_state(session=session, tenant_id=tenant_id)
    if state.template_applied:
        raise TemplateAlreadyAppliedError("Template already applied for tenant")

    board_repo = BoardPackRepository()
    report_repo = ReportRepository()
    delivery_repo = DeliveryRepository()

    section_configs = [
        SectionConfig(
            section_type=SectionType(str(section["section_type"])),
            order=index + 1,
        )
        for index, section in enumerate(template.board_pack_sections)
    ]
    board_schema = PackDefinitionSchema(
        name=f"{template.name} Board Pack",
        description=template.description,
        section_configs=section_configs,
        entity_ids=[tenant_id],
        period_type=PeriodType.MONTHLY,
        config={"template_id": template.id, "industry": template.industry},
    )
    board_definition = await board_repo.create_definition(
        db=session,
        tenant_id=tenant_id,
        schema=board_schema,
        created_by=user_id,
    )

    report_definition_ids: list[str] = []
    for report in template.report_definitions:
        report_schema = ReportDefinitionSchema(
            name=str(report["name"]),
            description=f"Created from onboarding template '{template.name}'",
            metric_keys=[str(metric_key) for metric_key in report["metric_keys"]],
            filter_config=FilterConfig(entity_ids=[tenant_id]),
            group_by=[],
            sort_config=None,
            export_formats=[ReportExportFormat.CSV, ReportExportFormat.PDF],
            config={"template_id": template.id, "industry": template.industry},
        )
        report_definition = await report_repo.create_definition(
            db=session,
            tenant_id=tenant_id,
            schema=report_schema,
            created_by=user_id,
        )
        report_definition_ids.append(str(report_definition.id))

    schedule_config = template.delivery_schedule
    recipients = [
        Recipient(type=ChannelType(str(recipient["type"])), address=str(recipient["address"]))
        for recipient in schedule_config.get("recipients", [])
    ]
    schedule_schema = ScheduleDefinitionSchema(
        name=f"{template.name} Delivery",
        description=f"Default delivery schedule for {template.name}",
        schedule_type=ScheduleType.BOARD_PACK,
        source_definition_id=board_definition.id,
        cron_expression=str(schedule_config["cron_expression"]),
        timezone="UTC",
        recipients=recipients,
        export_format=DeliveryExportFormat(str(schedule_config.get("export_format", "PDF"))),
        config={"template_id": template.id, "industry": template.industry},
    )
    delivery_schedule = await delivery_repo.create_schedule(
        db=session,
        tenant_id=tenant_id,
        schema=schedule_schema,
        created_by=user_id,
    )

    now = datetime.now(UTC)
    state.industry = template.industry
    state.template_applied = True
    state.template_applied_at = now
    state.template_id = template.id
    state.current_step = 3
    state.updated_at = now
    await session.flush()

    return {
        "board_pack_definition_id": str(board_definition.id),
        "report_definition_ids": report_definition_ids,
        "delivery_schedule_id": str(delivery_schedule.id),
        "step": 3,
        "board_pack_sections_count": len(template.board_pack_sections),
        "report_definitions_count": len(template.report_definitions),
    }


async def complete_onboarding(
    session: AsyncSession,
    tenant_id: uuid.UUID,
) -> OnboardingState:
    row = await get_or_create_onboarding_state(session=session, tenant_id=tenant_id)
    now = datetime.now(UTC)
    row.completed = True
    row.completed_at = now
    row.current_step = 5
    row.updated_at = now
    await session.flush()
    return row


__all__ = [
    "TemplateAlreadyAppliedError",
    "apply_template",
    "complete_onboarding",
    "get_or_create_onboarding_state",
    "update_onboarding_step",
]
