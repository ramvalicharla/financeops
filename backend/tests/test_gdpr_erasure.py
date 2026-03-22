from __future__ import annotations

import hashlib
import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.security import create_access_token, hash_password
from financeops.db.append_only import append_only_function_sql, create_trigger_sql
from financeops.db.models.credits import CreditDirection, CreditTransaction, CreditTransactionStatus
from financeops.db.models.tenants import IamTenant
from financeops.db.models.users import IamUser, UserRole
from financeops.db.rls import set_tenant_context
from financeops.modules.compliance.erasure_service import erase_user_pii
from financeops.modules.compliance.models import ErasureLog


async def _create_user(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    email: str,
    role: UserRole = UserRole.finance_team,
) -> IamUser:
    user = IamUser(
        tenant_id=tenant_id,
        email=email,
        hashed_password=hash_password("TestPass123!"),
        full_name="GDPR Target",
        role=role,
        is_active=True,
        mfa_enabled=True,
    )
    session.add(user)
    await session.flush()
    return user


async def _create_finance_leader(session: AsyncSession, tenant_id: uuid.UUID) -> IamUser:
    return await _create_user(
        session,
        tenant_id=tenant_id,
        email=f"leader_{uuid.uuid4().hex[:10]}@example.com",
        role=UserRole.finance_leader,
    )


@pytest.mark.asyncio
async def test_erasure_creates_audit_log(async_session: AsyncSession, test_tenant: IamTenant) -> None:
    """Erasure request creates immutable log entry."""
    await set_tenant_context(async_session, test_tenant.id)
    actor = await _create_finance_leader(async_session, test_tenant.id)
    target = await _create_user(
        async_session,
        tenant_id=test_tenant.id,
        email=f"erase_{uuid.uuid4().hex[:8]}@example.com",
    )
    result = await erase_user_pii(
        async_session,
        tenant_id=test_tenant.id,
        user_id=target.id,
        requested_by=actor.id,
        request_method="admin",
    )
    user_id_hash = hashlib.sha256(str(target.id).encode()).hexdigest()
    assert result["status"] == "completed"
    rows = (
        await async_session.execute(
            text(
                """
                SELECT status, user_id_hash, user_id
                FROM erasure_log
                WHERE tenant_id = CAST(:tenant_id AS uuid)
                  AND user_id_hash = :user_id_hash
                ORDER BY created_at DESC
                """
            ),
            {"tenant_id": str(test_tenant.id), "user_id_hash": user_id_hash},
        )
    ).all()
    assert any(row[0] == "completed" for row in rows)
    assert any(row[1] == user_id_hash for row in rows)
    completed_row = next(row for row in rows if row[0] == "completed")
    assert completed_row[2] is None


@pytest.mark.asyncio
async def test_erased_user_cannot_authenticate(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_tenant: IamTenant,
) -> None:
    """After erasure, user cannot log in."""
    await set_tenant_context(async_session, test_tenant.id)
    actor = await _create_finance_leader(async_session, test_tenant.id)
    target_email = f"login_erase_{uuid.uuid4().hex[:8]}@example.com"
    target = await _create_user(
        async_session,
        tenant_id=test_tenant.id,
        email=target_email,
    )
    await erase_user_pii(
        async_session,
        tenant_id=test_tenant.id,
        user_id=target.id,
        requested_by=actor.id,
        request_method="admin",
    )
    response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": target_email, "password": "TestPass123!"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_erased_user_email_is_anonymised(async_session: AsyncSession, test_tenant: IamTenant) -> None:
    """After erasure, email field contains no PII."""
    await set_tenant_context(async_session, test_tenant.id)
    actor = await _create_finance_leader(async_session, test_tenant.id)
    target = await _create_user(
        async_session,
        tenant_id=test_tenant.id,
        email="real@example.com",
    )
    await erase_user_pii(
        async_session,
        tenant_id=test_tenant.id,
        user_id=target.id,
        requested_by=actor.id,
        request_method="admin",
    )
    row = (
        await async_session.execute(
            text("SELECT email FROM iam_users WHERE id = CAST(:id AS uuid)"),
            {"id": str(target.id)},
        )
    ).scalar_one()
    assert "real@example.com" not in row
    assert row.endswith("@erased.invalid")


