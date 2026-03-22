from __future__ import annotations

import calendar
import logging
import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.config import settings
from financeops.core.exceptions import NotFoundError, ValidationError
from financeops.db.models.fx_rates import (
    FxManualMonthlyRate,
    FxRateFetchRun,
    FxRateQuote,
    FxVarianceResult,
)
from financeops.services.audit_writer import AuditEvent, AuditWriter
from financeops.services.fx.cache import (
    RedisLike,
    cache_selected_rate,
    get_cached_selected_rate,
    invalidate_manual_monthly_cache,
)
from financeops.services.fx.conversion import apply_rate_to_lines, convert_amount
from financeops.services.fx.normalization import (
    normalize_currency_code,
    normalize_currency_pair,
    normalize_rate_decimal,
)
from financeops.services.fx.provider_clients import (
    ProviderFetchResult,
    ProviderQuote,
    fetch_all_provider_quotes,
)
from financeops.services.fx.selector import (
    SelectedRateDecision,
    build_side_by_side,
    select_rate_with_precedence,
)
from financeops.services.fx.variance import compute_fx_variance

log = logging.getLogger(__name__)

_PROVIDER_NAMES: tuple[str, ...] = (
    "ecb",
    "frankfurter",
    "open_exchange_rates",
    "exchange_rate_api",
)


async def _get_latest_manual_monthly_rate(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    period_year: int,
    period_month: int,
    base_currency: str,
    quote_currency: str,
) -> FxManualMonthlyRate | None:
    result = await session.execute(
        select(FxManualMonthlyRate)
        .where(
            FxManualMonthlyRate.tenant_id == tenant_id,
            FxManualMonthlyRate.period_year == period_year,
            FxManualMonthlyRate.period_month == period_month,
            FxManualMonthlyRate.base_currency == base_currency,
            FxManualMonthlyRate.quote_currency == quote_currency,
        )
        .order_by(desc(FxManualMonthlyRate.created_at))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _get_previous_selected_from_runs(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    base_currency: str,
    quote_currency: str,
    as_of_date: date,
) -> tuple[Decimal, str] | None:
    result = await session.execute(
        select(FxRateFetchRun)
        .where(
            FxRateFetchRun.tenant_id == tenant_id,
            FxRateFetchRun.base_currency == base_currency,
            FxRateFetchRun.quote_currency == quote_currency,
            FxRateFetchRun.rate_date <= as_of_date,
            FxRateFetchRun.selected_rate.is_not(None),
        )
        .order_by(
            desc(FxRateFetchRun.rate_date),
            desc(FxRateFetchRun.created_at),
        )
        .limit(1)
    )
    run = result.scalar_one_or_none()
    if run is None or run.selected_rate is None:
        return None
    return run.selected_rate, run.selected_source or "previous_valid_selected_rate"


def _provider_errors(provider_results: list[ProviderFetchResult]) -> dict[str, str]:
    errors: dict[str, str] = {}
    for item in provider_results:
        if item.error:
            errors[item.provider_name] = item.error
    return errors


def _build_comparison_payload(
    *,
    fetch_run: FxRateFetchRun,
    provider_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "fetch_run_id": str(fetch_run.id),
        "status": fetch_run.status,
        "base_currency": fetch_run.base_currency,
        "quote_currency": fetch_run.quote_currency,
        "rate_date": fetch_run.rate_date.isoformat(),
        "selected_rate": str(fetch_run.selected_rate) if fetch_run.selected_rate is not None else None,
        "selected_source": fetch_run.selected_source,
        "selection_method": fetch_run.selection_method,
        "fallback_used": fetch_run.fallback_used,
        "providers": provider_rows,
    }


async def _persist_fetch_run(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    requested_by: uuid.UUID | None,
    correlation_id: str | None,
    rate_date: date,
    base_currency: str,
    quote_currency: str,
    status: str,
    provider_count: int,
    success_count: int,
    failure_count: int,
    selected_rate: Decimal | None,
    selected_source: str | None,
    selection_method: str | None,
    fallback_used: bool,
    provider_errors: dict[str, str] | None,
) -> FxRateFetchRun:
    record = await AuditWriter.insert_financial_record(
        session,
        model_class=FxRateFetchRun,
        tenant_id=tenant_id,
        record_data={
            "rate_date": rate_date.isoformat(),
            "base_currency": base_currency,
            "quote_currency": quote_currency,
            "status": status,
            "selected_rate": str(selected_rate) if selected_rate is not None else None,
            "correlation_id": correlation_id,
        },
        values={
            "rate_date": rate_date,
            "base_currency": base_currency,
            "quote_currency": quote_currency,
            "status": status,
            "provider_count": provider_count,
            "success_count": success_count,
            "failure_count": failure_count,
            "selected_rate": selected_rate,
            "selected_source": selected_source,
            "selection_method": selection_method,
            "fallback_used": fallback_used,
            "initiated_by": requested_by,
            "correlation_id": correlation_id,
            "provider_errors": provider_errors,
        },
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=requested_by,
            action="fx.fetch.run.created",
            resource_type="fx_rate_fetch_run",
            new_value={
                "base_currency": base_currency,
                "quote_currency": quote_currency,
                "rate_date": rate_date.isoformat(),
                "status": status,
                "correlation_id": correlation_id,
            },
        ),
    )
    return record


