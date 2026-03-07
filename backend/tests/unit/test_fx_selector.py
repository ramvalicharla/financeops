from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from financeops.services.fx.provider_clients import ProviderFetchResult, ProviderQuote
from financeops.services.fx.selector import select_rate_with_precedence


def _quote(provider: str, rate: str) -> ProviderQuote:
    return ProviderQuote(
        provider_name=provider,
        base_currency="USD",
        quote_currency="INR",
        rate_date=date(2026, 3, 6),
        rate=Decimal(rate),
        source_timestamp=datetime(2026, 3, 6, tzinfo=UTC),
        raw_payload={"provider": provider},
    )


def test_selector_prefers_manual_monthly_rate() -> None:
    decision = select_rate_with_precedence(
        provider_quotes=[_quote("ecb", "83.100000")],
        provider_results=[ProviderFetchResult("ecb", _quote("ecb", "83.100000"), None)],
        manual_monthly_rate=Decimal("84.250000"),
        previous_valid_rate=Decimal("80.000000"),
    )
    assert decision.selected_source == "manual_monthly"
    assert decision.selected_rate == Decimal("84.250000")


def test_selector_uses_provider_median_when_manual_missing() -> None:
    quotes = [_quote("ecb", "83.100000"), _quote("frankfurter", "83.300000"), _quote("exchange_rate_api", "83.200000")]
    results = [ProviderFetchResult(q.provider_name, q, None) for q in quotes]
    decision = select_rate_with_precedence(
        provider_quotes=quotes,
        provider_results=results,
        manual_monthly_rate=None,
        previous_valid_rate=None,
    )
    assert decision.selected_source == "provider_consensus"
    assert decision.selected_rate == Decimal("83.200000")


def test_selector_falls_back_to_previous_when_providers_absent() -> None:
    decision = select_rate_with_precedence(
        provider_quotes=[],
        provider_results=[ProviderFetchResult("ecb", None, "timeout")],
        manual_monthly_rate=None,
        previous_valid_rate=Decimal("82.000000"),
    )
    assert decision.selected_source == "previous_valid_selected_rate"
    assert decision.selected_rate == Decimal("82.000000")
    assert decision.degraded is True
