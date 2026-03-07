from __future__ import annotations

import asyncio
import csv
import io
import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import httpx

from financeops.services.fx.normalization import normalize_rate_decimal

log = logging.getLogger(__name__)

_REQUEST_TIMEOUT_SECONDS = 8.0
_MAX_RETRIES = 2

_ECB_BASE_URL = "https://data-api.ecb.europa.eu/service/data/EXR"
_FRANKFURTER_BASE_URL = "https://api.frankfurter.app"
_OPEN_EXCHANGE_RATES_URL = "https://openexchangerates.org/api/latest.json"
_EXCHANGE_RATE_API_URL_TEMPLATE = "https://v6.exchangerate-api.com/v6/{api_key}/latest/USD"


@dataclass(frozen=True)
class ProviderQuote:
    provider_name: str
    base_currency: str
    quote_currency: str
    rate_date: date
    rate: Decimal
    source_timestamp: datetime | None
    raw_payload: dict[str, Any] | None


@dataclass(frozen=True)
class ProviderFetchResult:
    provider_name: str
    quote: ProviderQuote | None
    error: str | None

    @property
    def ok(self) -> bool:
        return self.quote is not None and self.error is None


async def _request_with_retries(
    client: httpx.AsyncClient,
    *,
    method: str,
    url: str,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    last_error: Exception | None = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            response = await client.request(
                method,
                url,
                params=params,
                headers=headers,
                timeout=_REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            return response
        except (httpx.TimeoutException, httpx.HTTPError) as exc:
            last_error = exc
            if attempt >= _MAX_RETRIES:
                break
            await asyncio.sleep(0.2 * (attempt + 1))
    if last_error is None:  # pragma: no cover
        raise RuntimeError("Unreachable request retry branch")
    raise last_error


def _parse_ecb_csv_payload(payload: str) -> tuple[date, Decimal]:
    reader = csv.DictReader(io.StringIO(payload))
    rows = list(reader)
    if not rows:
        raise ValueError("ECB response contains no rows")
    row = rows[-1]
    date_token = row.get("TIME_PERIOD") or row.get("DATE")
    rate_token = row.get("OBS_VALUE")
    if not date_token or not rate_token:
        raise ValueError("ECB response missing TIME_PERIOD/OBS_VALUE")
    parsed_date = date.fromisoformat(str(date_token))
    parsed_rate = normalize_rate_decimal(Decimal(str(rate_token)))
    return parsed_date, parsed_rate


def _extract_rate_from_usd_matrix(
    rates_by_currency: dict[str, Any],
    *,
    base_currency: str,
    quote_currency: str,
) -> Decimal:
    if base_currency == quote_currency:
        return Decimal("1")
    if quote_currency not in rates_by_currency:
        raise ValueError(f"Quote currency {quote_currency} missing from matrix")
    quote_vs_usd = Decimal(str(rates_by_currency[quote_currency]))
    if base_currency == "USD":
        return normalize_rate_decimal(quote_vs_usd)
    if base_currency not in rates_by_currency:
        raise ValueError(f"Base currency {base_currency} missing from matrix")
    base_vs_usd = Decimal(str(rates_by_currency[base_currency]))
    if quote_currency == "USD":
        return normalize_rate_decimal(Decimal("1") / base_vs_usd)
    return normalize_rate_decimal(quote_vs_usd / base_vs_usd)


async def fetch_ecb_quote(
    client: httpx.AsyncClient,
    *,
    base_currency: str,
    quote_currency: str,
    rate_date: date,
) -> ProviderFetchResult:
    provider_name = "ecb"
    if base_currency == quote_currency:
        return ProviderFetchResult(
            provider_name=provider_name,
            quote=ProviderQuote(
                provider_name=provider_name,
                base_currency=base_currency,
                quote_currency=quote_currency,
                rate_date=rate_date,
                rate=Decimal("1"),
                source_timestamp=datetime.combine(rate_date, datetime.min.time(), tzinfo=UTC),
                raw_payload=None,
            ),
            error=None,
        )
    try:
        # Canonical convention: 1 base = X quote.
        # ECB EXR pair is queried as D.quote.base.SP00.A to align with this convention.
        url = f"{_ECB_BASE_URL}/D.{quote_currency}.{base_currency}.SP00.A"
        response = await _request_with_retries(
            client,
            method="GET",
            url=url,
            params={
                "startPeriod": rate_date.isoformat(),
                "endPeriod": rate_date.isoformat(),
                "lastNObservations": 1,
                "format": "csvdata",
            },
        )
        observed_date, rate = _parse_ecb_csv_payload(response.text)
        return ProviderFetchResult(
            provider_name=provider_name,
            quote=ProviderQuote(
                provider_name=provider_name,
                base_currency=base_currency,
                quote_currency=quote_currency,
                rate_date=observed_date,
                rate=rate,
                source_timestamp=datetime.combine(
                    observed_date, datetime.min.time(), tzinfo=UTC
                ),
                raw_payload={"csv": response.text[:5000]},
            ),
            error=None,
        )
    except Exception as exc:
        return ProviderFetchResult(provider_name=provider_name, quote=None, error=str(exc))


async def fetch_frankfurter_quote(
    client: httpx.AsyncClient,
    *,
    base_currency: str,
    quote_currency: str,
    rate_date: date,
) -> ProviderFetchResult:
    provider_name = "frankfurter"
    try:
        path = rate_date.isoformat()
        response = await _request_with_retries(
            client,
            method="GET",
            url=f"{_FRANKFURTER_BASE_URL}/{path}",
            params={"from": base_currency, "to": quote_currency},
        )
        payload = response.json()
        rates = payload.get("rates", {})
        if quote_currency not in rates:
            raise ValueError(f"Frankfurter quote missing {quote_currency}")
        observed_date = date.fromisoformat(payload.get("date", rate_date.isoformat()))
        rate = normalize_rate_decimal(Decimal(str(rates[quote_currency])))
        return ProviderFetchResult(
            provider_name=provider_name,
            quote=ProviderQuote(
                provider_name=provider_name,
                base_currency=base_currency,
                quote_currency=quote_currency,
                rate_date=observed_date,
                rate=rate,
                source_timestamp=datetime.combine(
                    observed_date, datetime.min.time(), tzinfo=UTC
                ),
                raw_payload=payload,
            ),
            error=None,
        )
    except Exception as exc:
        return ProviderFetchResult(provider_name=provider_name, quote=None, error=str(exc))


async def fetch_open_exchange_rates_quote(
    client: httpx.AsyncClient,
    *,
    api_key: str,
    base_currency: str,
    quote_currency: str,
    rate_date: date,
) -> ProviderFetchResult:
    provider_name = "open_exchange_rates"
    if not api_key:
        return ProviderFetchResult(
            provider_name=provider_name,
            quote=None,
            error="OPEN_EXCHANGE_RATES_API_KEY not configured",
        )
    try:
        response = await _request_with_retries(
            client,
            method="GET",
            url=_OPEN_EXCHANGE_RATES_URL,
            params={
                "app_id": api_key,
                "symbols": ",".join(sorted({"USD", base_currency, quote_currency})),
                "show_alternative": "false",
            },
        )
        payload = response.json()
        rates = payload.get("rates", {})
        rate = _extract_rate_from_usd_matrix(
            rates, base_currency=base_currency, quote_currency=quote_currency
        )
        timestamp = payload.get("timestamp")
        source_timestamp = (
            datetime.fromtimestamp(int(timestamp), tz=UTC)
            if timestamp is not None
            else datetime.combine(rate_date, datetime.min.time(), tzinfo=UTC)
        )
        observed_date = source_timestamp.date()
        return ProviderFetchResult(
            provider_name=provider_name,
            quote=ProviderQuote(
                provider_name=provider_name,
                base_currency=base_currency,
                quote_currency=quote_currency,
                rate_date=observed_date,
                rate=rate,
                source_timestamp=source_timestamp,
                raw_payload=payload,
            ),
            error=None,
        )
    except Exception as exc:
        return ProviderFetchResult(provider_name=provider_name, quote=None, error=str(exc))


async def fetch_exchange_rate_api_quote(
    client: httpx.AsyncClient,
    *,
    api_key: str,
    base_currency: str,
    quote_currency: str,
    rate_date: date,
) -> ProviderFetchResult:
    provider_name = "exchange_rate_api"
    if not api_key:
        return ProviderFetchResult(
            provider_name=provider_name,
            quote=None,
            error="EXCHANGE_RATE_API_KEY not configured",
        )
    try:
        url = _EXCHANGE_RATE_API_URL_TEMPLATE.format(api_key=api_key)
        response = await _request_with_retries(client, method="GET", url=url)
        payload = response.json()
        rates = payload.get("conversion_rates", {})
        rate = _extract_rate_from_usd_matrix(
            rates, base_currency=base_currency, quote_currency=quote_currency
        )
        updated_at = payload.get("time_last_update_unix")
        source_timestamp = (
            datetime.fromtimestamp(int(updated_at), tz=UTC)
            if updated_at is not None
            else datetime.combine(rate_date, datetime.min.time(), tzinfo=UTC)
        )
        observed_date = source_timestamp.date()
        return ProviderFetchResult(
            provider_name=provider_name,
            quote=ProviderQuote(
                provider_name=provider_name,
                base_currency=base_currency,
                quote_currency=quote_currency,
                rate_date=observed_date,
                rate=rate,
                source_timestamp=source_timestamp,
                raw_payload=payload,
            ),
            error=None,
        )
    except Exception as exc:
        return ProviderFetchResult(provider_name=provider_name, quote=None, error=str(exc))


async def fetch_all_provider_quotes(
    *,
    base_currency: str,
    quote_currency: str,
    rate_date: date,
    open_exchange_rates_api_key: str,
    exchange_rate_api_key: str,
) -> list[ProviderFetchResult]:
    async with httpx.AsyncClient() as client:
        coroutines = [
            fetch_ecb_quote(
                client,
                base_currency=base_currency,
                quote_currency=quote_currency,
                rate_date=rate_date,
            ),
            fetch_frankfurter_quote(
                client,
                base_currency=base_currency,
                quote_currency=quote_currency,
                rate_date=rate_date,
            ),
            fetch_open_exchange_rates_quote(
                client,
                api_key=open_exchange_rates_api_key,
                base_currency=base_currency,
                quote_currency=quote_currency,
                rate_date=rate_date,
            ),
            fetch_exchange_rate_api_quote(
                client,
                api_key=exchange_rate_api_key,
                base_currency=base_currency,
                quote_currency=quote_currency,
                rate_date=rate_date,
            ),
        ]
        gathered = await asyncio.gather(*coroutines, return_exceptions=True)

    results: list[ProviderFetchResult] = []
    provider_order = [
        "ecb",
        "frankfurter",
        "open_exchange_rates",
        "exchange_rate_api",
    ]
    for provider_name, item in zip(provider_order, gathered, strict=True):
        if isinstance(item, Exception):
            results.append(
                ProviderFetchResult(
                    provider_name=provider_name,
                    quote=None,
                    error=f"Unhandled provider error: {item}",
                )
            )
            continue
        results.append(item)
    return results
