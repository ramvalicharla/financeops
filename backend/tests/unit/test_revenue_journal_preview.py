from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

import pytest

from financeops.db.models.revenue import RevenueSchedule
from financeops.services.revenue.journal_preview import build_revenue_journal_preview


def _uuid(value: str) -> UUID:
    return UUID(value)


@pytest.mark.asyncio
async def test_revenue_journal_preview_builds_deterministic_namespaced_rows() -> None:
    run_id = _uuid("00000000-0000-0000-0000-000000000931")
    schedule_1 = RevenueSchedule(
        id=_uuid("00000000-0000-0000-0000-000000000932"),
        tenant_id=_uuid("00000000-0000-0000-0000-000000000999"),
        chain_hash="a" * 64,
        previous_hash="0" * 64,
        run_id=run_id,
        contract_id=_uuid("00000000-0000-0000-0000-000000000933"),
        obligation_id=_uuid("00000000-0000-0000-0000-000000000934"),
        contract_line_item_id=_uuid("00000000-0000-0000-0000-000000000935"),
        period_seq=1,
        recognition_date=date(2026, 1, 31),
        recognition_period_year=2026,
        recognition_period_month=1,
        schedule_version_token="root",
        recognition_method="straight_line",
        base_amount_contract_currency=Decimal("100.000000"),
        fx_rate_used=Decimal("1.000000"),
        recognized_amount_reporting_currency=Decimal("100.000000"),
        cumulative_recognized_reporting_currency=Decimal("100.000000"),
        schedule_status="recognized",
        source_contract_reference="SRC-1",
        parent_reference_id=_uuid("00000000-0000-0000-0000-000000000934"),
        source_reference_id=_uuid("00000000-0000-0000-0000-000000000935"),
        correlation_id="00000000-0000-0000-0000-000000000111",
    )
    schedule_2 = RevenueSchedule(
        id=_uuid("00000000-0000-0000-0000-000000000936"),
        tenant_id=_uuid("00000000-0000-0000-0000-000000000999"),
        chain_hash="b" * 64,
        previous_hash="0" * 64,
        run_id=run_id,
        contract_id=_uuid("00000000-0000-0000-0000-000000000933"),
        obligation_id=_uuid("00000000-0000-0000-0000-000000000934"),
        contract_line_item_id=_uuid("00000000-0000-0000-0000-000000000937"),
        period_seq=2,
        recognition_date=date(2026, 2, 28),
        recognition_period_year=2026,
        recognition_period_month=2,
        schedule_version_token="root",
        recognition_method="straight_line",
        base_amount_contract_currency=Decimal("100.000000"),
        fx_rate_used=Decimal("1.000000"),
        recognized_amount_reporting_currency=Decimal("100.000000"),
        cumulative_recognized_reporting_currency=Decimal("200.000000"),
        schedule_status="recognized",
        source_contract_reference="SRC-1",
        parent_reference_id=_uuid("00000000-0000-0000-0000-000000000934"),
        source_reference_id=_uuid("00000000-0000-0000-0000-000000000937"),
        correlation_id="00000000-0000-0000-0000-000000000111",
    )

    preview = build_revenue_journal_preview(run_id=run_id, schedules=[schedule_2, schedule_1])
    assert len(preview) == 2
    assert preview[0].journal_reference.startswith("REV-")
    assert preview[1].journal_reference.startswith("REV-")
    assert preview[0].entry_date == date(2026, 1, 31)
    assert preview[1].entry_date == date(2026, 2, 28)
    assert preview[0].parent_reference_id == schedule_1.id
    assert preview[0].source_reference_id == schedule_1.contract_line_item_id
