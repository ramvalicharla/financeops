from __future__ import annotations

import hashlib
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.security import create_access_token
from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql
from financeops.db.models.users import IamUser
from financeops.modules.auditor_portal.models import AuditorPortalAccess, AuditorRequest
from financeops.modules.auditor_portal.service import (
    authenticate_auditor,
    get_pbc_tracker,
    grant_auditor_access,
    respond_to_request,
    seed_pbc_checklist,
)


def _auth_headers(user: IamUser) -> dict[str, str]:
    token = create_access_token(user.id, user.tenant_id, user.role.value)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_grant_access_returns_plain_token(async_session: AsyncSession, test_user: IamUser) -> None:
    row, token = await grant_auditor_access(
        async_session,
        tenant_id=test_user.tenant_id,
        auditor_email="audit@example.com",
        auditor_firm="Big4",
        engagement_name="Statutory Audit FY26",
        valid_from=date.today(),
        valid_until=date.today() + timedelta(days=30),
        modules_accessible=["mis", "tax"],
        created_by=test_user.id,
    )
    assert token
    assert row.access_token_hash != token


@pytest.mark.asyncio
async def test_access_token_hashed_in_db(async_session: AsyncSession, test_user: IamUser) -> None:
    row, token = await grant_auditor_access(
        async_session,
        tenant_id=test_user.tenant_id,
        auditor_email="hash@example.com",
        auditor_firm="Firm",
        engagement_name="Audit",
        valid_from=date.today(),
        valid_until=date.today() + timedelta(days=30),
        modules_accessible=[],
        created_by=test_user.id,
    )
    assert row.access_token_hash == hashlib.sha256(token.encode("utf-8")).hexdigest()


@pytest.mark.asyncio
async def test_authenticate_auditor_valid_token(async_session: AsyncSession, test_user: IamUser) -> None:
    _, token = await grant_auditor_access(
        async_session,
        tenant_id=test_user.tenant_id,
        auditor_email="valid@example.com",
        auditor_firm="Firm",
        engagement_name="Audit",
        valid_from=date.today(),
        valid_until=date.today() + timedelta(days=30),
        modules_accessible=[],
        created_by=test_user.id,
    )
    auth = await authenticate_auditor(async_session, token)
    assert auth is not None


@pytest.mark.asyncio
async def test_authenticate_auditor_invalid_token(async_session: AsyncSession) -> None:
    auth = await authenticate_auditor(async_session, "not-a-token")
    assert auth is None


@pytest.mark.asyncio
async def test_authenticate_auditor_expired_access(async_session: AsyncSession, test_user: IamUser) -> None:
    _, token = await grant_auditor_access(
        async_session,
        tenant_id=test_user.tenant_id,
        auditor_email="expired@example.com",
        auditor_firm="Firm",
        engagement_name="Audit",
        valid_from=date.today() - timedelta(days=10),
        valid_until=date.today() - timedelta(days=1),
        modules_accessible=[],
        created_by=test_user.id,
    )
    auth = await authenticate_auditor(async_session, token)
    assert auth is None


@pytest.mark.asyncio
async def test_pbc_checklist_seeded(async_session: AsyncSession, test_user: IamUser) -> None:
    access, _ = await grant_auditor_access(
        async_session,
        tenant_id=test_user.tenant_id,
        auditor_email="seed@example.com",
        auditor_firm="Firm",
        engagement_name="Audit",
        valid_from=date.today(),
        valid_until=date.today() + timedelta(days=30),
        modules_accessible=[],
        created_by=test_user.id,
    )
    rows = await seed_pbc_checklist(async_session, access.id, test_user.tenant_id)
    assert len(rows) == 12


@pytest.mark.asyncio
async def test_request_numbers_sequential(async_session: AsyncSession, test_user: IamUser) -> None:
    access, _ = await grant_auditor_access(
        async_session,
        tenant_id=test_user.tenant_id,
        auditor_email="seq@example.com",
        auditor_firm="Firm",
        engagement_name="Audit",
        valid_from=date.today(),
        valid_until=date.today() + timedelta(days=30),
        modules_accessible=[],
        created_by=test_user.id,
    )
    rows = await seed_pbc_checklist(async_session, access.id, test_user.tenant_id)
    assert rows[0].request_number == "PBC-001"
    assert rows[-1].request_number == "PBC-012"


@pytest.mark.asyncio
async def test_respond_creates_new_record(async_session: AsyncSession, test_user: IamUser) -> None:
    access, _ = await grant_auditor_access(
        async_session,
        tenant_id=test_user.tenant_id,
        auditor_email="resp@example.com",
        auditor_firm="Firm",
        engagement_name="Audit",
        valid_from=date.today(),
        valid_until=date.today() + timedelta(days=30),
        modules_accessible=[],
        created_by=test_user.id,
    )
    rows = await seed_pbc_checklist(async_session, access.id, test_user.tenant_id)
    before = len((await async_session.execute(select(AuditorRequest).where(AuditorRequest.request_number == rows[0].request_number))).scalars().all())
    await respond_to_request(async_session, test_user.tenant_id, rows[0].id, "provided", "Done", ["https://x"], test_user.id)
    after = len((await async_session.execute(select(AuditorRequest).where(AuditorRequest.request_number == rows[0].request_number))).scalars().all())
    assert after == before + 1


