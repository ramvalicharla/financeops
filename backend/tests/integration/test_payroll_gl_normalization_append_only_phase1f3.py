from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.append_only import APPEND_ONLY_TABLES
from tests.integration.normalization_phase1f3_helpers import (
    build_normalization_service,
    csv_b64,
    ensure_tenant_context,
)


async def _seed_payroll_run(
    session: AsyncSession, *, tenant_id: uuid.UUID
) -> dict:
    service = build_normalization_service(session)
    committed = await service.commit_source_version(
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        source_family="payroll",
        source_code=f"payroll_src_{uuid.uuid4().hex[:8]}",
        source_name="Payroll Source",
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
    return uploaded


async def _seed_payroll_run_with_exception(
    session: AsyncSession, *, tenant_id: uuid.UUID
) -> dict:
    service = build_normalization_service(session)
    committed = await service.commit_source_version(
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        source_family="payroll",
        source_code=f"payroll_src_exc_{uuid.uuid4().hex[:8]}",
        source_name="Payroll Source Exceptions",
        structure_hash="d" * 64,
        header_hash="e" * 64,
        row_signature_hash="f" * 64,
        source_detection_summary_json={
            "headers": ["Employee ID", "Employee Name", "Gross Pay", "Currency"]
        },
        activate=True,
        created_by=tenant_id,
    )
    return await service.upload_run(
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        source_id=uuid.UUID(committed["source_id"]),
        source_version_id=uuid.UUID(committed["source_version_id"]),
        run_type="payroll_normalization",
        reporting_period=date(2026, 1, 31),
        source_artifact_id=uuid.uuid4(),
        file_name="payroll_bad.csv",
        file_content_base64=csv_b64(
            "Employee ID,Employee Name,Gross Pay,Currency\nE001,Alice,abc,USD\n"
        ),
        sheet_name="csv",
        created_by=tenant_id,
    )


async def _seed_gl_run(session: AsyncSession, *, tenant_id: uuid.UUID) -> dict:
    service = build_normalization_service(session)
    committed = await service.commit_source_version(
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        source_family="gl",
        source_code=f"gl_src_{uuid.uuid4().hex[:8]}",
        source_name="GL Source",
        structure_hash="1" * 64,
        header_hash="2" * 64,
        row_signature_hash="3" * 64,
        source_detection_summary_json={
            "headers": ["Account Code", "Debit", "Credit", "Currency", "Posting Date"]
        },
        activate=True,
        created_by=tenant_id,
    )
    return await service.upload_run(
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        source_id=uuid.UUID(committed["source_id"]),
        source_version_id=uuid.UUID(committed["source_version_id"]),
        run_type="gl_normalization",
        reporting_period=date(2026, 1, 31),
        source_artifact_id=uuid.uuid4(),
        file_name="gl.csv",
        file_content_base64=csv_b64(
            "Account Code,Debit,Credit,Currency,Posting Date\n4000,1000,0,USD,2026-01-31\n"
        ),
        sheet_name="csv",
        created_by=tenant_id,
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_append_only_rejects_update_on_normalization_runs(
    normalization_phase1f3_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(normalization_phase1f3_session, tenant_id)
    uploaded = await _seed_payroll_run(normalization_phase1f3_session, tenant_id=tenant_id)
    with pytest.raises(DBAPIError):
        await normalization_phase1f3_session.execute(
            text("UPDATE normalization_runs SET run_status='failed' WHERE id=:id"),
            {"id": uploaded["run_id"]},
        )
        await normalization_phase1f3_session.flush()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_append_only_rejects_update_on_normalization_source_versions(
    normalization_phase1f3_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(normalization_phase1f3_session, tenant_id)
    uploaded = await _seed_payroll_run(normalization_phase1f3_session, tenant_id=tenant_id)
    version_id = (
        await normalization_phase1f3_session.execute(
            text("SELECT source_version_id FROM normalization_runs WHERE id=:id"),
            {"id": uploaded["run_id"]},
        )
    ).scalar_one()
    with pytest.raises(DBAPIError):
        await normalization_phase1f3_session.execute(
            text(
                "UPDATE normalization_source_versions "
                "SET status='rejected' WHERE id=:id"
            ),
            {"id": str(version_id)},
        )
        await normalization_phase1f3_session.flush()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_append_only_rejects_update_on_normalization_mappings(
    normalization_phase1f3_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(normalization_phase1f3_session, tenant_id)
    await _seed_payroll_run(normalization_phase1f3_session, tenant_id=tenant_id)
    mapping_id = (
        await normalization_phase1f3_session.execute(
            text("SELECT id FROM normalization_mappings ORDER BY created_at LIMIT 1")
        )
    ).scalar_one()
    with pytest.raises(DBAPIError):
        await normalization_phase1f3_session.execute(
            text(
                "UPDATE normalization_mappings SET canonical_field_name='net_pay' WHERE id=:id"
            ),
            {"id": str(mapping_id)},
        )
        await normalization_phase1f3_session.flush()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_append_only_rejects_update_on_payroll_normalized_lines(
    normalization_phase1f3_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(normalization_phase1f3_session, tenant_id)
    uploaded = await _seed_payroll_run(normalization_phase1f3_session, tenant_id=tenant_id)
    line_id = (
        await normalization_phase1f3_session.execute(
            text("SELECT id FROM payroll_normalized_lines WHERE run_id=:run_id LIMIT 1"),
            {"run_id": uploaded["run_id"]},
        )
    ).scalar_one()
    with pytest.raises(DBAPIError):
        await normalization_phase1f3_session.execute(
            text("UPDATE payroll_normalized_lines SET amount_value=2000 WHERE id=:id"),
            {"id": str(line_id)},
        )
        await normalization_phase1f3_session.flush()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_append_only_rejects_update_on_gl_normalized_lines(
    normalization_phase1f3_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(normalization_phase1f3_session, tenant_id)
    uploaded = await _seed_gl_run(normalization_phase1f3_session, tenant_id=tenant_id)
    line_id = (
        await normalization_phase1f3_session.execute(
            text("SELECT id FROM gl_normalized_lines WHERE run_id=:run_id LIMIT 1"),
            {"run_id": uploaded["run_id"]},
        )
    ).scalar_one()
    with pytest.raises(DBAPIError):
        await normalization_phase1f3_session.execute(
            text("UPDATE gl_normalized_lines SET signed_amount=2000 WHERE id=:id"),
            {"id": str(line_id)},
        )
        await normalization_phase1f3_session.flush()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_append_only_rejects_update_on_normalization_exceptions(
    normalization_phase1f3_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(normalization_phase1f3_session, tenant_id)
    uploaded = await _seed_payroll_run_with_exception(
        normalization_phase1f3_session, tenant_id=tenant_id
    )
    exception_id = (
        await normalization_phase1f3_session.execute(
            text("SELECT id FROM normalization_exceptions WHERE run_id=:run_id LIMIT 1"),
            {"run_id": uploaded["run_id"]},
        )
    ).scalar_one()
    with pytest.raises(DBAPIError):
        await normalization_phase1f3_session.execute(
            text(
                "UPDATE normalization_exceptions "
                "SET resolution_status='resolved' WHERE id=:id"
            ),
            {"id": str(exception_id)},
        )
        await normalization_phase1f3_session.flush()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_append_only_rejects_update_on_normalization_evidence_links(
    normalization_phase1f3_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(normalization_phase1f3_session, tenant_id)
    uploaded = await _seed_payroll_run(normalization_phase1f3_session, tenant_id=tenant_id)
    evidence_id = (
        await normalization_phase1f3_session.execute(
            text(
                "SELECT id FROM normalization_evidence_links WHERE run_id=:run_id LIMIT 1"
            ),
            {"run_id": uploaded["run_id"]},
        )
    ).scalar_one()
    with pytest.raises(DBAPIError):
        await normalization_phase1f3_session.execute(
            text(
                "UPDATE normalization_evidence_links "
                "SET evidence_label='changed' WHERE id=:id"
            ),
            {"id": str(evidence_id)},
        )
        await normalization_phase1f3_session.flush()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_append_only_registry_includes_normalization_tables() -> None:
    required = {
        "normalization_sources",
        "normalization_source_versions",
        "normalization_mappings",
        "normalization_runs",
        "payroll_normalized_lines",
        "gl_normalized_lines",
        "normalization_exceptions",
        "normalization_evidence_links",
    }
    assert required.issubset(set(APPEND_ONLY_TABLES))
