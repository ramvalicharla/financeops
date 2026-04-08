from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from financeops.core.governance.airlock import AirlockAdmissionService
from financeops.core.exceptions import ValidationError
from financeops.core.intent.context import MutationContext, governed_mutation_context
from financeops.modules.erp_sync.application.sync_service import SyncService
from financeops.modules.erp_sync.domain.enums import DatasetType


def _scalar_result(value):
    return SimpleNamespace(scalar_one_or_none=lambda: value)


@pytest.mark.asyncio
async def test_trigger_sync_run_uses_persisted_secret_ref_for_connector_extract() -> None:
    tenant_id = uuid.uuid4()
    connection = SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        connector_type="zoho",
        pinned_connector_version=None,
        source_system_instance_id="zoho-instance",
        pii_masking_enabled=True,
        data_residency_region="in",
        secret_ref="enc-secret",
    )
    definition = SimpleNamespace(dataset_type="trial_balance", entity_id=None)
    version = SimpleNamespace(version_no=1, period_resolution_json={}, extraction_scope_json={})

    session = AsyncMock()
    session.execute = AsyncMock(return_value=_scalar_result(None))
    connector = SimpleNamespace(
        connector_version="1.2.0",
        supports_resumable_extraction=False,
        extract=AsyncMock(return_value={"line_count": 1, "currency": "INR"}),
    )
    mapping_service = SimpleNamespace(
        get_active_mapping_for_connection=AsyncMock(
            return_value={"mapping_version_token": "mapping-token"}
        )
    )
    normalization_service = SimpleNamespace(normalize=MagicMock(return_value={"rows": []}))
    validation_service = SimpleNamespace(validate=MagicMock(return_value={"run_status": "completed"}))
    service = SyncService(
        session,
        mapping_service=mapping_service,
        normalization_service=normalization_service,
        validation_service=validation_service,
    )

    with governed_mutation_context(
        MutationContext(
            intent_id=uuid.uuid4(),
            job_id=uuid.uuid4(),
            actor_user_id=uuid.uuid4(),
            actor_role="finance_leader",
            intent_type="TEST_ERP_SYNC_TRIGGER",
        )
    ):
        with (
            patch.object(
                service,
                "_fetch_sync_context",
                new_callable=AsyncMock,
                return_value=(connection, definition, version),
            ),
            patch.object(
                service,
                "_resolve_active_secret_ref",
                new_callable=AsyncMock,
                return_value="enc-active-secret",
            ),
            patch.object(
                service,
                "_build_sync_token",
                new_callable=AsyncMock,
                return_value="sync-token",
            ),
            patch(
                "financeops.modules.erp_sync.application.sync_service.get_connector",
                return_value=connector,
            ),
            patch.object(
                AirlockAdmissionService,
                "assert_admitted",
                new=AsyncMock(return_value=SimpleNamespace(id=uuid.uuid4(), status="ADMITTED")),
            ),
            patch(
                "financeops.modules.erp_sync.application.sync_service.AuditWriter.insert_financial_record",
                new_callable=AsyncMock,
                side_effect=[
                    SimpleNamespace(id=uuid.uuid4(), run_status="completed", run_token="sync-token"),
                    SimpleNamespace(id=uuid.uuid4(), snapshot_token="snapshot-token"),
                ],
            ),
        ):
            result = await service.trigger_sync_run(
                tenant_id=tenant_id,
                organisation_id=tenant_id,
                entity_id=None,
                connection_id=connection.id,
                sync_definition_id=uuid.uuid4(),
                sync_definition_version_id=uuid.uuid4(),
                dataset_type=DatasetType.TRIAL_BALANCE,
                idempotency_key="idempotency-key",
                created_by=uuid.uuid4(),
                extraction_kwargs={"checkpoint": {"page": 2}},
                admitted_airlock_item_id=uuid.uuid4(),
                source_type="erp_sync_request",
            )

    extract_kwargs = connector.extract.await_args.kwargs
    assert extract_kwargs["secret_ref"] == "enc-active-secret"
    assert extract_kwargs["checkpoint"] == {"page": 2}
    assert result["sync_run_status"] == "completed"


@pytest.mark.asyncio
async def test_trigger_sync_run_requires_admitted_airlock_reference() -> None:
    service = SyncService(AsyncMock())

    with pytest.raises(ValidationError, match="cannot run without an active intent/job context"):
        await service.trigger_sync_run(
            tenant_id=uuid.uuid4(),
            organisation_id=uuid.uuid4(),
            entity_id=None,
            connection_id=uuid.uuid4(),
            sync_definition_id=uuid.uuid4(),
            sync_definition_version_id=uuid.uuid4(),
            dataset_type=DatasetType.TRIAL_BALANCE,
            idempotency_key="idempotency-key",
            created_by=uuid.uuid4(),
            extraction_kwargs={},
        )


@pytest.mark.asyncio
async def test_trigger_sync_run_requires_admitted_airlock_reference_after_context() -> None:
    service = SyncService(AsyncMock())

    with governed_mutation_context(
        MutationContext(
            intent_id=uuid.uuid4(),
            job_id=uuid.uuid4(),
            actor_user_id=uuid.uuid4(),
            actor_role="finance_leader",
            intent_type="TEST_ERP_SYNC_TRIGGER",
        )
    ):
        with pytest.raises(ValidationError, match="admitted_airlock_item_id is required"):
            await service.trigger_sync_run(
                tenant_id=uuid.uuid4(),
                organisation_id=uuid.uuid4(),
                entity_id=None,
                connection_id=uuid.uuid4(),
                sync_definition_id=uuid.uuid4(),
                sync_definition_version_id=uuid.uuid4(),
                dataset_type=DatasetType.TRIAL_BALANCE,
                idempotency_key="idempotency-key",
                created_by=uuid.uuid4(),
                extraction_kwargs={},
            )