@pytest.mark.asyncio
async def test_pbc_tracker_completion_pct(async_session: AsyncSession, test_user: IamUser) -> None:
    access, _ = await grant_auditor_access(
        async_session,
        tenant_id=test_user.tenant_id,
        auditor_email="pct@example.com",
        auditor_firm="Firm",
        engagement_name="Audit",
        valid_from=date.today(),
        valid_until=date.today() + timedelta(days=30),
        modules_accessible=[],
        created_by=test_user.id,
    )
    rows = await seed_pbc_checklist(async_session, access.id, test_user.tenant_id)
    for row in rows[:6]:
        await respond_to_request(async_session, test_user.tenant_id, row.id, "provided", "ok", [], test_user.id)
    payload = await get_pbc_tracker(async_session, access.id, test_user.tenant_id)
    assert payload["completion_pct"] == Decimal("50.00")


@pytest.mark.asyncio
async def test_auditor_requests_append_only(async_session: AsyncSession, test_user: IamUser) -> None:
    access, _ = await grant_auditor_access(
        async_session,
        tenant_id=test_user.tenant_id,
        auditor_email="append@example.com",
        auditor_firm="Firm",
        engagement_name="Audit",
        valid_from=date.today(),
        valid_until=date.today() + timedelta(days=30),
        modules_accessible=[],
        created_by=test_user.id,
    )
    rows = await seed_pbc_checklist(async_session, access.id, test_user.tenant_id)

    await async_session.execute(text(append_only_function_sql()))
    await async_session.execute(text(drop_trigger_sql("auditor_requests")))
    await async_session.execute(text(create_trigger_sql("auditor_requests")))
    await async_session.flush()

    with pytest.raises(Exception):
        await async_session.execute(text("UPDATE auditor_requests SET status='provided' WHERE id=:id"), {"id": rows[0].id})


@pytest.mark.asyncio
async def test_overdue_requests_detected(async_session: AsyncSession, test_user: IamUser) -> None:
    access, _ = await grant_auditor_access(
        async_session,
        tenant_id=test_user.tenant_id,
        auditor_email="overdue@example.com",
        auditor_firm="Firm",
        engagement_name="Audit",
        valid_from=date.today(),
        valid_until=date.today() + timedelta(days=30),
        modules_accessible=[],
        created_by=test_user.id,
    )
    rows = await seed_pbc_checklist(async_session, access.id, test_user.tenant_id)
    rows[0].due_date = date.today() - timedelta(days=1)
    await async_session.flush()
    payload = await get_pbc_tracker(async_session, access.id, test_user.tenant_id)
    assert payload["overdue_requests"]


@pytest.mark.asyncio
async def test_auditor_rls(async_session: AsyncSession, test_user: IamUser) -> None:
    rows = (
        await async_session.execute(
            select(AuditorPortalAccess).where(AuditorPortalAccess.tenant_id == test_user.tenant_id)
        )
    ).scalars().all()
    assert all(row.tenant_id == test_user.tenant_id for row in rows)


@pytest.mark.asyncio
async def test_api_grant_access(async_client, test_user: IamUser) -> None:
    response = await async_client.post(
        "/api/v1/audit/access/grant",
        headers=_auth_headers(test_user),
        json={
            "auditor_email": "api@example.com",
            "auditor_firm": "Firm",
            "engagement_name": "Audit",
            "valid_from": date.today().isoformat(),
            "valid_until": (date.today() + timedelta(days=30)).isoformat(),
            "modules_accessible": ["mis"],
        },
    )
    assert response.status_code == 200
    assert "token" in response.json()["data"]


@pytest.mark.asyncio
async def test_api_respond_to_request(async_client, async_session: AsyncSession, test_user: IamUser) -> None:
    access, _ = await grant_auditor_access(
        async_session,
        tenant_id=test_user.tenant_id,
        auditor_email="apiresp@example.com",
        auditor_firm="Firm",
        engagement_name="Audit",
        valid_from=date.today(),
        valid_until=date.today() + timedelta(days=30),
        modules_accessible=[],
        created_by=test_user.id,
    )
    rows = await seed_pbc_checklist(async_session, access.id, test_user.tenant_id)
    response = await async_client.post(
        f"/api/v1/audit/{access.id}/requests/{rows[0].id}/respond",
        headers=_auth_headers(test_user),
        json={"status": "provided", "response_notes": "ok", "evidence_urls": ["https://x"]},
    )
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "provided"


@pytest.mark.asyncio
async def test_api_pbc_tracker_structure(async_client, async_session: AsyncSession, test_user: IamUser) -> None:
    access, _ = await grant_auditor_access(
        async_session,
        tenant_id=test_user.tenant_id,
        auditor_email="apipbc@example.com",
        auditor_firm="Firm",
        engagement_name="Audit",
        valid_from=date.today(),
        valid_until=date.today() + timedelta(days=30),
        modules_accessible=[],
        created_by=test_user.id,
    )
    await seed_pbc_checklist(async_session, access.id, test_user.tenant_id)
    response = await async_client.get(f"/api/v1/audit/{access.id}/pbc", headers=_auth_headers(test_user))
    assert response.status_code == 200
    payload = response.json()["data"]
    assert {"engagement_name", "total_requests", "completion_pct", "recent_activity"}.issubset(payload)
