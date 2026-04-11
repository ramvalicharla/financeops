from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.platform.api.v1 import control_plane as control_plane_routes
from financeops.core.governance.events import GovernanceActor, emit_governance_event
from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql
from financeops.db.models.governance_control import CanonicalGovernanceEvent
from financeops.platform.services.control_plane.phase4_service import Phase4ControlPlaneService
from financeops.services.audit_writer import AuditWriter


def _scalar_result(value):
    return SimpleNamespace(scalar_one_or_none=lambda: value)


@pytest.mark.asyncio
async def test_determinism_endpoint_translates_missing_subject(monkeypatch: pytest.MonkeyPatch) -> None:
    session = AsyncMock()
    user = SimpleNamespace(id=uuid.uuid4(), tenant_id=uuid.uuid4(), role=SimpleNamespace(value="finance_leader"))
    request = SimpleNamespace(state=SimpleNamespace(request_id="req-1"))
    service = SimpleNamespace(build_determinism_summary=AsyncMock(side_effect=ValueError("snapshot not found")))

    monkeypatch.setattr(control_plane_routes, "_phase4_service", lambda _session: service)

    with pytest.raises(HTTPException) as exc_info:
        await control_plane_routes.get_determinism_endpoint(
            request=request,
            subject_type="report_run",
            subject_id=str(uuid.uuid4()),
            session=session,
            user=user,
        )

    assert exc_info.value.status_code == 404
    assert "snapshot not found" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_ensure_snapshot_reuses_latest_when_hash_matches(monkeypatch: pytest.MonkeyPatch) -> None:
    service = Phase4ControlPlaneService(SimpleNamespace(execute=AsyncMock(return_value=_scalar_result(None))))
    latest_snapshot = SimpleNamespace(id=uuid.uuid4(), determinism_hash="hash-1", version_no=2)
    resolve_mock = AsyncMock(
        return_value={
            "module_key": "reports",
            "snapshot_kind": "report_output",
            "subject_type": "report_run",
            "subject_id": "run-1",
            "entity_id": None,
            "determinism_hash": "hash-1",
            "payload": {},
            "comparison_payload": {},
            "inputs": [],
            "metadata": {},
        }
    )
    monkeypatch.setattr(service, "_resolve_subject", resolve_mock)
    monkeypatch.setattr(service, "_latest_subject_snapshot", AsyncMock(return_value=latest_snapshot))

    result = await service.ensure_snapshot_for_subject(
        tenant_id=uuid.uuid4(),
        actor_user_id=uuid.uuid4(),
        actor_role="finance_leader",
        subject_type="report_run",
        subject_id="run-1",
        trigger_event="report_generation_complete",
    )

    assert result is latest_snapshot


@pytest.mark.asyncio
async def test_ensure_snapshot_creates_new_version_when_hash_changes(monkeypatch: pytest.MonkeyPatch) -> None:
    service = Phase4ControlPlaneService(SimpleNamespace(execute=AsyncMock(return_value=_scalar_result(None))))
    tenant_id = uuid.uuid4()
    actor_user_id = uuid.uuid4()
    latest_snapshot = SimpleNamespace(id=uuid.uuid4(), determinism_hash="old-hash", version_no=4)
    created_snapshot = SimpleNamespace(id=uuid.uuid4(), determinism_hash="new-hash", version_no=5)

    monkeypatch.setattr(
        service,
        "_resolve_subject",
        AsyncMock(
            return_value={
                "module_key": "reports",
                "snapshot_kind": "report_output",
                "subject_type": "report_run",
                "subject_id": "run-2",
                "entity_id": None,
                "determinism_hash": "new-hash",
                "replay_supported": True,
                "payload": {"row_count": 2},
                "comparison_payload": {"row_count": 2},
                "inputs": [
                    {
                        "input_type": "report_definition",
                        "input_ref": "definition-1",
                        "input_hash": None,
                        "input_payload": {"filters": 2},
                    }
                ],
                "metadata": {"status": "COMPLETE"},
            }
        ),
    )
    monkeypatch.setattr(service, "_latest_subject_snapshot", AsyncMock(return_value=latest_snapshot))
    monkeypatch.setattr(service, "_resolve_event_actor_user_id", AsyncMock(return_value=actor_user_id))

    insert_calls: list[tuple[object, dict[str, object]]] = []

    async def insert_stub(_session, *, model_class, tenant_id, record_data, values, audit=None):
        insert_calls.append((model_class, values))
        if model_class.__name__ == "GovernanceSnapshot":
            return created_snapshot
        return SimpleNamespace(id=uuid.uuid4(), **values)

    emit_mock = AsyncMock()
    monkeypatch.setattr("financeops.platform.services.control_plane.phase4_service.AuditWriter.insert_financial_record", insert_stub)
    monkeypatch.setattr("financeops.platform.services.control_plane.phase4_service.emit_governance_event", emit_mock)

    result = await service.ensure_snapshot_for_subject(
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        actor_role="finance_leader",
        subject_type="report_run",
        subject_id="run-2",
        trigger_event="manual_snapshot",
    )

    assert result is created_snapshot
    assert insert_calls[0][1]["version_no"] == 5
    assert insert_calls[0][1]["determinism_hash"] == "new-hash"
    assert emit_mock.await_count == 1


