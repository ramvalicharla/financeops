from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

import pytest

from financeops.core.exceptions import ValidationError
from financeops.schemas.revenue import RevenueRecognitionMethod
from financeops.services.revenue.allocation_engine import allocate_contract_values
from financeops.services.revenue.contract_registry import RegisteredContract
from financeops.services.revenue.obligation_tracker import RegisteredObligation


def _uuid(value: str) -> UUID:
    return UUID(value)


@pytest.mark.asyncio
async def test_allocation_engine_reconciles_exactly_with_deterministic_residual() -> None:
    contract = RegisteredContract(
        contract_id=_uuid("00000000-0000-0000-0000-000000000901"),
        contract_number="REV-ALLOC-1",
        contract_currency="USD",
        contract_start_date=date(2026, 1, 1),
        contract_end_date=date(2026, 12, 31),
        total_contract_value=Decimal("100.000000"),
        source_contract_reference="SRC-ALLOC-1",
    )
    obligations = [
        RegisteredObligation(
            obligation_id=_uuid("00000000-0000-0000-0000-000000000902"),
            contract_id=contract.contract_id,
            contract_number=contract.contract_number,
            obligation_code="OBL-A",
            recognition_method=RevenueRecognitionMethod.straight_line,
            standalone_selling_price=Decimal("33.000000"),
        ),
        RegisteredObligation(
            obligation_id=_uuid("00000000-0000-0000-0000-000000000903"),
            contract_id=contract.contract_id,
            contract_number=contract.contract_number,
            obligation_code="OBL-B",
            recognition_method=RevenueRecognitionMethod.straight_line,
            standalone_selling_price=Decimal("33.000000"),
        ),
        RegisteredObligation(
            obligation_id=_uuid("00000000-0000-0000-0000-000000000904"),
            contract_id=contract.contract_id,
            contract_number=contract.contract_number,
            obligation_code="OBL-C",
            recognition_method=RevenueRecognitionMethod.straight_line,
            standalone_selling_price=Decimal("34.000000"),
        ),
    ]

    allocations = allocate_contract_values(contracts=[contract], obligations=obligations)
    assert len(allocations) == 3
    assert sum((row.allocated_amount_contract_currency for row in allocations), start=Decimal("0")) == Decimal(
        "100.000000"
    )

    # Deterministic residual lands on the first obligation in sorted obligation_code order.
    assert allocations[0].obligation_code == "OBL-A"
    assert allocations[0].allocated_amount_contract_currency >= Decimal("33.000000")


@pytest.mark.asyncio
async def test_allocation_engine_requires_obligations() -> None:
    contract = RegisteredContract(
        contract_id=_uuid("00000000-0000-0000-0000-000000000911"),
        contract_number="REV-ALLOC-2",
        contract_currency="USD",
        contract_start_date=date(2026, 1, 1),
        contract_end_date=date(2026, 12, 31),
        total_contract_value=Decimal("10.000000"),
        source_contract_reference="SRC-ALLOC-2",
    )

    with pytest.raises(ValidationError):
        allocate_contract_values(contracts=[contract], obligations=[])
