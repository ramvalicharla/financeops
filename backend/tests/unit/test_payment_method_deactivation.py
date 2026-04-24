from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException


async def test_delete_payment_method_detaches_from_stripe() -> None:
    """delete_payment_method: fetches the row, calls provider.detach, inserts tombstone, returns {success: true}."""
    from financeops.modules.payment.api.payment_methods import delete_payment_method

    tenant_id = uuid.uuid4()
    method_id = uuid.uuid4()
    provider_pm_id = "pm_stripe_abc123"

    mock_method = MagicMock()
    mock_method.id = method_id
    mock_method.tenant_id = tenant_id
    mock_method.provider = "stripe"
    mock_method.provider_payment_method_id = provider_pm_id
    mock_method.type = "card"
    mock_method.last4 = "4242"
    mock_method.brand = "visa"
    mock_method.expiry_month = 12
    mock_method.expiry_year = 2027
    mock_method.is_default = False
    mock_method.billing_details = {}

    mock_db = MagicMock()
    mock_db.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mock_method))
    )
    mock_db.flush = AsyncMock()

    mock_user = MagicMock()
    mock_user.tenant_id = tenant_id

    mock_request = MagicMock()
    mock_request.state.request_id = "req-123"

    mock_provider = MagicMock()
    mock_provider.detach_payment_method = AsyncMock(
        return_value=MagicMock(success=True, provider_id=provider_pm_id)
    )

    mock_audit_row = MagicMock()
    mock_audit_row.id = uuid.uuid4()

    with (
        patch(
            "financeops.modules.payment.api.payment_methods.get_provider",
            return_value=mock_provider,
        ),
        patch(
            "financeops.modules.payment.api.payment_methods.AuditWriter.insert_financial_record",
            new=AsyncMock(return_value=mock_audit_row),
        ),
    ):
        result = await delete_payment_method(
            request=mock_request,
            id=str(method_id),
            session=mock_db,
            user=mock_user,
        )

    mock_provider.detach_payment_method.assert_awaited_once_with(provider_pm_id)
    assert result["data"]["success"] is True


async def test_delete_default_payment_method_raises_400() -> None:
    """delete_payment_method: raises HTTP 400 when the method is marked is_default=True."""
    from financeops.modules.payment.api.payment_methods import delete_payment_method

    tenant_id = uuid.uuid4()
    method_id = uuid.uuid4()

    mock_method = MagicMock()
    mock_method.id = method_id
    mock_method.tenant_id = tenant_id
    mock_method.is_default = True

    mock_db = MagicMock()
    mock_db.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mock_method))
    )

    mock_user = MagicMock()
    mock_user.tenant_id = tenant_id

    mock_request = MagicMock()
    mock_request.state.request_id = "req-456"

    with pytest.raises(HTTPException) as exc_info:
        await delete_payment_method(
            request=mock_request,
            id=str(method_id),
            session=mock_db,
            user=mock_user,
        )

    assert exc_info.value.status_code == 400
    assert "default" in exc_info.value.detail.lower()
