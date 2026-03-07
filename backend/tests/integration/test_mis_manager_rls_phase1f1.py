from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.mis_manager import MisDataSnapshot
from financeops.services.audit_writer import AuditWriter
from tests.integration.mis_phase1f1_helpers import (
    MIS_TABLES,
    ensure_tenant_context,
    hash64,
    seed_mis_normalized_line,
    seed_mis_snapshot,
    seed_mis_template,
    seed_mis_template_version,
)


async def _configure_probe_role(session: AsyncSession) -> None:
    await session.execute(
        text(
            """
            DO $$
            BEGIN
              CREATE ROLE rls_mis_probe_user NOLOGIN NOSUPERUSER NOBYPASSRLS;
            EXCEPTION
              WHEN duplicate_object THEN NULL;
            END $$;
            """
        )
    )
    await session.execute(text("GRANT USAGE ON SCHEMA public TO rls_mis_probe_user"))
    for table_name in (
        "mis_templates",
        "mis_template_versions",
        "mis_data_snapshots",
        "mis_normalized_lines",
    ):
        await session.execute(
            text(
                f"GRANT SELECT, INSERT ON {table_name} TO rls_mis_probe_user"
            )
        )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_tenant_can_read_own_template(
    mis_phase1f1_session: AsyncSession,
) -> None:
    tenant_a = uuid.uuid4()
    await _configure_probe_role(mis_phase1f1_session)
    await mis_phase1f1_session.execute(text("SET ROLE rls_mis_probe_user"))
    try:
        await ensure_tenant_context(mis_phase1f1_session, tenant_a)
        await seed_mis_template(
            mis_phase1f1_session,
            tenant_id=tenant_a,
            template_code=f"rls_own_{uuid.uuid4().hex[:8]}",
        )
        rows = (
            await mis_phase1f1_session.execute(
                text("SELECT COUNT(*) FROM mis_templates WHERE tenant_id = :tenant_id"),
                {"tenant_id": str(tenant_a)},
            )
        ).scalar_one()
        assert rows == 1
    finally:
        if mis_phase1f1_session.in_transaction():
            await mis_phase1f1_session.rollback()
        await mis_phase1f1_session.execute(text("RESET ROLE"))


@pytest.mark.asyncio
@pytest.mark.integration
async def test_tenant_cannot_read_other_tenant_template(
    mis_phase1f1_session: AsyncSession,
) -> None:
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    await _configure_probe_role(mis_phase1f1_session)
    await mis_phase1f1_session.execute(text("SET ROLE rls_mis_probe_user"))
    try:
        await ensure_tenant_context(mis_phase1f1_session, tenant_a)
        await seed_mis_template(
            mis_phase1f1_session,
            tenant_id=tenant_a,
            template_code=f"rls_a_{uuid.uuid4().hex[:8]}",
        )
        await ensure_tenant_context(mis_phase1f1_session, tenant_b)
        template_b = await seed_mis_template(
            mis_phase1f1_session,
            tenant_id=tenant_b,
            template_code=f"rls_b_{uuid.uuid4().hex[:8]}",
        )
        await ensure_tenant_context(mis_phase1f1_session, tenant_a)
        visible = (
            await mis_phase1f1_session.execute(
                text("SELECT COUNT(*) FROM mis_templates WHERE id = :template_id"),
                {"template_id": str(template_b.id)},
            )
        ).scalar_one()
        assert visible == 0
    finally:
        if mis_phase1f1_session.in_transaction():
            await mis_phase1f1_session.rollback()
        await mis_phase1f1_session.execute(text("RESET ROLE"))


