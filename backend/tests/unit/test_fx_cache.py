from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest

from financeops.services.fx.cache import (
    cache_selected_rate,
    get_cached_selected_rate,
    selected_rate_cache_key,
)


class _FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    async def get(self, name: str) -> str | None:
        return self.values.get(name)

    async def setex(self, name: str, time: int, value: str) -> None:
        del time
        self.values[name] = value

    async def delete(self, *names: str) -> None:
        for name in names:
            self.values.pop(name, None)


@pytest.mark.asyncio
async def test_selected_rate_cache_roundtrip() -> None:
    redis = _FakeRedis()
    tenant_id = uuid.uuid4()
    rate_date = date(2026, 3, 6)
    await cache_selected_rate(
        redis,
        tenant_id=tenant_id,
        rate_date=rate_date,
        base_currency="USD",
        quote_currency="INR",
        selected_rate=Decimal("83.100000"),
        selected_source="provider_consensus",
        selection_method="median_of_available_provider_quotes",
    )

    cached = await get_cached_selected_rate(
        redis,
        tenant_id=tenant_id,
        rate_date=rate_date,
        base_currency="USD",
        quote_currency="INR",
    )
    assert cached is not None
    assert cached.rate == Decimal("83.100000")
    assert (
        selected_rate_cache_key(
            tenant_id=tenant_id,
            rate_date=rate_date,
            base_currency="USD",
            quote_currency="INR",
        )
        in redis.values
    )
