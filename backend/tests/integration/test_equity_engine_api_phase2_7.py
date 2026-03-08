from __future__ import annotations

import uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.security import create_access_token
from financeops.db.models.users import UserRole
from financeops.db.rls import set_tenant_context
from tests.integration.equity_phase2_7_helpers import seed_control_plane_for_equity
from tests.integration.payroll_gl_reconciliation_phase1f3_1_helpers import seed_identity_user


@pytest.mark.asyncio
@pytest.mark.integration
async def test_equity_statement_endpoint_requires_context_token(
    async_client: AsyncClient,
    test_access_token: str,
) -> None:
    response = await async_client.post(
        "/api/v1/equity/statements",
        headers={
            "Authorization": f"Bearer {test_access_token}",
            "X-Control-Plane-Token": "",
        },
        json={
            "organisation_id": str(uuid.uuid4()),
            "statement_code": "EQ_MAIN",
            "statement_name": "Equity Main",
            "reporting_currency_basis": "source_currency",
            "ownership_basis_flag": False,
            "effective_from": "2026-01-01",
            "status": "candidate",
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
@pytest.mark.integration
async def test_equity_run_endpoint_requires_rbac_permission(
    async_client: AsyncClient,
    async_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    await set_tenant_context(async_session, tenant_id)
    user = await seed_identity_user(
        async_session,
        tenant_id=tenant_id,
        user_id=user_id,
        email=f"equity-{uuid.uuid4().hex[:8]}@example.com",
        role=UserRole.finance_leader,
    )
    await seed_control_plane_for_equity(
        async_session,
        tenant_id=tenant_id,
        user_id=user_id,
        grant_permissions=False,
    )
    await async_session.flush()
    token = create_access_token(user.id, tenant_id, user.role.value)

    response = await async_client.post(
        "/api/v1/equity/runs",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "organisation_id": str(uuid.uuid4()),
            "reporting_period": "2026-01-31",
            "consolidation_run_ref_nullable": str(uuid.uuid4()),
            "fx_translation_run_ref_nullable": None,
            "ownership_consolidation_run_ref_nullable": None,
        },
    )
    assert response.status_code in {401, 403}


@pytest.mark.asyncio
@pytest.mark.integration
async def test_equity_list_statements_allows_authorized_tenant(
    async_client: AsyncClient,
    async_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    await set_tenant_context(async_session, tenant_id)
    user = await seed_identity_user(
        async_session,
        tenant_id=tenant_id,
        user_id=user_id,
        email=f"equity-ok-{uuid.uuid4().hex[:8]}@example.com",
        role=UserRole.finance_leader,
    )
    await seed_control_plane_for_equity(
        async_session,
        tenant_id=tenant_id,
        user_id=user_id,
        grant_permissions=True,
    )
    await async_session.flush()
    token = create_access_token(user.id, tenant_id, user.role.value)

    create_response = await async_client.post(
        "/api/v1/equity/statements",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "organisation_id": str(tenant_id),
            "statement_code": "EQ_AUTH_MAIN",
            "statement_name": "Equity Main",
            "reporting_currency_basis": "source_currency",
            "ownership_basis_flag": False,
            "effective_from": date(2026, 1, 1).isoformat(),
            "status": "candidate",
        },
    )
    assert create_response.status_code == 201

    list_response = await async_client.get(
        "/api/v1/equity/statements",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_response.status_code == 200
    rows = list_response.json()
    assert any(row["statement_code"] == "EQ_AUTH_MAIN" for row in rows)
