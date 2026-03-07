from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import ValidationError
from financeops.schemas.revenue import RevenueRateMode, RevenueRecognitionMethod
from financeops.services.revenue.allocation_engine import ObligationAllocation
from financeops.services.revenue.contract_registry import RegisteredContract
from financeops.services.revenue.obligation_tracker import RegisteredLineItem
from financeops.services.revenue.schedule_generator import _resolve_fx_rate, generate_schedule_rows


def _uuid(value: str) -> UUID:
    return UUID(value)


def _registered_contract() -> RegisteredContract:
    return RegisteredContract(
        contract_id=_uuid("00000000-0000-0000-0000-000000000921"),
        contract_number="REV-SCHED-1",
        contract_currency="USD",
        contract_start_date=date(2026, 1, 1),
        contract_end_date=date(2026, 3, 31),
        total_contract_value=Decimal("300.000000"),
        source_contract_reference="SRC-SCHED-1",
    )


@pytest.mark.asyncio
async def test_schedule_generator_straight_line_distributes_months(
    async_session: AsyncSession,
    test_tenant,
) -> None:
    contract = _registered_contract()
    line = RegisteredLineItem(
        line_item_id=_uuid("00000000-0000-0000-0000-000000000922"),
        contract_id=contract.contract_id,
        contract_number=contract.contract_number,
        obligation_id=_uuid("00000000-0000-0000-0000-000000000923"),
        line_code="LINE-1",
        line_amount=Decimal("300.000000"),
        line_currency="USD",
        milestone_reference=None,
        usage_reference=None,
        source_contract_reference=contract.source_contract_reference,
        recognition_method=RevenueRecognitionMethod.straight_line,
        completion_percentage=None,
        completed_flag=None,
        milestone_achieved=None,
        usage_quantity=None,
        recognition_date=None,
        recognition_start_date=date(2026, 1, 1),
        recognition_end_date=date(2026, 3, 31),
    )
    allocation = ObligationAllocation(
        contract_id=contract.contract_id,
        obligation_id=line.obligation_id,
        obligation_code="OBL-1",
        allocated_amount_contract_currency=Decimal("300.000000"),
    )

    with patch(
        "financeops.services.revenue.schedule_generator._resolve_fx_rate",
        new=AsyncMock(return_value=Decimal("1.000000")),
    ):
        output = await generate_schedule_rows(
            async_session,
            tenant_id=test_tenant.id,
            contracts=[contract],
            line_items=[line],
            allocations=[allocation],
            reporting_currency="USD",
            rate_mode=RevenueRateMode.daily,
        )

    assert len(output.rows) == 3
    assert {row.recognition_period_month for row in output.rows} == {1, 2, 3}
    assert sum((row.base_amount_contract_currency for row in output.rows), start=Decimal("0")) == Decimal(
        "300.000000"
    )


@pytest.mark.asyncio
async def test_schedule_generator_completed_service_pending_when_not_completed(
    async_session: AsyncSession,
    test_tenant,
) -> None:
    contract = _registered_contract()
    line = RegisteredLineItem(
        line_item_id=_uuid("00000000-0000-0000-0000-000000000924"),
        contract_id=contract.contract_id,
        contract_number=contract.contract_number,
        obligation_id=_uuid("00000000-0000-0000-0000-000000000925"),
        line_code="LINE-2",
        line_amount=Decimal("50.000000"),
        line_currency="USD",
        milestone_reference=None,
        usage_reference=None,
        source_contract_reference=contract.source_contract_reference,
        recognition_method=RevenueRecognitionMethod.completed_service,
        completion_percentage=None,
        completed_flag=False,
        milestone_achieved=None,
        usage_quantity=None,
        recognition_date=date(2026, 3, 31),
        recognition_start_date=None,
        recognition_end_date=None,
    )
    allocation = ObligationAllocation(
        contract_id=contract.contract_id,
        obligation_id=line.obligation_id,
        obligation_code="OBL-2",
        allocated_amount_contract_currency=Decimal("50.000000"),
    )

    with patch(
        "financeops.services.revenue.schedule_generator._resolve_fx_rate",
        new=AsyncMock(return_value=Decimal("1.000000")),
    ):
        output = await generate_schedule_rows(
            async_session,
            tenant_id=test_tenant.id,
            contracts=[contract],
            line_items=[line],
            allocations=[allocation],
            reporting_currency="USD",
            rate_mode=RevenueRateMode.daily,
        )

    assert len(output.rows) == 1
    assert output.rows[0].schedule_status == "pending"
    assert output.rows[0].recognized_amount_reporting_currency == Decimal("0.000000")


@pytest.mark.asyncio
async def test_schedule_generator_month_end_locked_requires_locked_rate(
    async_session: AsyncSession,
    test_tenant,
) -> None:
    with patch(
        "financeops.services.revenue.schedule_generator.list_manual_monthly_rates",
        new=AsyncMock(return_value=[]),
    ):
        with pytest.raises(ValidationError):
            await _resolve_fx_rate(
                async_session,
                tenant_id=test_tenant.id,
                base_currency="EUR",
                reporting_currency="USD",
                recognition_date=date(2026, 3, 10),
                rate_mode=RevenueRateMode.month_end_locked,
            )


@pytest.mark.asyncio
async def test_schedule_generator_uses_selected_rate_surface(async_session: AsyncSession, test_tenant) -> None:
    decision = type("Decision", (), {"selected_rate": Decimal("1.250000")})
    with patch(
        "financeops.services.revenue.schedule_generator.resolve_selected_rate",
        new=AsyncMock(return_value=decision),
    ) as resolve_spy:
        rate = await _resolve_fx_rate(
            async_session,
            tenant_id=test_tenant.id,
            base_currency="EUR",
            reporting_currency="USD",
            recognition_date=date(2026, 3, 10),
            rate_mode=RevenueRateMode.daily,
        )

    assert rate == Decimal("1.250000")
    assert resolve_spy.await_count == 1