@pytest.mark.asyncio
async def test_resolve_accounting_period_subject_returns_hashable_payload() -> None:
    tenant_id = uuid.uuid4()
    period_id = uuid.uuid4()
    entity_id = uuid.uuid4()
    session = AsyncMock()
    session.execute = AsyncMock(
        return_value=_scalar_result(
            SimpleNamespace(
                id=period_id,
                tenant_id=tenant_id,
                org_entity_id=entity_id,
                fiscal_year=2026,
                period_number=3,
                period_start=__import__("datetime").date(2026, 3, 1),
                period_end=__import__("datetime").date(2026, 3, 31),
                status="HARD_CLOSED",
                locked_by=None,
                locked_at=None,
                reopened_by=None,
                reopened_at=None,
                notes="period closed",
            )
        )
    )

    payload = await Phase4ControlPlaneService(session)._resolve_accounting_period_subject(
        tenant_id=tenant_id,
        subject_id=str(period_id),
    )

    assert payload is not None
    assert payload["subject_type"] == "accounting_period"
    assert payload["subject_id"] == str(period_id)
    assert payload["determinism_hash"]


@pytest.mark.asyncio
async def test_verify_determinism_hash_compares_expected_hash(monkeypatch: pytest.MonkeyPatch) -> None:
    service = Phase4ControlPlaneService(SimpleNamespace(execute=AsyncMock()))
    monkeypatch.setattr(
        service,
        "build_determinism_summary",
        AsyncMock(
            return_value={
                "snapshot_id": "snapshot-1",
                "determinism_hash": "hash-1",
                "replay_supported": True,
                "replay": {"recomputed_hash": "hash-1", "matches": True},
            }
        ),
    )

    payload = await service.verify_determinism_hash(
        tenant_id=uuid.uuid4(),
        actor_user_id=uuid.uuid4(),
        actor_role="finance_leader",
        subject_type="report_run",
        subject_id="run-1",
        expected_hash="hash-1",
    )

    assert payload["matches_expected"] is True
    assert payload["matches_replay"] is True
    assert payload["snapshot_id"] == "snapshot-1"


def test_serialize_job_exposes_capability_contract() -> None:
    job = SimpleNamespace(
        id=uuid.uuid4(),
        job_type="RUN_REPORT",
        status="FAILED",
        runner_type="inline",
        queue_name="governed",
        requested_at=None,
        started_at=None,
        finished_at=None,
        failed_at=None,
        retry_count=0,
        max_retries=0,
        error_code=None,
        error_message="boom",
        error_details_json=None,
    )

    payload = control_plane_routes._serialize_job(job, entity_id=None, intent_id=uuid.uuid4())

    assert payload["capabilities"]["retry"]["supported"] is False
    assert payload["capabilities"]["retry"]["allowed"] is False
    assert payload["capabilities"]["retry"]["reason"] == "Not supported in current backend contract"


@pytest.mark.asyncio
async def test_timeline_semantics_endpoint_returns_backend_metadata() -> None:
    request = SimpleNamespace(state=SimpleNamespace(request_id="req-1"))
    user = SimpleNamespace(role=SimpleNamespace(value="finance_leader"))

    payload = await control_plane_routes.get_timeline_semantics_endpoint(
        request=request,
        user=user,
    )

    assert payload["data"]["title"] == "Timeline"
    assert payload["data"]["semantics"]["authoritative"] is True


@pytest.mark.asyncio
async def test_resolve_report_definition_subject_returns_hashable_payload() -> None:
    tenant_id = uuid.uuid4()
    definition_id = uuid.uuid4()
    session = AsyncMock()
    session.execute = AsyncMock(
        return_value=_scalar_result(
            SimpleNamespace(
                id=definition_id,
                tenant_id=tenant_id,
                name="Revenue report",
                description="desc",
                metric_keys=["mis.kpi.revenue"],
                filter_config={},
                group_by=[],
                sort_config={},
                export_formats=["CSV"],
                config={},
                is_active=True,
            )
        )
    )

    payload = await Phase4ControlPlaneService(session)._resolve_report_definition_subject(
        tenant_id=tenant_id,
        subject_id=str(definition_id),
    )

    assert payload is not None
    assert payload["subject_type"] == "report_definition"
    assert payload["subject_id"] == str(definition_id)
    assert payload["determinism_hash"]


