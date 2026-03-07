from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from financeops.core.exceptions import ValidationError
from financeops.services.accounting_common.run_validation import LineageValidationResult
from financeops.services.prepaid.lineage_validation import validate_prepaid_lineage
from financeops.services.prepaid.service_facade import validate_lineage_for_run


def _uuid(value: str) -> UUID:
    return UUID(value)


@pytest.mark.asyncio
async def test_validate_prepaid_lineage_complete_when_no_gaps() -> None:
    session = AsyncMock()
    session.scalar = AsyncMock(side_effect=[0, 0, 0])

    result = await validate_prepaid_lineage(
        session,
        tenant_id=_uuid("00000000-0000-0000-0000-000000010001"),
        run_id=_uuid("00000000-0000-0000-0000-000000010002"),
    )

    assert result.is_complete is True
    assert result.details == {
        "missing_schedule_prepaid_links": 0,
        "missing_schedule_source_links": 0,
        "missing_journal_schedule_links": 0,
    }


@pytest.mark.asyncio
async def test_validate_prepaid_lineage_incomplete_when_gaps_found() -> None:
    session = AsyncMock()
    session.scalar = AsyncMock(side_effect=[1, 2, 0])

    result = await validate_prepaid_lineage(
        session,
        tenant_id=_uuid("00000000-0000-0000-0000-000000010003"),
        run_id=_uuid("00000000-0000-0000-0000-000000010004"),
    )

    assert result.is_complete is False
    assert result.error_code == "LINEAGE_INCOMPLETE"


@pytest.mark.asyncio
async def test_validate_lineage_for_run_raises_on_incomplete(async_session) -> None:
    with pytest.raises(ValidationError):
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "financeops.services.prepaid.service_facade.validate_prepaid_lineage",
                AsyncMock(
                    return_value=LineageValidationResult(
                        is_complete=False,
                        details={"missing_schedule_source_links": 1},
                    )
                ),
            )
            await validate_lineage_for_run(
                async_session,
                tenant_id=_uuid("00000000-0000-0000-0000-000000010005"),
                run_id=_uuid("00000000-0000-0000-0000-000000010006"),
            )
