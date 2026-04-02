from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient
from prometheus_client import REGISTRY

from financeops.api.v1 import health as health_module
from financeops.observability.middleware import LoggingMiddleware
from financeops.observability.workflow_signals import complete_workflow, start_workflow


def _counter_total(metric_prefix: str) -> float:
    total = 0.0
    for metric in REGISTRY.collect():
        if metric.name.startswith(metric_prefix):
            for sample in metric.samples:
                if sample.name.endswith("_total"):
                    total += float(sample.value)
    return total


@pytest.mark.asyncio
async def test_logging_middleware_sets_request_and_correlation_headers() -> None:
    app = FastAPI()
    app.add_middleware(LoggingMiddleware)

    @app.get("/ping")
    async def ping() -> JSONResponse:
        return JSONResponse({"ok": True})

    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=True),
        base_url="http://test",
    ) as client:
        response = await client.get("/ping", headers={"X-Correlation-ID": "corr-unit-1"})

    assert response.status_code == 200
    assert response.headers.get("X-Correlation-ID") == "corr-unit-1"
    assert response.headers.get("X-Request-ID")


@pytest.mark.asyncio
async def test_readiness_fails_when_dependency_unhealthy(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _db_bad() -> dict[str, Any]:
        return {"status": "unhealthy", "latency_ms": 1.0}

    async def _redis_ok() -> dict[str, Any]:
        return {"status": "healthy", "latency_ms": 1.0}

    monkeypatch.setattr(health_module, "_check_database", _db_bad)
    monkeypatch.setattr(health_module, "_check_redis", _redis_ok)

    payload, status_code = await health_module.build_readiness_payload(startup_errors=[])
    assert status_code == 503
    assert payload["ready"] is False
    assert payload["checks"]["database"]["status"] == "unhealthy"


@pytest.mark.asyncio
async def test_readiness_healthy_dependencies_report_ready_even_with_startup_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _db_ok() -> dict[str, Any]:
        return {"status": "healthy", "latency_ms": 1.0}

    async def _redis_ok() -> dict[str, Any]:
        return {"status": "healthy", "latency_ms": 1.0}

    monkeypatch.setattr(health_module, "_check_database", _db_ok)
    monkeypatch.setattr(health_module, "_check_redis", _redis_ok)

    payload, status_code = await health_module.build_readiness_payload(
        startup_errors=["startup warning"],
    )
    assert status_code == 200
    assert payload["ready"] is True
    assert payload["startup_errors"] == ["startup warning"]


def test_liveness_payload_shape() -> None:
    payload = health_module.build_liveness_payload()
    assert payload["status"] == "alive"
    assert payload["live"] is True
    assert "timestamp" in payload


def test_workflow_signals_increment_metrics() -> None:
    before = _counter_total("financeops_finance_workflow")
    timer = start_workflow(
        workflow="unit_workflow",
        tenant_id="tenant-unit",
        module="unit",
        correlation_id="corr-unit",
        run_id="run-unit",
    )
    complete_workflow(timer, status="success")
    after = _counter_total("financeops_finance_workflow")
    assert after > before


def test_metrics_route_is_registered() -> None:
    from financeops.main import app

    assert any(getattr(route, "path", None) == "/metrics" for route in app.routes)
