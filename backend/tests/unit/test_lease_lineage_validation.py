from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from financeops.core.exceptions import ValidationError
from financeops.services.accounting_common.run_validation import LineageValidationResult
from financeops.services.lease.lineage_validation import validate_lease_lineage
from financeops.services.lease.service_facade import validate_lineage_for_run


def _uuid(value: str) -> UUID:
    return UUID(value)


@pytest.mark.asyncio
async def test_validate_lease_lineage_complete() -> None:
    session = AsyncMock()
    session.scalar = AsyncMock(side_effect=[0, 0, 0, 0])

    result = await validate_lease_lineage(
        session,
        tenant_id=_uuid("00000000-0000-0000-0000-000000001301"),
        run_id=_uuid("00000000-0000-0000-0000-000000001302"),
    )

    assert result.is_complete is True


@pytest.mark.asyncio
async def test_validate_lease_lineage_incomplete_raises_in_facade(async_session) -> None:
    with pytest.raises(ValidationError):
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "financeops.services.lease.service_facade.validate_lease_lineage",
                AsyncMock(
                    return_value=LineageValidationResult(
                        is_complete=False,
                        details={"missing_journal_schedule_links": 1},
                    )
                ),
            )
            await validate_lineage_for_run(
                async_session,
                tenant_id=_uuid("00000000-0000-0000-0000-000000001303"),
                run_id=_uuid("00000000-0000-0000-0000-000000001304"),
            )
