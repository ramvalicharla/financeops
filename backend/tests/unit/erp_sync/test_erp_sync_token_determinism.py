from __future__ import annotations

import uuid

import pytest

from financeops.modules.erp_sync.application.sync_service import SyncService
from financeops.modules.erp_sync.domain.enums import ConnectorType, DatasetType


@pytest.mark.asyncio
async def test_same_inputs_always_produce_same_sync_token() -> None:
    service = SyncService(session=None)  # type: ignore[arg-type]
    payload = dict(
        tenant_id=uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        organisation_id=uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
        entity_id=uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"),
        dataset_type=DatasetType.TRIAL_BALANCE,
        connector_type=ConnectorType.GENERIC_FILE,
        connector_version="1.0.0",
        source_system_instance_id="generic_file:abc12345",
        sync_definition_id=uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd"),
        sync_definition_version=1,
        period_resolution_hash="period_hash",
        extraction_scope_hash="scope_hash",
        raw_snapshot_payload_hash="raw_hash",
        mapping_version_token="mapping_token",
        normalization_version="phase4c.v1",
        pii_masking_enabled=True,
        data_residency_region="in",
    )

    token_one = await service._build_sync_token(**payload)
    token_two = await service._build_sync_token(**payload)

    assert token_one == token_two


@pytest.mark.asyncio
async def test_changed_input_changes_sync_token() -> None:
    service = SyncService(session=None)  # type: ignore[arg-type]
    base = dict(
        tenant_id=uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        organisation_id=uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
        entity_id=uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"),
        dataset_type=DatasetType.TRIAL_BALANCE,
        connector_type=ConnectorType.GENERIC_FILE,
        connector_version="1.0.0",
        source_system_instance_id="generic_file:abc12345",
        sync_definition_id=uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd"),
        sync_definition_version=1,
        period_resolution_hash="period_hash",
        extraction_scope_hash="scope_hash",
        raw_snapshot_payload_hash="raw_hash",
        mapping_version_token="mapping_token",
        normalization_version="phase4c.v1",
        pii_masking_enabled=True,
        data_residency_region="in",
    )
    changed = dict(base)
    changed["raw_snapshot_payload_hash"] = "raw_hash_changed"

    token_base = await service._build_sync_token(**base)
    token_changed = await service._build_sync_token(**changed)

    assert token_base != token_changed
