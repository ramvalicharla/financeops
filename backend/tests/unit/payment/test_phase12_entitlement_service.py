from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from financeops.modules.payment.application.entitlement_service import EntitlementService


@pytest.mark.asyncio
async def test_check_entitlement_denies_when_not_configured() -> None:
    session = AsyncMock()
    service = EntitlementService(session)
    service.get_latest_tenant_entitlement = AsyncMock(return_value=None)  # type: ignore[method-assign]
    service.refresh_tenant_entitlements = AsyncMock(return_value=[])  # type: ignore[method-assign]

    decision = await service.check_entitlement(
        tenant_id=uuid.uuid4(),
        feature_name="analytics",
        quantity=1,
    )

    assert decision.allowed is False
    assert decision.reason == "entitlement_not_configured"


@pytest.mark.asyncio
async def test_check_entitlement_limit_enforced() -> None:
    session = AsyncMock()
    service = EntitlementService(session)
    entitlement = SimpleNamespace(
        access_type="limit",
        effective_limit=5,
        feature_name="analytics",
    )
    service.get_latest_tenant_entitlement = AsyncMock(return_value=entitlement)  # type: ignore[method-assign]
    service.usage_in_period = AsyncMock(return_value=3)  # type: ignore[method-assign]

    allowed = await service.check_entitlement(
        tenant_id=uuid.uuid4(),
        feature_name="analytics",
        quantity=1,
    )
    denied = await service.check_entitlement(
        tenant_id=uuid.uuid4(),
        feature_name="analytics",
        quantity=3,
    )

    assert allowed.allowed is True
    assert allowed.remaining == 2
    assert denied.allowed is False
    assert denied.reason == "limit_exceeded"