@pytest.mark.asyncio
async def test_lineage_and_impact_include_semantics(monkeypatch: pytest.MonkeyPatch) -> None:
    service = Phase4ControlPlaneService(SimpleNamespace(execute=AsyncMock()))
    monkeypatch.setattr(
        service,
        "_forward_lineage_for_run",
        AsyncMock(return_value={"nodes": [{"run_id": "run-1"}], "edges": []}),
    )
    monkeypatch.setattr(
        service,
        "_reverse_lineage_for_run",
        AsyncMock(return_value={"nodes": [{"subject_type": "report_run"}], "edges": []}),
    )

    lineage = await service.build_lineage(
        tenant_id=uuid.uuid4(),
        subject_type="run",
        subject_id=str(uuid.uuid4()),
    )
    impact = await service.build_impact(
        tenant_id=uuid.uuid4(),
        subject_type="run",
        subject_id=str(uuid.uuid4()),
    )

    assert lineage["semantics"]["authoritative"] is True
    assert impact["semantics"]["authoritative"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("resolver_name", "row", "expected_subject_type", "expected_module_key"),
    [
        (
            "_resolve_journal_subject",
            SimpleNamespace(
                id=uuid.uuid4(),
                tenant_id=uuid.uuid4(),
                entity_id=uuid.uuid4(),
                jv_number="JV-001",
                status="APPROVED",
                version=2,
                period_date=__import__("datetime").date(2026, 4, 1),
                fiscal_year=2026,
                fiscal_period=4,
                description="April journal",
                reference="REF-1",
                source="manual",
                external_reference_id=None,
                total_debit="100.00",
                total_credit="100.00",
                currency="INR",
                created_by_intent_id=None,
                recorded_by_job_id=None,
                submitted_at=None,
                first_reviewed_at=None,
                decided_at=None,
                voided_at=None,
            ),
            "journal",
            "accounting_layer",
        ),
        (
            "_resolve_fixed_asset_subject",
            SimpleNamespace(
                id=uuid.uuid4(),
                tenant_id=uuid.uuid4(),
                entity_id=uuid.uuid4(),
                asset_class_id=uuid.uuid4(),
                asset_code="FA-001",
                asset_name="Laptop Fleet",
                description="Devices",
                status="ACTIVE",
                purchase_date=__import__("datetime").date(2026, 1, 1),
                capitalisation_date=__import__("datetime").date(2026, 1, 2),
                original_cost="1500.00",
                residual_value="100.00",
                useful_life_years="3",
                depreciation_method="SLM",
                disposal_date=None,
                disposal_proceeds=None,
                is_active=True,
            ),
            "fixed_asset",
            "fixed_assets",
        ),
        (
            "_resolve_prepaid_schedule_subject",
            SimpleNamespace(
                id=uuid.uuid4(),
                tenant_id=uuid.uuid4(),
                entity_id=uuid.uuid4(),
                reference_number="PP-001",
                description="Insurance",
                prepaid_type="insurance",
                vendor_name="Carrier",
                invoice_number="INV-1",
                total_amount="1200.00",
                amortised_amount="100.00",
                remaining_amount="1100.00",
                coverage_start=__import__("datetime").date(2026, 1, 1),
                coverage_end=__import__("datetime").date(2026, 12, 31),
                amortisation_method="straight_line",
                status="ACTIVE",
            ),
            "prepaid_schedule",
            "prepaid",
        ),
        (
            "_resolve_gst_return_subject",
            SimpleNamespace(
                id=uuid.uuid4(),
                tenant_id=uuid.uuid4(),
                entity_id=uuid.uuid4(),
                period_year=2026,
                period_month=4,
                gstin="29ABCDE1234F1Z5",
                return_type="GSTR3B",
                taxable_value="5000.00",
                igst_amount="0.00",
                cgst_amount="450.00",
                sgst_amount="450.00",
                cess_amount="0.00",
                total_tax="900.00",
                status="FILED",
                filing_date=__import__("datetime").date(2026, 5, 20),
                notes="Submitted",
            ),
            "gst_return",
            "gst",
        ),
        (
            "_resolve_erp_sync_run_subject",
            SimpleNamespace(
                id=uuid.uuid4(),
                tenant_id=uuid.uuid4(),
                organisation_id=uuid.uuid4(),
                entity_id=uuid.uuid4(),
                connection_id=uuid.uuid4(),
                sync_definition_id=uuid.uuid4(),
                sync_definition_version_id=uuid.uuid4(),
                dataset_type="gl_entries",
                reporting_period_label="2026-04",
                run_token="sync-1",
                run_status="PUBLISHED",
                source_airlock_item_id=None,
                source_type="erp",
                source_external_ref="ext-1",
                raw_snapshot_payload_hash="h" * 64,
                mapping_version_token="map-v1",
                normalization_version="norm-v1",
                validation_summary_json={"ok": True},
                extraction_total_records=20,
                extraction_fetched_records=20,
                published_at=datetime(2026, 4, 10, tzinfo=UTC),
            ),
            "erp_sync_run",
            "erp_sync",
        ),
    ],
)
async def test_new_financial_subject_resolvers_return_hashable_payload(
    resolver_name: str,
    row: SimpleNamespace,
    expected_subject_type: str,
    expected_module_key: str,
) -> None:
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_scalar_result(row))
    service = Phase4ControlPlaneService(session)

    payload = await getattr(service, resolver_name)(
        tenant_id=row.tenant_id,
        subject_id=str(row.id),
    )

    assert payload is not None
    assert payload["subject_type"] == expected_subject_type
    assert payload["module_key"] == expected_module_key
    assert payload["subject_id"] == str(row.id)
    assert payload["determinism_hash"]
    assert payload["replay_supported"] is False


