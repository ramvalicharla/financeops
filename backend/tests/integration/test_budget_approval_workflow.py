from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.security import create_access_token, hash_password
from financeops.db.models.users import IamUser, UserRole
from financeops.modules.budgeting.models import BudgetVersion, BudgetVersionStatusEvent


async def _create_budget_version(async_client: AsyncClient, token: str, name: str) -> str:
    response = await async_client.post(
        "/api/v1/budget/versions",
        headers={"Authorization": f"Bearer {token}"},
        json={"fiscal_year": 2025, "version_name": name},
    )
    assert response.status_code == 201
    return response.json()["data"]["id"]


@pytest.mark.asyncio
async def test_budget_approval_workflow_draft_to_submitted(
    async_client: AsyncClient,
    api_db_session: AsyncSession,
    api_test_access_token: str,
    api_test_user: IamUser,
) -> None:
    version_id = await _create_budget_version(async_client, api_test_access_token, "Phase8 Submit")

    response = await async_client.post(
        f"/api/v1/budget/versions/{version_id}/submit",
        headers={"Authorization": f"Bearer {api_test_access_token}"},
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["status"] == "submitted"

    row = (
        await api_db_session.execute(
            select(BudgetVersion.id, BudgetVersion.status).where(
                BudgetVersion.id == uuid.UUID(version_id)
            )
        )
    ).one()
    assert row.status == "submitted"

    events = (
        await api_db_session.execute(
            select(BudgetVersionStatusEvent.to_status)
            .where(
                BudgetVersionStatusEvent.tenant_id == api_test_user.tenant_id,
                BudgetVersionStatusEvent.budget_version_id == row.id,
            )
            .order_by(BudgetVersionStatusEvent.created_at.asc())
        )
    ).scalars().all()
    assert events == ["submitted"]
    await api_db_session.commit()


@pytest.mark.asyncio
async def test_budget_approval_requires_budget_approve_permission(
    async_client: AsyncClient,
    api_db_session: AsyncSession,
    api_test_access_token: str,
    api_test_user: IamUser,
) -> None:
    version_id = await _create_budget_version(
        async_client, api_test_access_token, "Phase8 Approval Guard"
    )
    submit_response = await async_client.post(
        f"/api/v1/budget/versions/{version_id}/submit",
        headers={"Authorization": f"Bearer {api_test_access_token}"},
    )
    assert submit_response.status_code == 200

    employee = IamUser(
        tenant_id=api_test_user.tenant_id,
        email=f"budget-employee-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=hash_password("TestPass123!"),
        full_name="Budget Employee",
        role=UserRole.employee,
        is_active=True,
        mfa_enabled=False,
    )
    api_db_session.add(employee)
    await api_db_session.flush()
    employee_token = create_access_token(employee.id, employee.tenant_id, employee.role.value)

    response = await async_client.post(
        f"/api/v1/budget/versions/{version_id}/approve",
        headers={"Authorization": f"Bearer {employee_token}"},
        json={"approval_level": "board"},
    )
    assert response.status_code == 403
    await api_db_session.commit()


@pytest.mark.asyncio
async def test_budget_previous_version_superseded_on_new_approval(
    async_client: AsyncClient,
    api_db_session: AsyncSession,
    api_test_access_token: str,
    api_test_user: IamUser,
) -> None:
    first_version_id = await _create_budget_version(async_client, api_test_access_token, "Budget v1")
    second_version_id = await _create_budget_version(async_client, api_test_access_token, "Budget v2")

    for version_id in (first_version_id, second_version_id):
        submit_response = await async_client.post(
            f"/api/v1/budget/versions/{version_id}/submit",
            headers={"Authorization": f"Bearer {api_test_access_token}"},
        )
        assert submit_response.status_code == 200

    first_approve = await async_client.post(
        f"/api/v1/budget/versions/{first_version_id}/approve",
        headers={"Authorization": f"Bearer {api_test_access_token}"},
        json={"approval_level": "board"},
    )
    assert first_approve.status_code == 200
    assert first_approve.json()["data"]["status"] == "board_approved"

    second_approve = await async_client.post(
        f"/api/v1/budget/versions/{second_version_id}/approve",
        headers={"Authorization": f"Bearer {api_test_access_token}"},
        json={"approval_level": "board"},
    )
    assert second_approve.status_code == 200
    assert second_approve.json()["data"]["status"] == "board_approved"

    version_rows = (
        await api_db_session.execute(
            select(BudgetVersion.id, BudgetVersion.status).where(
                BudgetVersion.id.in_(
                    (uuid.UUID(first_version_id), uuid.UUID(second_version_id))
                )
            )
        )
    ).all()
    status_by_id = {str(row.id): row.status for row in version_rows}
    assert status_by_id[first_version_id] == "superseded"
    assert status_by_id[second_version_id] == "board_approved"

    events = (
        await api_db_session.execute(
            select(BudgetVersionStatusEvent.budget_version_id, BudgetVersionStatusEvent.to_status)
            .where(BudgetVersionStatusEvent.tenant_id == api_test_user.tenant_id)
            .order_by(BudgetVersionStatusEvent.created_at.asc(), BudgetVersionStatusEvent.id.asc())
        )
    ).all()
    assert any(
        str(event.budget_version_id) == first_version_id and event.to_status == "superseded"
        for event in events
    )
    assert any(
        str(event.budget_version_id) == second_version_id and event.to_status == "board_approved"
        for event in events
    )
    await api_db_session.commit()
