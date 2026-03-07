from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import ValidationError
from financeops.schemas.revenue import RevenueContractInput
from financeops.services.revenue.contract_registry import register_contracts
from financeops.services.revenue.obligation_tracker import register_obligations_and_line_items


def _single_obligation_contract() -> RevenueContractInput:
    return RevenueContractInput.model_validate(
        {
            "contract_number": "REV-OBL-001",
            "customer_id": "CUST-OBL",
            "contract_currency": "USD",
            "contract_start_date": "2026-01-01",
            "contract_end_date": "2026-02-28",
            "total_contract_value": "200.000000",
            "source_contract_reference": "SRC-OBL-001",
            "policy_code": "ASC606",
            "policy_version": "v1",
            "performance_obligations": [
                {
                    "obligation_code": "OBL-A",
                    "description": "Primary obligation",
                    "standalone_selling_price": "200.000000",
                    "allocation_basis": "ssp",
                    "recognition_method": "straight_line",
                }
            ],
            "contract_line_items": [
                {
                    "line_code": "LINE-A",
                    "line_amount": "200.000000",
                    "line_currency": "USD",
                    "recognition_start_date": "2026-01-01",
                    "recognition_end_date": "2026-02-28",
                }
            ],
            "modifications": [],
        }
    )


def _multi_obligation_missing_line_mapping() -> RevenueContractInput:
    return RevenueContractInput.model_validate(
        {
            "contract_number": "REV-OBL-002",
            "customer_id": "CUST-OBL",
            "contract_currency": "USD",
            "contract_start_date": "2026-01-01",
            "contract_end_date": "2026-03-31",
            "total_contract_value": "300.000000",
            "source_contract_reference": "SRC-OBL-002",
            "policy_code": "ASC606",
            "policy_version": "v1",
            "performance_obligations": [
                {
                    "obligation_code": "OBL-A",
                    "description": "A",
                    "standalone_selling_price": "150.000000",
                    "allocation_basis": "ssp",
                    "recognition_method": "straight_line",
                },
                {
                    "obligation_code": "OBL-B",
                    "description": "B",
                    "standalone_selling_price": "150.000000",
                    "allocation_basis": "ssp",
                    "recognition_method": "straight_line",
                },
            ],
            "contract_line_items": [
                {
                    "line_code": "LINE-A",
                    "line_amount": "300.000000",
                    "line_currency": "USD",
                }
            ],
            "modifications": [],
        }
    )


@pytest.mark.asyncio
async def test_register_obligations_and_line_items_maps_single_obligation_default(
    async_session: AsyncSession,
    test_tenant,
) -> None:
    contract = _single_obligation_contract()
    registered_contracts = await register_contracts(
        async_session,
        tenant_id=test_tenant.id,
        user_id=test_tenant.id,
        correlation_id="corr-rev-obl-1",
        contracts=[contract],
    )

    result = await register_obligations_and_line_items(
        async_session,
        tenant_id=test_tenant.id,
        user_id=test_tenant.id,
        correlation_id="corr-rev-obl-1",
        contracts=[contract],
        registered_contracts=registered_contracts,
    )
    assert len(result.obligations) == 1
    assert len(result.line_items) == 1
    assert result.line_items[0].obligation_id == result.obligations[0].obligation_id
    assert result.line_items[0].recognition_method.value == "straight_line"


@pytest.mark.asyncio
async def test_register_obligations_requires_explicit_mapping_for_multi_obligation_contract(
    async_session: AsyncSession,
    test_tenant,
) -> None:
    contract = _multi_obligation_missing_line_mapping()
    registered_contracts = await register_contracts(
        async_session,
        tenant_id=test_tenant.id,
        user_id=test_tenant.id,
        correlation_id="corr-rev-obl-2",
        contracts=[contract],
    )

    with pytest.raises(ValidationError):
        await register_obligations_and_line_items(
            async_session,
            tenant_id=test_tenant.id,
            user_id=test_tenant.id,
            correlation_id="corr-rev-obl-2",
            contracts=[contract],
            registered_contracts=registered_contracts,
        )
