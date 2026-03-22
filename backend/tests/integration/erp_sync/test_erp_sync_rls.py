from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.erp_sync import ExternalConnection
from financeops.services.audit_writer import AuditWriter
from tests.integration.erp_sync_phase4c_helpers import ensure_erp_sync_tenant_context


async def _configure_probe_role(session: AsyncSession) -> None:
    await session.execute(
        text(
            """
            DO $$
            BEGIN
              CREATE ROLE rls_erp_sync_probe NOLOGIN NOSUPERUSER NOBYPASSRLS;
            EXCEPTION
              WHEN duplicate_object THEN NULL;
            END $$;
            """
        )
    )
    await session.execute(text("GRANT USAGE ON SCHEMA public TO rls_erp_sync_probe"))
    await session.execute(
        text("GRANT SELECT, INSERT ON external_connections TO rls_erp_sync_probe")
    )


async def _seed_connection(session: AsyncSession, *, tenant_id: uuid.UUID, code: str) -> uuid.UUID:
    row = await AuditWriter.insert_financial_record(
        session,
        model_class=ExternalConnection,
        tenant_id=tenant_id,
        record_data={"connection_code": code, "connector_type": "zoho"},
        values={
            "organisation_id": tenant_id,
            "entity_id": None,
            "connector_type": "zoho",
            "connection_code": code,
            "connection_name": f"Connection {code}",
            "source_system_instance_id": f"instance-{code}",
            "data_residency_region": "in",
            "pii_masking_enabled": True,
            "consent_reference": None,
            "pinned_connector_version": None,
            "connection_status": "active",
            "secret_ref": None,
            "created_by": tenant_id,
        },
    )
    return row.id


@pytest.mark.asyncio
@pytest.mark.integration
async def test_tenant_a_cannot_query_tenant_b_external_connection_records(
    erp_sync_phase4c_session: AsyncSession,
) -> None:
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()

    await _configure_probe_role(erp_sync_phase4c_session)
    await ensure_erp_sync_tenant_context(erp_sync_phase4c_session, tenant_b)
    row_b = await _seed_connection(
        erp_sync_phase4c_session,
        tenant_id=tenant_b,
        code=f"b_{uuid.uuid4().hex[:8]}",
    )

    await ensure_erp_sync_tenant_context(erp_sync_phase4c_session, tenant_a)
    row_a = await _seed_connection(
        erp_sync_phase4c_session,
        tenant_id=tenant_a,
        code=f"a_{uuid.uuid4().hex[:8]}",
    )

    await erp_sync_phase4c_session.execute(text("SET ROLE rls_erp_sync_probe"))
    try:
        await ensure_erp_sync_tenant_context(erp_sync_phase4c_session, tenant_a)
        own_visible = (
            await erp_sync_phase4c_session.execute(
                text("SELECT COUNT(*) FROM external_connections WHERE id = :id"),
                {"id": str(row_a)},
            )
        ).scalar_one()
        other_visible = (
            await erp_sync_phase4c_session.execute(
                text("SELECT COUNT(*) FROM external_connections WHERE id = :id"),
                {"id": str(row_b)},
            )
        ).scalar_one()
        assert own_visible == 1
        assert other_visible == 0
    finally:
        if erp_sync_phase4c_session.in_transaction():
            await erp_sync_phase4c_session.rollback()
        await erp_sync_phase4c_session.execute(text("RESET ROLE"))
