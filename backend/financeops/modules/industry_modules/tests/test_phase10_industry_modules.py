from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from financeops.core.exceptions import ValidationError
from financeops.db.models.users import UserRole
from financeops.modules.industry_modules.application.service import (
    _AccountPair,
    build_asset_projection,
    build_lease_projection,
    create_lease,
    split_evenly,
    _months_between_inclusive,
)
from financeops.modules.industry_modules.application import service as industry_service_module
from financeops.modules.industry_modules.schemas import LeaseCreateRequest


class TestScheduleMath:
    def test_split_evenly_preserves_total(self) -> None:
        total = Decimal("1000.0000")
        rows = split_evenly(total, 3)
        assert len(rows) == 3
        assert sum(rows) == total

    def test_split_evenly_rejects_zero_parts(self) -> None:
        with pytest.raises(ValidationError):
            split_evenly(Decimal("100"), 0)

    def test_months_between_inclusive(self) -> None:
        rows = _months_between_inclusive(date(2026, 1, 15), date(2026, 4, 15))
        assert rows == [
            date(2026, 1, 15),
            date(2026, 2, 15),
            date(2026, 3, 15),
            date(2026, 4, 15),
        ]

    def test_lease_projection_zero_rate(self) -> None:
        pv, rows = build_lease_projection(
            lease_payment=Decimal("1000"),
            annual_discount_rate=Decimal("0"),
            period_count=12,
        )
        assert pv == Decimal("12000.0000")
        assert len(rows) == 12
        assert rows[-1].closing_liability == Decimal("0.0000")

    def test_lease_projection_balance_shape(self) -> None:
        pv, rows = build_lease_projection(
            lease_payment=Decimal("5000"),
            annual_discount_rate=Decimal("0.12"),
            period_count=24,
        )
        assert pv > Decimal("0")
        assert rows[0].opening_liability == pv
        assert rows[-1].closing_liability == Decimal("0.0000")
        assert all(row.depreciation >= Decimal("0") for row in rows)

    def test_asset_projection_slm_reaches_residual(self) -> None:
        rows = build_asset_projection(
            cost=Decimal("100000"),
            residual_value=Decimal("10000"),
            period_count=12,
            depreciation_method="SLM",
        )
        assert len(rows) == 12
        assert rows[-1].net_book_value == Decimal("10000.0000")

    def test_asset_projection_wdv_reaches_residual(self) -> None:
        rows = build_asset_projection(
            cost=Decimal("200000"),
            residual_value=Decimal("20000"),
            period_count=24,
            depreciation_method="WDV",
        )
        assert len(rows) == 24
        assert rows[-1].net_book_value == Decimal("20000.0000")

    def test_asset_projection_invalid_method(self) -> None:
        with pytest.raises(ValidationError):
            build_asset_projection(
                cost=Decimal("100"),
                residual_value=Decimal("0"),
                period_count=4,
                depreciation_method="XYZ",
            )


class _Session:
    def __init__(self) -> None:
        self.rows: list[object] = []

    def add(self, row: object) -> None:
        self.rows.append(row)

    async def flush(self) -> None:
        for row in self.rows:
            if hasattr(row, "id") and getattr(row, "id", None) is None:
                setattr(row, "id", uuid.uuid4())


@pytest.mark.asyncio
async def test_create_lease_uses_governed_journal_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _Session()
    journal_id = uuid.uuid4()
    intent_id = uuid.uuid4()
    job_id = uuid.uuid4()

    monkeypatch.setattr(industry_service_module, "_ensure_module_enabled", AsyncMock(return_value=None))
    monkeypatch.setattr(
        industry_service_module,
        "_resolve_account_pair",
        AsyncMock(return_value=_AccountPair("1600", "2100")),
    )
    governed_mock = AsyncMock(
        return_value=SimpleNamespace(
            intent_id=intent_id,
            job_id=job_id,
            record_refs={"journal_id": str(journal_id), "status": "DRAFT"},
            require_journal_id=lambda: journal_id,
        )
    )
    monkeypatch.setattr(industry_service_module, "submit_governed_journal_intent", governed_mock)

    payload = await create_lease(
        session,
        tenant_id=uuid.uuid4(),
        actor_user_id=uuid.uuid4(),
        actor_role=UserRole.finance_leader.value,
        payload=LeaseCreateRequest(
            entity_id=uuid.uuid4(),
            lease_start_date=date(2026, 4, 1),
            lease_end_date=date(2026, 6, 1),
            lease_payment=Decimal("1000"),
            discount_rate=Decimal("0.12"),
            lease_type="OFFICE",
        ),
    )

    assert payload.draft_journal_id == journal_id
    assert payload.intent_id == intent_id
    assert payload.job_id == job_id
    kwargs = governed_mock.await_args.kwargs
    assert kwargs["intent_type"].value == "CREATE_JOURNAL"
    assert kwargs["payload"]["source"] == "MODULE"
    assert kwargs["payload"]["external_reference_id"].startswith("LEASE:")
