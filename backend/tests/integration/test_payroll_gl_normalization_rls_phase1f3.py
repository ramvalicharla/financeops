from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.payroll_gl_normalization import NormalizationRun
from financeops.services.audit_writer import AuditWriter
from tests.integration.normalization_phase1f3_helpers import (
    NORMALIZATION_TABLES,
    build_normalization_service,
    csv_b64,
    ensure_tenant_context,
    seed_normalization_source,
    seed_normalization_source_version,
)


async def _configure_probe_role(session: AsyncSession) -> None:
    await session.execute(
        text(
            """
            DO $$
            BEGIN
              CREATE ROLE rls_norm_probe_user NOLOGIN NOSUPERUSER NOBYPASSRLS;
            EXCEPTION
              WHEN duplicate_object THEN NULL;
            END $$;
            """
        )
    )
    await session.execute(text("GRANT USAGE ON SCHEMA public TO rls_norm_probe_user"))
    for table_name in (
        "normalization_sources",
        "normalization_runs",
        "payroll_normalized_lines",
    ):
        await session.execute(
            text(f"GRANT SELECT, INSERT ON {table_name} TO rls_norm_probe_user")
        )


async def _seed_payroll_run(
    session: AsyncSession, *, tenant_id: uuid.UUID
) -> dict:
    service = build_normalization_service(session)
    committed = await service.commit_source_version(
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        source_family="payroll",
        source_code=f"rls_src_{uuid.uuid4().hex[:8]}",
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
    return await service.upload_run(
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


@pytest.mark.asyncio
@pytest.mark.integration
async def test_tenant_can_read_own_source(
    normalization_phase1f3_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await _configure_probe_role(normalization_phase1f3_session)
    await normalization_phase1f3_session.execute(text("SET ROLE rls_norm_probe_user"))
    try:
        await ensure_tenant_context(normalization_phase1f3_session, tenant_id)
        source = await seed_normalization_source(
            normalization_phase1f3_session,
            tenant_id=tenant_id,
            organisation_id=tenant_id,
            source_family="payroll",
            source_code=f"own_{uuid.uuid4().hex[:8]}",
            source_name="Own Source",
            created_by=tenant_id,
        )
        visible = (
            await normalization_phase1f3_session.execute(
                text("SELECT COUNT(*) FROM normalization_sources WHERE id=:id"),
                {"id": str(source.id)},
            )
        ).scalar_one()
        assert visible == 1
    finally:
        if normalization_phase1f3_session.in_transaction():
            await normalization_phase1f3_session.rollback()
        await normalization_phase1f3_session.execute(text("RESET ROLE"))


@pytest.mark.asyncio
@pytest.mark.integration
async def test_tenant_cannot_read_other_tenant_source(
    normalization_phase1f3_session: AsyncSession,
) -> None:
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    await _configure_probe_role(normalization_phase1f3_session)
    await normalization_phase1f3_session.execute(text("SET ROLE rls_norm_probe_user"))
    try:
        await ensure_tenant_context(normalization_phase1f3_session, tenant_b)
        source_b = await seed_normalization_source(
            normalization_phase1f3_session,
            tenant_id=tenant_b,
            organisation_id=tenant_b,
            source_family="payroll",
            source_code=f"other_{uuid.uuid4().hex[:8]}",
            source_name="Other Source",
            created_by=tenant_b,
        )
        await ensure_tenant_context(normalization_phase1f3_session, tenant_a)
        visible = (
            await normalization_phase1f3_session.execute(
                text("SELECT COUNT(*) FROM normalization_sources WHERE id=:id"),
                {"id": str(source_b.id)},
            )
        ).scalar_one()
        assert visible == 0
    finally:
        if normalization_phase1f3_session.in_transaction():
            await normalization_phase1f3_session.rollback()
        await normalization_phase1f3_session.execute(text("RESET ROLE"))


@pytest.mark.asyncio
@pytest.mark.integration
async def test_tenant_cannot_insert_other_tenant_run(
    normalization_phase1f3_session: AsyncSession,
) -> None:
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    await _configure_probe_role(normalization_phase1f3_session)
    await ensure_tenant_context(normalization_phase1f3_session, tenant_a)
    source = await seed_normalization_source(
        normalization_phase1f3_session,
        tenant_id=tenant_a,
        organisation_id=tenant_a,
        source_family="payroll",
        source_code=f"insert_{uuid.uuid4().hex[:8]}",
        source_name="Insert Source",
        created_by=tenant_a,
    )
    version = await seed_normalization_source_version(
        normalization_phase1f3_session,
        tenant_id=tenant_a,
        source_id=source.id,
        version_no=1,
        version_token_seed="rls_insert_v1",
        structure_seed="rls_insert_v1",
        status="active",
        created_by=tenant_a,
    )
    await normalization_phase1f3_session.execute(text("SET ROLE rls_norm_probe_user"))
    try:
        await ensure_tenant_context(normalization_phase1f3_session, tenant_a)
        with pytest.raises(DBAPIError):
            await AuditWriter.insert_financial_record(
                normalization_phase1f3_session,
                model_class=NormalizationRun,
                tenant_id=tenant_b,
                record_data={
                    "source_id": str(source.id),
                    "source_version_id": str(version.id),
                    "run_type": "payroll_normalization",
                },
                values={
                    "organisation_id": tenant_b,
                    "source_id": source.id,
                    "source_version_id": version.id,
                    "mapping_version_token": "1" * 64,
                    "run_type": "payroll_normalization",
                    "reporting_period": date(2026, 1, 31),
                    "source_artifact_id": uuid.uuid4(),
                    "source_file_hash": "2" * 64,
                    "run_token": "3" * 64,
                    "run_status": "pending",
                    "validation_summary_json": {},
                    "created_by": tenant_b,
                },
            )
            await normalization_phase1f3_session.flush()
    finally:
        if normalization_phase1f3_session.in_transaction():
            await normalization_phase1f3_session.rollback()
        await normalization_phase1f3_session.execute(text("RESET ROLE"))


@pytest.mark.asyncio
@pytest.mark.integration
async def test_tenant_cannot_read_other_tenant_payroll_lines(
    normalization_phase1f3_session: AsyncSession,
) -> None:
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    await _configure_probe_role(normalization_phase1f3_session)
    await ensure_tenant_context(normalization_phase1f3_session, tenant_b)
    run_b = await _seed_payroll_run(normalization_phase1f3_session, tenant_id=tenant_b)
    await normalization_phase1f3_session.execute(text("SET ROLE rls_norm_probe_user"))
    try:
        await ensure_tenant_context(normalization_phase1f3_session, tenant_a)
        visible = (
            await normalization_phase1f3_session.execute(
                text("SELECT COUNT(*) FROM payroll_normalized_lines WHERE run_id=:run_id"),
                {"run_id": run_b["run_id"]},
            )
        ).scalar_one()
        assert visible == 0
    finally:
        if normalization_phase1f3_session.in_transaction():
            await normalization_phase1f3_session.rollback()
        await normalization_phase1f3_session.execute(text("RESET ROLE"))


@pytest.mark.asyncio
@pytest.mark.integration
async def test_force_rls_active_on_all_normalization_tables(
    normalization_phase1f3_session: AsyncSession,
) -> None:
    for table_name in NORMALIZATION_TABLES:
        row = (
            await normalization_phase1f3_session.execute(
                text(
                    """
                    SELECT relrowsecurity, relforcerowsecurity
                    FROM pg_class
                    WHERE relname = :table_name
                    """
                ),
                {"table_name": table_name},
            )
        ).one()
        assert row.relrowsecurity is True
        assert row.relforcerowsecurity is True
