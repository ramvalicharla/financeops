from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from financeops.core.exceptions import FeatureNotImplementedError
from financeops.db.rls import set_tenant_context
from financeops.modules.erp_sync.application.connection_service import ConnectionService
from financeops.modules.erp_sync.application.connector_version_service import ConnectorVersionService
from financeops.modules.erp_sync.application.consent_service import ConsentService
from financeops.modules.payment.application.entitlement_service import EntitlementService


@pytest.mark.asyncio
async def test_unimplemented_service_returns_501_not_200(
    async_client: AsyncClient,
    async_session,
    test_user,
    test_access_token: str,
) -> None:
    """Placeholder ERP endpoints fail closed with 501 and stable feature code."""
    await set_tenant_context(async_session, test_user.tenant_id)
    await EntitlementService(async_session).create_tenant_override_entitlement(
        tenant_id=test_user.tenant_id,
        feature_name="erp_integration",
        access_type="boolean",
        effective_limit=1,
        actor_user_id=test_user.id,
        metadata={"reason": "placeholder_service_test"},
    )
    await async_session.flush()

    target_id = uuid.uuid4()
    paths = (
        f"/api/v1/erp-sync/connections/{target_id}/rotate-credentials",
        f"/api/v1/erp-sync/connections/{target_id}/upgrade-connector-version",
    )
    for path in paths:
        response = await async_client.post(
            path,
            headers={"Authorization": f"Bearer {test_access_token}"},
        )
        assert response.status_code == 501
        payload = response.json()
        assert '"status":"not_implemented"' not in response.text
        assert payload.get("error", {}).get("code") == "feature_not_implemented"


@pytest.mark.asyncio
async def test_unimplemented_service_never_returns_200() -> None:
    """No placeholder ERP application service returns a success payload."""
    services = (
        ConsentService(),
        ConnectorVersionService(),
        ConnectionService(),
    )
    for service in services:
        with pytest.raises(FeatureNotImplementedError):
            await service.execute(sample=True)
