from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.security import create_access_token, hash_password
from financeops.db.models.users import IamUser, UserRole
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
    approver = IamUser(
        tenant_id=test_user.tenant_id,
        email="approver@example.com",
        hashed_password=hash_password("TestPass123!"),
        full_name="Approver User",
        role=UserRole.platform_admin,
        is_active=True,
        mfa_enabled=False,
    )
    async_session.add(approver)
    await async_session.flush()
    approver_headers = {
        "Authorization": f"Bearer {create_access_token(approver.id, approver.tenant_id, approver.role.value)}",
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
    assert created["status"] == "DRAFT"
    assert created["total_debit"] == "1500.0000"
    assert created["total_credit"] == "1500.0000"
    assert len(created["lines"]) == 2

    pre_post_gl = (
        await async_session.execute(
            select(GlEntry).where(
                GlEntry.tenant_id == test_user.tenant_id,
                GlEntry.source_ref == created["journal_number"],
            )
        )
    ).scalars().all()
    assert len(pre_post_gl) == 0

    submit_response = await async_client.post(
        f"/api/v1/accounting/journals/{created['id']}/submit",
        headers=headers,
    )
    assert submit_response.status_code == 200
    assert submit_response.json()["data"]["status"] == "SUBMITTED"

    review_response = await async_client.post(
        f"/api/v1/accounting/journals/{created['id']}/review",
        headers=headers,
    )
    assert review_response.status_code == 200
    assert review_response.json()["data"]["status"] == "REVIEWED"

    approve_response = await async_client.post(
        f"/api/v1/accounting/journals/{created['id']}/approve",
        headers=approver_headers,
    )
    assert approve_response.status_code == 200
    assert approve_response.json()["data"]["status"] == "APPROVED"

    post_response = await async_client.post(
        f"/api/v1/accounting/journals/{created['id']}/post",
        headers=approver_headers,
    )
    assert post_response.status_code == 200
    assert post_response.json()["data"]["status"] == "POSTED"

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
    assert fetched["status"] == "POSTED"
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

    trial_balance_response = await async_client.get(
        f"/api/v1/accounting/trial-balance?org_entity_id={entity.id}&as_of_date=2026-04-30",
        headers=headers,
    )
    assert trial_balance_response.status_code == 200
    tb_payload = trial_balance_response.json()["data"]
    assert tb_payload["total_debit"] == "1500.000000"
    assert tb_payload["total_credit"] == "1500.000000"

    reverse_response = await async_client.post(
        f"/api/v1/accounting/journals/{created['id']}/reverse",
        headers=headers,
    )
    assert reverse_response.status_code == 200
    reversed_journal = reverse_response.json()["data"]
    assert reversed_journal["status"] == "POSTED"
    assert reversed_journal["reference"] == f"REVERSAL_OF:{fetched['journal_number']}"

    reversal_gl_count = (
        await async_session.execute(
            select(GlEntry).where(
                GlEntry.tenant_id == test_user.tenant_id,
                GlEntry.source_ref == reversed_journal["journal_number"],
            )
        )
    ).scalars().all()
    assert len(reversal_gl_count) == 2

    trial_balance_after_reverse = await async_client.get(
        f"/api/v1/accounting/trial-balance?org_entity_id={entity.id}&as_of_date=2026-04-30",
        headers=headers,
    )
    assert trial_balance_after_reverse.status_code == 200
    tb_after = trial_balance_after_reverse.json()["data"]
    assert tb_after["total_debit"] == "3000.000000"
    assert tb_after["total_credit"] == "3000.000000"

    pnl_response = await async_client.get(
        f"/api/v1/accounting/pnl?org_entity_id={entity.id}&from_date=2026-04-01&to_date=2026-04-30",
        headers=headers,
    )
    assert pnl_response.status_code == 200
    pnl_data = pnl_response.json()["data"]
    assert "net_profit" in pnl_data
    assert "breakdown" in pnl_data

    balance_sheet_response = await async_client.get(
        f"/api/v1/accounting/balance-sheet?org_entity_id={entity.id}&as_of_date=2026-04-30",
        headers=headers,
    )
    assert balance_sheet_response.status_code == 200
    bs_data = balance_sheet_response.json()["data"]
    assert "assets" in bs_data
    assert "liabilities" in bs_data
    assert "equity" in bs_data
    assert "totals" in bs_data

    cash_flow_response = await async_client.get(
        f"/api/v1/accounting/cash-flow?org_entity_id={entity.id}&from_date=2026-04-01&to_date=2026-04-30",
        headers=headers,
    )
    assert cash_flow_response.status_code == 200
    cf_data = cash_flow_response.json()["data"]
    assert "operating_cash_flow" in cf_data
    assert "investing_cash_flow" in cf_data
    assert "financing_cash_flow" in cf_data
    assert "net_cash_flow" in cf_data
