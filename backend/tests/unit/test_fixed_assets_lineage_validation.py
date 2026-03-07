from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from financeops.core.exceptions import ValidationError
from financeops.services.accounting_common.run_validation import LineageValidationResult
from financeops.services.fixed_assets.lineage_validation import validate_fixed_assets_lineage
from financeops.services.fixed_assets.service_facade import validate_lineage_for_run


def _uuid(value: str) -> UUID:
    return UUID(value)


@pytest.mark.asyncio
async def test_validate_fixed_assets_lineage_complete_when_no_gaps() -> None:
    session = AsyncMock()
    session.scalar = AsyncMock(side_effect=[0, 0, 0, 0, 0])

    result = await validate_fixed_assets_lineage(
        session,
        tenant_id=_uuid("00000000-0000-0000-0000-00000000f701"),
        run_id=_uuid("00000000-0000-0000-0000-00000000f702"),
    )

    assert result.is_complete is True


@pytest.mark.asyncio
async def test_validate_lineage_for_run_raises_on_incomplete(async_session) -> None:
    with pytest.raises(ValidationError):
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "financeops.services.fixed_assets.service_facade.validate_fixed_assets_lineage",
                AsyncMock(
                    return_value=LineageValidationResult(
                        is_complete=False,
                        details={"missing_schedule_source_links": 1},
                    )
                ),
            )
            await validate_lineage_for_run(
                async_session,
                tenant_id=_uuid("00000000-0000-0000-0000-00000000f703"),
                run_id=_uuid("00000000-0000-0000-0000-00000000f704"),
            )
