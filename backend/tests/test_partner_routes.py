from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.security import create_access_token, hash_password
from financeops.db.models.users import IamUser, UserRole
from financeops.modules.partner_program.service import register_partner


@pytest.mark.asyncio
async def test_partner_routes_require_auth(async_client) -> None:
    response = await async_client.get("/api/v1/partner/dashboard")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_partner_routes_require_partner_role(
    async_client,
    async_session: AsyncSession,
    test_user: IamUser,
) -> None:
    employee = IamUser(
        tenant_id=test_user.tenant_id,
        email=f"employee-partner-{uuid.uuid4()}@example.com",
        hashed_password=hash_password("TestPass123!"),
        full_name="Employee",
        role=UserRole.employee,
        is_active=True,
        mfa_enabled=False,
    )
    async_session.add(employee)
    await async_session.flush()
    token = create_access_token(employee.id, employee.tenant_id, employee.role.value)

    response = await async_client.get(
        "/api/v1/partner/dashboard",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_partner_dashboard_returns_200(
    async_client,
    async_session: AsyncSession,
    test_user: IamUser,
    test_access_token: str,
) -> None:
    await register_partner(
        async_session,
        tenant_id=test_user.tenant_id,
        partner_tier="referral",
        company_name="Partner Dashboard Co",
        contact_email="partner-dashboard@example.com",
    )

    response = await async_client.get(
        "/api/v1/partner/dashboard",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_partner_routes_rate_limited(
    async_client,
    async_session: AsyncSession,
    test_user: IamUser,
    test_access_token: str,
) -> None:
    await register_partner(
        async_session,
        tenant_id=test_user.tenant_id,
        partner_tier="referral",
        company_name="Partner Limit Co",
        contact_email="partner-limit@example.com",
    )

    response = await async_client.get(
        "/api/v1/partner/dashboard",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 200
    assert "x-ratelimit-limit" in {key.lower() for key in response.headers.keys()}