async def _persist_provider_quote(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    requested_by: uuid.UUID | None,
    correlation_id: str | None,
    fetch_run_id: uuid.UUID,
    quote: ProviderQuote,
) -> FxRateQuote:
    record = await AuditWriter.insert_financial_record(
        session,
        model_class=FxRateQuote,
        tenant_id=tenant_id,
        record_data={
            "fetch_run_id": str(fetch_run_id),
            "provider_name": quote.provider_name,
            "base_currency": quote.base_currency,
            "quote_currency": quote.quote_currency,
            "rate_date": quote.rate_date.isoformat(),
            "rate": str(quote.rate),
        },
        values={
            "fetch_run_id": fetch_run_id,
            "provider_name": quote.provider_name,
            "rate_date": quote.rate_date,
            "base_currency": quote.base_currency,
            "quote_currency": quote.quote_currency,
            "rate": quote.rate,
            "source_timestamp": quote.source_timestamp,
            "correlation_id": correlation_id,
            "raw_payload": quote.raw_payload,
        },
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=requested_by,
            action="fx.rate.quote.ingested",
            resource_type="fx_rate_quote",
            new_value={
                "provider_name": quote.provider_name,
                "base_currency": quote.base_currency,
                "quote_currency": quote.quote_currency,
                "rate_date": quote.rate_date.isoformat(),
                "correlation_id": correlation_id,
            },
        ),
    )
    return record


