from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import pytest

from financeops.modules.fx_translation_reporting.application.rate_selection_service import (
    RateSelectionService,
)
from financeops.modules.fx_translation_reporting.domain.invariants import q6
from financeops.modules.fx_translation_reporting.domain.value_objects import (
    FxTranslationRunTokenInput,
)
from financeops.modules.fx_translation_reporting.infrastructure.token_builder import (
    build_fx_translation_run_token,
)


@dataclass
class _ManualRate:
    id: uuid.UUID
    rate: Decimal


class _RepoStub:
    def __init__(self) -> None:
        self.locked_direct: _ManualRate | None = None
        self.locked_inverse: _ManualRate | None = None
        self.manual_direct: _ManualRate | None = None
        self.manual_inverse: _ManualRate | None = None

    async def get_latest_locked_manual_rate(self, **kwargs):  # type: ignore[no-untyped-def]
        if kwargs["base_currency"] == "EUR" and kwargs["quote_currency"] == "USD":
            return self.locked_direct
        if kwargs["base_currency"] == "USD" and kwargs["quote_currency"] == "EUR":
            return self.locked_inverse
        return None

    async def get_latest_manual_rate(self, **kwargs):  # type: ignore[no-untyped-def]
        if kwargs["base_currency"] == "EUR" and kwargs["quote_currency"] == "USD":
            return self.manual_direct
        if kwargs["base_currency"] == "USD" and kwargs["quote_currency"] == "EUR":
            return self.manual_inverse
        return None

    async def get_latest_quote_on_or_before(self, **kwargs):  # type: ignore[no-untyped-def]
        return None

    async def get_average_quote_for_month(self, **kwargs):  # type: ignore[no-untyped-def]
        return None


def test_fx_translation_run_token_is_stable_for_same_inputs() -> None:
    tenant_id = uuid.uuid4()
    org_id = uuid.uuid4()
    payload = FxTranslationRunTokenInput(
        tenant_id=tenant_id,
        organisation_id=org_id,
        reporting_period=date(2026, 1, 31),
        reporting_currency_code="USD",
        reporting_currency_version_token="r1",
        translation_rule_version_token="t1",
        rate_policy_version_token="p1",
        rate_source_version_token="s1",
        source_consolidation_run_refs=[
            {"source_type": "consolidation_run", "run_id": "00000000-0000-0000-0000-000000000001"}
        ],
        run_status="created",
    )
    token_a = build_fx_translation_run_token(payload)
    token_b = build_fx_translation_run_token(payload)
    assert token_a == token_b


@pytest.mark.asyncio
async def test_rate_selection_fail_closed_when_locked_required_and_missing() -> None:
    service = RateSelectionService()
    repo = _RepoStub()
    with pytest.raises(ValueError, match="Missing required locked FX rate"):
        await service.resolve_selected_rate(
            repository=repo,  # type: ignore[arg-type]
            tenant_id=uuid.uuid4(),
            source_currency="EUR",
            reporting_currency="USD",
            reporting_period=date(2026, 1, 31),
            rate_type="closing",
            locked_rate_required=True,
            fallback_behavior_json={},
        )


@pytest.mark.asyncio
async def test_rate_selection_uses_inverse_locked_manual_rate_deterministically() -> None:
    service = RateSelectionService()
    repo = _RepoStub()
    repo.locked_inverse = _ManualRate(id=uuid.uuid4(), rate=Decimal("2.000000"))
    selected = await service.resolve_selected_rate(
        repository=repo,  # type: ignore[arg-type]
        tenant_id=uuid.uuid4(),
        source_currency="EUR",
        reporting_currency="USD",
        reporting_period=date(2026, 1, 31),
        rate_type="closing",
        locked_rate_required=True,
        fallback_behavior_json={},
    )
    assert selected.multiplier == Decimal("0.50000000")
    assert selected.rate_type == "locked_manual_inverse"


def test_translation_arithmetic_rounds_to_6dp() -> None:
    assert q6(Decimal("100.000000") * Decimal("1.20000000")) == Decimal("120.000000")

