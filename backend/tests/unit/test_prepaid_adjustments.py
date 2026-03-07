from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.prepaid import Prepaid, PrepaidAdjustment, PrepaidRun
from financeops.schemas.prepaid import PrepaidAdjustmentInput
from financeops.services.prepaid.adjustments import (
    build_schedule_version_token,
    persist_adjustments,
)
from financeops.services.audit_writer import AuditWriter


def _uuid(value: str) -> UUID:
    return UUID(value)


@pytest.mark.asyncio
async def test_schedule_version_token_is_deterministic() -> None:
    token_a = build_schedule_version_token(
        prepaid_id=_uuid("00000000-0000-0000-0000-00000000f001"),
        pattern_normalized_json={"pattern_type": "straight_line", "periods": []},
        reporting_currency="USD",
        rate_mode="month_end_locked",
        adjustment_effective_date=date(2026, 1, 1),
        prior_schedule_version_token_or_root="root",
    )
    token_b = build_schedule_version_token(
        prepaid_id=_uuid("00000000-0000-0000-0000-00000000f001"),
        pattern_normalized_json={"pattern_type": "straight_line", "periods": []},
        reporting_currency="USD",
        rate_mode="month_end_locked",
        adjustment_effective_date=date(2026, 1, 1),
        prior_schedule_version_token_or_root="root",
    )
    assert token_a == token_b


@pytest.mark.asyncio
async def test_persist_adjustments_is_idempotent_and_chained(
    async_session: AsyncSession,
    test_tenant,
) -> None:
    run = await AuditWriter.insert_financial_record(
        async_session,
        model_class=PrepaidRun,
        tenant_id=test_tenant.id,
        record_data={"request_signature": "ppd-adj", "workflow_id": "wf-ppd-adj"},
        values={
            "request_signature": "ppd-adj",
            "initiated_by": test_tenant.id,
            "configuration_json": {"prepaids": []},
            "workflow_id": "wf-ppd-adj",
            "correlation_id": "00000000-0000-0000-0000-00000000f101",
        },
    )
    prepaid = await AuditWriter.insert_financial_record(
        async_session,
        model_class=Prepaid,
        tenant_id=test_tenant.id,
        record_data={"prepaid_code": "PPD-ADJ-1", "source_expense_reference": "SRC-PPD-ADJ-1"},
        values={
            "prepaid_code": "PPD-ADJ-1",
            "description": "adjustment",
            "prepaid_currency": "USD",
            "reporting_currency": "USD",
            "term_start_date": date(2026, 1, 1),
            "term_end_date": date(2026, 3, 31),
            "base_amount_contract_currency": Decimal("300.000000"),
            "period_frequency": "monthly",
            "pattern_type": "straight_line",
            "pattern_json_normalized": {"pattern_type": "straight_line", "periods": []},
            "rate_mode": "month_end_locked",
            "source_expense_reference": "SRC-PPD-ADJ-1",
            "parent_reference_id": None,
            "source_reference_id": _uuid("00000000-0000-0000-0000-00000000f201"),
            "correlation_id": "00000000-0000-0000-0000-00000000f101",
            "supersedes_id": None,
        },
    )

    adjustments = [
        PrepaidAdjustmentInput.model_validate(
            {
                "effective_date": "2026-02-01",
                "adjustment_type": "prospective",
                "adjustment_reason": "policy update",
                "idempotency_key": "adj-1",
                "catch_up_amount_reporting_currency": "5.000000",
            }
        )
    ]

    first = await persist_adjustments(
        async_session,
        tenant_id=test_tenant.id,
        run_id=run.id,
        prepaid_id=prepaid.id,
        source_expense_reference=prepaid.source_expense_reference,
        parent_reference_id=prepaid.id,
        source_reference_id=prepaid.source_reference_id,
        correlation_id="00000000-0000-0000-0000-00000000f101",
        user_id=test_tenant.id,
        adjustments=adjustments,
        root_schedule_version_token="root-token",
        pattern_normalized_json={"pattern_type": "straight_line", "periods": []},
        reporting_currency="USD",
        rate_mode="month_end_locked",
    )
    second = await persist_adjustments(
        async_session,
        tenant_id=test_tenant.id,
        run_id=run.id,
        prepaid_id=prepaid.id,
        source_expense_reference=prepaid.source_expense_reference,
        parent_reference_id=prepaid.id,
        source_reference_id=prepaid.source_reference_id,
        correlation_id="00000000-0000-0000-0000-00000000f101",
        user_id=test_tenant.id,
        adjustments=adjustments,
        root_schedule_version_token="root-token",
        pattern_normalized_json={"pattern_type": "straight_line", "periods": []},
        reporting_currency="USD",
        rate_mode="month_end_locked",
    )

    assert len(first) == 1
    assert first[0].new_schedule_version_token == second[0].new_schedule_version_token

    count = int(
        await async_session.scalar(
            select(func.count()).select_from(PrepaidAdjustment).where(
                PrepaidAdjustment.tenant_id == test_tenant.id,
                PrepaidAdjustment.run_id == run.id,
            )
        )
        or 0
    )
    assert count == 1