async def fetch_live_rates(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    requested_by: uuid.UUID | None,
    correlation_id: str | None,
    base_currency: str,
    quote_currency: str,
    rate_date: date,
    redis_client: RedisLike | None = None,
) -> dict[str, Any]:
    base, quote = normalize_currency_pair(base_currency, quote_currency)

    provider_results = await fetch_all_provider_quotes(
        base_currency=base,
        quote_currency=quote,
        rate_date=rate_date,
        open_exchange_rates_api_key=settings.OPEN_EXCHANGE_RATES_API_KEY,
        exchange_rate_api_key=settings.EXCHANGE_RATE_API_KEY,
    )
    successful_quotes = [item.quote for item in provider_results if item.quote is not None]
    manual_for_month = await _get_latest_manual_monthly_rate(
        session,
        tenant_id=tenant_id,
        period_year=rate_date.year,
        period_month=rate_date.month,
        base_currency=base,
        quote_currency=quote,
    )
    manual_rate = manual_for_month.rate if manual_for_month is not None else None

    fallback_used = False
    decision: SelectedRateDecision | None = None

    if successful_quotes or manual_rate is not None:
        decision = select_rate_with_precedence(
            provider_quotes=successful_quotes,
            provider_results=provider_results,
            manual_monthly_rate=manual_rate,
            previous_valid_rate=None,
        )
    else:
        cached = await get_cached_selected_rate(
            redis_client,
            tenant_id=tenant_id,
            rate_date=rate_date,
            base_currency=base,
            quote_currency=quote,
        )
        if cached is not None:
            fallback_used = True
            decision = SelectedRateDecision(
                selected_rate=normalize_rate_decimal(cached.rate),
                selected_source=cached.selected_source,
                selection_method=cached.selection_method,
                degraded=True,
            )
        else:
            previous = await _get_previous_selected_from_runs(
                session,
                tenant_id=tenant_id,
                base_currency=base,
                quote_currency=quote,
                as_of_date=rate_date,
            )
            if previous is not None:
                fallback_used = True
                previous_rate, previous_source = previous
                decision = SelectedRateDecision(
                    selected_rate=normalize_rate_decimal(previous_rate),
                    selected_source=previous_source,
                    selection_method="fallback_previous_valid_rate",
                    degraded=True,
                )

    status = "failed"
    if decision is not None:
        status = "degraded" if decision.degraded or fallback_used else "success"

    run = await _persist_fetch_run(
        session,
        tenant_id=tenant_id,
        requested_by=requested_by,
        correlation_id=correlation_id,
        rate_date=rate_date,
        base_currency=base,
        quote_currency=quote,
        status=status,
        provider_count=len(provider_results),
        success_count=len(successful_quotes),
        failure_count=len(provider_results) - len(successful_quotes),
        selected_rate=decision.selected_rate if decision else None,
        selected_source=decision.selected_source if decision else None,
        selection_method=decision.selection_method if decision else None,
        fallback_used=fallback_used,
        provider_errors=_provider_errors(provider_results),
    )

    for provider_quote in successful_quotes:
        await _persist_provider_quote(
            session,
            tenant_id=tenant_id,
            requested_by=requested_by,
            correlation_id=correlation_id,
            fetch_run_id=run.id,
            quote=provider_quote,
        )

    if decision is not None:
        await cache_selected_rate(
            redis_client,
            tenant_id=tenant_id,
            rate_date=rate_date,
            base_currency=base,
            quote_currency=quote,
            selected_rate=decision.selected_rate,
            selected_source=decision.selected_source,
            selection_method=decision.selection_method,
        )

    provider_rows = build_side_by_side(provider_results)
    log.info(
        "FX fetch completed: tenant=%s pair=%s/%s status=%s corr=%s",
        str(tenant_id)[:8],
        base,
        quote,
        status,
        correlation_id,
    )
    return _build_comparison_payload(fetch_run=run, provider_rows=provider_rows)


async def get_latest_comparison(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    base_currency: str,
    quote_currency: str,
) -> dict[str, Any] | None:
    base, quote = normalize_currency_pair(base_currency, quote_currency)
    result = await session.execute(
        select(FxRateFetchRun)
        .where(
            FxRateFetchRun.tenant_id == tenant_id,
            FxRateFetchRun.base_currency == base,
            FxRateFetchRun.quote_currency == quote,
        )
        .order_by(desc(FxRateFetchRun.created_at))
        .limit(1)
    )
    run = result.scalar_one_or_none()
    if run is None:
        return None

    quote_result = await session.execute(
        select(FxRateQuote).where(
            FxRateQuote.tenant_id == tenant_id,
            FxRateQuote.fetch_run_id == run.id,
        )
    )
    quotes = list(quote_result.scalars().all())
    quotes_by_provider = {quote_row.provider_name: quote_row for quote_row in quotes}
    provider_rows: list[dict[str, Any]] = []
    for provider_name in _PROVIDER_NAMES:
        quote_row = quotes_by_provider.get(provider_name)
        provider_error = (run.provider_errors or {}).get(provider_name)
        provider_rows.append(
            {
                "provider": provider_name,
                "status": "ok" if quote_row is not None else "error",
                "rate": str(quote_row.rate) if quote_row is not None else None,
                "rate_date": quote_row.rate_date.isoformat() if quote_row is not None else None,
                "error": provider_error,
            }
        )
    return _build_comparison_payload(fetch_run=run, provider_rows=provider_rows)


