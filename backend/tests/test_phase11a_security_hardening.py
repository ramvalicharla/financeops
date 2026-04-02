from __future__ import annotations

from datetime import timedelta
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.security import create_access_token, hash_password
from financeops.db.models.users import IamUser, UserRole


@pytest.mark.asyncio
async def test_coa_validate_rejects_path_traversal_filename(
    async_client,
    test_access_token: str,
) -> None:
    response = await async_client.post(
        "/api/v1/coa/validate",
        files={
            "file": (
                "../coa.csv",
                b"group_code,group_name,subgroup_code,subgroup_name,ledger_code,ledger_name,ledger_type,is_control_account\n",
                "text/csv",
            )
        },
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 422
    payload = response.json()
    assert payload["success"] is False
    assert "file_validation_failed" in payload["error"]["message"]


@pytest.mark.asyncio
async def test_erp_sync_denies_read_only_role(
    async_client,
    async_session: AsyncSession,
    test_tenant,
) -> None:
    read_only = IamUser(
        tenant_id=test_tenant.id,
        email=f"readonly-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=hash_password("TestPass123!"),
        full_name="Read Only",
        role=UserRole.read_only,
        is_active=True,
        mfa_enabled=False,
    )
    async_session.add(read_only)
    await async_session.flush()

    token = create_access_token(read_only.id, read_only.tenant_id, read_only.role.value)
    response = await async_client.get(
        "/api/v1/erp-sync/datasets",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_erp_sync_replay_requires_auth(async_client) -> None:
    response = await async_client.post(
        f"/api/v1/erp-sync/sync-runs/{uuid.uuid4()}/replay",
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_role_downgrade_blocks_finance_endpoint(
    async_client,
    async_session: AsyncSession,
    test_tenant,
) -> None:
    user = IamUser(
        tenant_id=test_tenant.id,
        email=f"role-downgrade-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=hash_password("TestPass123!"),
        full_name="Role Downgrade",
        role=UserRole.finance_team,
        is_active=True,
        mfa_enabled=False,
    )
    async_session.add(user)
    await async_session.flush()
    token = create_access_token(user.id, user.tenant_id, user.role.value)

    # Simulate an access token minted before role downgrade.
    user.role = UserRole.read_only
    await async_session.flush()

    response = await async_client.get(
        "/api/v1/erp-sync/datasets",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_revoke_all_sessions_blocks_refresh_reuse(
    async_client,
    test_user: IamUser,
) -> None:
    login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": test_user.email, "password": "TestPass123!"},
    )
    assert login.status_code == 200
    tokens = login.json()["data"]
    refresh_token = tokens["refresh_token"]
    access_token = tokens["access_token"]

    revoke = await async_client.post(
        "/api/v1/auth/sessions/revoke-all",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert revoke.status_code == 200
    assert revoke.json()["data"]["revoked_sessions"] >= 1

    refresh = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh.status_code == 401


@pytest.mark.asyncio
async def test_invalid_token_response_is_safe(async_client) -> None:
    response = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid.token.value"},
    )
    assert response.status_code == 401
    payload = response.json()
    assert payload["success"] is False
    assert payload["error"]["code"] in {"authentication_error", "http_401"}
    assert "Traceback" not in payload["error"]["message"]


@pytest.mark.asyncio
async def test_oversized_payload_is_rejected(async_client) -> None:
    response = await async_client.post(
        "/api/v1/auth/login",
        content=b"{}",
        headers={
            "content-type": "application/json",
            "content-length": str(60 * 1024 * 1024),
        },
    )
    assert response.status_code == 413
    payload = response.json()
    serialized = str(payload)
    assert "payload_too_large" in serialized


@pytest.mark.asyncio
async def test_expired_token_is_rejected(async_client, test_user: IamUser) -> None:
    expired = create_access_token(
        test_user.id,
        test_user.tenant_id,
        test_user.role.value,
        expires_delta=timedelta(seconds=-1),
    )
    response = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired}"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_tenant_mismatch_token_is_rejected(
    async_client,
    test_user: IamUser,
) -> None:
    wrong_tenant_token = create_access_token(
        test_user.id,
        uuid.uuid4(),
        test_user.role.value,
    )
    response = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {wrong_tenant_token}"},
    )
    assert response.status_code == 401
