from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.scheduled_delivery import DeliveryLog, DeliverySchedule
from financeops.modules.scheduled_delivery.domain.schedule_definition import (
    ScheduleDefinitionSchema,
)


class DeliveryRepository:
    async def create_schedule(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        schema: ScheduleDefinitionSchema,
        created_by: uuid.UUID,
        *,
        next_run_at: datetime | None = None,
    ) -> DeliverySchedule:
        now = datetime.now(UTC)
        row = DeliverySchedule(
            tenant_id=tenant_id,
            name=schema.name,
            description=schema.description,
            schedule_type=schema.schedule_type.value,
            source_definition_id=schema.source_definition_id,
            cron_expression=schema.cron_expression,
            timezone=schema.timezone,
            recipients=[recipient.model_dump(mode="json") for recipient in schema.recipients],
            export_format=schema.export_format.value,
            is_active=True,
            next_run_at=next_run_at,
            config=dict(schema.config or {}),
            created_by=created_by,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
        await db.flush()
        return row

    async def get_schedule(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        schedule_id: uuid.UUID,
    ) -> DeliverySchedule | None:
        result = await db.execute(
            select(DeliverySchedule).where(
                DeliverySchedule.tenant_id == tenant_id,
                DeliverySchedule.id == schedule_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_schedules(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        active_only: bool = False,
    ) -> list[DeliverySchedule]:
        stmt = select(DeliverySchedule).where(DeliverySchedule.tenant_id == tenant_id)
        if active_only:
            stmt = stmt.where(DeliverySchedule.is_active.is_(True))
        stmt = stmt.order_by(DeliverySchedule.created_at.desc(), DeliverySchedule.id.desc())
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def update_schedule(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        schedule_id: uuid.UUID,
        updates: dict[str, Any],
    ) -> DeliverySchedule:
        row = await self.get_schedule(db=db, tenant_id=tenant_id, schedule_id=schedule_id)
        if row is None:
            raise ValueError("Delivery schedule not found")

        if "name" in updates and updates["name"] is not None:
            row.name = str(updates["name"])
        if "description" in updates:
            row.description = updates["description"]
        if "schedule_type" in updates and updates["schedule_type"] is not None:
            row.schedule_type = str(updates["schedule_type"])
        if "source_definition_id" in updates and updates["source_definition_id"] is not None:
            row.source_definition_id = updates["source_definition_id"]
        if "cron_expression" in updates and updates["cron_expression"] is not None:
            row.cron_expression = str(updates["cron_expression"])
        if "timezone" in updates and updates["timezone"] is not None:
            row.timezone = str(updates["timezone"])
        if "recipients" in updates and updates["recipients"] is not None:
            row.recipients = list(updates["recipients"])
        if "export_format" in updates and updates["export_format"] is not None:
            row.export_format = str(updates["export_format"])
        if "is_active" in updates and updates["is_active"] is not None:
            row.is_active = bool(updates["is_active"])
        if "last_triggered_at" in updates:
            row.last_triggered_at = updates["last_triggered_at"]
        if "next_run_at" in updates:
            row.next_run_at = updates["next_run_at"]
        if "config" in updates and updates["config"] is not None:
            row.config = dict(updates["config"])
        row.updated_at = datetime.now(UTC)
        await db.flush()
        return row

    async def deactivate_schedule(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        schedule_id: uuid.UUID,
    ) -> DeliverySchedule:
        return await self.update_schedule(
            db=db,
            tenant_id=tenant_id,
            schedule_id=schedule_id,
            updates={"is_active": False},
        )

    async def create_log(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        schedule_id: uuid.UUID,
        channel_type: str,
        recipient_address: str,
        source_run_id: uuid.UUID | None = None,
        *,
        status: str = "PENDING",
        completed_at: datetime | None = None,
        error_message: str | None = None,
        retry_count: int = 0,
        response_metadata: dict[str, Any] | None = None,
    ) -> DeliveryLog:
        row = DeliveryLog(
            tenant_id=tenant_id,
            schedule_id=schedule_id,
            status=status,
            channel_type=channel_type,
            recipient_address=recipient_address,
            source_run_id=source_run_id,
            completed_at=completed_at,
            error_message=error_message,
            retry_count=retry_count,
            response_metadata=dict(response_metadata or {}),
            created_at=datetime.now(UTC),
        )
        db.add(row)
        await db.flush()
        return row

    async def get_log(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        log_id: uuid.UUID,
    ) -> DeliveryLog | None:
        result = await db.execute(
            select(DeliveryLog).where(
                DeliveryLog.tenant_id == tenant_id,
                DeliveryLog.id == log_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_logs(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        schedule_id: uuid.UUID | None = None,
        status: str | None = None,
        limit: int = 20,
    ) -> list[DeliveryLog]:
        clamped_limit = max(1, min(200, int(limit)))
        stmt = select(DeliveryLog).where(DeliveryLog.tenant_id == tenant_id)
        if schedule_id is not None:
            stmt = stmt.where(DeliveryLog.schedule_id == schedule_id)
        if status is not None:
            stmt = stmt.where(DeliveryLog.status == status)
        stmt = stmt.order_by(DeliveryLog.triggered_at.desc(), DeliveryLog.id.desc()).limit(clamped_limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def list_due_schedules(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
    ) -> list[DeliverySchedule]:
        now = datetime.now(UTC)
        result = await db.execute(
            select(DeliverySchedule)
            .where(
                DeliverySchedule.tenant_id == tenant_id,
                DeliverySchedule.is_active.is_(True),
                DeliverySchedule.next_run_at.is_not(None),
                DeliverySchedule.next_run_at <= now,
            )
            .order_by(DeliverySchedule.next_run_at.asc(), DeliverySchedule.id.asc())
        )
        return list(result.scalars().all())


__all__ = ["DeliveryRepository"]
