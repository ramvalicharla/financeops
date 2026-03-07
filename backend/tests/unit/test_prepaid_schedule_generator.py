from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.services.prepaid.adjustments import PersistedAdjustment
from financeops.services.prepaid.pattern_resolver import normalize_pattern
from financeops.services.prepaid.prepaid_registry import RegisteredPrepaid
from financeops.services.prepaid.schedule_generator import (
    MissingLockedRateError,
    generate_schedule_rows,
)
from financeops.core.exceptions import ValidationError
from financeops.schemas.prepaid import PrepaidInput


def _uuid(value: str) -> UUID:
    return UUID(value)


def _registered_prepaid(payload: dict, prepaid_id: str) -> RegisteredPrepaid:
    model = PrepaidInput.model_validate(payload)
    normalized = normalize_pattern(model)
    return RegisteredPrepaid(
        prepaid_id=_uuid(prepaid_id),
        prepaid_code=model.prepaid_code,
        prepaid_currency=model.prepaid_currency,
        reporting_currency=model.reporting_currency,
        term_start_date=model.term_start_date,
        term_end_date=model.term_end_date,
        base_amount_contract_currency=model.base_amount_contract_currency,
        period_frequency=model.period_frequency,
        pattern_type=model.pattern_type.value,
        normalized_pattern=normalized,
        rate_mode=model.rate_mode.value,
        source_expense_reference=model.source_expense_reference,
        parent_reference_id=model.parent_reference_id,
        source_reference_id=model.source_reference_id,
        adjustments=list(model.adjustments),
    )


@pytest.mark.asyncio
async def test_schedule_generator_straight_line_is_deterministic(async_session: AsyncSession, test_tenant) -> None:
    prepaid = _registered_prepaid(
        {
            "prepaid_code": "PPD-SCHED-1",
            "description": "straight line",
            "prepaid_currency": "USD",
            "reporting_currency": "USD",
            "term_start_date": "2026-01-01",
            "term_end_date": "2026-03-31",
            "base_amount_contract_currency": "300.000000",
            "period_frequency": "monthly",
            "pattern_type": "straight_line",
            "rate_mode": "month_end_locked",
            "source_expense_reference": "SRC-PPD-SCHED-1",
            "source_reference_id": "00000000-0000-0000-0000-00000000d001",
        },
        "00000000-0000-0000-0000-00000000d101",
    )

    output = await generate_schedule_rows(
        async_session,
        tenant_id=test_tenant.id,
        prepaids=[prepaid],
        adjustment_map={},
    )

    assert len(output.rows) == 3
    assert sum((row.base_amount_contract_currency for row in output.rows), start=Decimal("0")) == Decimal(
        "300.000000"
    )
    assert {row.recognition_period_month for row in output.rows} == {1, 2, 3}


@pytest.mark.asyncio
async def test_schedule_generator_assigns_residual_to_anchor(async_session: AsyncSession, test_tenant) -> None:
    prepaid = _registered_prepaid(
        {
            "prepaid_code": "PPD-SCHED-2",
            "description": "weighted",
            "prepaid_currency": "USD",
            "reporting_currency": "USD",
            "term_start_date": "2026-01-01",
            "term_end_date": "2026-03-31",
            "base_amount_contract_currency": "100.000000",
            "period_frequency": "monthly",
            "pattern_type": "weighted_period",
            "rate_mode": "month_end_locked",
            "source_expense_reference": "SRC-PPD-SCHED-2",
            "source_reference_id": "00000000-0000-0000-0000-00000000d002",
            "periods": [
                {
                    "period_seq": 1,
                    "period_start_date": "2026-01-01",
                    "period_end_date": "2026-01-31",
                    "recognition_date": "2026-01-31",
                    "weight": "1",
                },
                {
                    "period_seq": 2,
                    "period_start_date": "2026-02-01",
                    "period_end_date": "2026-02-28",
                    "recognition_date": "2026-02-28",
                    "weight": "1",
                },
                {
                    "period_seq": 3,
                    "period_start_date": "2026-03-01",
                    "period_end_date": "2026-03-31",
                    "recognition_date": "2026-03-31",
                    "weight": "1",
                },
            ],
        },
        "00000000-0000-0000-0000-00000000d102",
    )

    output = await generate_schedule_rows(
        async_session,
        tenant_id=test_tenant.id,
        prepaids=[prepaid],
        adjustment_map={},
    )

    first_row = sorted(output.rows, key=lambda row: row.period_seq)[0]
    assert first_row.base_amount_contract_currency == Decimal("33.333334")


