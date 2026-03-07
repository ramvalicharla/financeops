from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.fx_rates import FxManualMonthlyRate, FxRateFetchRun, FxRateQuote
from financeops.services.audit_writer import AuditWriter
from financeops.services.fx.fx_rate_service import (
    create_manual_monthly_rate,
    fetch_live_rates,
)
from financeops.services.fx.provider_clients import ProviderFetchResult, ProviderQuote


class _FakeRedis:
    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def get(self, name: str) -> str | None:
        return self._store.get(name)

    async def setex(self, name: str, time: int, value: str) -> None:
        del time
        self._store[name] = value

    async def delete(self, *names: str) -> None:
        for name in names:
            self._store.pop(name, None)


def _provider_quote(provider: str, rate: str) -> ProviderQuote:
    return ProviderQuote(
        provider_name=provider,
        base_currency="USD",
        quote_currency="INR",
        rate_date=date(2026, 3, 6),
        rate=Decimal(rate),
        source_timestamp=datetime(2026, 3, 6, tzinfo=UTC),
        raw_payload={"provider": provider},
    )


@pytest.mark.asyncio
async def test_create_manual_monthly_rate_uses_audit_writer(
    async_session: AsyncSession,
    test_tenant,
):
    with patch(
        "financeops.services.fx.fx_rate_service.AuditWriter.insert_financial_record",
        wraps=AuditWriter.insert_financial_record,
    ) as spy:
        await create_manual_monthly_rate(
            async_session,
            tenant_id=test_tenant.id,
            entered_by=test_tenant.id,
            correlation_id="corr-manual",
            period_year=2026,
            period_month=3,
            base_currency="USD",
            quote_currency="INR",
            rate=Decimal("83.100000"),
            reason="manual month-end profile",
            supersedes_rate_id=None,
            redis_client=_FakeRedis(),
        )
    assert spy.await_count == 1


@pytest.mark.asyncio
async def test_fetch_live_rates_persists_run_and_quotes(
    async_session: AsyncSession,
    test_tenant,
):
    fake_results = [
        ProviderFetchResult("ecb", _provider_quote("ecb", "83.100000"), None),
        ProviderFetchResult("frankfurter", _provider_quote("frankfurter", "83.200000"), None),
        ProviderFetchResult("open_exchange_rates", None, "key missing"),
        ProviderFetchResult("exchange_rate_api", None, "timeout"),
    ]
    with patch(
        "financeops.services.fx.fx_rate_service.fetch_all_provider_quotes",
        return_value=fake_results,
    ):
        payload = await fetch_live_rates(
            async_session,
            tenant_id=test_tenant.id,
            requested_by=test_tenant.id,
            correlation_id="corr-fetch",
            base_currency="USD",
            quote_currency="INR",
            rate_date=date(2026, 3, 6),
            redis_client=_FakeRedis(),
        )

    assert payload["status"] == "degraded"
    assert payload["selected_source"] == "provider_consensus"
    assert len(payload["providers"]) == 4

    run = (
        await async_session.execute(select(FxRateFetchRun).where(FxRateFetchRun.tenant_id == test_tenant.id))
    ).scalars().one()
    assert run.success_count == 2
    assert run.failure_count == 2

    quotes = (
        await async_session.execute(select(FxRateQuote).where(FxRateQuote.fetch_run_id == run.id))
    ).scalars().all()
    assert len(quotes) == 2


@pytest.mark.asyncio
async def test_fetch_live_rates_uses_audit_writer_for_persistence(
    async_session: AsyncSession,
    test_tenant,
):
    with patch(
        "financeops.services.fx.fx_rate_service.fetch_all_provider_quotes",
        return_value=[
            ProviderFetchResult("ecb", _provider_quote("ecb", "83.100000"), None),
            ProviderFetchResult("frankfurter", None, "timeout"),
            ProviderFetchResult("open_exchange_rates", None, "timeout"),
            ProviderFetchResult("exchange_rate_api", None, "timeout"),
        ],
    ):
        with patch(
            "financeops.services.fx.fx_rate_service.AuditWriter.insert_financial_record",
            wraps=AuditWriter.insert_financial_record,
        ) as spy:
            await fetch_live_rates(
                async_session,
                tenant_id=test_tenant.id,
                requested_by=test_tenant.id,
                correlation_id="corr-audit-fetch",
                base_currency="USD",
                quote_currency="INR",
                rate_date=date(2026, 3, 6),
                redis_client=None,
            )
    # At least one fetch run row and one provider quote row must be inserted via AuditWriter.
    assert spy.await_count >= 2


@pytest.mark.asyncio
async def test_fetch_live_rates_uses_previous_valid_when_all_providers_fail(
    async_session: AsyncSession,
    test_tenant,
):
    await create_manual_monthly_rate(
        async_session,
        tenant_id=test_tenant.id,
        entered_by=test_tenant.id,
        correlation_id="corr-seed",
        period_year=2026,
        period_month=3,
        base_currency="USD",
        quote_currency="INR",
        rate=Decimal("83.500000"),
        reason="seed manual",
        supersedes_rate_id=None,
        redis_client=None,
    )
    with patch(
        "financeops.services.fx.fx_rate_service.fetch_all_provider_quotes",
        return_value=[
            ProviderFetchResult("ecb", None, "timeout"),
            ProviderFetchResult("frankfurter", None, "timeout"),
            ProviderFetchResult("open_exchange_rates", None, "timeout"),
            ProviderFetchResult("exchange_rate_api", None, "timeout"),
        ],
    ):
        payload = await fetch_live_rates(
            async_session,
            tenant_id=test_tenant.id,
            requested_by=test_tenant.id,
            correlation_id="corr-fetch-fallback",
            base_currency="USD",
            quote_currency="INR",
            rate_date=date(2026, 3, 6),
            redis_client=None,
        )
    assert payload["status"] in {"degraded", "failed"}
    # Manual monthly takes precedence for selection in the same month.
    assert payload["selected_source"] == "manual_monthly"

    manual_rows = (
        await async_session.execute(select(FxManualMonthlyRate).where(FxManualMonthlyRate.tenant_id == test_tenant.id))
    ).scalars().all()
    assert len(manual_rows) == 1
