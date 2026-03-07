from __future__ import annotations

from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.services.audit_writer import AuditWriter
from financeops.services.revenue.contract_registry import register_contracts
from financeops.schemas.revenue import RevenueContractInput


def _contract_payload(contract_number: str) -> RevenueContractInput:
    return RevenueContractInput.model_validate(
        {
            "contract_number": contract_number,
            "customer_id": "CUST-1",
            "contract_currency": "USD",
            "contract_start_date": "2026-01-01",
            "contract_end_date": "2026-03-31",
            "total_contract_value": "300.000000",
            "source_contract_reference": f"SRC-{contract_number}",
            "policy_code": "ASC606",
            "policy_version": "v1",
            "performance_obligations": [
                {
                    "obligation_code": "OBL-1",
                    "description": "Support services",
                    "standalone_selling_price": "300.000000",
                    "allocation_basis": "ssp",
                    "recognition_method": "straight_line",
                }
            ],
            "contract_line_items": [
                {
                    "line_code": "LINE-1",
                    "obligation_code": "OBL-1",
                    "line_amount": "300.000000",
                    "line_currency": "USD",
                    "recognition_method": "straight_line",
                    "recognition_start_date": "2026-01-01",
                    "recognition_end_date": "2026-03-31",
                }
            ],
            "modifications": [],
        }
    )


@pytest.mark.asyncio
async def test_register_contracts_uses_audit_writer(
    async_session: AsyncSession,
    test_tenant,
) -> None:
    contract = _contract_payload("REV-100")
    with patch(
        "financeops.services.revenue.contract_registry.AuditWriter.insert_financial_record",
        wraps=AuditWriter.insert_financial_record,
    ) as spy:
        rows = await register_contracts(
            async_session,
            tenant_id=test_tenant.id,
            user_id=test_tenant.id,
            correlation_id="corr-rev-contract",
            contracts=[contract],
        )
    assert len(rows) == 1
    assert spy.await_count == 1


@pytest.mark.asyncio
async def test_register_contracts_is_idempotent_for_same_correlation(
    async_session: AsyncSession,
    test_tenant,
) -> None:
    contract = _contract_payload("REV-200")
    first = await register_contracts(
        async_session,
        tenant_id=test_tenant.id,
        user_id=test_tenant.id,
        correlation_id="corr-rev-idempotent",
        contracts=[contract],
    )
    second = await register_contracts(
        async_session,
        tenant_id=test_tenant.id,
        user_id=test_tenant.id,
        correlation_id="corr-rev-idempotent",
        contracts=[contract],
    )
    assert len(first) == 1
    assert len(second) == 1
    assert first[0].contract_id == second[0].contract_id