@pytest.mark.asyncio
@pytest.mark.integration
async def test_tenant_cannot_insert_other_tenant_snapshot(
    mis_phase1f1_session: AsyncSession,
) -> None:
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    await _configure_probe_role(mis_phase1f1_session)
    await mis_phase1f1_session.execute(text("SET ROLE rls_mis_probe_user"))
    try:
        await ensure_tenant_context(mis_phase1f1_session, tenant_b)
        template_b = await seed_mis_template(
            mis_phase1f1_session,
            tenant_id=tenant_b,
            template_code=f"rls_snap_{uuid.uuid4().hex[:8]}",
        )
        version_b = await seed_mis_template_version(
            mis_phase1f1_session,
            tenant_id=tenant_b,
            template_id=template_b.id,
            version_no=1,
            version_token_seed="rls_snap_v1",
            structure_seed="rls_snap_v1",
            status="active",
        )

        await ensure_tenant_context(mis_phase1f1_session, tenant_a)
        with pytest.raises(DBAPIError):
            await AuditWriter.insert_financial_record(
                mis_phase1f1_session,
                model_class=MisDataSnapshot,
                tenant_id=tenant_b,
                record_data={
                    "template_version_id": str(version_b.id),
                    "snapshot_token": hash64("rls_mismatch"),
                },
                values={
                    "organisation_id": tenant_b,
                    "template_id": template_b.id,
                    "template_version_id": version_b.id,
                    "reporting_period": date(2026, 1, 31),
                    "upload_artifact_id": uuid.uuid4(),
                    "snapshot_token": hash64("rls_mismatch"),
                    "source_file_hash": hash64("rls_mismatch_file"),
                    "sheet_name": "Sheet1",
                    "snapshot_status": "pending",
                    "validation_summary_json": {"status": "pending"},
                    "created_by": tenant_b,
                },
            )
            await mis_phase1f1_session.flush()
        await mis_phase1f1_session.rollback()
    finally:
        await mis_phase1f1_session.execute(text("RESET ROLE"))


@pytest.mark.asyncio
@pytest.mark.integration
async def test_tenant_cannot_read_other_tenant_normalized_lines(
    mis_phase1f1_session: AsyncSession,
) -> None:
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    await _configure_probe_role(mis_phase1f1_session)
    await mis_phase1f1_session.execute(text("SET ROLE rls_mis_probe_user"))
    try:
        await ensure_tenant_context(mis_phase1f1_session, tenant_a)
        template_a = await seed_mis_template(
            mis_phase1f1_session,
            tenant_id=tenant_a,
            template_code=f"rls_line_a_{uuid.uuid4().hex[:8]}",
        )
        version_a = await seed_mis_template_version(
            mis_phase1f1_session,
            tenant_id=tenant_a,
            template_id=template_a.id,
            version_no=1,
            version_token_seed="rls_line_a_v1",
            structure_seed="rls_line_a_v1",
            status="active",
        )
        snapshot_a = await seed_mis_snapshot(
            mis_phase1f1_session,
            tenant_id=tenant_a,
            template_id=template_a.id,
            template_version_id=version_a.id,
            reporting_period=date(2026, 1, 31),
            snapshot_token_seed="rls_line_a_snap",
        )
        await seed_mis_normalized_line(
            mis_phase1f1_session,
            tenant_id=tenant_a,
            snapshot_id=snapshot_a.id,
            line_no=1,
        )

        await ensure_tenant_context(mis_phase1f1_session, tenant_b)
        template_b = await seed_mis_template(
            mis_phase1f1_session,
            tenant_id=tenant_b,
            template_code=f"rls_line_b_{uuid.uuid4().hex[:8]}",
        )
        version_b = await seed_mis_template_version(
            mis_phase1f1_session,
            tenant_id=tenant_b,
            template_id=template_b.id,
            version_no=1,
            version_token_seed="rls_line_b_v1",
            structure_seed="rls_line_b_v1",
            status="active",
        )
        snapshot_b = await seed_mis_snapshot(
            mis_phase1f1_session,
            tenant_id=tenant_b,
            template_id=template_b.id,
            template_version_id=version_b.id,
            reporting_period=date(2026, 1, 31),
            snapshot_token_seed="rls_line_b_snap",
        )
        line_b = await seed_mis_normalized_line(
            mis_phase1f1_session,
            tenant_id=tenant_b,
            snapshot_id=snapshot_b.id,
            line_no=1,
        )

        await ensure_tenant_context(mis_phase1f1_session, tenant_a)
        visible = (
            await mis_phase1f1_session.execute(
                text("SELECT COUNT(*) FROM mis_normalized_lines WHERE id = :line_id"),
                {"line_id": str(line_b.id)},
            )
        ).scalar_one()
        assert visible == 0
    finally:
        await mis_phase1f1_session.execute(text("RESET ROLE"))


@pytest.mark.asyncio
@pytest.mark.integration
async def test_force_rls_active_on_all_mis_tables(
    mis_phase1f1_session: AsyncSession,
) -> None:
    for table_name in (*MIS_TABLES, "mis_templates", "mis_uploads"):
        row = (
            await mis_phase1f1_session.execute(
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
