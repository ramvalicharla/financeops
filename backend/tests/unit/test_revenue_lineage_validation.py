from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from financeops.core.exceptions import ValidationError
from financeops.services.accounting_common.run_validation import LineageValidationResult
from financeops.services.revenue.lineage_validation import validate_revenue_lineage
from financeops.services.revenue.service_facade import validate_lineage_for_run


def _uuid(value: str) -> UUID:
    return UUID(value)


@pytest.mark.asyncio
async def test_validate_revenue_lineage_returns_complete_when_no_gaps() -> None:
    session = AsyncMock()
    session.scalar = AsyncMock(side_effect=[0, 0, 0, 0])

    result = await validate_revenue_lineage(
        session,
        tenant_id=_uuid("00000000-0000-0000-0000-000000000941"),
        run_id=_uuid("00000000-0000-0000-0000-000000000942"),
    )

    assert result.is_complete is True
    assert result.details == {
        "missing_schedule_line_links": 0,
        "missing_line_item_contract_links": 0,
        "missing_line_item_obligation_links": 0,
        "missing_journal_schedule_links": 0,
    }


@pytest.mark.asyncio
async def test_validate_revenue_lineage_returns_incomplete_when_gaps_found() -> None:
    session = AsyncMock()
    session.scalar = AsyncMock(side_effect=[1, 0, 2, 0])

    result = await validate_revenue_lineage(
        session,
        tenant_id=_uuid("00000000-0000-0000-0000-000000000943"),
        run_id=_uuid("00000000-0000-0000-0000-000000000944"),
    )

    assert result.is_complete is False
    assert result.error_code == "LINEAGE_INCOMPLETE"
    assert result.details == {
        "missing_schedule_line_links": 1,
        "missing_line_item_contract_links": 0,
        "missing_line_item_obligation_links": 2,
        "missing_journal_schedule_links": 0,
    }


@pytest.mark.asyncio
async def test_validate_lineage_for_run_raises_on_incomplete_lineage(async_session) -> None:
    with pytest.raises(ValidationError):
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "financeops.services.revenue.service_facade.validate_revenue_lineage",
                AsyncMock(
                    return_value=LineageValidationResult(
                        is_complete=False,
                        details={"missing_schedule_line_links": 1},
                    )
                ),
            )
            await validate_lineage_for_run(
                async_session,
                tenant_id=_uuid("00000000-0000-0000-0000-000000000945"),
                run_id=_uuid("00000000-0000-0000-0000-000000000946"),
            )
