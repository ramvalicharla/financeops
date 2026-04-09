from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import NotFoundError, ValidationError
from financeops.core.intent.context import apply_mutation_linkage, require_mutation_context
from financeops.modules.prepaid_expenses.application.amortisation_engine import (
    calculate_slm_schedule,
    get_period_amount,
)
from financeops.modules.prepaid_expenses.models import PrepaidAmortisationEntry, PrepaidSchedule


class PrepaidService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _limit(limit: int) -> int:
        return max(1, min(limit, 1000))

    async def _get_schedule_or_404(self, tenant_id: uuid.UUID, schedule_id: uuid.UUID) -> PrepaidSchedule:
        row = (
            await self._session.execute(
                select(PrepaidSchedule).where(
                    PrepaidSchedule.id == schedule_id,
                    PrepaidSchedule.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            raise NotFoundError("Prepaid schedule not found")
        return row

    async def create_schedule(
        self,
        tenant_id: uuid.UUID,
        entity_id: uuid.UUID,
        data: dict[str, Any],
    ) -> PrepaidSchedule:
        require_mutation_context("Prepaid schedule creation")
        existing = (
            await self._session.execute(
                select(PrepaidSchedule.id).where(
                    PrepaidSchedule.tenant_id == tenant_id,
                    PrepaidSchedule.entity_id == entity_id,
                    PrepaidSchedule.reference_number == str(data["reference_number"]),
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            raise ValidationError("reference_number already exists for entity")

        total = Decimal(str(data["total_amount"]))
        row = PrepaidSchedule(
            tenant_id=tenant_id,
            entity_id=entity_id,
            reference_number=str(data["reference_number"]),
            description=str(data["description"]),
            prepaid_type=str(data["prepaid_type"]).upper(),
            vendor_name=data.get("vendor_name"),
            invoice_number=data.get("invoice_number"),
            total_amount=total,
            amortised_amount=Decimal("0"),
            remaining_amount=total,
            coverage_start=data["coverage_start"],
            coverage_end=data["coverage_end"],
            amortisation_method=str(data.get("amortisation_method", "SLM")).upper(),
            coa_prepaid_account_id=data.get("coa_prepaid_account_id"),
            coa_expense_account_id=data.get("coa_expense_account_id"),
            location_id=data.get("location_id"),
            cost_centre_id=data.get("cost_centre_id"),
            status=str(data.get("status", "ACTIVE")).upper(),
        )
        apply_mutation_linkage(row)
        self._session.add(row)
        await self._session.flush()
        return row

    async def update_schedule(
        self,
        tenant_id: uuid.UUID,
        schedule_id: uuid.UUID,
        data: dict[str, Any],
    ) -> PrepaidSchedule:
        require_mutation_context("Prepaid schedule update")
        row = await self._get_schedule_or_404(tenant_id, schedule_id)
        entries_exist = int(
            (
                await self._session.execute(
                    select(func.count()).select_from(PrepaidAmortisationEntry).where(
                        PrepaidAmortisationEntry.tenant_id == tenant_id,
                        PrepaidAmortisationEntry.schedule_id == schedule_id,
                    )
                )
            ).scalar_one()
        ) > 0

        financial_fields = {
            "total_amount",
            "amortised_amount",
            "remaining_amount",
            "coverage_start",
            "coverage_end",
            "amortisation_method",
        }
        if entries_exist and any(field in data for field in financial_fields):
            raise ValidationError("Financial fields cannot be changed after amortisation entries exist")

        allowed = {
            "description",
            "vendor_name",
            "invoice_number",
            "status",
            "prepaid_type",
            "coa_prepaid_account_id",
            "coa_expense_account_id",
            "location_id",
            "cost_centre_id",
        }
        if not entries_exist:
            allowed |= financial_fields

        for key, value in data.items():
            if key in allowed:
                setattr(row, key, value)

        apply_mutation_linkage(row)
        await self._session.flush()
        return row

    async def get_schedules(
        self,
        tenant_id: uuid.UUID,
        entity_id: uuid.UUID,
        skip: int,
        limit: int,
        status: str | None = None,
        prepaid_type: str | None = None,
        location_id: uuid.UUID | None = None,
        cost_centre_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        effective_limit = self._limit(limit)
        stmt = select(PrepaidSchedule).where(
            PrepaidSchedule.tenant_id == tenant_id,
            PrepaidSchedule.entity_id == entity_id,
        )
        if status:
            stmt = stmt.where(PrepaidSchedule.status == status)
        if prepaid_type:
            stmt = stmt.where(PrepaidSchedule.prepaid_type == prepaid_type)
        if location_id is not None:
            stmt = stmt.where(PrepaidSchedule.location_id == location_id)
        if cost_centre_id is not None:
            stmt = stmt.where(PrepaidSchedule.cost_centre_id == cost_centre_id)

        total = int((await self._session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one())
        rows = (
            await self._session.execute(
                stmt.order_by(PrepaidSchedule.coverage_start.desc(), PrepaidSchedule.reference_number)
                .offset(skip)
                .limit(effective_limit)
            )
        ).scalars().all()
        return {
            "items": list(rows),
            "total": total,
            "skip": skip,
            "limit": effective_limit,
            "has_more": (skip + len(rows)) < total,
        }

    async def get_schedule(self, tenant_id: uuid.UUID, schedule_id: uuid.UUID) -> PrepaidSchedule:
        return await self._get_schedule_or_404(tenant_id, schedule_id)

    async def get_entries(
        self,
        tenant_id: uuid.UUID,
        schedule_id: uuid.UUID,
        skip: int,
        limit: int,
    ) -> dict[str, Any]:
        effective_limit = self._limit(limit)
        total = int(
            (
                await self._session.execute(
                    select(func.count()).select_from(PrepaidAmortisationEntry).where(
                        PrepaidAmortisationEntry.tenant_id == tenant_id,
                        PrepaidAmortisationEntry.schedule_id == schedule_id,
                    )
                )
            ).scalar_one()
        )
        rows = (
            await self._session.execute(
                select(PrepaidAmortisationEntry)
                .where(
                    PrepaidAmortisationEntry.tenant_id == tenant_id,
                    PrepaidAmortisationEntry.schedule_id == schedule_id,
                )
                .order_by(PrepaidAmortisationEntry.period_start.desc(), PrepaidAmortisationEntry.created_at.desc())
                .offset(skip)
                .limit(effective_limit)
            )
        ).scalars().all()
        return {
            "items": list(rows),
            "total": total,
            "skip": skip,
            "limit": effective_limit,
            "has_more": (skip + len(rows)) < total,
        }

    async def run_period(
        self,
        tenant_id: uuid.UUID,
        entity_id: uuid.UUID,
        period_start: date,
        period_end: date,
    ) -> list[PrepaidAmortisationEntry]:
        require_mutation_context("Prepaid amortization posting")
        schedules = (
            await self._session.execute(
                select(PrepaidSchedule)
                .where(
                    PrepaidSchedule.tenant_id == tenant_id,
                    PrepaidSchedule.entity_id == entity_id,
                    PrepaidSchedule.status == "ACTIVE",
                )
                .order_by(PrepaidSchedule.reference_number)
            )
        ).scalars().all()

        entries: list[PrepaidAmortisationEntry] = []
        for schedule in schedules:
            run_reference = f"{schedule.id}:{period_start.isoformat()}:{period_end.isoformat()}"
            existing = (
                await self._session.execute(
                    select(PrepaidAmortisationEntry).where(
                        PrepaidAmortisationEntry.tenant_id == tenant_id,
                        PrepaidAmortisationEntry.run_reference == run_reference,
                    )
                )
            ).scalar_one_or_none()
            if existing is not None:
                entries.append(existing)
                continue

            amount = get_period_amount(schedule, period_start, period_end)
            if amount <= Decimal("0"):
                continue

            remaining_before = Decimal(str(schedule.remaining_amount))
            is_last = amount >= remaining_before
            entry_amount = remaining_before if is_last else amount

            row = apply_mutation_linkage(PrepaidAmortisationEntry(
                tenant_id=tenant_id,
                entity_id=entity_id,
                schedule_id=schedule.id,
                period_start=period_start,
                period_end=period_end,
                amortisation_amount=entry_amount,
                is_last_period=is_last,
                run_reference=run_reference,
            ))
            self._session.add(row)
            entries.append(row)

            schedule.amortised_amount = Decimal(str(schedule.amortised_amount)) + entry_amount
            schedule.remaining_amount = Decimal(str(schedule.total_amount)) - Decimal(str(schedule.amortised_amount))
            if schedule.remaining_amount <= Decimal("0"):
                schedule.remaining_amount = Decimal("0")
                schedule.status = "FULLY_AMORTISED"
            apply_mutation_linkage(schedule)

        await self._session.flush()
        return entries

    async def get_amortisation_schedule(
        self,
        tenant_id: uuid.UUID,
        schedule_id: uuid.UUID,
    ) -> list[dict[str, Any]]:
        schedule = await self._get_schedule_or_404(tenant_id, schedule_id)

        entries = (
            await self._session.execute(
                select(PrepaidAmortisationEntry)
                .where(
                    PrepaidAmortisationEntry.tenant_id == tenant_id,
                    PrepaidAmortisationEntry.schedule_id == schedule_id,
                )
                .order_by(PrepaidAmortisationEntry.period_start)
            )
        ).scalars().all()
        actual_by_key = {
            (row.period_start, row.period_end): row
            for row in entries
        }

        periods = calculate_slm_schedule(
            total_amount=Decimal(str(schedule.total_amount)),
            coverage_start=schedule.coverage_start,
            coverage_end=schedule.coverage_end,
        )

        output: list[dict[str, Any]] = []
        for period in periods:
            actual = actual_by_key.get((period.period_start, period.period_end))
            output.append(
                {
                    "period_start": period.period_start,
                    "period_end": period.period_end,
                    "amount": Decimal(str(actual.amortisation_amount)) if actual else period.amount,
                    "is_last_period": bool(actual.is_last_period) if actual else period.is_last_period,
                    "is_actual": actual is not None,
                    "status": "past" if actual is not None else "future",
                }
            )

        return output


__all__ = ["PrepaidService"]
