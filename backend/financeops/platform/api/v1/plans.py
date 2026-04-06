from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import (
    get_async_session,
    require_platform_admin,
    require_platform_owner,
)
from financeops.db.models.payment import BillingEntitlement, BillingPlan
from financeops.db.models.users import IamUser
from financeops.modules.payment.application.entitlement_service import EntitlementService
from financeops.services.audit_writer import AuditEvent, AuditWriter

router = APIRouter()


class PlanEntitlementInput(BaseModel):
    feature_name: str = Field(min_length=1, max_length=128)
    access_type: str = Field(pattern="^(boolean|limit|quota)$")
    limit_value: int | None = Field(default=None, ge=0)
    metadata: dict = Field(default_factory=dict)


class PlanCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    plan_tier: str = Field(pattern="^(starter|professional|enterprise)$")
    pricing_type: str = Field(pattern="^(flat|tiered|usage|hybrid)$")
    price: Decimal = Field(ge=Decimal("0"))
    billing_cycle: str = Field(pattern="^(monthly|annual)$")
    currency: str = Field(min_length=3, max_length=3)
    included_credits: int = Field(default=0, ge=0)
    max_entities: int = Field(default=1, ge=1)
    max_connectors: int = Field(default=1, ge=0)
    max_users: int = Field(default=1, ge=1)
    modules_enabled: dict = Field(default_factory=dict)
    trial_days: int = Field(default=0, ge=0)
    annual_discount_pct: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    is_active: bool = True
    entitlements: list[PlanEntitlementInput] = Field(default_factory=list)


class PlanUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    pricing_type: str | None = Field(default=None, pattern="^(flat|tiered|usage|hybrid)$")
    price: Decimal | None = Field(default=None, ge=Decimal("0"))
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    included_credits: int | None = Field(default=None, ge=0)
    max_entities: int | None = Field(default=None, ge=1)
    max_connectors: int | None = Field(default=None, ge=0)
    max_users: int | None = Field(default=None, ge=1)
    modules_enabled: dict | None = None
    trial_days: int | None = Field(default=None, ge=0)
    annual_discount_pct: Decimal | None = Field(default=None, ge=Decimal("0"))
    is_active: bool | None = None
    valid_until: datetime | None = None
    entitlements: list[PlanEntitlementInput] | None = None


class TenantEntitlementOverrideRequest(BaseModel):
    tenant_id: uuid.UUID
    feature_name: str = Field(min_length=1, max_length=128)
    access_type: str = Field(pattern="^(boolean|limit|quota)$")
    effective_limit: int | None = Field(default=None, ge=0)
    metadata: dict = Field(default_factory=dict)


async def _create_entitlements(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    plan_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    entitlements: list[PlanEntitlementInput],
) -> list[BillingEntitlement]:
    rows: list[BillingEntitlement] = []
    for item in entitlements:
        row = await AuditWriter.insert_financial_record(
            session,
            model_class=BillingEntitlement,
            tenant_id=tenant_id,
            record_data={
                "plan_id": str(plan_id),
                "feature_name": item.feature_name,
                "access_type": item.access_type,
                "limit_value": str(item.limit_value or ""),
            },
            values={
                "plan_id": plan_id,
                "feature_name": item.feature_name,
                "access_type": item.access_type,
                "limit_value": item.limit_value,
                "metadata_json": dict(item.metadata or {}),
                "is_active": True,
            },
            audit=AuditEvent(
                tenant_id=tenant_id,
                user_id=actor_user_id,
                action="billing.plan.entitlement.created",
                resource_type="billing_entitlement",
                new_value={
                    "feature_name": item.feature_name,
                    "access_type": item.access_type,
                },
            ),
        )
        rows.append(row)
    return rows


