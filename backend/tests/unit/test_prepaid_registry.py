from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import pytest

from financeops.db.models.prepaid import Prepaid
from financeops.schemas.prepaid import PrepaidInput
from financeops.services.prepaid.prepaid_registry import register_prepaids


def _prepaid_input() -> PrepaidInput:
    return PrepaidInput.model_validate(
        {
            "prepaid_code": "PPD-REG-001",
            "description": "Registry test prepaid",
            "prepaid_currency": "USD",
            "reporting_currency": "USD",
            "term_start_date": "2026-01-01",
            "term_end_date": "2026-03-31",
            "base_amount_contract_currency": "300.000000",
            "period_frequency": "monthly",
            "pattern_type": "straight_line",
            "rate_mode": "month_end_locked",
            "source_expense_reference": "SRC-PPD-REG-001",
            "source_reference_id": "00000000-0000-0000-0000-00000000a001",
            "adjustments": [],
        }
    )


@pytest.mark.asyncio
async def test_prepaid_registry_creates_and_reuses_records(
    async_session: AsyncSession,
    test_tenant,
) -> None:
    payload = [_prepaid_input()]

    first = await register_prepaids(
        async_session,
        tenant_id=test_tenant.id,
        user_id=test_tenant.id,
        correlation_id="00000000-0000-0000-0000-00000000b001",
        prepaids=payload,
    )
    second = await register_prepaids(
        async_session,
        tenant_id=test_tenant.id,
        user_id=test_tenant.id,
        correlation_id="00000000-0000-0000-0000-00000000b001",
        prepaids=payload,
    )

    assert len(first) == 1
    assert len(second) == 1
    assert first[0].prepaid_id == second[0].prepaid_id

    count = int(
        await async_session.scalar(
            select(func.count()).select_from(Prepaid).where(Prepaid.tenant_id == test_tenant.id)
        )
        or 0
    )
    assert count == 1
