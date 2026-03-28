from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.fixed_assets import Asset, FarRun
from financeops.platform.db.models import CpEntity
from financeops.schemas.fixed_assets import AssetDisposalInput
from financeops.services.audit_writer import AuditWriter
from financeops.services.fixed_assets.depreciation_engine import GeneratedDepreciationRow
from financeops.services.fixed_assets.disposal_handler import apply_disposals


def _uuid(value: str) -> UUID:
    return UUID(value)


def _rows() -> list[GeneratedDepreciationRow]:
    return [
        GeneratedDepreciationRow(
            asset_id=_uuid("00000000-0000-0000-0000-00000000f501"),
            period_seq=1,
            depreciation_date=date(2026, 1, 31),
            depreciation_period_year=2026,
            depreciation_period_month=1,
            schedule_version_token="root-token",
            opening_carrying_amount_reporting_currency=Decimal("1000.000000"),
            depreciation_amount_reporting_currency=Decimal("100.000000"),
            cumulative_depreciation_reporting_currency=Decimal("100.000000"),
            closing_carrying_amount_reporting_currency=Decimal("900.000000"),
            fx_rate_used=Decimal("1.000000"),
            fx_rate_date=date(2026, 1, 31),
            fx_rate_source="same_currency",
            schedule_status="scheduled",
            source_acquisition_reference="SRC-FAR-DISP-1",
            parent_reference_id=_uuid("00000000-0000-0000-0000-00000000f502"),
            source_reference_id=_uuid("00000000-0000-0000-0000-00000000f503"),
        ),
        GeneratedDepreciationRow(
            asset_id=_uuid("00000000-0000-0000-0000-00000000f501"),
            period_seq=2,
            depreciation_date=date(2026, 2, 28),
            depreciation_period_year=2026,
            depreciation_period_month=2,
            schedule_version_token="root-token",
            opening_carrying_amount_reporting_currency=Decimal("900.000000"),
            depreciation_amount_reporting_currency=Decimal("100.000000"),
            cumulative_depreciation_reporting_currency=Decimal("200.000000"),
            closing_carrying_amount_reporting_currency=Decimal("800.000000"),
            fx_rate_used=Decimal("1.000000"),
            fx_rate_date=date(2026, 2, 28),
            fx_rate_source="same_currency",
            schedule_status="scheduled",
            source_acquisition_reference="SRC-FAR-DISP-1",
            parent_reference_id=_uuid("00000000-0000-0000-0000-00000000f502"),
            source_reference_id=_uuid("00000000-0000-0000-0000-00000000f503"),
        ),
    ]


@pytest.mark.asyncio
async def test_apply_disposals_creates_event_and_stops_future_rows(
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
        record_data={"request_signature": "far-disp-run", "workflow_id": "wf-far-disp"},
        values={
            "request_signature": "far-disp-run",
            "initiated_by": test_tenant.id,
            "configuration_json": {"assets": []},
            "workflow_id": "wf-far-disp",
            "correlation_id": "corr-far-disp",
        },
    )
    asset = await AuditWriter.insert_financial_record(
        async_session,
        model_class=Asset,
        tenant_id=test_tenant.id,
        record_data={"asset_code": "FAR-DISP-001", "source_acquisition_reference": "SRC-FAR-DISP-1"},
        values={
            "asset_code": "FAR-DISP-001",
            "description": "disposal asset",
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
            "source_acquisition_reference": "SRC-FAR-DISP-1",
            "parent_reference_id": _uuid("00000000-0000-0000-0000-00000000f502"),
            "source_reference_id": _uuid("00000000-0000-0000-0000-00000000f503"),
            "correlation_id": "corr-far-disp",
            "supersedes_id": None,
        },
    )
    rows = [
        GeneratedDepreciationRow(
            asset_id=asset.id,
            period_seq=row.period_seq,
            depreciation_date=row.depreciation_date,
            depreciation_period_year=row.depreciation_period_year,
            depreciation_period_month=row.depreciation_period_month,
            schedule_version_token=row.schedule_version_token,
            opening_carrying_amount_reporting_currency=row.opening_carrying_amount_reporting_currency,
            depreciation_amount_reporting_currency=row.depreciation_amount_reporting_currency,
            cumulative_depreciation_reporting_currency=row.cumulative_depreciation_reporting_currency,
            closing_carrying_amount_reporting_currency=row.closing_carrying_amount_reporting_currency,
            fx_rate_used=row.fx_rate_used,
            fx_rate_date=row.fx_rate_date,
            fx_rate_source=row.fx_rate_source,
            schedule_status=row.schedule_status,
            source_acquisition_reference=row.source_acquisition_reference,
            parent_reference_id=row.parent_reference_id,
            source_reference_id=row.source_reference_id,
        )
        for row in _rows()
    ]

    events = [
        AssetDisposalInput.model_validate(
            {
                "disposal_date": "2026-02-15",
                "proceeds_reporting_currency": "700.000000",
                "disposal_cost_reporting_currency": "5.000000",
                "idempotency_key": "disp-1",
            }
        )
    ]

    result = await apply_disposals(
        async_session,
        tenant_id=test_tenant.id,
        run_id=run.id,
        user_id=test_tenant.id,
        correlation_id="00000000-0000-0000-0000-00000000f505",
        asset_id=asset.id,
        source_acquisition_reference="SRC-FAR-DISP-1",
        parent_reference_id=_uuid("00000000-0000-0000-0000-00000000f502"),
        source_reference_id=_uuid("00000000-0000-0000-0000-00000000f503"),
        depreciation_method="straight_line",
        useful_life_months=12,
        reducing_balance_rate_annual=None,
        residual_value_reporting_currency=Decimal("0.000000"),
        reporting_currency="USD",
        rate_mode="month_end_locked",
        current_rows=rows,
        disposals=events,
        prior_schedule_version_token="root-token",
    )

    assert len(result.events) == 1
    assert result.latest_schedule_version_token != "root-token"
    assert result.events[0].gain_loss_reporting_currency == Decimal("-151.428571")
