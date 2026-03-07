from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.normalization_phase1f3_helpers import (
    build_normalization_service,
    csv_b64,
    ensure_tenant_context,
)

ENGINE_TABLES = (
    "revenue_schedules",
    "lease_liability_schedule",
    "prepaid_amortization_schedule",
    "asset_depreciation_schedule",
)

JOURNAL_TABLES = (
    "revenue_journal_entries",
    "lease_journal_entries",
    "prepaid_journal_entries",
    "asset_journal_entries",
)

RECON_TABLES = (
    "reconciliation_sessions",
    "reconciliation_lines",
    "reconciliation_exceptions",
    "reconciliation_resolution_events",
    "reconciliation_evidence_links",
)

FX_TABLES = (
    "fx_rate_fetch_runs",
    "fx_rate_quotes",
    "fx_manual_monthly_rates",
    "fx_variance_results",
)


async def _table_counts(session: AsyncSession, table_names: tuple[str, ...]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table_name in table_names:
        count = (await session.execute(text(f"SELECT COUNT(*) FROM {table_name}"))).scalar_one()
        counts[table_name] = int(count)
    return counts


async def _run_payroll_normalization(
    session: AsyncSession, *, tenant_id: uuid.UUID
) -> dict:
    service = build_normalization_service(session)
    committed = await service.commit_source_version(
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        source_family="payroll",
        source_code=f"isolation_src_{uuid.uuid4().hex[:8]}",
        source_name="Isolation Payroll Source",
        structure_hash="a" * 64,
        header_hash="b" * 64,
        row_signature_hash="c" * 64,
        source_detection_summary_json={
            "headers": ["Employee ID", "Employee Name", "Gross Pay", "Currency"]
        },
        activate=True,
        created_by=tenant_id,
    )
    uploaded = await service.upload_run(
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        source_id=uuid.UUID(committed["source_id"]),
        source_version_id=uuid.UUID(committed["source_version_id"]),
        run_type="payroll_normalization",
        reporting_period=date(2026, 1, 31),
        source_artifact_id=uuid.uuid4(),
        file_name="payroll.csv",
        file_content_base64=csv_b64(
            "Employee ID,Employee Name,Gross Pay,Currency\nE001,Alice,1000,USD\n"
        ),
        sheet_name="csv",
        created_by=tenant_id,
    )
    validated = await service.validate_run(
        tenant_id=tenant_id,
        run_id=uuid.UUID(uploaded["run_id"]),
        created_by=tenant_id,
    )
    finalized = await service.finalize_run(
        tenant_id=tenant_id,
        run_id=uuid.UUID(validated["run_id"]),
        created_by=tenant_id,
    )
    return {"uploaded": uploaded, "validated": validated, "finalized": finalized}


@pytest.mark.asyncio
@pytest.mark.integration
async def test_normalization_upload_does_not_modify_accounting_engine_tables(
    normalization_phase1f3_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(normalization_phase1f3_session, tenant_id)
    before_engine = await _table_counts(normalization_phase1f3_session, ENGINE_TABLES)
    before_journals = await _table_counts(normalization_phase1f3_session, JOURNAL_TABLES)
    await _run_payroll_normalization(normalization_phase1f3_session, tenant_id=tenant_id)
    after_engine = await _table_counts(normalization_phase1f3_session, ENGINE_TABLES)
    after_journals = await _table_counts(normalization_phase1f3_session, JOURNAL_TABLES)
    assert before_engine == after_engine
    assert before_journals == after_journals


@pytest.mark.asyncio
@pytest.mark.integration
async def test_normalization_finalize_does_not_modify_reconciliation_tables(
    normalization_phase1f3_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(normalization_phase1f3_session, tenant_id)
    before_recon = await _table_counts(normalization_phase1f3_session, RECON_TABLES)
    await _run_payroll_normalization(normalization_phase1f3_session, tenant_id=tenant_id)
    after_recon = await _table_counts(normalization_phase1f3_session, RECON_TABLES)
    assert before_recon == after_recon


@pytest.mark.asyncio
@pytest.mark.integration
async def test_normalization_pipeline_does_not_invoke_fx_tables(
    normalization_phase1f3_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(normalization_phase1f3_session, tenant_id)
    before_fx = await _table_counts(normalization_phase1f3_session, FX_TABLES)
    await _run_payroll_normalization(normalization_phase1f3_session, tenant_id=tenant_id)
    after_fx = await _table_counts(normalization_phase1f3_session, FX_TABLES)
    assert before_fx == after_fx
