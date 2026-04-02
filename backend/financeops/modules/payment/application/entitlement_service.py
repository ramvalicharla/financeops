from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.payment import (
    BillingEntitlement,
    BillingUsageAggregate,
    BillingUsageEvent,
    TenantEntitlement,
    TenantSubscription,
)
from financeops.services.audit_writer import AuditEvent, AuditWriter


@dataclass(frozen=True)
class EntitlementDecision:
    allowed: bool
    feature_name: str
    access_type: str
    effective_limit: int | None
    used: int
    remaining: int | None
    reason: str


class EntitlementService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_latest_tenant_entitlement(
        self,
        *,
        tenant_id: uuid.UUID,
        feature_name: str,
    ) -> TenantEntitlement | None:
        rows = list(
            (
                await self._session.execute(
                    select(TenantEntitlement)
                    .where(
                        TenantEntitlement.tenant_id == tenant_id,
                        TenantEntitlement.feature_name == feature_name,
                        TenantEntitlement.is_active.is_(True),
                    )
                    .order_by(TenantEntitlement.created_at.desc(), TenantEntitlement.id.desc())
                )
            ).scalars()
        )
        if not rows:
            return None

        # Tenant override always wins over plan-derived value.
        for row in rows:
            if row.source == "override":
                return row
        return rows[0]

    async def list_latest_tenant_entitlements(
        self,
        *,
        tenant_id: uuid.UUID,
    ) -> list[TenantEntitlement]:
        rows = list(
            (
                await self._session.execute(
                    select(TenantEntitlement)
                    .where(
                        TenantEntitlement.tenant_id == tenant_id,
                        TenantEntitlement.is_active.is_(True),
                    )
                    .order_by(TenantEntitlement.created_at.desc(), TenantEntitlement.id.desc())
                )
            ).scalars()
        )
        latest: dict[str, list[TenantEntitlement]] = {}
        for row in rows:
            latest.setdefault(row.feature_name, []).append(row)

        effective: list[TenantEntitlement] = []
        for _, feature_rows in latest.items():
            override = next((row for row in feature_rows if row.source == "override"), None)
            effective.append(override or feature_rows[0])
        return effective

    async def create_tenant_override_entitlement(
        self,
        *,
        tenant_id: uuid.UUID,
        feature_name: str,
        access_type: str,
        effective_limit: int | None,
        metadata: dict[str, Any] | None = None,
        actor_user_id: uuid.UUID | None = None,
        source_reference_id: uuid.UUID | None = None,
    ) -> TenantEntitlement:
        if access_type not in {"boolean", "limit", "quota"}:
            raise ValueError("access_type must be one of boolean|limit|quota")
        normalized_limit = effective_limit
        if access_type == "boolean" and normalized_limit is None:
            normalized_limit = 1
        if normalized_limit is not None and normalized_limit < 0:
            raise ValueError("effective_limit must be >= 0")
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=TenantEntitlement,
            tenant_id=tenant_id,
            record_data={
                "feature_name": feature_name,
                "access_type": access_type,
                "effective_limit": str(normalized_limit) if normalized_limit is not None else "",
                "source": "override",
            },
            values={
                "feature_name": feature_name,
                "access_type": access_type,
                "effective_limit": normalized_limit,
                "source": "override",
                "source_reference_id": source_reference_id,
                "metadata_json": metadata or {},
                "is_active": True,
            },
            audit=AuditEvent(
                tenant_id=tenant_id,
                user_id=actor_user_id,
                action="billing.entitlement.override.created",
                resource_type="billing_tenant_entitlement",
                new_value={"feature_name": feature_name, "access_type": access_type},
            ),
        )

    async def refresh_tenant_entitlements(
        self,
        *,
        tenant_id: uuid.UUID,
        actor_user_id: uuid.UUID | None = None,
    ) -> list[TenantEntitlement]:
        subscription = (
            await self._session.execute(
                select(TenantSubscription)
                .where(TenantSubscription.tenant_id == tenant_id)
                .order_by(TenantSubscription.created_at.desc(), TenantSubscription.id.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if subscription is None:
            return []

        ent_rows = list(
            (
                await self._session.execute(
                    select(BillingEntitlement)
                    .where(
                        BillingEntitlement.tenant_id == tenant_id,
                        BillingEntitlement.plan_id == subscription.plan_id,
                        BillingEntitlement.is_active.is_(True),
                    )
                    .order_by(BillingEntitlement.created_at.desc(), BillingEntitlement.id.desc())
                )
            ).scalars()
        )

        latest_plan_entitlements: dict[str, BillingEntitlement] = {}
        for row in ent_rows:
            if row.feature_name not in latest_plan_entitlements:
                latest_plan_entitlements[row.feature_name] = row

        inserted: list[TenantEntitlement] = []
        for feature_name, row in latest_plan_entitlements.items():
            effective_limit = row.limit_value
            if row.access_type == "boolean" and effective_limit is None:
                effective_limit = 1
            inserted_row = await AuditWriter.insert_financial_record(
                self._session,
                model_class=TenantEntitlement,
                tenant_id=tenant_id,
                record_data={
                    "feature_name": feature_name,
                    "access_type": row.access_type,
                    "effective_limit": str(effective_limit) if effective_limit is not None else "",
                    "source": "plan",
                    "source_reference_id": str(row.id),
                },
                values={
                    "feature_name": feature_name,
                    "access_type": row.access_type,
                    "effective_limit": effective_limit,
                    "source": "plan",
                    "source_reference_id": row.id,
                    "metadata_json": dict(row.metadata_json or {}),
                    "is_active": True,
                },
                audit=AuditEvent(
                    tenant_id=tenant_id,
                    user_id=actor_user_id,
                    action="billing.entitlement.refresh",
                    resource_type="billing_tenant_entitlement",
                    new_value={"feature_name": feature_name, "source": "plan"},
                ),
            )
            inserted.append(inserted_row)
        return inserted

    async def usage_in_period(
        self,
        *,
        tenant_id: uuid.UUID,
        feature_name: str,
        period_start: date,
        period_end: date,
    ) -> int:
        result = await self._session.execute(
            select(func.coalesce(func.sum(BillingUsageEvent.usage_quantity), 0)).where(
                BillingUsageEvent.tenant_id == tenant_id,
                BillingUsageEvent.feature_name == feature_name,
                BillingUsageEvent.event_time >= datetime.combine(period_start, datetime.min.time(), tzinfo=UTC),
                BillingUsageEvent.event_time < datetime.combine(period_end, datetime.min.time(), tzinfo=UTC),
            )
        )
        return int(result.scalar_one() or 0)

    async def check_entitlement(
        self,
        *,
        tenant_id: uuid.UUID,
        feature_name: str,
        quantity: int = 1,
    ) -> EntitlementDecision:
        entitlement = await self.get_latest_tenant_entitlement(
            tenant_id=tenant_id,
            feature_name=feature_name,
        )
        if entitlement is None:
            refreshed = await self.refresh_tenant_entitlements(tenant_id=tenant_id)
            entitlement = next((row for row in refreshed if row.feature_name == feature_name), None)

        if entitlement is None:
            return EntitlementDecision(
                allowed=False,
                feature_name=feature_name,
                access_type="boolean",
                effective_limit=None,
                used=0,
                remaining=None,
                reason="entitlement_not_configured",
            )

        now = datetime.now(UTC)
        period_start = date(year=now.year, month=now.month, day=1)
        if now.month == 12:
            period_end = date(year=now.year + 1, month=1, day=1)
        else:
            period_end = date(year=now.year, month=now.month + 1, day=1)

        used = await self.usage_in_period(
            tenant_id=tenant_id,
            feature_name=feature_name,
            period_start=period_start,
            period_end=period_end,
        )

        if entitlement.access_type == "boolean":
            allowed = bool((entitlement.effective_limit or 0) > 0)
            return EntitlementDecision(
                allowed=allowed,
                feature_name=feature_name,
                access_type=entitlement.access_type,
                effective_limit=entitlement.effective_limit,
                used=used,
                remaining=(entitlement.effective_limit or 0) - used,
                reason="enabled" if allowed else "disabled",
            )

        if entitlement.effective_limit is None:
            return EntitlementDecision(
                allowed=True,
                feature_name=feature_name,
                access_type=entitlement.access_type,
                effective_limit=None,
                used=used,
                remaining=None,
                reason="unbounded",
            )

        projected = used + max(quantity, 0)
        allowed = projected <= entitlement.effective_limit
        remaining = entitlement.effective_limit - used
        return EntitlementDecision(
            allowed=allowed,
            feature_name=feature_name,
            access_type=entitlement.access_type,
            effective_limit=entitlement.effective_limit,
            used=used,
            remaining=remaining,
            reason="within_limit" if allowed else "limit_exceeded",
        )

    async def record_usage_event(
        self,
        *,
        tenant_id: uuid.UUID,
        feature_name: str,
        usage_quantity: int,
        reference_type: str | None = None,
        reference_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        actor_user_id: uuid.UUID | None = None,
    ) -> BillingUsageEvent:
        now = datetime.now(UTC)
        period_start = date(year=now.year, month=now.month, day=1)
        if now.month == 12:
            period_end = date(year=now.year + 1, month=1, day=1)
        else:
            period_end = date(year=now.year, month=now.month + 1, day=1)

        event = await AuditWriter.insert_financial_record(
            self._session,
            model_class=BillingUsageEvent,
            tenant_id=tenant_id,
            record_data={
                "feature_name": feature_name,
                "usage_quantity": usage_quantity,
                "reference_type": reference_type or "",
                "reference_id": reference_id or "",
            },
            values={
                "feature_name": feature_name,
                "usage_quantity": usage_quantity,
                "event_time": now,
                "period_start": period_start,
                "period_end": period_end,
                "reference_type": reference_type,
                "reference_id": reference_id,
                "metadata_json": metadata or {},
            },
            audit=AuditEvent(
                tenant_id=tenant_id,
                user_id=actor_user_id,
                action="billing.usage.recorded",
                resource_type="billing_usage_event",
                new_value={"feature_name": feature_name, "usage_quantity": usage_quantity},
            ),
        )

        total_usage = await self.usage_in_period(
            tenant_id=tenant_id,
            feature_name=feature_name,
            period_start=period_start,
            period_end=period_end,
        )

        await AuditWriter.insert_financial_record(
            self._session,
            model_class=BillingUsageAggregate,
            tenant_id=tenant_id,
            record_data={
                "feature_name": feature_name,
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "total_usage": total_usage,
            },
            values={
                "feature_name": feature_name,
                "period_start": period_start,
                "period_end": period_end,
                "total_usage": total_usage,
                "last_event_id": event.id,
                "metadata_json": {},
            },
            audit=AuditEvent(
                tenant_id=tenant_id,
                user_id=actor_user_id,
                action="billing.usage.aggregated",
                resource_type="billing_usage_aggregate",
                new_value={"feature_name": feature_name, "total_usage": total_usage},
            ),
        )

        return event

    async def list_latest_usage_aggregates(
        self,
        *,
        tenant_id: uuid.UUID,
    ) -> list[BillingUsageAggregate]:
        rows = list(
            (
                await self._session.execute(
                    select(BillingUsageAggregate)
                    .where(BillingUsageAggregate.tenant_id == tenant_id)
                    .order_by(BillingUsageAggregate.created_at.desc(), BillingUsageAggregate.id.desc())
                )
            ).scalars()
        )
        latest: dict[tuple[str, date, date], BillingUsageAggregate] = {}
        for row in rows:
            key = (row.feature_name, row.period_start, row.period_end)
            if key not in latest:
                latest[key] = row
        return list(latest.values())

    async def calculate_overage_charge(
        self,
        *,
        tenant_id: uuid.UUID,
        feature_name: str,
        unit_price: Decimal,
        period_start: date,
        period_end: date,
        included_limit: int,
    ) -> Decimal:
        used = await self.usage_in_period(
            tenant_id=tenant_id,
            feature_name=feature_name,
            period_start=period_start,
            period_end=period_end,
        )
        overage = max(used - included_limit, 0)
        return unit_price * Decimal(overage)
