from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.reconciliation import GlEntry
from financeops.modules.coa.models import TenantCoaAccount
from financeops.platform.db.models.entities import CpEntity
from financeops.platform.services.enforcement.context_token import issue_context_token


def _control_plane_token(tenant_id: uuid.UUID) -> str:
    now = datetime.now(UTC)
    return issue_context_token(
        {
            "tenant_id": str(tenant_id),
            "module_code": "accounting_layer",
            "decision": "allow",
            "policy_snapshot_version": 1,
            "quota_check_id": "test-quota",
            "isolation_route_version": 1,
            "issued_at": now.isoformat(),
            "expires_at": (now + timedelta(minutes=30)).isoformat(),
            "correlation_id": "test-journal-flow",
        }
    )


@pytest.mark.asyncio
async def test_create_list_get_journal(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_user,
    test_access_token: str,
) -> None:
    entity = (
        await async_session.execute(
            select(CpEntity).where(CpEntity.tenant_id == test_user.tenant_id)
        )
    ).scalar_one()

    async_session.add_all(
        [
            TenantCoaAccount(
                id=uuid.uuid4(),
                tenant_id=test_user.tenant_id,
                account_code="1000",
                display_name="Cash",
                is_active=True,
            ),
            TenantCoaAccount(
                id=uuid.uuid4(),
                tenant_id=test_user.tenant_id,
                account_code="2000",
                display_name="Revenue",
                is_active=True,
            ),
        ]
    )
    await async_session.flush()

    headers = {
        "Authorization": f"Bearer {test_access_token}",
        "X-Control-Plane-Token": _control_plane_token(test_user.tenant_id),
    }
    payload = {
        "org_entity_id": str(entity.id),
        "journal_date": "2026-04-01",
        "reference": "API-POST-001",
        "narration": "Journal post test",
        "lines": [
            {"account_code": "1000", "debit": "1500.00", "credit": "0.00", "memo": "Debit line"},
            {"account_code": "2000", "debit": "0.00", "credit": "1500.00", "memo": "Credit line"},
        ],
    }

    create_response = await async_client.post(
        "/api/v1/accounting/journals/",
        headers=headers,
        json=payload,
    )
    assert create_response.status_code == 200
    created = create_response.json()["data"]
    assert created["status"] == "POSTED"
    assert created["total_debit"] == "1500.0000"
    assert created["total_credit"] == "1500.0000"
    assert len(created["lines"]) == 2

    list_response = await async_client.get(
        "/api/v1/accounting/journals/",
        headers=headers,
    )
    assert list_response.status_code == 200
    rows = list_response.json()["data"]
    assert any(item["id"] == created["id"] for item in rows)

    get_response = await async_client.get(
        f"/api/v1/accounting/journals/{created['id']}",
        headers=headers,
    )
    assert get_response.status_code == 200
    fetched = get_response.json()["data"]
    assert fetched["id"] == created["id"]
    assert fetched["journal_number"]

    gl_count = (
        await async_session.execute(
            select(GlEntry).where(
                GlEntry.tenant_id == test_user.tenant_id,
                GlEntry.source_ref == fetched["journal_number"],
            )
        )
    ).scalars().all()
    assert len(gl_count) == 2
