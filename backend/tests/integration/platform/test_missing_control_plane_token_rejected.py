from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from financeops.platform.services.enforcement.service_token import issue_service_token


def _service_token(*, tenant_id: str, module_code: str, scope: str = "finance.execute") -> str:
    issued_at = datetime.now(UTC)
    return issue_service_token(
        {
            "service_id": "worker.financeops",
            "tenant_id": tenant_id,
            "module_code": module_code,
            "scope": scope,
            "nonce": "svc-probe-1",
            "issued_at": issued_at.isoformat(),
            "expires_at": (issued_at + timedelta(minutes=5)).isoformat(),
        }
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_missing_service_token_rejected_even_for_browser_user(
    async_client: AsyncClient,
    test_access_token: str,
) -> None:
    response = await async_client.post(
        "/api/v1/platform/modules/finance-exec-probe",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "module_code": "revenue",
            "resource_type": "revenue_run",
            "action": "execute",
            "execution_mode": "internal",
            "request_fingerprint": "rf-missing-token",
            "resource_id": "run-1",
            "context_scope": {},
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
@pytest.mark.integration
async def test_invalid_service_token_rejected(
    async_client: AsyncClient,
    test_access_token: str,
) -> None:
    response = await async_client.post(
        "/api/v1/platform/modules/finance-exec-probe",
        headers={
            "Authorization": f"Bearer {test_access_token}",
            "X-Service-Token": "invalid.token",
        },
        json={
            "module_code": "revenue",
            "resource_type": "revenue_run",
            "action": "execute",
            "execution_mode": "internal",
            "request_fingerprint": "rf-invalid-token",
            "resource_id": "run-1",
            "context_scope": {},
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
@pytest.mark.integration
async def test_valid_service_token_allows_internal_probe(
    async_client: AsyncClient,
    test_user,
) -> None:
    response = await async_client.post(
        "/api/v1/platform/modules/finance-exec-probe",
        headers={
            "X-Service-Token": _service_token(
                tenant_id=str(test_user.tenant_id),
                module_code="revenue",
            ),
        },
        json={
            "module_code": "revenue",
            "resource_type": "revenue_run",
            "action": "execute",
            "execution_mode": "internal",
            "request_fingerprint": "rf-valid-token",
            "resource_id": "run-1",
            "context_scope": {},
        },
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["status"] == "executed"
    assert payload["module_code"] == "revenue"
    assert payload["service_id"] == "worker.financeops"
