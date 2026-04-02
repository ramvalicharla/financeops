from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from starlette.requests import Request

from financeops.db.models.users import UserRole
from financeops.modules.accounting_layer.application.jv_service import _generate_jv_number
from financeops.modules.ai_cfo_layer.api import routes as ai_routes
from financeops.modules.analytics_layer.api.routes import _query_signature
from financeops.modules.analytics_layer.application.alert_service import list_alerts


def _make_request(path: str, query: str = "") -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": path,
        "headers": [],
        "query_string": query.encode("utf-8"),
        "scheme": "http",
        "server": ("testserver", 80),
        "client": ("127.0.0.1", 12345),
    }
    request = Request(scope)
    request.state.request_id = "req-unit"
    return request


class _ScalarResult:
    def __init__(self, value: int) -> None:
        self._value = value

    def scalar_one(self) -> int:
        return self._value


class _ListResult:
    class _Scalars:
        def all(self) -> list[object]:
            return []

    def scalars(self) -> "_ListResult._Scalars":
        return self._Scalars()


@pytest.mark.asyncio
async def test_generate_jv_number_uses_count_result() -> None:
    captured: dict[str, object] = {}

    class _Session:
        async def execute(self, stmt: object) -> _ScalarResult:
            captured["stmt"] = stmt
            return _ScalarResult(7)

    jv_number = await _generate_jv_number(
        _Session(),  # type: ignore[arg-type]
        tenant_id=uuid.uuid4(),
        fiscal_year=2026,
        fiscal_period=3,
    )

    assert jv_number == "JV-2026-03-0008"
    assert captured["stmt"] is not None


@pytest.mark.asyncio
async def test_list_alerts_applies_limit_and_offset() -> None:
    captured: dict[str, object] = {}

    class _Session:
        async def execute(self, stmt: object) -> _ListResult:
            captured["stmt"] = stmt
            return _ListResult()

    await list_alerts(
        _Session(),  # type: ignore[arg-type]
        tenant_id=uuid.uuid4(),
        limit=25,
        offset=10,
    )

    stmt = captured["stmt"]
    assert getattr(stmt, "_limit_clause").value == 25  # type: ignore[attr-defined]
    assert getattr(stmt, "_offset_clause").value == 10  # type: ignore[attr-defined]


def test_query_signature_is_order_insensitive() -> None:
    req_a = _make_request("/api/v1/analytics/kpis", "a=1&b=2")
    req_b = _make_request("/api/v1/analytics/kpis", "b=2&a=1")
    assert _query_signature(req_a) == _query_signature(req_b)


@pytest.mark.asyncio
async def test_narrative_async_endpoint_enqueues_task(monkeypatch: pytest.MonkeyPatch) -> None:
    user = SimpleNamespace(
        tenant_id=uuid.uuid4(),
        id=uuid.uuid4(),
        role=UserRole.finance_team,
    )

    class _Task:
        id = "task-123"

    def _fake_delay(**_: object) -> _Task:
        return _Task()

    monkeypatch.setattr(ai_routes.generate_narrative_async_task, "delay", _fake_delay)

    payload = await ai_routes.narrative_async_endpoint(
        request=_make_request("/api/v1/ai/narrative/async"),
        org_entity_id=None,
        org_group_id=None,
        from_date=None,
        to_date=None,
        comparison="prev_month",
        user=user,  # type: ignore[arg-type]
    )
    assert payload["success"] is True
    assert payload["data"]["task_id"] == "task-123"
    assert payload["data"]["status"] == "queued"


@pytest.mark.asyncio
async def test_narrative_task_status_success(monkeypatch: pytest.MonkeyPatch) -> None:
    user = SimpleNamespace(
        tenant_id=uuid.uuid4(),
        id=uuid.uuid4(),
        role=UserRole.finance_team,
    )

    class _Result:
        status = "SUCCESS"
        result = {"summary": "ok"}

        def successful(self) -> bool:
            return True

        def failed(self) -> bool:
            return False

    monkeypatch.setattr(ai_routes, "AsyncResult", lambda *_args, **_kwargs: _Result())

    payload = await ai_routes.narrative_task_status_endpoint(
        request=_make_request("/api/v1/ai/narrative/tasks/task-123"),
        task_id="task-123",
        user=user,  # type: ignore[arg-type]
    )
    assert payload["success"] is True
    assert payload["data"]["status"] == "success"
    assert payload["data"]["result"] == {"summary": "ok"}