@pytest.mark.asyncio
async def test_timeline_for_governance_events_is_append_only_and_ordered(
    async_session: AsyncSession,
    test_user,
) -> None:
    await async_session.execute(text(append_only_function_sql()))
    await async_session.execute(text(drop_trigger_sql("canonical_governance_events")))
    await async_session.execute(text(create_trigger_sql("canonical_governance_events")))
    await async_session.flush()

    occurred_at = datetime(2026, 4, 10, 10, 0, tzinfo=UTC)
    first = await AuditWriter.insert_financial_record(
        async_session,
        model_class=CanonicalGovernanceEvent,
        tenant_id=test_user.tenant_id,
        record_data={
            "module_key": "accounting_layer",
            "subject_type": "journal",
            "subject_id": "journal-1",
            "event_type": "JOURNAL_SUBMITTED",
        },
        values={
            "entity_id": None,
            "module_key": "accounting_layer",
            "subject_type": "journal",
            "subject_id": "journal-1",
            "event_type": "JOURNAL_SUBMITTED",
            "actor_user_id": test_user.id,
            "actor_role": "finance_leader",
            "payload_json": {"step": 1},
            "created_at": occurred_at,
        },
    )
    second = await AuditWriter.insert_financial_record(
        async_session,
        model_class=CanonicalGovernanceEvent,
        tenant_id=test_user.tenant_id,
        record_data={
            "module_key": "accounting_layer",
            "subject_type": "journal",
            "subject_id": "journal-1",
            "event_type": "JOURNAL_APPROVED",
        },
        values={
            "entity_id": None,
            "module_key": "accounting_layer",
            "subject_type": "journal",
            "subject_id": "journal-1",
            "event_type": "JOURNAL_APPROVED",
            "actor_user_id": test_user.id,
            "actor_role": "finance_leader",
            "payload_json": {"step": 2},
            "created_at": occurred_at + timedelta(minutes=1),
        },
    )
    await async_session.flush()

    timeline = await Phase4ControlPlaneService(async_session).build_timeline(
        tenant_id=test_user.tenant_id,
        subject_type="journal",
        subject_id="journal-1",
        limit=10,
    )

    governance_events = [event for event in timeline if event["module_key"] == "accounting_layer"]
    assert [event["timeline_type"] for event in governance_events] == [
        "JOURNAL_SUBMITTED",
        "JOURNAL_APPROVED",
    ]

    update_attempt = await async_session.begin_nested()
    with pytest.raises(DBAPIError):
        await async_session.execute(
            text("UPDATE canonical_governance_events SET event_type='MUTATED' WHERE id = CAST(:id AS uuid)"),
            {"id": str(first.id)},
        )
    await update_attempt.rollback()

    delete_attempt = await async_session.begin_nested()
    with pytest.raises(DBAPIError):
        await async_session.execute(
            text("DELETE FROM canonical_governance_events WHERE id = CAST(:id AS uuid)"),
            {"id": str(second.id)},
        )
    await delete_attempt.rollback()