@router.get("")
async def list_plans(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_platform_admin),
) -> dict:
    rows = list(
        (
            await session.execute(
                select(BillingPlan)
                .where(BillingPlan.tenant_id == user.tenant_id)
                .order_by(BillingPlan.created_at.desc(), BillingPlan.id.desc())
            )
        ).scalars()
    )
    return {
        "items": [
            {
                "id": str(row.id),
                "name": row.name,
                "plan_tier": row.plan_tier,
                "pricing_type": row.pricing_type,
                "price": str(row.price) if row.price is not None else None,
                "billing_cycle": row.billing_cycle,
                "currency": row.currency,
                "included_credits": row.included_credits,
                "max_entities": row.max_entities,
                "max_connectors": row.max_connectors,
                "max_users": row.max_users,
                "trial_days": row.trial_days,
                "is_active": row.is_active,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]
    }


@router.post("")
async def create_plan(
    body: PlanCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_platform_owner),
) -> dict:
    row = await AuditWriter.insert_financial_record(
        session,
        model_class=BillingPlan,
        tenant_id=user.tenant_id,
        record_data={
            "name": body.name,
            "plan_tier": body.plan_tier,
            "pricing_type": body.pricing_type,
            "price": str(body.price),
            "billing_cycle": body.billing_cycle,
            "currency": body.currency.upper(),
        },
        values={
            "name": body.name,
            "plan_tier": body.plan_tier,
            "pricing_type": body.pricing_type,
            "price": body.price,
            "currency": body.currency.upper(),
            "billing_cycle": body.billing_cycle,
            "base_price_inr": body.price if body.currency.upper() == "INR" else Decimal("0"),
            "base_price_usd": body.price if body.currency.upper() == "USD" else Decimal("0"),
            "included_credits": body.included_credits,
            "max_entities": body.max_entities,
            "max_connectors": body.max_connectors,
            "max_users": body.max_users,
            "modules_enabled": dict(body.modules_enabled),
            "trial_days": body.trial_days,
            "annual_discount_pct": body.annual_discount_pct,
            "is_active": body.is_active,
            "valid_from": datetime.now(UTC).date(),
            "valid_until": None,
        },
        audit=AuditEvent(
            tenant_id=user.tenant_id,
            user_id=user.id,
            action="billing.plan.created",
            resource_type="billing_plan",
            new_value={"name": body.name, "plan_tier": body.plan_tier},
        ),
    )

    entitlement_rows = await _create_entitlements(
        session,
        tenant_id=user.tenant_id,
        plan_id=row.id,
        actor_user_id=user.id,
        entitlements=body.entitlements,
    )

    await session.commit()
    return {
        "id": str(row.id),
        "name": row.name,
        "entitlements_created": len(entitlement_rows),
    }


@router.put("/{plan_id}")
async def update_plan(
    plan_id: uuid.UUID,
    body: PlanUpdateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_platform_owner),
) -> dict:
    source = (
        await session.execute(
            select(BillingPlan).where(BillingPlan.tenant_id == user.tenant_id, BillingPlan.id == plan_id)
        )
    ).scalar_one_or_none()
    if source is None:
        raise HTTPException(status_code=404, detail="plan not found")

    row = await AuditWriter.insert_financial_record(
        session,
        model_class=BillingPlan,
        tenant_id=user.tenant_id,
        record_data={
            "name": body.name or source.name or source.plan_tier,
            "plan_tier": source.plan_tier,
            "pricing_type": body.pricing_type or source.pricing_type or "flat",
            "price": str(body.price if body.price is not None else source.price or source.base_price_usd),
            "billing_cycle": source.billing_cycle,
            "currency": (body.currency or source.currency or "USD").upper(),
            "supersedes_plan_id": str(source.id),
        },
        values={
            "name": body.name or source.name,
            "plan_tier": source.plan_tier,
            "pricing_type": body.pricing_type or source.pricing_type,
            "price": body.price if body.price is not None else source.price,
            "currency": (body.currency or source.currency),
            "billing_cycle": source.billing_cycle,
            "base_price_inr": source.base_price_inr,
            "base_price_usd": source.base_price_usd,
            "included_credits": body.included_credits if body.included_credits is not None else source.included_credits,
            "max_entities": body.max_entities if body.max_entities is not None else source.max_entities,
            "max_connectors": body.max_connectors if body.max_connectors is not None else source.max_connectors,
            "max_users": body.max_users if body.max_users is not None else source.max_users,
            "modules_enabled": dict(body.modules_enabled) if body.modules_enabled is not None else dict(source.modules_enabled or {}),
            "trial_days": body.trial_days if body.trial_days is not None else source.trial_days,
            "annual_discount_pct": body.annual_discount_pct if body.annual_discount_pct is not None else source.annual_discount_pct,
            "is_active": body.is_active if body.is_active is not None else source.is_active,
            "valid_from": datetime.now(UTC).date(),
            "valid_until": body.valid_until.date() if body.valid_until is not None else source.valid_until,
        },
        audit=AuditEvent(
            tenant_id=user.tenant_id,
            user_id=user.id,
            action="billing.plan.updated",
            resource_type="billing_plan",
            resource_id=str(source.id),
            new_value={"new_plan_id": str(row.id)},
        ),
    )

    entitlements_created = 0
    if body.entitlements is not None:
        created_rows = await _create_entitlements(
            session,
            tenant_id=user.tenant_id,
            plan_id=row.id,
            actor_user_id=user.id,
            entitlements=body.entitlements,
        )
        entitlements_created = len(created_rows)

    await session.commit()
    return {
        "id": str(row.id),
        "supersedes_plan_id": str(source.id),
        "entitlements_created": entitlements_created,
    }


