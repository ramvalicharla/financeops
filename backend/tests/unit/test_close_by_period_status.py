from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException


async def test_get_status_by_period_returns_running() -> None:
    from financeops.api.v1.close import get_month_end_close_status_by_period

    tenant_id = uuid.uuid4()
    mock_user = MagicMock()
    mock_user.tenant_id = tenant_id

    fake_description = MagicMock()
    fake_description.status.name = "RUNNING"

    fake_handle = MagicMock()
    fake_handle.describe = AsyncMock(return_value=fake_description)
    fake_handle.id = f"month-end-close-{tenant_id}-2024-03"

    with patch("financeops.api.v1.close.JobDispatcher") as MockDispatcher:
        MockDispatcher.return_value.get_temporal_workflow_handle = AsyncMock(return_value=fake_handle)
        result = await get_month_end_close_status_by_period(period="2024-03", user=mock_user)

    assert result["workflow_id"] == f"month-end-close-{tenant_id}-2024-03"
    assert result["status"] == "running"
    assert result["result"] is None


async def test_get_status_by_period_invalid_period_raises_400() -> None:
    from financeops.api.v1.close import get_month_end_close_status_by_period

    mock_user = MagicMock()
    mock_user.tenant_id = uuid.uuid4()

    with pytest.raises(HTTPException) as exc_info:
        await get_month_end_close_status_by_period(period="March-2024", user=mock_user)

    assert exc_info.value.status_code == 400