async def create_manual_monthly_rate(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entered_by: uuid.UUID,
    correlation_id: str | None,
    period_year: int,
    period_month: int,
    base_currency: str,
    quote_currency: str,
    rate: Decimal,
    reason: str,
    supersedes_rate_id: uuid.UUID | None,
    source_type: str = "manual",
    is_month_end_locked: bool = False,
    redis_client: RedisLike | None = None,
) -> FxManualMonthlyRate:
    base, quote = normalize_currency_pair(base_currency, quote_currency)
    normalized_rate = normalize_rate_decimal(rate)
    latest = await _get_latest_manual_monthly_rate(
        session,
        tenant_id=tenant_id,
        period_year=period_year,
        period_month=period_month,
        base_currency=base,
        quote_currency=quote,
    )

    if latest is not None and latest.is_month_end_locked and supersedes_rate_id is None:
        raise ValidationError(
            "Month-end rate is locked; provide supersedes_rate_id for append-only supersession"
        )
    if supersedes_rate_id is not None and latest is not None and supersedes_rate_id != latest.id:
        raise ValidationError("supersedes_rate_id must point to the latest monthly rate")

    record = await AuditWriter.insert_financial_record(
        session,
        model_class=FxManualMonthlyRate,
        tenant_id=tenant_id,
        record_data={
            "period_year": period_year,
            "period_month": period_month,
            "base_currency": base,
            "quote_currency": quote,
            "rate": str(normalized_rate),
            "source_type": source_type,
            "is_month_end_locked": is_month_end_locked,
        },
        values={
            "period_year": period_year,
            "period_month": period_month,
            "base_currency": base,
            "quote_currency": quote,
            "rate": normalized_rate,
            "entered_by": entered_by,
            "reason": reason,
            "supersedes_rate_id": supersedes_rate_id,
            "source_type": source_type,
            "is_month_end_locked": is_month_end_locked,
            "correlation_id": correlation_id,
        },
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=entered_by,
            action="fx.rate.manual.created",
            resource_type="fx_manual_monthly_rate",
            resource_id=None,
            new_value={
                "period_year": period_year,
                "period_month": period_month,
                "base_currency": base,
                "quote_currency": quote,
                "correlation_id": correlation_id,
                "source_type": source_type,
            },
        ),
    )
    await invalidate_manual_monthly_cache(
        redis_client,
        tenant_id=tenant_id,
        period_year=period_year,
        period_month=period_month,
        base_currency=base,
        quote_currency=quote,
    )
    return record


