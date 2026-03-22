from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.append_only import APPEND_ONLY_TABLES
from financeops.db.models.erp_sync import ExternalConnection
from financeops.services.audit_writer import AuditWriter
from tests.integration.erp_sync_phase4c_helpers import (
    ERP_SYNC_TABLES,
    ensure_erp_sync_tenant_context,
)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_append_only_registry_includes_all_external_tables() -> None:
    assert set(ERP_SYNC_TABLES).issubset(set(APPEND_ONLY_TABLES))


@pytest.mark.asyncio
@pytest.mark.integration
async def test_append_only_rejects_update_on_external_connections(
    erp_sync_phase4c_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    connection_code = f"conn_{uuid.uuid4().hex[:8]}"
    await ensure_erp_sync_tenant_context(erp_sync_phase4c_session, tenant_id)

    row = await AuditWriter.insert_financial_record(
        erp_sync_phase4c_session,
        model_class=ExternalConnection,
        tenant_id=tenant_id,
        record_data={
            "connection_code": connection_code,
            "connector_type": "zoho",
        },
        values={
            "organisation_id": tenant_id,
            "entity_id": None,
            "connector_type": "zoho",
            "connection_code": connection_code,
            "connection_name": "ERP Sync Connection",
            "source_system_instance_id": "instance-001",
            "data_residency_region": "in",
            "pii_masking_enabled": True,
            "consent_reference": None,
            "pinned_connector_version": None,
            "connection_status": "active",
            "secret_ref": None,
            "created_by": tenant_id,
        },
    )

    with pytest.raises(DBAPIError):
        await erp_sync_phase4c_session.execute(
            text(
                "UPDATE external_connections "
                "SET connection_name = 'tampered' "
                "WHERE id = :id"
            ),
            {"id": str(row.id)},
        )
        await erp_sync_phase4c_session.flush()
