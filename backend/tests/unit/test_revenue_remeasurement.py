from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.append_only import create_trigger_sql, drop_trigger_sql
from financeops.db.models.revenue import RevenueAdjustment, RevenueContract, RevenueRun, RevenueSchedule
from financeops.schemas.revenue import RevenueContractInput
from financeops.services.accounting_common.accounting_errors import AccountingValidationError
from financeops.services.accounting_common.error_codes import DUPLICATE_IDEMPOTENT_REQUEST
from financeops.services.audit_writer import AuditWriter
from financeops.services.revenue.contract_registry import register_contracts
from financeops.services.revenue.obligation_tracker import register_obligations_and_line_items
from financeops.services.revenue.remeasurement import apply_contract_modifications


def _contract_payload_with_modification() -> RevenueContractInput:
    return RevenueContractInput.model_validate(
        {
            "contract_number": "REV-REM-001",
            "customer_id": "CUST-REM",
            "contract_currency": "USD",
            "contract_start_date": "2026-01-01",
            "contract_end_date": "2026-12-31",
            "total_contract_value": "120.000000",
            "source_contract_reference": "SRC-REM-001",
            "policy_code": "ASC606",
            "policy_version": "v1",
            "performance_obligations": [
                {
                    "obligation_code": "OBL-REM",
                    "description": "Remeasureable obligation",
                    "standalone_selling_price": "120.000000",
                    "allocation_basis": "ssp",
                    "recognition_method": "straight_line",
                }
            ],
            "contract_line_items": [
                {
                    "line_code": "LINE-REM",
                    "obligation_code": "OBL-REM",
                    "line_amount": "120.000000",
                    "line_currency": "USD",
                    "recognition_method": "straight_line",
                    "recognition_start_date": "2026-01-01",
                    "recognition_end_date": "2026-12-31",
                }
            ],
            "modifications": [
                {
                    "effective_date": "2026-06-30",
                    "adjustment_type": "contract_modification",
                    "adjustment_reason": "Scope increased",
                    "new_total_contract_value": "180.000000",
                    "requires_catch_up": True,
                }
            ],
        }
    )


@pytest.mark.asyncio
async def test_apply_contract_modifications_creates_superseding_contract_and_adjustment(
    async_session: AsyncSession,
    test_tenant,
) -> None:
    contract_input = _contract_payload_with_modification()
    registered_contracts = await register_contracts(
        async_session,
        tenant_id=test_tenant.id,
        user_id=test_tenant.id,
        correlation_id="corr-rev-rem-1",
        contracts=[contract_input],
    )
    obligation_set = await register_obligations_and_line_items(
        async_session,
        tenant_id=test_tenant.id,
        user_id=test_tenant.id,
        correlation_id="corr-rev-rem-1",
        contracts=[contract_input],
        registered_contracts=registered_contracts,
    )

    run = await AuditWriter.insert_financial_record(
        async_session,
        model_class=RevenueRun,
        tenant_id=test_tenant.id,
        record_data={
            "request_signature": "rev-rem-signature",
            "workflow_id": "rev-rem-workflow",
        },
        values={
            "request_signature": "rev-rem-signature",
            "initiated_by": test_tenant.id,
            "configuration_json": {"reporting_currency": "USD", "rate_mode": "daily", "contracts": []},
            "workflow_id": "rev-rem-workflow",
            "correlation_id": "corr-rev-rem-1",
        },
    )

    current_contract = (
        await async_session.execute(
            select(RevenueContract).where(RevenueContract.id == registered_contracts[0].contract_id)
        )
    ).scalar_one()

    await AuditWriter.insert_financial_record(
        async_session,
        model_class=RevenueSchedule,
        tenant_id=test_tenant.id,
        record_data={
            "run_id": str(run.id),
            "contract_id": str(current_contract.id),
            "obligation_id": str(obligation_set.obligations[0].obligation_id),
            "contract_line_item_id": str(obligation_set.line_items[0].line_item_id),
            "recognition_date": "2026-03-31",
        },
        values={
            "run_id": run.id,
            "contract_id": current_contract.id,
            "obligation_id": obligation_set.obligations[0].obligation_id,
            "contract_line_item_id": obligation_set.line_items[0].line_item_id,
            "period_seq": 1,
            "recognition_date": contract_input.contract_start_date,
            "recognition_period_year": 2026,
            "recognition_period_month": 1,
            "schedule_version_token": "root",
            "recognition_method": "straight_line",
            "base_amount_contract_currency": Decimal("10.000000"),
            "fx_rate_used": Decimal("1.000000"),
            "recognized_amount_reporting_currency": Decimal("10.000000"),
            "cumulative_recognized_reporting_currency": Decimal("10.000000"),
            "schedule_status": "recognized",
            "source_contract_reference": current_contract.source_contract_reference,
            "parent_reference_id": current_contract.id,
            "source_reference_id": current_contract.id,
            "correlation_id": "corr-rev-rem-1",
        },
    )

    result = await apply_contract_modifications(
        async_session,
        tenant_id=test_tenant.id,
        user_id=test_tenant.id,
        run_id=run.id,
        correlation_id="corr-rev-rem-1",
        contracts=[contract_input],
        registered_contracts=registered_contracts,
        root_schedule_version_tokens={current_contract.id: "root"},
        reporting_currency="USD",
        rate_mode="daily",
    )

    assert result.adjustment_count == 1

    adjustments = (
        await async_session.execute(
            select(RevenueAdjustment).where(
                RevenueAdjustment.tenant_id == test_tenant.id,
                RevenueAdjustment.run_id == run.id,
            )
        )
    ).scalars().all()
    assert len(adjustments) == 1
    assert adjustments[0].adjustment_type == "contract_modification"

    superseding_contracts = (
        await async_session.execute(
            select(RevenueContract).where(
                RevenueContract.tenant_id == test_tenant.id,
                RevenueContract.supersedes_id == current_contract.id,
                RevenueContract.total_contract_value == Decimal("180.000000"),
            )
        )
    ).scalars().all()
    assert len(superseding_contracts) == 1
    first_token = adjustments[0].new_schedule_version_token

    replay = await apply_contract_modifications(
        async_session,
        tenant_id=test_tenant.id,
        user_id=test_tenant.id,
        run_id=run.id,
        correlation_id="corr-rev-rem-1",
        contracts=[contract_input],
        registered_contracts=registered_contracts,
        root_schedule_version_tokens={current_contract.id: "root"},
        reporting_currency="USD",
        rate_mode="daily",
    )
    assert replay.adjustment_count == 0
    replay_adjustments = (
        await async_session.execute(
            select(RevenueAdjustment).where(
                RevenueAdjustment.tenant_id == test_tenant.id,
                RevenueAdjustment.run_id == run.id,
            )
        )
    ).scalars().all()
    assert len(replay_adjustments) == 1
    assert replay_adjustments[0].new_schedule_version_token == first_token


