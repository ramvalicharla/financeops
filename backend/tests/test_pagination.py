from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.rls import set_tenant_context


async def _insert_anomaly_run(async_session: AsyncSession, tenant_id: uuid.UUID) -> uuid.UUID:
    run_id = uuid.uuid4()
    await async_session.execute(
        text(
            """
            INSERT INTO anomaly_runs (
                id, tenant_id, chain_hash, previous_hash, created_at,
                organisation_id, reporting_period,
                anomaly_definition_version_token, pattern_rule_version_token,
                persistence_rule_version_token, correlation_rule_version_token,
                statistical_rule_version_token,
                source_metric_run_ids_json, source_variance_run_ids_json,
                source_trend_run_ids_json, source_risk_run_ids_json,
                source_reconciliation_session_ids_json,
                run_token, status, validation_summary_json, created_by
            ) VALUES (
                :id, :tenant_id, :chain_hash, :previous_hash, :created_at,
                :organisation_id, :reporting_period,
                :anomaly_definition_version_token, :pattern_rule_version_token,
                :persistence_rule_version_token, :correlation_rule_version_token,
                :statistical_rule_version_token,
                CAST(:source_metric_run_ids_json AS jsonb), CAST(:source_variance_run_ids_json AS jsonb),
                CAST(:source_trend_run_ids_json AS jsonb), CAST(:source_risk_run_ids_json AS jsonb),
                CAST(:source_reconciliation_session_ids_json AS jsonb),
                :run_token, :status, CAST(:validation_summary_json AS jsonb), :created_by
            )
            """
        ),
        {
            "id": str(run_id),
            "tenant_id": str(tenant_id),
            "chain_hash": "0" * 64,
            "previous_hash": "0" * 64,
            "created_at": datetime.now(UTC),
            "organisation_id": str(tenant_id),
            "reporting_period": date(2026, 1, 31),
            "anomaly_definition_version_token": "def-token",
            "pattern_rule_version_token": "pattern-token",
            "persistence_rule_version_token": "persist-token",
            "correlation_rule_version_token": "corr-token",
            "statistical_rule_version_token": "stat-token",
            "source_metric_run_ids_json": f"[\"{uuid.uuid4()}\"]",
            "source_variance_run_ids_json": f"[\"{uuid.uuid4()}\"]",
            "source_trend_run_ids_json": "[]",
            "source_risk_run_ids_json": "[]",
            "source_reconciliation_session_ids_json": "[]",
            "run_token": f"run_{uuid.uuid4().hex}",
            "status": "completed",
            "validation_summary_json": "{}",
            "created_by": str(tenant_id),
        },
    )
    await async_session.flush()
    return run_id


