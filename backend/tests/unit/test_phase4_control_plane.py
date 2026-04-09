from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from financeops.platform.api.v1 import control_plane as control_plane_routes
from financeops.platform.services.control_plane.phase4_service import Phase4ControlPlaneService


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
