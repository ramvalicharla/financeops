from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch


async def test_map_coa_upserts_new_mappings() -> None:
    """POST /mappings/coa — new accounts are inserted and upserted count returned."""
    from financeops.modules.erp_sync.api.coa_mappings import upsert_coa_mappings

    tenant_id = uuid.uuid4()
    connection_id = uuid.uuid4()
    mapping_id = uuid.uuid4()

    mock_user = MagicMock()
    mock_user.tenant_id = tenant_id
    mock_user.id = uuid.uuid4()

    mock_connection = MagicMock()
    mock_connection.id = connection_id
    mock_connection.connector_type = "xero"
    mock_connection.organisation_id = uuid.uuid4()

    mock_definition = MagicMock()
    mock_definition.id = mapping_id

    mock_session = MagicMock()
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()

    # Connection found, no existing ref
    execute_results = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_connection)),  # ExternalConnection lookup
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_definition)),  # ExternalMappingDefinition lookup
        MagicMock(scalar_one_or_none=MagicMock(return_value=None)),             # ErpAccountExternalRef lookup (new)
    ]
    mock_session.execute = AsyncMock(side_effect=execute_results)

    mock_request = MagicMock()
    mock_request.state.request_id = None

    body = {
        "connection_id": str(connection_id),
        "accounts": [
            {
                "external_account_id": "EXT-001",
                "internal_account_code": "1001",
                "external_account_name": "Cash",
            }
        ],
    }

    result = await upsert_coa_mappings(
        request=mock_request,
        body=body,
        session=mock_session,
        user=mock_user,
    )

    assert result["data"]["upserted"] == 1
    assert result["data"]["mapping_definition_id"] == str(mapping_id)
    mock_session.add.assert_called_once()


async def test_map_coa_updates_existing_mapping() -> None:
    """POST /mappings/coa — existing account ref is updated in-place (no new row)."""
    from financeops.modules.erp_sync.api.coa_mappings import upsert_coa_mappings

    tenant_id = uuid.uuid4()
    connection_id = uuid.uuid4()
    mapping_id = uuid.uuid4()

    mock_user = MagicMock()
    mock_user.tenant_id = tenant_id
    mock_user.id = uuid.uuid4()

    mock_connection = MagicMock()
    mock_connection.id = connection_id
    mock_connection.connector_type = "tally"
    mock_connection.organisation_id = uuid.uuid4()

    mock_definition = MagicMock()
    mock_definition.id = mapping_id

    existing_ref = MagicMock()
    existing_ref.internal_account_code = "OLD-CODE"
    existing_ref.external_account_code = ""
    existing_ref.external_account_name = ""

    mock_session = MagicMock()
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()

    execute_results = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_connection)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_definition)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=existing_ref)),  # existing match
    ]
    mock_session.execute = AsyncMock(side_effect=execute_results)

    mock_request = MagicMock()
    mock_request.state.request_id = None

    body = {
        "connection_id": str(connection_id),
        "accounts": [
            {
                "external_account_id": "EXT-001",
                "internal_account_code": "NEW-CODE",
            }
        ],
    }

    result = await upsert_coa_mappings(
        request=mock_request,
        body=body,
        session=mock_session,
        user=mock_user,
    )

    assert result["data"]["upserted"] == 1
    assert existing_ref.internal_account_code == "NEW-CODE"
    # session.add called to persist the mutation
    mock_session.add.assert_called_once_with(existing_ref)


async def test_export_journals_creates_sync_run() -> None:
    """POST /sync-runs/export-journals — creates ExternalSyncRun with dataset_type='journal_export'."""
    from financeops.modules.erp_sync.api.export_journals import export_journals

    tenant_id = uuid.uuid4()
    connection_id = uuid.uuid4()
    sync_def_id = uuid.uuid4()
    sync_def_ver_id = uuid.uuid4()
    sync_run_id = uuid.uuid4()

    mock_user = MagicMock()
    mock_user.tenant_id = tenant_id
    mock_user.id = uuid.uuid4()

    mock_connection = MagicMock()
    mock_connection.id = connection_id
    mock_connection.organisation_id = uuid.uuid4()
    mock_connection.entity_id = None

    mock_definition = MagicMock()
    mock_definition.id = sync_def_id

    mock_version = MagicMock()
    mock_version.id = sync_def_ver_id

    mock_sync_run = MagicMock()
    mock_sync_run.id = sync_run_id
    mock_sync_run.run_token = "tok-abc"

    mock_session = MagicMock()
    mock_session.flush = AsyncMock()

    execute_results = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_connection)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_definition)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_version)),
    ]
    mock_session.execute = AsyncMock(side_effect=execute_results)

    mock_request = MagicMock()
    mock_request.state.request_id = None

    body = {
        "connection_id": str(connection_id),
        "sync_definition_id": str(sync_def_id),
        "sync_definition_version_id": str(sync_def_ver_id),
        "journal_ids": ["jnl-1", "jnl-2"],
    }

    with patch(
        "financeops.modules.erp_sync.api.export_journals.AuditWriter.insert_financial_record",
        new=AsyncMock(return_value=mock_sync_run),
    ):
        result = await export_journals(
            request=mock_request,
            body=body,
            session=mock_session,
            user=mock_user,
        )

    assert result["data"]["status"] == "created"
    assert result["data"]["record_refs"]["sync_run_id"] == str(sync_run_id)
    assert result["data"]["record_refs"]["dataset_type"] == "journal_export"


async def test_export_journals_tenant_scoped() -> None:
    """POST /sync-runs/export-journals — connection lookup uses user.tenant_id (cross-tenant blocked)."""
    from financeops.modules.erp_sync.api.export_journals import export_journals
    from fastapi import HTTPException

    import pytest

    tenant_id = uuid.uuid4()
    connection_id = uuid.uuid4()

    mock_user = MagicMock()
    mock_user.tenant_id = tenant_id
    mock_user.id = uuid.uuid4()

    mock_session = MagicMock()
    mock_session.flush = AsyncMock()
    # connection not found for this tenant
    mock_session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    )

    mock_request = MagicMock()
    mock_request.state.request_id = None

    body = {
        "connection_id": str(connection_id),
        "sync_definition_id": str(uuid.uuid4()),
        "sync_definition_version_id": str(uuid.uuid4()),
    }

    with pytest.raises(HTTPException) as exc_info:
        await export_journals(
            request=mock_request,
            body=body,
            session=mock_session,
            user=mock_user,
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "connection_not_found"
