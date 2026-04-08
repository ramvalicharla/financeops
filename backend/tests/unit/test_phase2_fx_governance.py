from __future__ import annotations

import uuid
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from financeops.core.exceptions import ValidationError
from financeops.modules.accounting_layer.application import revaluation_service


@pytest.mark.asyncio
async def test_fx_revaluation_blocks_when_canonical_approval_denied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        revaluation_service,
        "_get_entity_for_tenant",
        AsyncMock(return_value=SimpleNamespace(base_currency="INR")),
    )
    monkeypatch.setattr(
        revaluation_service,
        "GuardEngine",
        lambda: SimpleNamespace(
            evaluate_mutation=AsyncMock(return_value=SimpleNamespace(overall_passed=True, blocking_failures=[]))
        ),
    )
    monkeypatch.setattr(
        revaluation_service,
        "ApprovalPolicyResolver",
        lambda: SimpleNamespace(
            resolve_mutation=AsyncMock(
                return_value=SimpleNamespace(
                    approval_required=True,
                    is_granted=False,
                    required_role="finance_leader",
                    reason="fx approval denied",
                )
            )
        ),
    )

    with pytest.raises(ValidationError, match="fx approval denied"):
        await revaluation_service.run_fx_revaluation(
            AsyncMock(),
            tenant_id=uuid.uuid4(),
            entity_id=uuid.uuid4(),
            as_of_date=date(2026, 3, 31),
            initiated_by=uuid.uuid4(),
            actor_role="finance_team",
        )