@pytest.mark.asyncio
async def test_apply_contract_modifications_rejects_idempotency_conflict(
    async_session: AsyncSession,
    test_tenant,
) -> None:
    tenant_id = test_tenant.id
    contract_input = _contract_payload_with_modification()
    registered_contracts = await register_contracts(
        async_session,
        tenant_id=tenant_id,
        user_id=tenant_id,
        correlation_id="corr-rev-rem-conflict",
        contracts=[contract_input],
    )
    obligation_set = await register_obligations_and_line_items(
        async_session,
        tenant_id=tenant_id,
        user_id=tenant_id,
        correlation_id="corr-rev-rem-conflict",
        contracts=[contract_input],
        registered_contracts=registered_contracts,
    )
    run = await AuditWriter.insert_financial_record(
        async_session,
        model_class=RevenueRun,
        tenant_id=tenant_id,
        record_data={"request_signature": "rev-rem-conflict", "workflow_id": "rev-rem-conflict"},
        values={
            "request_signature": "rev-rem-conflict",
            "initiated_by": tenant_id,
            "configuration_json": {"reporting_currency": "USD", "rate_mode": "daily", "contracts": []},
            "workflow_id": "rev-rem-conflict",
            "correlation_id": "corr-rev-rem-conflict",
        },
    )
    run_id = run.id
    current_contract = (
        await async_session.execute(
            select(RevenueContract).where(RevenueContract.id == registered_contracts[0].contract_id)
        )
    ).scalar_one()
    current_contract_id = current_contract.id
    await AuditWriter.insert_financial_record(
        async_session,
        model_class=RevenueSchedule,
        tenant_id=tenant_id,
        record_data={
                "run_id": str(run.id),
                "contract_id": str(current_contract_id),
            "obligation_id": str(obligation_set.obligations[0].obligation_id),
            "contract_line_item_id": str(obligation_set.line_items[0].line_item_id),
            "recognition_date": "2026-01-31",
        },
        values={
            "run_id": run_id,
            "contract_id": current_contract_id,
            "obligation_id": obligation_set.obligations[0].obligation_id,
            "contract_line_item_id": obligation_set.line_items[0].line_item_id,
            "period_seq": 1,
            "recognition_date": date(2026, 1, 31),
            "recognition_period_year": 2026,
            "recognition_period_month": 1,
            "schedule_version_token": "root",
            "recognition_method": "straight_line",
            "base_amount_contract_currency": Decimal("10.000000"),
            "fx_rate_used": Decimal("1.000000"),
            "recognized_amount_reporting_currency": Decimal("10.000000"),
            "cumulative_recognized_reporting_currency": Decimal("10.000000"),
            "schedule_status": "recognized",
            "source_contract_reference": current_contract.source_contract_reference,
            "parent_reference_id": current_contract.id,
            "source_reference_id": current_contract.id,
            "correlation_id": "corr-rev-rem-conflict",
        },
    )
    await apply_contract_modifications(
        async_session,
        tenant_id=tenant_id,
        user_id=tenant_id,
        run_id=run_id,
        correlation_id="corr-rev-rem-conflict",
        contracts=[contract_input],
        registered_contracts=registered_contracts,
        root_schedule_version_tokens={current_contract_id: "root"},
        reporting_currency="USD",
        rate_mode="daily",
    )
    # Simulate tampered persisted state for idempotency conflict validation.
    # revenue_adjustments is append-only in production; this unit test intentionally
    # bypasses the trigger to inject a corrupted value.
    await async_session.execute(text(drop_trigger_sql("revenue_adjustments")))
    await async_session.execute(
        text(
            "UPDATE revenue_adjustments "
            "SET new_schedule_version_token='tampered' "
            "WHERE run_id = :run_id AND tenant_id = :tenant_id"
        ),
        {"run_id": str(run_id), "tenant_id": str(tenant_id)},
    )
    await async_session.execute(text(create_trigger_sql("revenue_adjustments")))
    async_session.expire_all()

    with pytest.raises(AccountingValidationError) as exc:
        await apply_contract_modifications(
            async_session,
            tenant_id=tenant_id,
            user_id=tenant_id,
            run_id=run_id,
            correlation_id="corr-rev-rem-conflict",
            contracts=[contract_input],
            registered_contracts=registered_contracts,
            root_schedule_version_tokens={current_contract_id: "root"},
            reporting_currency="USD",
            rate_mode="daily",
        )
    assert exc.value.error_code == DUPLICATE_IDEMPOTENT_REQUEST
