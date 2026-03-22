from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Protocol


class RedisLike(Protocol):
    async def get(self, name: str) -> Any: ...
    async def setex(self, name: str, time: int, value: str) -> Any: ...
    async def delete(self, *names: str) -> Any: ...


_FX_CACHE_TTL_SECONDS = 3600


@dataclass(frozen=True)
class CachedSelectedRate:
    rate: Decimal
    selected_source: str
    selection_method: str
    rate_date: date


def selected_rate_cache_key(
    *,
    tenant_id: uuid.UUID,
    rate_date: date,
    base_currency: str,
    quote_currency: str,
) -> str:
    return (
        f"fx:selected_rate:{tenant_id}:{rate_date.isoformat()}:"
        f"{base_currency}:{quote_currency}"
    )


def manual_monthly_cache_key(
    *,
    tenant_id: uuid.UUID,
    period_year: int,
    period_month: int,
    base_currency: str,
    quote_currency: str,
) -> str:
    return (
        f"fx:manual_monthly:{tenant_id}:{period_year}:{period_month}:"
        f"{base_currency}:{quote_currency}"
    )


async def cache_selected_rate(
    redis_client: RedisLike | None,
    *,
    tenant_id: uuid.UUID,
    rate_date: date,
    base_currency: str,
    quote_currency: str,
    selected_rate: Decimal,
    selected_source: str,
    selection_method: str,
) -> None:
    if redis_client is None:
        return
    try:
        key = selected_rate_cache_key(
            tenant_id=tenant_id,
            rate_date=rate_date,
            base_currency=base_currency,
            quote_currency=quote_currency,
        )
        payload = json.dumps(
            {
                "rate": str(selected_rate),
                "selected_source": selected_source,
                "selection_method": selection_method,
                "rate_date": rate_date.isoformat(),
            }
        )
        await redis_client.setex(name=key, time=_FX_CACHE_TTL_SECONDS, value=payload)
    except Exception:
        return


async def get_cached_selected_rate(
    redis_client: RedisLike | None,
    *,
    tenant_id: uuid.UUID,
    rate_date: date,
    base_currency: str,
    quote_currency: str,
) -> CachedSelectedRate | None:
    if redis_client is None:
        return None
    try:
        key = selected_rate_cache_key(
            tenant_id=tenant_id,
            rate_date=rate_date,
            base_currency=base_currency,
            quote_currency=quote_currency,
        )
        raw = await redis_client.get(key)
        if not raw:
            return None
        payload = json.loads(raw)
        return CachedSelectedRate(
            rate=Decimal(str(payload["rate"])),
            selected_source=str(payload["selected_source"]),
            selection_method=str(payload["selection_method"]),
            rate_date=date.fromisoformat(str(payload["rate_date"])),
        )
    except Exception:
        return None


async def invalidate_manual_monthly_cache(
    redis_client: RedisLike | None,
    *,
    tenant_id: uuid.UUID,
    period_year: int,
    period_month: int,
    base_currency: str,
    quote_currency: str,
) -> None:
    if redis_client is None:
        return
    try:
        key = manual_monthly_cache_key(
            tenant_id=tenant_id,
            period_year=period_year,
            period_month=period_month,
            base_currency=base_currency,
            quote_currency=quote_currency,
        )
        await redis_client.delete(key)
    except Exception:
        return