@pytest.mark.asyncio
async def test_financial_records_preserved_after_erasure(async_session: AsyncSession, test_tenant: IamTenant) -> None:
    """Financial records referencing erased user are intact."""
    await set_tenant_context(async_session, test_tenant.id)
    actor = await _create_finance_leader(async_session, test_tenant.id)
    target = await _create_user(
        async_session,
        tenant_id=test_tenant.id,
        email=f"finance_{uuid.uuid4().hex[:8]}@example.com",
    )
    tx = CreditTransaction(
        tenant_id=test_tenant.id,
        user_id=target.id,
        task_type="gdpr_test",
        amount=Decimal("10.000000"),
        direction=CreditDirection.credit,
        balance_before=Decimal("0.000000"),
        balance_after=Decimal("10.000000"),
        reservation_id=None,
        status=CreditTransactionStatus.confirmed,
        chain_hash="a" * 64,
        previous_hash="0" * 64,
    )
    async_session.add(tx)
    await async_session.flush()
    tx_id = tx.id

    await erase_user_pii(
        async_session,
        tenant_id=test_tenant.id,
        user_id=target.id,
        requested_by=actor.id,
        request_method="admin",
    )
    exists = (
        await async_session.execute(
            text(
                """
                SELECT COUNT(*) FROM credit_transactions
                WHERE id = CAST(:id AS uuid)
                """
            ),
            {"id": str(tx_id)},
        )
    ).scalar_one()
    assert exists == 1


@pytest.mark.asyncio
async def test_erasure_log_is_append_only(async_session: AsyncSession, test_tenant: IamTenant) -> None:
    """erasure_log table blocks UPDATE and DELETE."""
    await set_tenant_context(async_session, test_tenant.id)
    actor = await _create_finance_leader(async_session, test_tenant.id)
    record = ErasureLog(
        tenant_id=test_tenant.id,
        user_id=None,
        user_id_hash=hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest(),
        requested_by=actor.id,
        request_method="admin",
        status="initiated",
        pii_fields_erased=[],
    )
    async_session.add(record)
    await async_session.flush()
    await async_session.execute(text(append_only_function_sql()))
    await async_session.execute(text(create_trigger_sql("erasure_log")))
    await async_session.flush()
    with pytest.raises(DBAPIError):
        await async_session.execute(
            text(
                """
                UPDATE erasure_log
                SET status = 'failed'
                WHERE id = CAST(:id AS uuid)
                """
            ),
            {"id": str(record.id)},
        )


@pytest.mark.asyncio
async def test_erasure_endpoint_requires_finance_leader_role(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_tenant: IamTenant,
) -> None:
    """POST /compliance/erasure requires elevated role."""
    await set_tenant_context(async_session, test_tenant.id)
    low_user = await _create_user(
        async_session,
        tenant_id=test_tenant.id,
        email=f"team_{uuid.uuid4().hex[:8]}@example.com",
        role=UserRole.finance_team,
    )
    token = create_access_token(low_user.id, low_user.tenant_id, low_user.role.value)
    response = await async_client.post(
        "/api/v1/compliance/erasure",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_erasure_endpoint_self_request(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_tenant: IamTenant,
) -> None:
    """Finance leader can trigger self erasure."""
    await set_tenant_context(async_session, test_tenant.id)
    actor = await _create_finance_leader(async_session, test_tenant.id)
    token = create_access_token(actor.id, actor.tenant_id, actor.role.value)
    response = await async_client.post(
        "/api/v1/compliance/erasure",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "completed"


@pytest.mark.asyncio
async def test_erasure_log_endpoint_paginated(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_tenant: IamTenant,
) -> None:
    """GET /compliance/erasure-log returns paginated envelope."""
    await set_tenant_context(async_session, test_tenant.id)
    actor = await _create_finance_leader(async_session, test_tenant.id)
    token = create_access_token(actor.id, actor.tenant_id, actor.role.value)
    response = await async_client.get(
        "/api/v1/compliance/erasure-log?limit=5&offset=0",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert "data" in payload
    assert "total" in payload
    assert payload["limit"] == 5
    assert payload["offset"] == 0


@pytest.mark.asyncio
async def test_erasure_unknown_user_returns_404(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_tenant: IamTenant,
) -> None:
    """Unknown user erasure returns 404."""
    await set_tenant_context(async_session, test_tenant.id)
    actor = await _create_finance_leader(async_session, test_tenant.id)
    token = create_access_token(actor.id, actor.tenant_id, actor.role.value)
    response = await async_client.post(
        "/api/v1/compliance/erasure",
        headers={"Authorization": f"Bearer {token}"},
        json={"user_id": str(uuid.uuid4())},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_erasure_disables_account(async_session: AsyncSession, test_tenant: IamTenant) -> None:
    """Erasure deactivates account and disables MFA."""
    await set_tenant_context(async_session, test_tenant.id)
    actor = await _create_finance_leader(async_session, test_tenant.id)
    target = await _create_user(
        async_session,
        tenant_id=test_tenant.id,
        email=f"mfa_{uuid.uuid4().hex[:8]}@example.com",
    )
    await erase_user_pii(
        async_session,
        tenant_id=test_tenant.id,
        user_id=target.id,
        requested_by=actor.id,
        request_method="admin",
    )
    row = (
        await async_session.execute(
            text(
                """
                SELECT is_active, mfa_enabled, totp_secret_encrypted
                FROM iam_users
                WHERE id = CAST(:id AS uuid)
                """
            ),
            {"id": str(target.id)},
        )
    ).one()
    assert row[0] is False
    assert row[1] is False
    assert row[2] is None
