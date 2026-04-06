from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from financeops.core.exceptions import FeatureNotImplementedError, ValidationError
from financeops.api import deps as api_deps
from financeops.db.rls import set_tenant_context
from financeops.modules.erp_sync.application.connection_service import ConnectionService
from financeops.modules.erp_sync.application.connector_version_service import ConnectorVersionService
from financeops.modules.erp_sync.application.consent_service import ConsentService
from financeops.modules.payment.application.entitlement_service import EntitlementService


async def _grant_erp_entitlement(async_session, *, tenant_id, actor_user_id) -> None:
    await set_tenant_context(async_session, tenant_id)
    await EntitlementService(async_session).create_tenant_override_entitlement(
        tenant_id=tenant_id,
        feature_name="erp_integration",
        access_type="boolean",
        effective_limit=1,
        actor_user_id=actor_user_id,
        metadata={"reason": "erp_lifecycle_validation"},
    )
    await async_session.flush()


class _FakeRedis:
    async def get(self, key: str):  # type: ignore[no-untyped-def]
        _ = key
        return None

    async def setex(self, key: str, ttl: int, value: str):  # type: ignore[no-untyped-def]
        _ = (key, ttl, value)
        return True


@pytest.mark.asyncio
async def test_erp_connection_lifecycle_routes_are_live(
    async_client: AsyncClient,
    async_session,
    test_user,
    test_access_token: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(api_deps, "_redis_pool", _FakeRedis())
    await _grant_erp_entitlement(
        async_session,
        tenant_id=test_user.tenant_id,
        actor_user_id=test_user.id,
    )

    create_response = await async_client.post(
        "/api/v1/erp-sync/connections",
        headers={
            "Authorization": f"Bearer {test_access_token}",
            "Idempotency-Key": str(uuid.uuid4()),
        },
        json={
            "connector_type": "zoho",
            "connection_code": f"zoho-{uuid.uuid4().hex[:8]}",
            "connection_name": "Zoho Lifecycle",
            "organisation_id": str(test_user.tenant_id),
            "connection_status": "draft",
            "client_id": "zoho-client",
            "client_secret": "zoho-secret",
            "organization_id": "zoho-org-1",
        },
    )
    assert create_response.status_code == 200
    connection_id = create_response.json()["data"]["connection_id"]

    suspend_response = await async_client.post(
        f"/api/v1/erp-sync/connections/{connection_id}/suspend",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert suspend_response.status_code == 200
    assert suspend_response.json()["data"]["connection_status"] == "suspended"

    activate_response = await async_client.post(
        f"/api/v1/erp-sync/connections/{connection_id}/activate",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert activate_response.status_code == 200
    assert activate_response.json()["data"]["connection_status"] == "active"

    rotate_response = await async_client.post(
        f"/api/v1/erp-sync/connections/{connection_id}/rotate-credentials",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={"organization_id": "zoho-org-rotated", "access_token": "access-123"},
    )
    assert rotate_response.status_code == 200
    assert rotate_response.json()["data"]["rotated"] is True
    assert "organization_id" in rotate_response.json()["data"]["updated_fields"]

    upgrade_response = await async_client.post(
        f"/api/v1/erp-sync/connections/{connection_id}/upgrade-connector-version",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={"pinned_connector_version": "1.2.3"},
    )
    assert upgrade_response.status_code == 200
    assert upgrade_response.json()["data"]["pinned_connector_version"] == "1.2.3"


@pytest.mark.asyncio
async def test_erp_bootstrap_test_ready_creates_mapping_and_sync_definition(
    async_client: AsyncClient,
    async_session,
    test_user,
    test_access_token: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(api_deps, "_redis_pool", _FakeRedis())
    await _grant_erp_entitlement(
        async_session,
        tenant_id=test_user.tenant_id,
        actor_user_id=test_user.id,
    )

    create_response = await async_client.post(
        "/api/v1/erp-sync/connections",
        headers={
            "Authorization": f"Bearer {test_access_token}",
            "Idempotency-Key": str(uuid.uuid4()),
        },
        json={
            "connector_type": "quickbooks",
            "connection_code": f"qbo-{uuid.uuid4().hex[:8]}",
            "connection_name": "QBO Bootstrap",
            "organisation_id": str(test_user.tenant_id),
            "connection_status": "draft",
            "client_id": "qbo-client",
            "client_secret": "qbo-secret",
            "realm_id": "realm-1",
            "use_sandbox": True,
        },
    )
    assert create_response.status_code == 200
    connection_id = create_response.json()["data"]["connection_id"]

    bootstrap_response = await async_client.post(
        "/api/v1/erp-sync/bootstrap/test-ready",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "connection_id": connection_id,
            "dataset_type": "trial_balance",
        },
    )
    assert bootstrap_response.status_code == 200
    payload = bootstrap_response.json()["data"]
    assert payload["connection_id"] == connection_id
    assert payload["connection_status"] == "active"
    assert payload["mapping_definition_id"]
    assert payload["mapping_version_id"]
    assert payload["sync_definition_id"]
    assert payload["sync_definition_version_id"]


@pytest.mark.asyncio
async def test_unimplemented_services_remain_closed_and_connection_service_rejects_unknown_action() -> None:
    services = (
        ConsentService(),
        ConnectorVersionService(),
    )
    for service in services:
        with pytest.raises(FeatureNotImplementedError):
            await service.execute(sample=True)

    with pytest.raises(ValidationError, match="Unsupported connection service action"):
        await ConnectionService(AsyncMock()).execute(action="bogus")
