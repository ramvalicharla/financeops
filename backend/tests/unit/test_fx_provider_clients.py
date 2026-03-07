from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from financeops.services.fx import provider_clients
from financeops.services.fx.provider_clients import ProviderFetchResult, ProviderQuote


def test_parse_ecb_csv_payload() -> None:
    parsed_date, parsed_rate = provider_clients._parse_ecb_csv_payload(  # noqa: SLF001
        "TIME_PERIOD,OBS_VALUE\n2026-03-06,83.123456\n"
    )
    assert parsed_date == date(2026, 3, 6)
    assert parsed_rate == Decimal("83.123456")


def test_extract_rate_from_usd_matrix() -> None:
    rate = provider_clients._extract_rate_from_usd_matrix(  # noqa: SLF001
        {"USD": 1, "INR": 83.0, "EUR": 0.9},
        base_currency="EUR",
        quote_currency="INR",
    )
    assert rate == Decimal("92.222222")


@pytest.mark.asyncio
async def test_fetch_all_provider_quotes_handles_partial_failure() -> None:
    successful_quote = ProviderQuote(
        provider_name="ecb",
        base_currency="USD",
        quote_currency="INR",
        rate_date=date(2026, 3, 6),
        rate=Decimal("83.100000"),
        source_timestamp=datetime(2026, 3, 6, tzinfo=UTC),
        raw_payload={"provider": "ecb"},
    )

    with patch(
        "financeops.services.fx.provider_clients.fetch_ecb_quote",
        new=AsyncMock(return_value=ProviderFetchResult("ecb", successful_quote, None)),
    ), patch(
        "financeops.services.fx.provider_clients.fetch_frankfurter_quote",
        new=AsyncMock(side_effect=RuntimeError("boom")),
    ), patch(
        "financeops.services.fx.provider_clients.fetch_open_exchange_rates_quote",
        new=AsyncMock(return_value=ProviderFetchResult("open_exchange_rates", None, "missing key")),
    ), patch(
        "financeops.services.fx.provider_clients.fetch_exchange_rate_api_quote",
        new=AsyncMock(return_value=ProviderFetchResult("exchange_rate_api", None, "timeout")),
    ):
        results = await provider_clients.fetch_all_provider_quotes(
            base_currency="USD",
            quote_currency="INR",
            rate_date=date(2026, 3, 6),
            open_exchange_rates_api_key="",
            exchange_rate_api_key="",
        )
    assert len(results) == 4
    assert any(result.ok for result in results)
    assert any(result.error for result in results)


@pytest.mark.asyncio
async def test_paid_provider_clients_return_config_error_when_api_key_missing() -> None:
    async with httpx.AsyncClient() as client:
        open_exchange_result = await provider_clients.fetch_open_exchange_rates_quote(
            client,
            api_key="",
            base_currency="USD",
            quote_currency="INR",
            rate_date=date(2026, 3, 6),
        )
        exchange_rate_api_result = await provider_clients.fetch_exchange_rate_api_quote(
            client,
            api_key="",
            base_currency="USD",
            quote_currency="INR",
            rate_date=date(2026, 3, 6),
        )

    assert open_exchange_result.ok is False
    assert open_exchange_result.error == "OPEN_EXCHANGE_RATES_API_KEY not configured"
    assert exchange_rate_api_result.ok is False
    assert exchange_rate_api_result.error == "EXCHANGE_RATE_API_KEY not configured"


@pytest.mark.asyncio
async def test_fetch_all_provider_quotes_reports_degraded_when_paid_provider_keys_missing() -> None:
    successful_quote = ProviderQuote(
        provider_name="ecb",
        base_currency="USD",
        quote_currency="INR",
        rate_date=date(2026, 3, 6),
        rate=Decimal("83.100000"),
        source_timestamp=datetime(2026, 3, 6, tzinfo=UTC),
        raw_payload={"provider": "ecb"},
    )

    with patch(
        "financeops.services.fx.provider_clients.fetch_ecb_quote",
        new=AsyncMock(return_value=ProviderFetchResult("ecb", successful_quote, None)),
    ), patch(
        "financeops.services.fx.provider_clients.fetch_frankfurter_quote",
        new=AsyncMock(return_value=ProviderFetchResult("frankfurter", successful_quote, None)),
    ):
        results = await provider_clients.fetch_all_provider_quotes(
            base_currency="USD",
            quote_currency="INR",
            rate_date=date(2026, 3, 6),
            open_exchange_rates_api_key="",
            exchange_rate_api_key="",
        )

    success_count = sum(1 for result in results if result.ok)
    failure_count = len(results) - success_count
    assert len(results) == 4
    assert success_count == 2
    assert failure_count == 2
    open_exchange_result = next(result for result in results if result.provider_name == "open_exchange_rates")
    exchange_rate_api_result = next(result for result in results if result.provider_name == "exchange_rate_api")
    assert open_exchange_result.error == "OPEN_EXCHANGE_RATES_API_KEY not configured"
    assert exchange_rate_api_result.error == "EXCHANGE_RATE_API_KEY not configured"
