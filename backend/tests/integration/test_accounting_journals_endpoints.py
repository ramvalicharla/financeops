from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.intent.enums import IntentEventType
from financeops.core.security import create_access_token, hash_password
from financeops.db.models.accounting_jv import AccountingJVAggregate
from financeops.db.models.intent_pipeline import CanonicalIntent, CanonicalIntentEvent
from financeops.db.models.reconciliation import GlEntry
from financeops.db.models.users import IamUser, UserRole
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
async def test_journal_endpoints_run_through_intent_pipeline(
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
        mfa_enabled=True,
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
    create_data = create_response.json()["data"]
    assert create_data["intent_id"]
    assert create_data["job_id"]
    assert create_data["status"] == "RECORDED"
    created_journal_id = uuid.UUID(create_data["record_refs"]["journal_id"])

    created_journal = (
        await async_session.execute(
            select(AccountingJVAggregate).where(AccountingJVAggregate.id == created_journal_id)
        )
    ).scalar_one()
    assert created_journal.created_by_intent_id == uuid.UUID(create_data["intent_id"])
    assert created_journal.recorded_by_job_id == uuid.UUID(create_data["job_id"])

    pre_post_gl = (
        await async_session.execute(
            select(GlEntry).where(
                GlEntry.tenant_id == test_user.tenant_id,
                GlEntry.source_ref == created_journal.jv_number,
            )
        )
    ).scalars().all()
    assert len(pre_post_gl) == 0

    submit_response = await async_client.post(
        f"/api/v1/accounting/journals/{created_journal_id}/submit",
        headers=headers,
    )
    assert submit_response.status_code == 200
    assert submit_response.json()["data"]["status"] == "RECORDED"

    review_response = await async_client.post(
        f"/api/v1/accounting/journals/{created_journal_id}/review",
        headers=headers,
    )
    assert review_response.status_code == 200
    assert review_response.json()["data"]["record_refs"]["status"] == "REVIEWED"

    approve_response = await async_client.post(
        f"/api/v1/accounting/journals/{created_journal_id}/approve",
        headers=approver_headers,
    )
    assert approve_response.status_code == 200
    assert approve_response.json()["data"]["record_refs"]["status"] == "APPROVED"

    post_response = await async_client.post(
        f"/api/v1/accounting/journals/{created_journal_id}/post",
        headers=approver_headers,
    )
    assert post_response.status_code == 200
    post_data = post_response.json()["data"]
    assert post_data["status"] == "RECORDED"
    assert post_data["record_refs"]["status"] == "POSTED"

    list_response = await async_client.get(
        "/api/v1/accounting/journals/",
        headers=headers,
    )
    assert list_response.status_code == 200
    rows = list_response.json()["data"]
    assert any(item["id"] == str(created_journal_id) for item in rows)

    get_response = await async_client.get(
        f"/api/v1/accounting/journals/{created_journal_id}",
        headers=headers,
    )
    assert get_response.status_code == 200
    fetched = get_response.json()["data"]
    assert fetched["id"] == str(created_journal_id)
    assert fetched["status"] == "POSTED"
    assert fetched["journal_number"]

    gl_rows = (
        await async_session.execute(
            select(GlEntry).where(
                GlEntry.tenant_id == test_user.tenant_id,
                GlEntry.source_ref == fetched["journal_number"],
            )
        )
    ).scalars().all()
    assert len(gl_rows) == 2
    assert all(row.created_by_intent_id == uuid.UUID(post_data["intent_id"]) for row in gl_rows)
    assert all(row.recorded_by_job_id == uuid.UUID(post_data["job_id"]) for row in gl_rows)

    create_intent_events = (
        await async_session.execute(
            select(CanonicalIntentEvent).where(
                CanonicalIntentEvent.intent_id == uuid.UUID(create_data["intent_id"])
            )
        )
    ).scalars().all()
    assert {
        event.event_type for event in create_intent_events
    } >= {
        IntentEventType.AUTH_CONTEXT_CAPTURED.value,
        IntentEventType.INTENT_CREATED.value,
        IntentEventType.INTENT_SUBMITTED.value,
        IntentEventType.INTENT_VALIDATED.value,
        IntentEventType.INTENT_APPROVED.value,
        IntentEventType.JOB_DISPATCHED.value,
        IntentEventType.JOB_EXECUTED.value,
        IntentEventType.RECORD_RECORDED.value,
    }

    trial_balance_response = await async_client.get(
        f"/api/v1/accounting/trial-balance?org_entity_id={entity.id}&as_of_date=2026-04-30",
        headers=headers,
    )
    assert trial_balance_response.status_code == 200
    tb_payload = trial_balance_response.json()["data"]
    assert tb_payload["total_debit"] == "1500.000000"
    assert tb_payload["total_credit"] == "1500.000000"

    reverse_response = await async_client.post(
        f"/api/v1/accounting/journals/{created_journal_id}/reverse",
        headers=approver_headers,
    )
    assert reverse_response.status_code == 200
    reverse_data = reverse_response.json()["data"]
    reversed_journal_id = uuid.UUID(reverse_data["record_refs"]["journal_id"])

    reversed_get_response = await async_client.get(
        f"/api/v1/accounting/journals/{reversed_journal_id}",
        headers=headers,
    )
    assert reversed_get_response.status_code == 200
    reversed_journal = reversed_get_response.json()["data"]
    assert reversed_journal["status"] == "POSTED"
    assert reversed_journal["reference"] == f"REVERSAL_OF:{fetched['journal_number']}"

    reversal_gl_rows = (
        await async_session.execute(
            select(GlEntry).where(
                GlEntry.tenant_id == test_user.tenant_id,
                GlEntry.source_ref == reversed_journal["journal_number"],
            )
        )
    ).scalars().all()
    assert len(reversal_gl_rows) == 2

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


@pytest.mark.asyncio
async def test_direct_jv_mutation_endpoints_are_blocked(
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
    headers = {
        "Authorization": f"Bearer {test_access_token}",
        "X-Control-Plane-Token": _control_plane_token(test_user.tenant_id),
    }
    response = await async_client.post(
        "/api/v1/accounting/jv/",
        headers=headers,
        json={
            "entity_id": str(entity.id),
            "period_date": "2026-04-01",
            "fiscal_year": 2026,
            "fiscal_period": 4,
            "lines": [
                {"account_code": "1000", "entry_type": "DEBIT", "amount": "10.00"},
                {"account_code": "2000", "entry_type": "CREDIT", "amount": "10.00"},
            ],
        },
    )
    assert response.status_code == 422
    assert "Direct JV mutation endpoints are disabled" in response.json()["error"]["message"]
