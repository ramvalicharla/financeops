from __future__ import annotations

import uuid
from datetime import date

import pytest

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.modules.mis_manager.infrastructure.repository import MisManagerRepository
from tests.integration.mis_phase1f1_helpers import (
    build_ingest_service,
    csv_b64,
    ensure_tenant_context,
    hash64,
)

ACCOUNTING_ENGINE_TABLES: tuple[str, ...] = (
    "revenue_runs",
    "revenue_schedules",
    "revenue_journal_entries",
    "lease_runs",
    "lease_liability_schedule",
    "lease_journal_entries",
    "prepaid_runs",
    "prepaid_amortization_schedule",
    "prepaid_journal_entries",
    "far_runs",
    "asset_depreciation_schedule",
    "asset_journal_entries",
)

FX_TABLES: tuple[str, ...] = (
    "fx_rate_fetch_runs",
    "fx_rate_quotes",
    "fx_manual_monthly_rates",
    "fx_variance_results",
)


async def _count_tables(
    session: AsyncSession,
    table_names: tuple[str, ...],
) -> dict[str, int]:
    result: dict[str, int] = {}
    for name in table_names:
        result[name] = int((await session.execute(text(f"SELECT COUNT(*) FROM {name}"))).scalar_one())
    return result


async def _create_template_version(session: AsyncSession, tenant_id: uuid.UUID) -> tuple:
    await ensure_tenant_context(session, tenant_id)
    service = build_ingest_service(session)
    commit = await service.commit_template_version(
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        template_code=f"isolation_{uuid.uuid4().hex[:8]}",
        template_name="Isolation Template",
        template_type="pnl_monthly",
        created_by=tenant_id,
        structure_hash=hash64("isolation:structure"),
        header_hash=hash64("isolation:header"),
        row_signature_hash=hash64("isolation:row"),
        column_signature_hash=hash64("isolation:column"),
        detection_summary_json={"seed": "isolation"},
        drift_reason=None,
        activate=True,
        effective_from=None,
    )
    return service, uuid.UUID(commit["template_id"]), uuid.UUID(commit["template_version_id"])


async def _run_mis_upload_flow(session: AsyncSession, tenant_id: uuid.UUID) -> dict:
    service, template_id, template_version_id = await _create_template_version(session, tenant_id)
    upload = await service.upload_snapshot(
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        template_id=template_id,
        template_version_id=template_version_id,
        reporting_period=date(2026, 1, 31),
        upload_artifact_id=uuid.uuid4(),
        file_name="snapshot.csv",
        file_content_base64=csv_b64(
            "Metric,Period_2026_01\nRevenue Net,1000\nMarketing Expense,200\n"
        ),
        sheet_name="csv",
        currency_code="USD",
        created_by=tenant_id,
    )
    return {"upload": upload}


async def _run_mis_finalize_flow(session: AsyncSession, tenant_id: uuid.UUID) -> dict:
    service, template_id, template_version_id = await _create_template_version(session, tenant_id)
    repository = MisManagerRepository(session)
    validated = await repository.insert_snapshot(
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        template_id=template_id,
        template_version_id=template_version_id,
        reporting_period=date(2026, 1, 31),
        upload_artifact_id=uuid.uuid4(),
        snapshot_token=hash64(f"isolation:validated:{uuid.uuid4()}"),
        source_file_hash=hash64("isolation:source"),
        sheet_name="csv",
        snapshot_status="validated",
        validation_summary_json={"status": "passed", "seed": "isolation"},
        created_by=tenant_id,
    )
    finalized = await service.finalize_snapshot(
        tenant_id=tenant_id,
        snapshot_id=validated.id,
        created_by=tenant_id,
    )
    return {"validated_snapshot_id": str(validated.id), "finalized": finalized}


@pytest.mark.asyncio
@pytest.mark.integration
async def test_mis_upload_does_not_modify_accounting_engine_tables(
    async_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    before = await _count_tables(async_session, ACCOUNTING_ENGINE_TABLES)
    await _run_mis_upload_flow(async_session, tenant_id)
    after = await _count_tables(async_session, ACCOUNTING_ENGINE_TABLES)
    assert after == before


@pytest.mark.asyncio
@pytest.mark.integration
async def test_mis_finalize_does_not_create_journal_rows(
    async_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    journal_tables = (
        "revenue_journal_entries",
        "lease_journal_entries",
        "prepaid_journal_entries",
        "asset_journal_entries",
    )
    before = await _count_tables(async_session, journal_tables)
    await _run_mis_finalize_flow(async_session, tenant_id)
    after = await _count_tables(async_session, journal_tables)
    assert after == before


@pytest.mark.asyncio
@pytest.mark.integration
async def test_mis_pipeline_does_not_invoke_fx_logic(
    async_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    before = await _count_tables(async_session, FX_TABLES)
    await _run_mis_upload_flow(async_session, tenant_id)
    await _run_mis_finalize_flow(async_session, tenant_id)
    after = await _count_tables(async_session, FX_TABLES)
    assert after == before
