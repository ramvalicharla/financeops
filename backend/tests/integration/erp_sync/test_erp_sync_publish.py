from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.erp_sync import (
    ExternalConnection,
    ExternalSyncDefinition,
    ExternalSyncDefinitionVersion,
    ExternalSyncError,
    ExternalSyncPublishEvent,
    ExternalSyncRun,
)
from financeops.db.models.reconciliation import GlEntry
from financeops.modules.erp_sync.application.publish_service import PublishService
from financeops.modules.erp_sync.domain.exceptions import DuplicateGLEntryError
from financeops.modules.erp_sync.application.validation_service import VALIDATION_CATEGORIES
from financeops.services.audit_writer import AuditWriter
from tests.integration.erp_sync.test_erp_sync_publish_governance import _seed_sync_run
from tests.integration.erp_sync_phase4c_helpers import ensure_erp_sync_tenant_context


def _validation_summary(*, passed: bool, dataset_type: str) -> dict[str, object]:
    return {
        "dataset_type": dataset_type,
        "passed": passed,
        "run_status": "completed" if passed else "halted",
        "categories": [
            {"category": category, "passed": passed, "message": "ok" if passed else "failed"}
            for category in VALIDATION_CATEGORIES
        ],
    }


async def _seed_general_ledger_run(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    source_external_ref: str,
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
        record_data={"definition_code": f"def_{uuid.uuid4().hex[:8]}", "dataset_type": "general_ledger"},
        values={
            "organisation_id": organisation_id,
            "entity_id": None,
            "connection_id": connection.id,
            "definition_code": f"def_{uuid.uuid4().hex[:8]}",
            "definition_name": "GL Definition",
            "dataset_type": "general_ledger",
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
            "dataset_type": "general_ledger",
            "run_token": uuid.uuid4().hex,
        },
        values={
            "organisation_id": organisation_id,
            "entity_id": None,
            "connection_id": connection.id,
            "sync_definition_id": definition.id,
            "sync_definition_version_id": definition_version.id,
            "dataset_type": "general_ledger",
            "reporting_period_label": "2026-01",
            "run_token": uuid.uuid4().hex,
            "idempotency_key": uuid.uuid4().hex,
            "source_external_ref": source_external_ref,
            "run_status": "completed",
            "raw_snapshot_payload_hash": uuid.uuid4().hex,
            "mapping_version_token": uuid.uuid4().hex,
            "normalization_version": "phase4c.v1",
            "validation_summary_json": _validation_summary(passed=True, dataset_type="general_ledger"),
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
async def test_publish_gl_entry_rollback_when_sync_run_update_fails(
    erp_sync_phase4c_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_erp_sync_tenant_context(erp_sync_phase4c_session, tenant_id)
    run = await _seed_sync_run(erp_sync_phase4c_session, tenant_id=tenant_id, validation_passed=True)
    service = PublishService(erp_sync_phase4c_session)

    async def _boom(*, tenant_id: uuid.UUID, sync_run_id: uuid.UUID, created_by: uuid.UUID) -> None:
        _ = (tenant_id, sync_run_id, created_by)
        raise RuntimeError("period lock side effect failed")

    monkeypatch.setattr(service._period_lock_service, "auto_lock_on_publish", _boom)

    with pytest.raises(RuntimeError, match="period lock side effect failed"):
        await service.approve_publish_event(
            tenant_id=tenant_id,
            sync_run_id=run.id,
            idempotency_key=uuid.uuid4().hex,
            actor_user_id=tenant_id,
        )

    publish_events = (
        await erp_sync_phase4c_session.execute(
            select(ExternalSyncPublishEvent).where(ExternalSyncPublishEvent.sync_run_id == run.id)
        )
    ).scalars().all()
    assert publish_events == []

    error_rows = (
        await erp_sync_phase4c_session.execute(
            select(ExternalSyncError).where(
                ExternalSyncError.sync_run_id == run.id,
                ExternalSyncError.error_code == "PUBLISH_TRANSACTION_FAILED",
            )
        )
    ).scalars().all()
    assert len(error_rows) == 1


@pytest.mark.asyncio
@pytest.mark.integration
async def test_publish_deduplication_skips_already_posted_ref(
    erp_sync_phase4c_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_erp_sync_tenant_context(erp_sync_phase4c_session, tenant_id)
    run = await _seed_general_ledger_run(
        erp_sync_phase4c_session,
        tenant_id=tenant_id,
        source_external_ref="erp-ref-001",
    )

    erp_sync_phase4c_session.add(
        GlEntry(
            tenant_id=tenant_id,
            chain_hash="seed-chain",
            previous_hash="seed-prev",
            entity_id=None,
            period_year=2026,
            period_month=1,
            entity_name="ERP Entity",
            account_code="1000",
            account_name="Cash",
            debit_amount=Decimal("100.000000"),
            credit_amount=Decimal("0.000000"),
            description="seed",
            source_ref="erp-ref-001",
            currency="INR",
            uploaded_by=tenant_id,
        )
    )
    await erp_sync_phase4c_session.flush()

    payload = await PublishService(erp_sync_phase4c_session).approve_publish_event(
        tenant_id=tenant_id,
        sync_run_id=run.id,
        idempotency_key=uuid.uuid4().hex,
        actor_user_id=tenant_id,
    )

    assert payload["status"] == "approved"
    assert payload["gl_posting_skipped"] is True
    assert payload["skipped_external_ref"] == "erp-ref-001"
    assert payload["publish_event_id"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_publish_end_to_end_posts_gl_and_marks_sync_complete(
    erp_sync_phase4c_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_erp_sync_tenant_context(erp_sync_phase4c_session, tenant_id)
    run = await _seed_sync_run(erp_sync_phase4c_session, tenant_id=tenant_id, validation_passed=True)

    payload = await PublishService(erp_sync_phase4c_session).approve_publish_event(
        tenant_id=tenant_id,
        sync_run_id=run.id,
        idempotency_key=uuid.uuid4().hex,
        actor_user_id=tenant_id,
    )

    assert payload["status"] == "approved"
    assert payload["target_table"] == "reconciliation_trial_balance"
    assert payload["idempotent_replay"] is False

    row = (
        await erp_sync_phase4c_session.execute(
            select(ExternalSyncPublishEvent).where(ExternalSyncPublishEvent.id == uuid.UUID(payload["publish_event_id"]))
        )
    ).scalar_one()
    assert row.event_status == "approved"
    assert row.approved_at is not None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_duplicate_external_ref_raises_not_inserts(
    erp_sync_phase4c_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_erp_sync_tenant_context(erp_sync_phase4c_session, tenant_id)
    service = PublishService(erp_sync_phase4c_session)

    erp_sync_phase4c_session.add(
        GlEntry(
            tenant_id=tenant_id,
            chain_hash="seed-chain-1",
            previous_hash="seed-prev-1",
            entity_id=None,
            period_year=2026,
            period_month=1,
            entity_name="ERP Entity",
            account_code="1000",
            account_name="Cash",
            debit_amount=Decimal("100.000000"),
            credit_amount=Decimal("0.000000"),
            description="seed",
            source_ref="dup-ref-001",
            currency="INR",
            uploaded_by=tenant_id,
        )
    )
    await erp_sync_phase4c_session.flush()

    with pytest.raises(DuplicateGLEntryError, match="dup-ref-001"):
        await service.assert_gl_ref_not_already_posted(
            tenant_id=tenant_id,
            external_ref="dup-ref-001",
        )
