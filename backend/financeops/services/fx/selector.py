from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from statistics import median
from typing import Any

from financeops.services.fx.normalization import normalize_rate_decimal
from financeops.services.fx.provider_clients import ProviderFetchResult, ProviderQuote


@dataclass(frozen=True)
class SelectedRateDecision:
    selected_rate: Decimal
    selected_source: str
    selection_method: str
    degraded: bool


def build_side_by_side(provider_results: list[ProviderFetchResult]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in provider_results:
        rows.append(
            {
                "provider": result.provider_name,
                "status": "ok" if result.ok else "error",
                "rate": str(result.quote.rate) if result.quote else None,
                "rate_date": result.quote.rate_date.isoformat() if result.quote else None,
                "error": result.error,
            }
        )
    return rows


def select_rate_with_precedence(
    *,
    provider_quotes: list[ProviderQuote],
    provider_results: list[ProviderFetchResult],
    manual_monthly_rate: Decimal | None,
    previous_valid_rate: Decimal | None,
) -> SelectedRateDecision:
    degraded = any(item.error for item in provider_results)
    if manual_monthly_rate is not None:
        return SelectedRateDecision(
            selected_rate=normalize_rate_decimal(manual_monthly_rate),
            selected_source="manual_monthly",
            selection_method="manual_monthly_override",
            degraded=degraded,
        )

    if provider_quotes:
        numeric_rates = [quote.rate for quote in provider_quotes]
        provider_median = Decimal(str(median(numeric_rates)))
        return SelectedRateDecision(
            selected_rate=normalize_rate_decimal(provider_median),
            selected_source="provider_consensus",
            selection_method="median_of_available_provider_quotes",
            degraded=degraded,
        )

    if previous_valid_rate is not None:
        return SelectedRateDecision(
            selected_rate=normalize_rate_decimal(previous_valid_rate),
            selected_source="previous_valid_selected_rate",
            selection_method="fallback_previous_valid_rate",
            degraded=True,
        )

    raise ValueError("No selectable FX rate available from manual/provider/previous sources")
