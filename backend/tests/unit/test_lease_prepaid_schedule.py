from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock


async def test_lease_schedule_returns_empty_when_no_runs() -> None:
    from financeops.api.v1.lease import get_lease_schedule_endpoint

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session = MagicMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    mock_user = MagicMock()
    mock_user.tenant_id = uuid.uuid4()

    result = await get_lease_schedule_endpoint(session=mock_session, user=mock_user)
    assert result == []


async def test_prepaid_schedule_returns_empty_when_no_runs() -> None:
    from financeops.api.v1.prepaid import get_prepaid_schedule_endpoint

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session = MagicMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    mock_user = MagicMock()
    mock_user.tenant_id = uuid.uuid4()

    result = await get_prepaid_schedule_endpoint(session=mock_session, user=mock_user)
    assert result == []
