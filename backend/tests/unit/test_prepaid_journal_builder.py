from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

import pytest

from financeops.db.models.prepaid import PrepaidAmortizationSchedule
from financeops.services.prepaid.journal_builder import build_prepaid_journal_preview


def _uuid(value: str) -> UUID:
    return UUID(value)


@pytest.mark.asyncio
async def test_prepaid_journal_builder_creates_deterministic_ppd_namespace_rows() -> None:
    run_id = _uuid("00000000-0000-0000-0000-00000000e001")
    schedule_1 = PrepaidAmortizationSchedule(
        id=_uuid("00000000-0000-0000-0000-00000000e011"),
        tenant_id=_uuid("00000000-0000-0000-0000-00000000eff1"),
        chain_hash="a" * 64,
        previous_hash="0" * 64,
        run_id=run_id,
        prepaid_id=_uuid("00000000-0000-0000-0000-00000000e101"),
        period_seq=1,
        amortization_date=date(2026, 1, 31),
        recognition_period_year=2026,
        recognition_period_month=1,
        schedule_version_token="tok-a",
        base_amount_contract_currency=Decimal("100.000000"),
        amortized_amount_reporting_currency=Decimal("100.000000"),
        cumulative_amortized_reporting_currency=Decimal("100.000000"),
        fx_rate_used=Decimal("1.000000"),
        fx_rate_date=date(2026, 1, 31),
        fx_rate_source="same_currency_1_0",
        schedule_status="scheduled",
        source_expense_reference="SRC-PPD-1",
        parent_reference_id=_uuid("00000000-0000-0000-0000-00000000e101"),
        source_reference_id=_uuid("00000000-0000-0000-0000-00000000e901"),
        correlation_id="00000000-0000-0000-0000-00000000e999",
    )
    schedule_2 = PrepaidAmortizationSchedule(
        id=_uuid("00000000-0000-0000-0000-00000000e012"),
        tenant_id=_uuid("00000000-0000-0000-0000-00000000eff1"),
        chain_hash="b" * 64,
        previous_hash="0" * 64,
        run_id=run_id,
        prepaid_id=_uuid("00000000-0000-0000-0000-00000000e101"),
        period_seq=2,
        amortization_date=date(2026, 2, 28),
        recognition_period_year=2026,
        recognition_period_month=2,
        schedule_version_token="tok-a",
        base_amount_contract_currency=Decimal("100.000000"),
        amortized_amount_reporting_currency=Decimal("100.000000"),
        cumulative_amortized_reporting_currency=Decimal("200.000000"),
        fx_rate_used=Decimal("1.000000"),
        fx_rate_date=date(2026, 2, 28),
        fx_rate_source="same_currency_1_0",
        schedule_status="scheduled",
        source_expense_reference="SRC-PPD-1",
        parent_reference_id=_uuid("00000000-0000-0000-0000-00000000e101"),
        source_reference_id=_uuid("00000000-0000-0000-0000-00000000e902"),
        correlation_id="00000000-0000-0000-0000-00000000e999",
    )

    preview = build_prepaid_journal_preview(run_id=run_id, schedule_rows=[schedule_2, schedule_1])

    assert len(preview) == 2
    assert preview[0].journal_reference.startswith("PPD-")
    assert preview[1].journal_reference.startswith("PPD-")
    assert preview[0].entry_date == date(2026, 1, 31)
    assert preview[0].parent_reference_id == schedule_1.id
