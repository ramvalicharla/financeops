from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from financeops.modules.multi_entity_consolidation.domain.exceptions import (
    MissingSourceEntityError,
)
from tests.integration.entitlement_helpers import grant_boolean_entitlement


@pytest.fixture(autouse=True)
async def _grant_consolidation_entitlement(api_db_session, api_test_user, async_session, test_user) -> None:
    await grant_boolean_entitlement(
        api_db_session,
        tenant_id=api_test_user.tenant_id,
        feature_name="multi_entity_consolidation",
        actor_user_id=api_test_user.id,
    )
    await grant_boolean_entitlement(
        api_db_session,
        tenant_id=api_test_user.tenant_id,
        feature_name="consolidation",
        actor_user_id=api_test_user.id,
    )
    await grant_boolean_entitlement(
        async_session,
        tenant_id=test_user.tenant_id,
        feature_name="multi_entity_consolidation",
        actor_user_id=test_user.id,
    )
    await grant_boolean_entitlement(
        async_session,
        tenant_id=test_user.tenant_id,
        feature_name="consolidation",
        actor_user_id=test_user.id,
    )


@pytest.mark.asyncio
async def test_group_consolidation_summary_returns_404_for_unknown_group(
    async_client: AsyncClient,
    test_access_token: str,
    test_user,
) -> None:
    _ = test_user
    response = await async_client.get(
        f"/api/v1/consolidation/summary?org_group_id={uuid.uuid4()}&as_of_date=2026-03-31",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )

    assert response.status_code == 404
    payload = response.json()["error"]
    assert payload["code"] == "not_found"
    assert payload["message"] == "Organisation group not found"


@pytest.mark.asyncio
async def test_multi_entity_consolidation_endpoints_return_derived_outputs(
    async_client: AsyncClient,
    api_test_access_token: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from financeops.modules.multi_entity_consolidation.api import routes as consolidation_routes

    run_id = uuid.uuid4()

    class _FakeRunService:
        async def get_run(self, *, tenant_id, run_id):  # type: ignore[no-untyped-def]
            return {
                "id": str(run_id),
                "organisation_id": str(uuid.uuid4()),
                "reporting_period": "2026-03-31",
                "hierarchy_id": str(uuid.uuid4()),
                "scope_id": str(uuid.uuid4()),
                "hierarchy_version_token": "h-v1",
                "scope_version_token": "s-v1",
                "rule_version_token": "r-v1",
                "intercompany_version_token": "ic-v1",
                "adjustment_version_token": "adj-v1",
                "source_run_refs": [],
                "run_token": "run-token-1",
                "run_status": "completed",
                "validation_summary_json": {"ok": True},
                "created_at": "2026-03-31T00:00:00+00:00",
            }

        async def summary(self, *, tenant_id, run_id):  # type: ignore[no-untyped-def]
            return {
                "run_id": str(run_id),
                "run_token": "run-token-1",
                "run_status": "completed",
                "metric_count": 2,
                "variance_count": 1,
                "evidence_count": 2,
            }

        async def list_metrics(self, *, tenant_id, run_id):  # type: ignore[no-untyped-def]
            return [
                {
                    "id": str(uuid.uuid4()),
                    "metric_code": "EBITDA",
                    "aggregated_value": "125.000000",
                    "currency_code": "INR",
                    "entity_count": 2,
                    "materiality_flag": False,
                }
            ]

        async def list_variances(self, *, tenant_id, run_id):  # type: ignore[no-untyped-def]
            return [
                {
                    "id": str(uuid.uuid4()),
                    "metric_code": "EBITDA",
                    "comparison_type": "vs_budget",
                    "base_value": "100.000000",
                    "current_value": "125.000000",
                    "variance_value": "25.000000",
                    "variance_pct": "25.000000",
                    "materiality_flag": True,
                }
            ]

        async def list_evidence(self, *, tenant_id, run_id):  # type: ignore[no-untyped-def]
            return [
                {
                    "id": str(uuid.uuid4()),
                    "evidence_type": "validation_report",
                    "evidence_ref": "data-quality:summary",
                    "evidence_label": "Validation summary",
                    "evidence_payload_json": {
                        "reports": [
                            {
                                "status": "FAIL",
                                "reason": "Entity A is missing a mapped counterparty",
                            }
                        ]
                    },
                },
                {
                    "id": str(uuid.uuid4()),
                    "evidence_type": "intercompany_decision",
                    "evidence_ref": "intercompany:summary",
                    "evidence_label": "Intercompany summary",
                    "evidence_payload_json": {
                        "unmatched_count": 2,
                        "validation_report": {"status": "PASS", "reason": "review required"},
                    },
                },
            ]

    monkeypatch.setattr(consolidation_routes, "_build_service", lambda _session: _FakeRunService())

    headers = {"Authorization": f"Bearer {api_test_access_token}"}

    risks_response = await async_client.get(
        f"/api/v1/consolidation/runs/{run_id}/risks",
        headers=headers,
    )
    assert risks_response.status_code == 200
    risks = risks_response.json()["data"]
    assert len(risks) == 2
    assert {item["risk_type"] for item in risks} == {"validation_report", "intercompany_unmatched"}

    anomalies_response = await async_client.get(
        f"/api/v1/consolidation/runs/{run_id}/anomalies",
        headers=headers,
    )
    assert anomalies_response.status_code == 200
    anomalies = anomalies_response.json()["data"]
    assert len(anomalies) == 1
    assert anomalies[0]["metric_code"] == "EBITDA"
    assert anomalies[0]["anomaly_type"] == "variance"

    board_pack_response = await async_client.get(
        f"/api/v1/consolidation/runs/{run_id}/board-pack",
        headers=headers,
    )
    assert board_pack_response.status_code == 200
    board_pack = board_pack_response.json()["data"]
    assert board_pack["status"] == "ready"
    assert len(board_pack["sections"]) == 4
    assert board_pack["sections"][0]["section"] == "summary"


@pytest.mark.asyncio
async def test_missing_source_entity_returns_422_with_entity_ids_not_500(
    async_client: AsyncClient,
    api_test_access_token: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from financeops.modules.multi_entity_consolidation.api import routes as consolidation_routes

    missing_entity_id = uuid.uuid4()
    run_id = uuid.uuid4()

    async def _raise_missing_entity(*args, **kwargs):  # type: ignore[no-untyped-def]
        _ = (args, kwargs)
        raise MissingSourceEntityError(missing_ids=[missing_entity_id])

    monkeypatch.setattr(consolidation_routes, "_submit_intent", _raise_missing_entity)

    response = await async_client.post(
        f"/api/v1/consolidation/runs/{run_id}/execute",
        headers={"Authorization": f"Bearer {api_test_access_token}"},
        json={},
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["success"] is False
    assert payload["error"]["details"]["missing_ids"] == [str(missing_entity_id)]
    assert "Missing source entities" in payload["error"]["message"]
