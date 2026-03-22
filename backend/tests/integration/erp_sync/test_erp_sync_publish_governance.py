from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import ValidationError
from financeops.db.models.erp_sync import (
    ExternalBackdatedModificationAlert,
    ExternalConnection,
    ExternalPeriodLock,
    ExternalSyncDefinition,
    ExternalSyncDefinitionVersion,
    ExternalSyncDriftReport,
    ExternalSyncRun,
)
from financeops.modules.erp_sync.application.publish_service import PublishService
from financeops.modules.erp_sync.application.validation_service import VALIDATION_CATEGORIES
from financeops.services.audit_writer import AuditWriter
from tests.integration.erp_sync_phase4c_helpers import ensure_erp_sync_tenant_context


def _validation_summary(*, passed: bool) -> dict[str, object]:
    return {
        "dataset_type": "trial_balance",
        "passed": passed,
        "run_status": "completed" if passed else "halted",
        "categories": [
            {"category": category, "passed": passed, "message": "ok" if passed else "failed"}
            for category in VALIDATION_CATEGORIES
        ],
    }


async def _seed_sync_run(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    validation_passed: bool,
) -> ExternalSyncRun:
    organisation_id = tenant_id
    created_by = tenant_id

    connection = await AuditWriter.insert_financial_record(
        session,
        model_class=ExternalConnection,
        tenant_id=tenant_id,
        record_data={"connection_code": f"conn_{uuid.uuid4().hex[:8]}", "connector_type": "generic_file"},
        values={
            "organisation_id": organisation_id,
            "entity_id": None,
            "connector_type": "generic_file",
            "connection_code": f"conn_{uuid.uuid4().hex[:8]}",
            "connection_name": "ERP Connection",
            "source_system_instance_id": f"instance_{uuid.uuid4().hex[:8]}",
            "data_residency_region": "in",
            "pii_masking_enabled": True,
            "consent_reference": None,
            "pinned_connector_version": "1.0.0",
            "connection_status": "active",
            "secret_ref": "secret://test",
            "created_by": created_by,
        },
    )

    definition = await AuditWriter.insert_financial_record(
        session,
        model_class=ExternalSyncDefinition,
        tenant_id=tenant_id,
        record_data={"definition_code": f"def_{uuid.uuid4().hex[:8]}", "dataset_type": "trial_balance"},
        values={
            "organisation_id": organisation_id,
            "entity_id": None,
            "connection_id": connection.id,
            "definition_code": f"def_{uuid.uuid4().hex[:8]}",
            "definition_name": "Trial Balance Definition",
            "dataset_type": "trial_balance",
            "sync_mode": "full",
            "definition_status": "active",
            "created_by": created_by,
        },
    )

    definition_version = await AuditWriter.insert_financial_record(
        session,
        model_class=ExternalSyncDefinitionVersion,
        tenant_id=tenant_id,
        record_data={"sync_definition_id": str(definition.id), "version_no": 1, "version_token": uuid.uuid4().hex},
        values={
            "sync_definition_id": definition.id,
            "version_no": 1,
            "version_token": uuid.uuid4().hex,
            "period_resolution_json": {"granularity": "monthly"},
            "extraction_scope_json": {"scope": "all"},
            "supersedes_id": None,
            "status": "active",
            "created_by": created_by,
        },
    )

    return await AuditWriter.insert_financial_record(
        session,
        model_class=ExternalSyncRun,
        tenant_id=tenant_id,
        record_data={
            "connection_id": str(connection.id),
            "sync_definition_id": str(definition.id),
            "dataset_type": "trial_balance",
            "run_token": uuid.uuid4().hex,
        },
        values={
            "organisation_id": organisation_id,
            "entity_id": None,
            "connection_id": connection.id,
            "sync_definition_id": definition.id,
            "sync_definition_version_id": definition_version.id,
            "dataset_type": "trial_balance",
            "reporting_period_label": "2026-01",
            "run_token": uuid.uuid4().hex,
            "idempotency_key": uuid.uuid4().hex,
            "run_status": "completed",
            "raw_snapshot_payload_hash": uuid.uuid4().hex,
            "mapping_version_token": uuid.uuid4().hex,
            "normalization_version": "phase4c.v1",
            "validation_summary_json": _validation_summary(passed=validation_passed),
            "extraction_total_records": 10,
            "extraction_fetched_records": 10,
            "extraction_checkpoint": None,
            "extraction_chunk_size": 500,
            "is_resumable": False,
            "resumed_from_run_id": None,
            "published_at": None,
            "created_by": created_by,
        },
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_publish_blocked_when_validation_failed(erp_sync_phase4c_session: AsyncSession) -> None:
    tenant_id = uuid.uuid4()
    await ensure_erp_sync_tenant_context(erp_sync_phase4c_session, tenant_id)
    run = await _seed_sync_run(erp_sync_phase4c_session, tenant_id=tenant_id, validation_passed=False)
    service = PublishService(erp_sync_phase4c_session)

    with pytest.raises(ValidationError, match="validation summary"):
        await service.approve_publish_event(
            tenant_id=tenant_id,
            sync_run_id=run.id,
            idempotency_key=uuid.uuid4().hex,
            actor_user_id=tenant_id,
        )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_publish_blocked_when_drift_is_critical(erp_sync_phase4c_session: AsyncSession) -> None:
    tenant_id = uuid.uuid4()
    await ensure_erp_sync_tenant_context(erp_sync_phase4c_session, tenant_id)
    run = await _seed_sync_run(erp_sync_phase4c_session, tenant_id=tenant_id, validation_passed=True)
    await AuditWriter.insert_financial_record(
        erp_sync_phase4c_session,
        model_class=ExternalSyncDriftReport,
        tenant_id=tenant_id,
        record_data={"sync_run_id": str(run.id), "drift_severity": "critical"},
        values={
            "sync_run_id": run.id,
            "drift_detected": True,
            "drift_severity": "critical",
            "total_variances": 2,
            "metrics_checked_json": [],
            "generated_at": datetime.now(UTC),
            "created_by": tenant_id,
        },
    )
    service = PublishService(erp_sync_phase4c_session)

    with pytest.raises(ValidationError, match="critical drift"):
        await service.approve_publish_event(
            tenant_id=tenant_id,
            sync_run_id=run.id,
            idempotency_key=uuid.uuid4().hex,
            actor_user_id=tenant_id,
        )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_publish_blocked_when_backdated_alert_unacknowledged(
    erp_sync_phase4c_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_erp_sync_tenant_context(erp_sync_phase4c_session, tenant_id)
    run = await _seed_sync_run(erp_sync_phase4c_session, tenant_id=tenant_id, validation_passed=True)
    period_lock = await AuditWriter.insert_financial_record(
        erp_sync_phase4c_session,
        model_class=ExternalPeriodLock,
        tenant_id=tenant_id,
        record_data={
            "organisation_id": str(run.organisation_id),
            "dataset_type": run.dataset_type,
            "period_key": "2026-01",
        },
        values={
            "organisation_id": run.organisation_id,
            "entity_id": run.entity_id,
            "dataset_type": run.dataset_type,
            "period_key": "2026-01",
            "lock_status": "locked",
            "lock_reason": "seed",
            "source_sync_run_id": run.id,
            "supersedes_id": None,
            "created_by": tenant_id,
        },
    )
    await AuditWriter.insert_financial_record(
        erp_sync_phase4c_session,
        model_class=ExternalBackdatedModificationAlert,
        tenant_id=tenant_id,
        record_data={"sync_run_id": str(run.id), "severity": "critical"},
        values={
            "sync_run_id": run.id,
            "period_lock_id": period_lock.id,
            "severity": "critical",
            "alert_status": "open",
            "message": "critical backdated change",
            "details_json": {"source": "seed"},
            "acknowledged_by": None,
            "acknowledged_at": None,
            "created_by": tenant_id,
        },
    )
    service = PublishService(erp_sync_phase4c_session)

    with pytest.raises(ValidationError, match="backdated modification"):
        await service.approve_publish_event(
            tenant_id=tenant_id,
            sync_run_id=run.id,
            idempotency_key=uuid.uuid4().hex,
            actor_user_id=tenant_id,
        )