async def _insert_anomaly_alerts(
    async_session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    run_id: uuid.UUID,
    count: int,
) -> None:
    for idx in range(count):
        await async_session.execute(
            text(
                """
                INSERT INTO anomaly_results (
                    id, tenant_id, run_id, chain_hash, previous_hash, created_at,
                    line_no, anomaly_code, anomaly_name, anomaly_domain, anomaly_score,
                    z_score, severity, alert_status, persistence_classification, correlation_flag,
                    materiality_elevated, risk_elevated, board_flag, confidence_score,
                    seasonal_adjustment_flag, seasonal_normalized_value, benchmark_group_id,
                    benchmark_baseline_value, benchmark_deviation_score, source_summary_json,
                    created_by
                ) VALUES (
                    :id, :tenant_id, :run_id, :chain_hash, :previous_hash, :created_at,
                    :line_no, :anomaly_code, :anomaly_name, :anomaly_domain, :anomaly_score,
                    :z_score, :severity, :alert_status, :persistence_classification, :correlation_flag,
                    :materiality_elevated, :risk_elevated, :board_flag, :confidence_score,
                    :seasonal_adjustment_flag, :seasonal_normalized_value, :benchmark_group_id,
                    :benchmark_baseline_value, :benchmark_deviation_score, CAST(:source_summary_json AS jsonb),
                    :created_by
                )
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "tenant_id": str(tenant_id),
                "run_id": str(run_id),
                "chain_hash": "1" * 64,
                "previous_hash": "0" * 64,
                "created_at": datetime.now(UTC),
                "line_no": idx + 1,
                "anomaly_code": f"ANOM_{idx}",
                "anomaly_name": "Anomaly Test",
                "anomaly_domain": "payroll",
                "anomaly_score": "0.850000",
                "z_score": "1.500000",
                "severity": "high",
                "alert_status": "OPEN",
                "persistence_classification": "first_detected",
                "correlation_flag": False,
                "materiality_elevated": False,
                "risk_elevated": False,
                "board_flag": False,
                "confidence_score": "0.900000",
                "seasonal_adjustment_flag": False,
                "seasonal_normalized_value": None,
                "benchmark_group_id": None,
                "benchmark_baseline_value": None,
                "benchmark_deviation_score": None,
                "source_summary_json": "{}",
                "created_by": str(tenant_id),
            },
        )
    await async_session.flush()


@pytest.mark.asyncio
async def test_anomaly_list_is_paginated(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_access_token: str,
    test_user,
) -> None:
    """GET /anomalies returns paginated envelope."""
    await set_tenant_context(async_session, test_user.tenant_id)
    run_id = await _insert_anomaly_run(async_session, test_user.tenant_id)
    await _insert_anomaly_alerts(
        async_session,
        tenant_id=test_user.tenant_id,
        run_id=run_id,
        count=25,
    )
    response = await async_client.get(
        "/api/v1/anomalies?limit=10&offset=0&status=ALL",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert {"data", "total", "limit", "offset"}.issubset(payload.keys())
    assert len(payload["data"]) == 10
    assert payload["total"] == 25
    assert payload["limit"] == 10
    assert payload["offset"] == 0


@pytest.mark.asyncio
async def test_pagination_second_page(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_access_token: str,
    test_user,
) -> None:
    """Second page returns correct slice."""
    await set_tenant_context(async_session, test_user.tenant_id)
    run_id = await _insert_anomaly_run(async_session, test_user.tenant_id)
    await _insert_anomaly_alerts(
        async_session,
        tenant_id=test_user.tenant_id,
        run_id=run_id,
        count=25,
    )
    response = await async_client.get(
        "/api/v1/anomalies?limit=10&offset=10&status=ALL",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert len(payload["data"]) == 10
    assert payload["offset"] == 10


@pytest.mark.asyncio
async def test_pagination_last_page(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_access_token: str,
    test_user,
) -> None:
    """Last page returns remaining records."""
    await set_tenant_context(async_session, test_user.tenant_id)
    run_id = await _insert_anomaly_run(async_session, test_user.tenant_id)
    await _insert_anomaly_alerts(
        async_session,
        tenant_id=test_user.tenant_id,
        run_id=run_id,
        count=25,
    )
    response = await async_client.get(
        "/api/v1/anomalies?limit=10&offset=20&status=ALL",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert len(payload["data"]) == 5
    assert payload["total"] == 25


@pytest.mark.asyncio
async def test_pagination_limit_enforced(
    async_client: AsyncClient,
    test_access_token: str,
) -> None:
    """limit > 100 is rejected with 422."""
    response = await async_client.get(
        "/api/v1/anomalies?limit=101&status=ALL",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_default_limit_is_20(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_access_token: str,
    test_user,
) -> None:
    """Default limit is 20 when not specified."""
    await set_tenant_context(async_session, test_user.tenant_id)
    run_id = await _insert_anomaly_run(async_session, test_user.tenant_id)
    await _insert_anomaly_alerts(
        async_session,
        tenant_id=test_user.tenant_id,
        run_id=run_id,
        count=30,
    )
    response = await async_client.get(
        "/api/v1/anomalies?status=ALL",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 200
    assert isinstance(response.json()["data"], list)
    assert len(response.json()["data"]) == 20


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "endpoint",
    [
        "/api/v1/pipeline/runs?limit=5&offset=0",
        "/api/v1/secrets/rotation-log?limit=5&offset=0",
        "/api/v1/erp-sync/sync-runs?limit=5&offset=0",
        "/api/v1/erp-sync/connections?limit=5&offset=0",
    ],
)
async def test_paginated_endpoints_return_envelope(
    async_client: AsyncClient,
    test_access_token: str,
    endpoint: str,
) -> None:
    """Selected list endpoints return paginated envelope when limit/offset are provided."""
    response = await async_client.get(
        endpoint,
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert "data" in payload
    assert "total" in payload
    assert "limit" in payload
    assert "offset" in payload


@pytest.mark.asyncio
async def test_onboarding_templates_paginated(async_client: AsyncClient) -> None:
    """Public onboarding template list supports pagination envelope."""
    response = await async_client.get("/api/v1/onboarding/templates?limit=5&offset=0")
    assert response.status_code == 200
    payload = response.json()["data"]
    assert "data" in payload
    assert payload["limit"] == 5
    assert payload["offset"] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "endpoint",
    [
        "/api/v1/pipeline/runs?limit=101&offset=0",
        "/api/v1/secrets/rotation-log?limit=201&offset=0",
        "/api/v1/erp-sync/sync-runs?limit=101&offset=0",
        "/api/v1/erp-sync/connections?limit=101&offset=0",
    ],
)
async def test_limit_upper_bound_enforced_on_paginated_endpoints(
    async_client: AsyncClient,
    test_access_token: str,
    endpoint: str,
) -> None:
    """Paginated endpoints reject out-of-range limit values."""
    response = await async_client.get(
        endpoint,
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "endpoint",
    [
        "/api/v1/pipeline/runs",
        "/api/v1/secrets/rotation-log",
        "/api/v1/erp-sync/sync-runs",
        "/api/v1/erp-sync/connections",
    ],
)
async def test_default_limit_is_20_on_paginated_endpoints(
    async_client: AsyncClient,
    test_access_token: str,
    endpoint: str,
) -> None:
    """Paginated endpoints default to limit=20 when limit is omitted."""
    response = await async_client.get(
        endpoint,
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    if isinstance(payload, dict):
        if "limit" in payload:
            assert payload["limit"] == 20
        if "offset" in payload:
            assert payload["offset"] == 0
        list_values = [value for value in payload.values() if isinstance(value, list)]
        if list_values:
            assert all(len(value) <= 20 for value in list_values)
    else:
        assert isinstance(payload, list)
        assert len(payload) <= 20


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "endpoint",
    [
        "/api/v1/pipeline/runs?limit=10&offset=-1",
        "/api/v1/secrets/rotation-log?limit=10&offset=-1",
        "/api/v1/erp-sync/sync-runs?limit=10&offset=-1",
        "/api/v1/erp-sync/connections?limit=10&offset=-1",
    ],
)
async def test_negative_offset_rejected_on_paginated_endpoints(
    async_client: AsyncClient,
    test_access_token: str,
    endpoint: str,
) -> None:
    """Paginated endpoints reject negative offset values."""
    response = await async_client.get(
        endpoint,
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 422
