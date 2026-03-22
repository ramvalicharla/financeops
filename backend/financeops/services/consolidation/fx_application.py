from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import ValidationError
from financeops.services.consolidation.entity_loader import LoadedEntitySnapshot
from financeops.services.consolidation.fx_impact_calculator import (
    compute_fx_delta_component,
    quantize_persisted_amount,
    quantize_rate,
)
from financeops.services.fx import list_manual_monthly_rates, resolve_selected_rate
from financeops.services.fx.normalization import normalize_currency_code


@dataclass(frozen=True)
class AppliedFxLine:
    entity_id: UUID
    snapshot_line_id: UUID
    account_code: str
    local_currency: str
    local_amount: Decimal
    fx_rate_used: Decimal
    expected_rate: Decimal
    parent_amount: Decimal
    fx_delta_component: Decimal
    ic_reference: str | None
    ic_counterparty_entity: UUID | None
    transaction_date: date | None


def _month_end_date(period_year: int, period_month: int) -> date:
    _, last_day = calendar.monthrange(period_year, period_month)
    return date(period_year, period_month, last_day)


async def _get_locked_month_end_rate(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    period_year: int,
    period_month: int,
    base_currency: str,
    quote_currency: str,
) -> Decimal | None:
    rows = await list_manual_monthly_rates(
        session,
        tenant_id=tenant_id,
        period_year=period_year,
        period_month=period_month,
        base_currency=base_currency,
        quote_currency=quote_currency,
        limit=50,
        offset=0,
    )
    for row in rows:
        if row.is_month_end_locked:
            return quantize_rate(row.rate)
    return None


async def ensure_locked_rates_available(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    period_year: int,
    period_month: int,
    entity_currencies: set[str],
    parent_currency: str,
) -> None:
    parent = normalize_currency_code(parent_currency)
    for raw_currency in sorted(entity_currencies):
        base_currency = normalize_currency_code(raw_currency)
        if base_currency == parent:
            continue
        locked = await _get_locked_month_end_rate(
            session,
            tenant_id=tenant_id,
            period_year=period_year,
            period_month=period_month,
            base_currency=base_currency,
            quote_currency=parent,
        )
        if locked is None:
            raise ValidationError(
                "Missing locked month-end selected rate "
                f"for {base_currency}/{parent} in {period_year}-{period_month:02d}"
            )


async def _resolve_expected_rate(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    period_year: int,
    period_month: int,
    base_currency: str,
    parent_currency: str,
    rate_mode: str,
) -> Decimal:
    if base_currency == parent_currency:
        return Decimal("1.000000")
    locked = await _get_locked_month_end_rate(
        session,
        tenant_id=tenant_id,
        period_year=period_year,
        period_month=period_month,
        base_currency=base_currency,
        quote_currency=parent_currency,
    )
    if rate_mode == "month_end_locked":
        if locked is None:
            raise ValidationError(
                "Missing locked month-end selected rate "
                f"for {base_currency}/{parent_currency} in {period_year}-{period_month:02d}"
            )
        return locked
    if locked is not None:
        return locked
    month_end = _month_end_date(period_year, period_month)
    decision = await resolve_selected_rate(
        session,
        tenant_id=tenant_id,
        base_currency=base_currency,
        quote_currency=parent_currency,
        as_of_date=month_end,
        redis_client=None,
    )
    return quantize_rate(decision.selected_rate)


async def resolve_expected_rate_for_entity(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    period_year: int,
    period_month: int,
    base_currency: str,
    parent_currency: str,
    rate_mode: str,
) -> Decimal:
    return await _resolve_expected_rate(
        session,
        tenant_id=tenant_id,
        period_year=period_year,
        period_month=period_month,
        base_currency=normalize_currency_code(base_currency),
        parent_currency=normalize_currency_code(parent_currency),
        rate_mode=rate_mode,
    )


async def apply_fx_to_snapshots(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    period_year: int,
    period_month: int,
    parent_currency: str,
    rate_mode: str,
    bundles: list[LoadedEntitySnapshot],
) -> list[AppliedFxLine]:
    parent = normalize_currency_code(parent_currency)
    if rate_mode not in {"month_end_locked", "daily"}:
        raise ValidationError("Unsupported consolidation rate_mode")

    month_end = _month_end_date(period_year, period_month)
    rate_cache: dict[tuple[str, str, date], Decimal] = {}
    expected_cache: dict[tuple[str, str], Decimal] = {}
    applied_rows: list[AppliedFxLine] = []

    for bundle in bundles:
        base_currency = normalize_currency_code(bundle.header.entity_currency)
        expected_rate = expected_cache.get((base_currency, parent))
        if expected_rate is None:
            expected_rate = await _resolve_expected_rate(
                session,
                tenant_id=tenant_id,
                period_year=period_year,
                period_month=period_month,
                base_currency=base_currency,
                parent_currency=parent,
                rate_mode=rate_mode,
            )
            expected_cache[(base_currency, parent)] = expected_rate

        for line in bundle.lines:
            line_currency = normalize_currency_code(line.currency)
            fx_rate_used = Decimal("1.000000")
            converted_date = line.transaction_date or month_end
            if line_currency != parent:
                if rate_mode == "month_end_locked":
                    fx_rate_used = expected_rate
                else:
                    cache_key = (line_currency, parent, converted_date)
                    cached = rate_cache.get(cache_key)
                    if cached is None:
                        decision = await resolve_selected_rate(
                            session,
                            tenant_id=tenant_id,
                            base_currency=line_currency,
                            quote_currency=parent,
                            as_of_date=converted_date,
                            redis_client=None,
                        )
                        cached = quantize_rate(decision.selected_rate)
                        rate_cache[cache_key] = cached
                    fx_rate_used = cached

            parent_amount = quantize_persisted_amount(line.local_amount * fx_rate_used)
            delta = compute_fx_delta_component(
                parent_amount=parent_amount,
                local_amount=line.local_amount,
                expected_rate=expected_rate if line_currency != parent else Decimal("1.000000"),
            )
            applied_rows.append(
                AppliedFxLine(
                    entity_id=bundle.header.entity_id,
                    snapshot_line_id=line.snapshot_line_id,
                    account_code=line.account_code,
                    local_currency=line_currency,
                    local_amount=quantize_persisted_amount(line.local_amount),
                    fx_rate_used=quantize_rate(fx_rate_used),
                    expected_rate=expected_rate if line_currency != parent else Decimal("1.000000"),
                    parent_amount=parent_amount,
                    fx_delta_component=delta,
                    ic_reference=line.ic_reference,
                    ic_counterparty_entity=line.counterparty_entity,
                    transaction_date=line.transaction_date,
                )
            )

    applied_rows.sort(
        key=lambda row: (str(row.entity_id), row.account_code, str(row.snapshot_line_id))
    )
    return applied_rows