async def list_manual_monthly_rates(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    period_year: int | None = None,
    period_month: int | None = None,
    base_currency: str | None = None,
    quote_currency: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[FxManualMonthlyRate]:
    stmt = select(FxManualMonthlyRate).where(FxManualMonthlyRate.tenant_id == tenant_id)
    if period_year is not None:
        stmt = stmt.where(FxManualMonthlyRate.period_year == period_year)
    if period_month is not None:
        stmt = stmt.where(FxManualMonthlyRate.period_month == period_month)
    if base_currency is not None:
        stmt = stmt.where(FxManualMonthlyRate.base_currency == normalize_currency_code(base_currency))
    if quote_currency is not None:
        stmt = stmt.where(FxManualMonthlyRate.quote_currency == normalize_currency_code(quote_currency))
    stmt = stmt.order_by(desc(FxManualMonthlyRate.created_at)).limit(limit).offset(offset)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def resolve_selected_rate(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    base_currency: str,
    quote_currency: str,
    as_of_date: date,
    redis_client: RedisLike | None = None,
) -> SelectedRateDecision:
    base, quote = normalize_currency_pair(base_currency, quote_currency)
    manual = await _get_latest_manual_monthly_rate(
        session,
        tenant_id=tenant_id,
        period_year=as_of_date.year,
        period_month=as_of_date.month,
        base_currency=base,
        quote_currency=quote,
    )
    manual_rate = manual.rate if manual is not None else None
    if manual_rate is not None:
        return SelectedRateDecision(
            selected_rate=normalize_rate_decimal(manual_rate),
            selected_source="manual_monthly",
            selection_method="manual_monthly_override",
            degraded=False,
        )

    cached = await get_cached_selected_rate(
        redis_client,
        tenant_id=tenant_id,
        rate_date=as_of_date,
        base_currency=base,
        quote_currency=quote,
    )
    previous = await _get_previous_selected_from_runs(
        session,
        tenant_id=tenant_id,
        base_currency=base,
        quote_currency=quote,
        as_of_date=as_of_date,
    )
    previous_rate = previous[0] if previous is not None else None

    provider_quotes_result = await session.execute(
        select(FxRateQuote).where(
            FxRateQuote.tenant_id == tenant_id,
            FxRateQuote.base_currency == base,
            FxRateQuote.quote_currency == quote,
            FxRateQuote.rate_date == as_of_date,
        )
    )
    provider_quote_rows = list(provider_quotes_result.scalars().all())
    provider_quotes = [
        ProviderQuote(
            provider_name=row.provider_name,
            base_currency=row.base_currency,
            quote_currency=row.quote_currency,
            rate_date=row.rate_date,
            rate=row.rate,
            source_timestamp=row.source_timestamp,
            raw_payload=row.raw_payload,
        )
        for row in provider_quote_rows
    ]
    provider_results = [
        ProviderFetchResult(provider_name=quote_item.provider_name, quote=quote_item, error=None)
        for quote_item in provider_quotes
    ]
    if cached is not None and not provider_quotes and previous_rate is None:
        return SelectedRateDecision(
            selected_rate=normalize_rate_decimal(cached.rate),
            selected_source=cached.selected_source,
            selection_method=cached.selection_method,
            degraded=True,
        )
    if not provider_results:
        provider_results = [ProviderFetchResult(provider_name=name, quote=None, error="no_quote") for name in _PROVIDER_NAMES]

    return select_rate_with_precedence(
        provider_quotes=provider_quotes,
        provider_results=provider_results,
        manual_monthly_rate=manual_rate,
        previous_valid_rate=previous_rate,
    )


async def convert_daily_lines(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    lines: list[dict[str, Any]],
    redis_client: RedisLike | None = None,
) -> list[dict[str, Any]]:
    response_lines: list[dict[str, Any]] = []
    for line in lines:
        decision = await resolve_selected_rate(
            session,
            tenant_id=tenant_id,
            base_currency=str(line["base_currency"]),
            quote_currency=str(line["quote_currency"]),
            as_of_date=line["transaction_date"],
            redis_client=redis_client,
        )
        amount = Decimal(str(line["amount"]))
        converted_amount = convert_amount(amount, decision.selected_rate)
        response_lines.append(
            {
                "reference": line.get("reference"),
                "transaction_date": line["transaction_date"].isoformat(),
                "amount": str(amount),
                "base_currency": line["base_currency"],
                "quote_currency": line["quote_currency"],
                "applied_rate": str(decision.selected_rate),
                "selected_source": decision.selected_source,
                "converted_amount": str(converted_amount),
            }
        )
    return response_lines


async def apply_month_end_rate(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    correlation_id: str | None,
    period_year: int,
    period_month: int,
    base_currency: str,
    quote_currency: str,
    line_items: list[tuple[str | None, Decimal]],
    approval_reason: str,
    redis_client: RedisLike | None = None,
) -> dict[str, Any]:
    _, last_day = calendar.monthrange(period_year, period_month)
    month_end_date = date(period_year, period_month, last_day)
    decision = await resolve_selected_rate(
        session,
        tenant_id=tenant_id,
        base_currency=base_currency,
        quote_currency=quote_currency,
        as_of_date=month_end_date,
        redis_client=redis_client,
    )
    converted = apply_rate_to_lines(line_items=line_items, rate=decision.selected_rate)

    base, quote = normalize_currency_pair(base_currency, quote_currency)
    latest = await _get_latest_manual_monthly_rate(
        session,
        tenant_id=tenant_id,
        period_year=period_year,
        period_month=period_month,
        base_currency=base,
        quote_currency=quote,
    )
    lock_row: FxManualMonthlyRate | None = None
    lock_needed = (
        latest is None
        or not latest.is_month_end_locked
        or latest.rate != decision.selected_rate
    )
    if lock_needed:
        lock_row = await create_manual_monthly_rate(
            session,
            tenant_id=tenant_id,
            entered_by=user_id,
            correlation_id=correlation_id,
            period_year=period_year,
            period_month=period_month,
            base_currency=base,
            quote_currency=quote,
            rate=decision.selected_rate,
            reason=(
                f"month_end_lock:{approval_reason};"
                f"selected_source={decision.selected_source}"
            ),
            supersedes_rate_id=latest.id if latest else None,
            source_type="locked_selection",
            is_month_end_locked=True,
            redis_client=redis_client,
        )

    return {
        "period_year": period_year,
        "period_month": period_month,
        "base_currency": base,
        "quote_currency": quote,
        "selected_rate": str(decision.selected_rate),
        "selected_source": decision.selected_source,
        "lines": [
            {
                "reference": line.reference,
                "amount": str(line.amount),
                "converted_amount": str(line.converted_amount),
                "applied_rate": str(line.applied_rate),
            }
            for line in converted
        ],
        "count": len(converted),
        "lock_rate_id": str(lock_row.id) if lock_row else None,
    }


async def compute_and_store_variance(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    computed_by: uuid.UUID,
    correlation_id: str | None,
    period_year: int,
    period_month: int,
    base_currency: str,
    quote_currency: str,
    expected_difference: Decimal,
    actual_difference: Decimal,
    entity_name: str | None,
    notes: str | None,
) -> FxVarianceResult:
    base, quote = normalize_currency_pair(base_currency, quote_currency)
    breakdown = compute_fx_variance(
        expected_difference=expected_difference,
        actual_difference=actual_difference,
    )
    record = await AuditWriter.insert_financial_record(
        session,
        model_class=FxVarianceResult,
        tenant_id=tenant_id,
        record_data={
            "period_year": period_year,
            "period_month": period_month,
            "base_currency": base,
            "quote_currency": quote,
            "expected_difference": str(breakdown.expected_difference),
            "actual_difference": str(breakdown.actual_difference),
            "fx_variance": str(breakdown.fx_variance),
        },
        values={
            "period_year": period_year,
            "period_month": period_month,
            "entity_name": entity_name,
            "base_currency": base,
            "quote_currency": quote,
            "expected_difference": breakdown.expected_difference,
            "actual_difference": breakdown.actual_difference,
            "fx_variance": breakdown.fx_variance,
            "computed_by": computed_by,
            "notes": notes,
            "correlation_id": correlation_id,
        },
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=computed_by,
            action="fx.variance.computed",
            resource_type="fx_variance_result",
            new_value={
                "period_year": period_year,
                "period_month": period_month,
                "base_currency": base,
                "quote_currency": quote,
                "correlation_id": correlation_id,
            },
        ),
    )
    return record


async def get_required_latest_comparison(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    base_currency: str,
    quote_currency: str,
) -> dict[str, Any]:
    comparison = await get_latest_comparison(
        session,
        tenant_id=tenant_id,
        base_currency=base_currency,
        quote_currency=quote_currency,
    )
    if comparison is None:
        raise NotFoundError("No FX comparison available for this currency pair")
    return comparison

