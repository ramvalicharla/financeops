from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.fixed_assets import (
    Asset,
    AssetDepreciationSchedule,
    AssetJournalEntry,
    FarRun,
)
from financeops.platform.db.models import CpEntity
from financeops.services.audit_writer import AuditWriter
from financeops.services.fixed_assets.drilldown_service import (
    get_asset_drill,
    get_depreciation_drill,
    get_journal_drill,
)


@pytest.mark.asyncio
async def test_fixed_assets_drilldown_returns_lineage_navigation(
    async_session: AsyncSession,
    test_tenant,
    test_user,
) -> None:
    del test_user
    entity_id = await async_session.scalar(
        select(CpEntity.id).where(CpEntity.tenant_id == test_tenant.id).limit(1)
    )
    assert entity_id is not None

    run = await AuditWriter.insert_financial_record(
        async_session,
        model_class=FarRun,
        tenant_id=test_tenant.id,
        record_data={"request_signature": f"far-drill-{uuid.uuid4()}", "workflow_id": "wf-far-drill"},
        values={
            "request_signature": f"far-drill-{uuid.uuid4()}",
            "initiated_by": test_tenant.id,
            "configuration_json": {"assets": []},
            "workflow_id": "wf-far-drill",
            "correlation_id": str(uuid.uuid4()),
        },
    )
    asset = await AuditWriter.insert_financial_record(
        async_session,
        model_class=Asset,
        tenant_id=test_tenant.id,
        record_data={"asset_code": "FAR-DRILL-001", "source_acquisition_reference": "SRC-FAR-DRILL-1"},
        values={
            "asset_code": "FAR-DRILL-001",
            "description": "drill asset",
            "entity_id": entity_id,
            "asset_class": "equipment",
            "asset_currency": "USD",
            "reporting_currency": "USD",
            "capitalization_date": date(2026, 1, 1),
            "in_service_date": date(2026, 1, 1),
            "capitalized_amount_asset_currency": Decimal("1000.000000"),
            "depreciation_method": "straight_line",
            "useful_life_months": 12,
            "reducing_balance_rate_annual": None,
            "residual_value_reporting_currency": Decimal("0.000000"),
            "rate_mode": "month_end_locked",
            "source_acquisition_reference": "SRC-FAR-DRILL-1",
            "parent_reference_id": None,
            "source_reference_id": test_tenant.id,
            "correlation_id": str(uuid.uuid4()),
            "supersedes_id": None,
        },
    )
    schedule = await AuditWriter.insert_financial_record(
        async_session,
        model_class=AssetDepreciationSchedule,
        tenant_id=test_tenant.id,
        record_data={
            "run_id": str(run.id),
            "asset_id": str(asset.id),
            "period_seq": 1,
            "depreciation_date": "2026-01-31",
            "schedule_version_token": "tok-drill",
        },
        values={
            "run_id": run.id,
            "asset_id": asset.id,
            "period_seq": 1,
            "depreciation_date": date(2026, 1, 31),
            "depreciation_period_year": 2026,
            "depreciation_period_month": 1,
            "schedule_version_token": "tok-drill",
            "opening_carrying_amount_reporting_currency": Decimal("1000.000000"),
            "depreciation_amount_reporting_currency": Decimal("100.000000"),
            "cumulative_depreciation_reporting_currency": Decimal("100.000000"),
            "closing_carrying_amount_reporting_currency": Decimal("900.000000"),
            "fx_rate_used": Decimal("1.000000"),
            "fx_rate_date": date(2026, 1, 31),
            "fx_rate_source": "same_currency",
            "schedule_status": "scheduled",
            "source_acquisition_reference": "SRC-FAR-DRILL-1",
            "parent_reference_id": asset.id,
            "source_reference_id": asset.source_reference_id,
            "correlation_id": str(uuid.uuid4()),
        },
    )
    journal = await AuditWriter.insert_financial_record(
        async_session,
        model_class=AssetJournalEntry,
        tenant_id=test_tenant.id,
        record_data={
            "run_id": str(run.id),
            "asset_id": str(asset.id),
            "journal_reference": "FAR-TEST-1",
            "line_seq": 1,
        },
        values={
            "run_id": run.id,
            "asset_id": asset.id,
            "depreciation_schedule_id": schedule.id,
            "impairment_id": None,
            "disposal_id": None,
            "journal_reference": "FAR-TEST-1",
            "line_seq": 1,
            "entry_date": date(2026, 1, 31),
            "debit_account": "Depreciation Expense",
            "credit_account": "Accumulated Depreciation",
            "amount_reporting_currency": Decimal("100.000000"),
            "source_acquisition_reference": "SRC-FAR-DRILL-1",
            "parent_reference_id": schedule.id,
            "source_reference_id": asset.source_reference_id,
            "correlation_id": str(uuid.uuid4()),
        },
    )

    asset_drill = await get_asset_drill(
        async_session,
        tenant_id=test_tenant.id,
        run_id=run.id,
        asset_id=asset.id,
    )
    dep_drill = await get_depreciation_drill(
        async_session,
        tenant_id=test_tenant.id,
        run_id=run.id,
        line_id=schedule.id,
    )
    journal_drill = await get_journal_drill(
        async_session,
        tenant_id=test_tenant.id,
        run_id=run.id,
        journal_id=journal.id,
    )

    assert asset_drill["id"] == asset.id
    assert schedule.id in asset_drill["child_ids"]
    assert dep_drill["id"] == schedule.id
    assert journal_drill["id"] == journal.id
    assert journal_drill["depreciation_schedule_id"] == schedule.id
