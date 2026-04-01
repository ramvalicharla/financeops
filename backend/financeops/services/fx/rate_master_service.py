from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import case, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import NotFoundError, ValidationError
from financeops.db.models.fx_ias21 import FxRate, FxRateType
from financeops.services.fx.normalization import normalize_currency_code, normalize_rate_decimal


def _normalize_rate_type(value: str) -> str:
    normalized = str(value or "").strip().upper()
    if normalized not in FxRateType.ALL:
        allowed = ", ".join(sorted(FxRateType.ALL))
        raise ValidationError(f"Invalid rate_type '{value}'. Allowed values: {allowed}.")
    return normalized


def _normalize_pair(from_currency: str, to_currency: str) -> tuple[str, str]:
    source = normalize_currency_code(from_currency)
    target = normalize_currency_code(to_currency)
    if source == target:
        raise ValidationError("from_currency and to_currency must differ.")
    return source, target


async def create_fx_rate(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID | None,
    from_currency: str,
    to_currency: str,
    rate: Decimal,
    rate_type: str,
    effective_date: date,
    source: str,
    created_by: uuid.UUID | None,
) -> FxRate:
    source_currency, target_currency = _normalize_pair(from_currency, to_currency)
    normalized_rate = normalize_rate_decimal(rate)
    normalized_rate_type = _normalize_rate_type(rate_type)
    payload_source = (source or "manual").strip().lower() or "manual"

    row = FxRate(
        tenant_id=tenant_id,
        from_currency=source_currency,
        to_currency=target_currency,
        rate=normalized_rate,
        rate_type=normalized_rate_type,
        effective_date=effective_date,
        source=payload_source,
        created_by=created_by,
    )
    db.add(row)
    await db.flush()
    return row


async def list_fx_rates(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    from_currency: str | None = None,
    to_currency: str | None = None,
    rate_type: str | None = None,
    effective_date: date | None = None,
    limit: int = 200,
) -> list[FxRate]:
    stmt = (
        select(FxRate)
        .where(or_(FxRate.tenant_id == tenant_id, FxRate.tenant_id.is_(None)))
        .order_by(
            case((FxRate.tenant_id == tenant_id, 0), else_=1),
            FxRate.effective_date.desc(),
            FxRate.created_at.desc(),
        )
        .limit(limit)
    )
    if from_currency and to_currency:
        source_currency, target_currency = _normalize_pair(from_currency, to_currency)
        stmt = stmt.where(
            FxRate.from_currency == source_currency,
            FxRate.to_currency == target_currency,
        )
    elif from_currency or to_currency:
        raise ValidationError("Provide both from_currency and to_currency together.")
    if rate_type:
        stmt = stmt.where(FxRate.rate_type == _normalize_rate_type(rate_type))
    if effective_date:
        stmt = stmt.where(FxRate.effective_date == effective_date)

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_latest_fx_rate(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    from_currency: str,
    to_currency: str,
    rate_type: str,
    as_of_date: date,
) -> FxRate | None:
    source_currency, target_currency = _normalize_pair(from_currency, to_currency)
    normalized_rate_type = _normalize_rate_type(rate_type)
    stmt = (
        select(FxRate)
        .where(
            or_(FxRate.tenant_id == tenant_id, FxRate.tenant_id.is_(None)),
            FxRate.from_currency == source_currency,
            FxRate.to_currency == target_currency,
            FxRate.rate_type == normalized_rate_type,
            FxRate.effective_date <= as_of_date,
        )
        .order_by(
            case((FxRate.tenant_id == tenant_id, 0), else_=1),
            FxRate.effective_date.desc(),
            FxRate.created_at.desc(),
        )
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_required_latest_fx_rate(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    from_currency: str,
    to_currency: str,
    rate_type: str,
    as_of_date: date,
) -> FxRate:
    row = await get_latest_fx_rate(
        db,
        tenant_id=tenant_id,
        from_currency=from_currency,
        to_currency=to_currency,
        rate_type=rate_type,
        as_of_date=as_of_date,
    )
    if row is None:
        raise NotFoundError(
            f"No {rate_type.upper()} FX rate found for {from_currency.upper()}/{to_currency.upper()} as of {as_of_date}."
        )
    return row

