from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from financeops.core.exceptions import InsufficientCreditsError
from financeops.modules.payment.application.credit_service import CreditService


class _ExecuteResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


@pytest.mark.asyncio
async def test_consume_credits_raises_when_balance_insufficient() -> None:
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_ExecuteResult(SimpleNamespace(credits_balance_after=5)))
    service = CreditService(session)

    with pytest.raises(InsufficientCreditsError):
        await service.consume_credits(
            tenant_id=uuid.uuid4(),
            credits=10,
            reference_id="ref-1",
            reference_type="test",
            created_by=uuid.uuid4(),
        )


@pytest.mark.asyncio
async def test_get_balance_returns_integer_total() -> None:
    session = AsyncMock()
    session.scalar = AsyncMock(return_value=12)
    service = CreditService(session)

    balance = await service.get_balance(tenant_id=uuid.uuid4())
    assert balance == 12

