from __future__ import annotations

import uuid

import pytest

from financeops.api import deps as api_deps
from tests.integration.payment.helpers import DummyPaymentProvider


@pytest.fixture
def mock_payment_provider(monkeypatch: pytest.MonkeyPatch) -> DummyPaymentProvider:
    provider = DummyPaymentProvider()
    monkeypatch.setattr("financeops.modules.payment.application.billing_service.get_provider", lambda _provider: provider)
    monkeypatch.setattr("financeops.modules.payment.api.invoices.get_provider", lambda _provider: provider)
    monkeypatch.setattr("financeops.modules.payment.api.credits.get_provider", lambda _provider: provider)
    monkeypatch.setattr("financeops.modules.payment.api.payment_methods.get_provider", lambda _provider: provider)
    monkeypatch.setattr("financeops.modules.payment.api.billing_portal.get_provider", lambda _provider: provider)
    monkeypatch.setattr("financeops.modules.payment.application.webhook_service.get_provider", lambda _provider: provider)
    monkeypatch.setattr("financeops.modules.payment.infrastructure.providers.registry.get_provider", lambda _provider: provider)
    return provider


@pytest.fixture
def idem_headers() -> dict[str, str]:
    return {"Idempotency-Key": f"idem_{uuid.uuid4().hex}"}


class _InMemoryRedis:
    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def setex(self, key: str, ttl: int, value: str) -> None:
        _ = ttl
        self._store[key] = value


@pytest.fixture(autouse=True)
def payment_idempotency_cache() -> None:
    original = api_deps._redis_pool
    api_deps._redis_pool = _InMemoryRedis()
    try:
        yield
    finally:
        api_deps._redis_pool = original
