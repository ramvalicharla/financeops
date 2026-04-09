from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from financeops.api.v1 import consolidation as consolidation_routes
from financeops.schemas.consolidation import ConsolidationRunRequest


@pytest.mark.asyncio
async def test_legacy_consolidation_route_uses_intent_service(monkeypatch: pytest.MonkeyPatch) -> None:
    user = SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        role=SimpleNamespace(value="finance_leader"),
    )
    request = SimpleNamespace(
        state=SimpleNamespace(correlation_id="corr-1"),
        headers={},
    )
    session = AsyncMock()
    submit_mock = AsyncMock(
        return_value=SimpleNamespace(
            record_refs={
                "run_id": str(uuid.uuid4()),
                "workflow_id": "wf-1",
                "status": "accepted",
                "correlation_id": "corr-1",
                "determinism_hash": "hash-1",
                "snapshot_refs": ["snap-1"],
            }
        )
    )

    monkeypatch.setattr("financeops.api.v1.consolidation.IntentService.submit_intent", submit_mock)
    monkeypatch.setattr(
        consolidation_routes,
        "resolve_effective_period_lock",
        AsyncMock(return_value=SimpleNamespace(is_hard_closed=False)),
    )
    monkeypatch.setattr(
        consolidation_routes,
        "start_workflow",
        lambda **_: object(),
    )
    monkeypatch.setattr(consolidation_routes, "complete_workflow", lambda *_, **__: None)
    monkeypatch.setattr(consolidation_routes, "fail_workflow", lambda *_, **__: None)
    monkeypatch.setattr(
        consolidation_routes,
        "create_or_get_run",
        AsyncMock(side_effect=AssertionError("route should not call create_or_get_run directly")),
    )

    result = await consolidation_routes.start_consolidation_run_endpoint(
        body=ConsolidationRunRequest(
            period_year=2026,
            period_month=4,
            parent_currency="USD",
            rate_mode="daily",
            entity_snapshots=[
                {
                    "entity_id": uuid.uuid4(),
                    "snapshot_id": uuid.uuid4(),
                }
            ],
        ),
        request=request,
        session=session,
        user=user,
    )

    assert result["status"] == "accepted"
    assert result["determinism_hash"] == "hash-1"
    assert result["snapshot_refs"] == ["snap-1"]
    submit_mock.assert_awaited_once()