@router.delete("/{plan_id}")
async def deactivate_plan(
    plan_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_platform_owner),
) -> dict:
    source = (
        await session.execute(
            select(BillingPlan).where(BillingPlan.tenant_id == user.tenant_id, BillingPlan.id == plan_id)
        )
    ).scalar_one_or_none()
    if source is None:
        raise HTTPException(status_code=404, detail="plan not found")

    row = await AuditWriter.insert_financial_record(
        session,
        model_class=BillingPlan,
        tenant_id=user.tenant_id,
        record_data={
            "name": source.name or source.plan_tier,
            "plan_tier": source.plan_tier,
            "pricing_type": source.pricing_type or "flat",
            "price": str(source.price or source.base_price_usd),
            "billing_cycle": source.billing_cycle,
            "currency": source.currency or "USD",
            "is_active": "false",
            "supersedes_plan_id": str(source.id),
        },
        values={
            "name": source.name,
            "plan_tier": source.plan_tier,
            "pricing_type": source.pricing_type,
            "price": source.price,
            "currency": source.currency,
            "billing_cycle": source.billing_cycle,
            "base_price_inr": source.base_price_inr,
            "base_price_usd": source.base_price_usd,
            "included_credits": source.included_credits,
            "max_entities": source.max_entities,
            "max_connectors": source.max_connectors,
            "max_users": source.max_users,
            "modules_enabled": dict(source.modules_enabled or {}),
            "trial_days": source.trial_days,
            "annual_discount_pct": source.annual_discount_pct,
            "is_active": False,
            "valid_from": datetime.now(UTC).date(),
            "valid_until": datetime.now(UTC).date(),
        },
        audit=AuditEvent(
            tenant_id=user.tenant_id,
            user_id=user.id,
            action="billing.plan.deactivated",
            resource_type="billing_plan",
            resource_id=str(source.id),
            new_value={"new_plan_id": str(row.id), "is_active": False},
        ),
    )

    await session.commit()
    return {
        "deleted": True,
        "replacement_id": str(row.id),
    }


@router.get("/tenant-entitlements/{tenant_id}")
async def list_tenant_entitlements(
    tenant_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_platform_admin),
) -> dict:
    service = EntitlementService(session)
    rows = await service.list_latest_tenant_entitlements(tenant_id=tenant_id)
    return {
        "items": [
            {
                "id": str(row.id),
                "feature_name": row.feature_name,
                "access_type": row.access_type,
                "effective_limit": row.effective_limit,
                "source": row.source,
                "source_reference_id": str(row.source_reference_id)
                if row.source_reference_id
                else None,
                "metadata": row.metadata_json,
            }
            for row in rows
        ]
    }


@router.post("/tenant-entitlements/override")
async def override_tenant_entitlement(
    body: TenantEntitlementOverrideRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_platform_owner),
) -> dict:
    service = EntitlementService(session)
    row = await service.create_tenant_override_entitlement(
        tenant_id=body.tenant_id,
        feature_name=body.feature_name,
        access_type=body.access_type,
        effective_limit=body.effective_limit,
        metadata=dict(body.metadata or {}),
        actor_user_id=user.id,
        source_reference_id=None,
    )
    await session.commit()
    return {
        "id": str(row.id),
        "tenant_id": str(body.tenant_id),
        "feature_name": row.feature_name,
        "source": row.source,
    }
