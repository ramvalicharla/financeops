from __future__ import annotations

import uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.anomaly_pattern_phase1f6_helpers import (
    build_anomaly_service,
    ensure_tenant_context,
    seed_active_anomaly_configuration,
    seed_control_plane_for_anomaly,
    seed_upstream_for_anomaly,
)


async def _seed_alert_and_rule(
    async_session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
) -> tuple[str, str]:
    await seed_control_plane_for_anomaly(
        async_session,
        tenant_id=tenant_id,
        user_id=user_id,
        enable_module=True,
        grant_permissions=True,
    )
    await ensure_tenant_context(async_session, tenant_id)
    upstream = await seed_upstream_for_anomaly(
        async_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        created_by=user_id,
        reporting_period=date(2026, 1, 31),
    )
    await seed_active_anomaly_configuration(
        async_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        created_by=user_id,
        effective_from=date(2026, 1, 1),
    )
    service = build_anomaly_service(async_session)
    created = await service.create_run(
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        reporting_period=date(2026, 1, 31),
        source_metric_run_ids=[uuid.UUID(upstream["metric_run_id"])],
        source_variance_run_ids=[uuid.UUID(upstream["metric_run_id"])],
        source_trend_run_ids=[uuid.UUID(upstream["metric_run_id"])],
        source_risk_run_ids=[uuid.UUID(upstream["risk_run_id"])],
        source_reconciliation_session_ids=[],
        created_by=user_id,
    )
    executed = await service.execute_run(
        tenant_id=tenant_id,
        run_id=uuid.UUID(created["run_id"]),
        actor_user_id=user_id,
    )
    await async_session.commit()
    await ensure_tenant_context(async_session, tenant_id)
    alert_id = (
        await async_session.execute(
            text(
                """
                SELECT id
                FROM anomaly_results
                WHERE run_id = CAST(:run_id AS uuid)
                ORDER BY line_no ASC, id ASC
                LIMIT 1
                """
            ),
            {"run_id": executed["run_id"]},
        )
    ).scalar_one()
    rule_code = (
        await async_session.execute(
            text(
                """
                SELECT rule_code
                FROM anomaly_statistical_rules
                WHERE tenant_id = CAST(:tenant_id AS uuid)
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """
            ),
            {"tenant_id": str(tenant_id)},
        )
    ).scalar_one()
    return str(alert_id), str(rule_code)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_304_get_anomalies_returns_list(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_user,
    test_access_token: str,
) -> None:
    await _seed_alert_and_rule(async_session, tenant_id=test_user.tenant_id, user_id=test_user.id)
    response = await async_client.get(
        "/api/v1/anomalies",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert isinstance(data, list)
    assert len(data) >= 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_305_get_anomalies_filters_by_open_status(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_user,
    test_access_token: str,
) -> None:
    alert_id, _rule_code = await _seed_alert_and_rule(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
    )
    patch_response = await async_client.patch(
        f"/api/v1/anomalies/{alert_id}/status",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={"status": "RESOLVED", "note": "resolved in test"},
    )
    assert patch_response.status_code == 200

    response = await async_client.get(
        "/api/v1/anomalies?status=OPEN",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 200
    rows = response.json()["data"]
    assert all(str(row["alert_status"]).upper() == "OPEN" for row in rows)
    assert all(str(row["id"]) != alert_id for row in rows)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_306_patch_anomaly_status_resolved(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_user,
    test_access_token: str,
) -> None:
    alert_id, _rule_code = await _seed_alert_and_rule(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
    )
    response = await async_client.patch(
        f"/api/v1/anomalies/{alert_id}/status",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={"status": "RESOLVED", "note": "manual review complete"},
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["alert_status"] == "RESOLVED"
    assert payload["resolved_at"] is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_307_patch_snoozed_requires_snoozed_until(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_user,
    test_access_token: str,
) -> None:
    alert_id, _rule_code = await _seed_alert_and_rule(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
    )
    response = await async_client.patch(
        f"/api/v1/anomalies/{alert_id}/status",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={"status": "SNOOZED"},
    )
    assert response.status_code == 422


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_308_put_threshold_updates_rule(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_user,
    test_access_token: str,
) -> None:
    _alert_id, rule_code = await _seed_alert_and_rule(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
    )
    response = await async_client.put(
        f"/api/v1/anomalies/thresholds/{rule_code}",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={"threshold_value": "2.750000", "config": {"moderate_z": "2.25"}},
    )
    assert response.status_code == 200
    assert response.json()["data"] == {"rule_code": rule_code, "updated": True}
