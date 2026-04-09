from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import date
from types import SimpleNamespace

import pytest

from financeops.core.intent.enums import IntentType
from financeops.workflows.month_end_close import activities


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _FakeSession:
    def __init__(self, values):
        self._values = list(values)
        self.commits = 0
        self.rollbacks = 0

    async def execute(self, _stmt):
        if not self._values:
            raise AssertionError("Unexpected execute() call")
        return _ScalarResult(self._values.pop(0))

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


@pytest.mark.asyncio
async def test_run_consolidation_uses_intent_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    tenant_id = uuid.uuid4()
    organisation_id = uuid.uuid4()
    source_run_id = uuid.uuid4()
    consolidation_run_id = uuid.uuid4()
    session = _FakeSession([organisation_id, source_run_id])
    calls: list[dict] = []

    @asynccontextmanager
    async def _tenant_session(_tenant_id):
        yield session

    async def _submit(self, *, intent_type, actor, payload, idempotency_key, target_id=None):
        calls.append(
            {
                "intent_type": intent_type,
                "actor_role": actor.role,
                "payload": payload,
                "target_id": target_id,
                "idempotency_key": idempotency_key,
            }
        )
        if intent_type == IntentType.RUN_CONSOLIDATION:
            return SimpleNamespace(record_refs={"run_id": str(consolidation_run_id)})
        return SimpleNamespace(record_refs={"entity_count": 4})

    monkeypatch.setattr(activities, "tenant_session", _tenant_session)
    monkeypatch.setattr("financeops.workflows.month_end_close.activities.IntentService.submit_intent", _submit)

    result = await activities.run_consolidation(str(tenant_id), "2025-03")

    assert result == {"entities_consolidated": 4}
    assert session.commits == 1
    assert [call["intent_type"] for call in calls] == [
        IntentType.RUN_CONSOLIDATION,
        IntentType.EXECUTE_CONSOLIDATION,
    ]
    assert calls[0]["payload"]["organisation_id"] == str(organisation_id)
    assert calls[0]["payload"]["reporting_period"] == "2025-03-01"
    assert calls[0]["payload"]["source_run_refs"][0]["run_id"] == str(source_run_id)
    assert calls[1]["target_id"] == consolidation_run_id


@pytest.mark.asyncio
async def test_generate_board_pack_uses_intent_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    tenant_id = uuid.uuid4()
    definition_id = uuid.uuid4()
    run_id = uuid.uuid4()
    session = _FakeSession([definition_id])
    calls: list[dict] = []

    @asynccontextmanager
    async def _tenant_session(_tenant_id):
        yield session

    async def _submit(self, *, intent_type, actor, payload, idempotency_key, target_id=None):
        calls.append(
            {
                "intent_type": intent_type,
                "actor_role": actor.role,
                "payload": payload,
                "target_id": target_id,
                "idempotency_key": idempotency_key,
            }
        )
        return SimpleNamespace(record_refs={"run_id": str(run_id)})

    monkeypatch.setattr(activities, "tenant_session", _tenant_session)
    monkeypatch.setattr("financeops.workflows.month_end_close.activities.IntentService.submit_intent", _submit)

    result = await activities.generate_board_pack(str(tenant_id), "2025-03")

    assert result == {"board_pack_id": str(run_id)}
    assert session.commits == 1
    assert len(calls) == 1
    assert calls[0]["intent_type"] == IntentType.GENERATE_BOARD_PACK
    assert calls[0]["payload"] == {
        "definition_id": str(definition_id),
        "period_start": date(2025, 3, 1).isoformat(),
        "period_end": date(2025, 3, 31).isoformat(),
    }