@pytest.mark.asyncio
async def test_schedule_generator_missing_month_end_lock_raises(async_session: AsyncSession, test_tenant) -> None:
    prepaid = _registered_prepaid(
        {
            "prepaid_code": "PPD-SCHED-3",
            "description": "fx lock",
            "prepaid_currency": "EUR",
            "reporting_currency": "USD",
            "term_start_date": "2026-01-01",
            "term_end_date": "2026-01-31",
            "base_amount_contract_currency": "100.000000",
            "period_frequency": "monthly",
            "pattern_type": "straight_line",
            "rate_mode": "month_end_locked",
            "source_expense_reference": "SRC-PPD-SCHED-3",
            "source_reference_id": "00000000-0000-0000-0000-00000000d003",
        },
        "00000000-0000-0000-0000-00000000d103",
    )

    with patch(
        "financeops.services.prepaid.schedule_generator.list_manual_monthly_rates",
        new=AsyncMock(return_value=[]),
    ):
        with pytest.raises(MissingLockedRateError):
            await generate_schedule_rows(
                async_session,
                tenant_id=test_tenant.id,
                prepaids=[prepaid],
                adjustment_map={},
            )


@pytest.mark.asyncio
async def test_schedule_generator_uses_selected_rate_surface_for_daily_selected(
    async_session: AsyncSession,
    test_tenant,
) -> None:
    prepaid = _registered_prepaid(
        {
            "prepaid_code": "PPD-SCHED-4",
            "description": "daily selected",
            "prepaid_currency": "EUR",
            "reporting_currency": "USD",
            "term_start_date": "2026-01-01",
            "term_end_date": "2026-01-31",
            "base_amount_contract_currency": "100.000000",
            "period_frequency": "monthly",
            "pattern_type": "straight_line",
            "rate_mode": "daily_selected",
            "source_expense_reference": "SRC-PPD-SCHED-4",
            "source_reference_id": "00000000-0000-0000-0000-00000000d004",
        },
        "00000000-0000-0000-0000-00000000d104",
    )

    with patch(
        "financeops.services.prepaid.schedule_generator._tenant_allows_daily_selected",
        new=AsyncMock(return_value=True),
    ), patch(
        "financeops.services.prepaid.schedule_generator.resolve_selected_rate",
        new=AsyncMock(
            return_value=SimpleNamespace(
                selected_rate=Decimal("1.250000"),
                selected_source="provider_consensus",
            )
        ),
    ) as selected_spy:
        output = await generate_schedule_rows(
            async_session,
            tenant_id=test_tenant.id,
            prepaids=[prepaid],
            adjustment_map={
                prepaid.prepaid_id: [
                    PersistedAdjustment(
                        adjustment_id=_uuid("00000000-0000-0000-0000-00000000d201"),
                        effective_date=prepaid.term_start_date,
                        adjustment_type="prospective",
                        idempotency_key="adj-key",
                        prior_schedule_version_token="prior",
                        new_schedule_version_token="new",
                        catch_up_amount_reporting_currency=Decimal("0.000000"),
                    )
                ]
            },
        )

    assert output.rows
    assert selected_spy.await_count >= 1


@pytest.mark.asyncio
async def test_schedule_generator_rejects_daily_selected_without_tenant_policy(
    async_session: AsyncSession,
    test_tenant,
) -> None:
    prepaid = _registered_prepaid(
        {
            "prepaid_code": "PPD-SCHED-5",
            "description": "daily selected blocked",
            "prepaid_currency": "EUR",
            "reporting_currency": "USD",
            "term_start_date": "2026-01-01",
            "term_end_date": "2026-01-31",
            "base_amount_contract_currency": "100.000000",
            "period_frequency": "monthly",
            "pattern_type": "straight_line",
            "rate_mode": "daily_selected",
            "source_expense_reference": "SRC-PPD-SCHED-5",
            "source_reference_id": "00000000-0000-0000-0000-00000000d005",
        },
        "00000000-0000-0000-0000-00000000d105",
    )

    with patch(
        "financeops.services.prepaid.schedule_generator._tenant_allows_daily_selected",
        new=AsyncMock(return_value=False),
    ):
        with pytest.raises(ValidationError):
            await generate_schedule_rows(
                async_session,
                tenant_id=test_tenant.id,
                prepaids=[prepaid],
                adjustment_map={},
            )
