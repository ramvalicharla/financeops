from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import AuthorizationError
from financeops.services.auditor_service import (
    check_auditor_access,
    grant_auditor_access,
    list_access_logs,
    list_grants,
    log_auditor_access,
    revoke_auditor_access,
)


@pytest.mark.asyncio
async def test_grant_auditor_access(async_session: AsyncSession, test_tenant):
    auditor_id = uuid.uuid4()
    grant = await grant_auditor_access(
        async_session,
        tenant_id=test_tenant.id,
        auditor_user_id=auditor_id,
        granted_by=test_tenant.id,
        scope="limited",
        allowed_modules=["reconciliation", "bank_recon"],
    )
    assert grant.is_active is True
    assert grant.scope == "limited"
    assert grant.allowed_modules == {"modules": ["reconciliation", "bank_recon"]}
    assert len(grant.chain_hash) == 64


@pytest.mark.asyncio
async def test_revoke_auditor_access_creates_new_row(
    async_session: AsyncSession, test_tenant
):
    """Revoking inserts a new row with is_active=False (INSERT ONLY)."""
    auditor_id = uuid.uuid4()
    grant = await grant_auditor_access(
        async_session,
        tenant_id=test_tenant.id,
        auditor_user_id=auditor_id,
        granted_by=test_tenant.id,
        scope="full",
    )
    original_id = grant.id

    revoked = await revoke_auditor_access(
        async_session,
        tenant_id=test_tenant.id,
        grant_id=grant.id,
        revoked_by=test_tenant.id,
        notes="Engagement ended",
    )
    assert revoked is not None
    assert revoked.is_active is False
    assert revoked.revoked_at is not None
    # New INSERT — different id
    assert revoked.id != original_id
    assert len(revoked.chain_hash) == 64


@pytest.mark.asyncio
async def test_check_auditor_access_success(
    async_session: AsyncSession, test_tenant
):
    """Active grant with no expiry → access granted."""
    auditor_id = uuid.uuid4()
    await grant_auditor_access(
        async_session,
        tenant_id=test_tenant.id,
        auditor_user_id=auditor_id,
        granted_by=test_tenant.id,
        scope="full",
    )
    grant = await check_auditor_access(
        async_session,
        tenant_id=test_tenant.id,
        auditor_user_id=auditor_id,
    )
    assert grant.is_active is True


@pytest.mark.asyncio
async def test_check_auditor_access_no_grant_raises(
    async_session: AsyncSession, test_tenant
):
    """No grant for this auditor → AuthorizationError."""
    with pytest.raises(AuthorizationError, match="No active auditor grant"):
        await check_auditor_access(
            async_session,
            tenant_id=test_tenant.id,
            auditor_user_id=uuid.uuid4(),
        )


@pytest.mark.asyncio
async def test_check_auditor_access_expired_raises(
    async_session: AsyncSession, test_tenant
):
    """Expired grant → AuthorizationError."""
    auditor_id = uuid.uuid4()
    past = datetime.now(timezone.utc) - timedelta(days=1)
    await grant_auditor_access(
        async_session,
        tenant_id=test_tenant.id,
        auditor_user_id=auditor_id,
        granted_by=test_tenant.id,
        scope="limited",
        expires_at=past,
    )
    with pytest.raises(AuthorizationError, match="expired"):
        await check_auditor_access(
            async_session,
            tenant_id=test_tenant.id,
            auditor_user_id=auditor_id,
        )


@pytest.mark.asyncio
async def test_check_auditor_access_module_not_allowed(
    async_session: AsyncSession, test_tenant
):
    """Limited grant without the requested module → AuthorizationError."""
    auditor_id = uuid.uuid4()
    await grant_auditor_access(
        async_session,
        tenant_id=test_tenant.id,
        auditor_user_id=auditor_id,
        granted_by=test_tenant.id,
        scope="limited",
        allowed_modules=["reconciliation"],
    )
    with pytest.raises(AuthorizationError, match="not permitted"):
        await check_auditor_access(
            async_session,
            tenant_id=test_tenant.id,
            auditor_user_id=auditor_id,
            module="bank_recon",
        )


@pytest.mark.asyncio
async def test_log_auditor_access(async_session: AsyncSession, test_tenant):
    auditor_id = uuid.uuid4()
    entry = await log_auditor_access(
        async_session,
        tenant_id=test_tenant.id,
        grant_id=uuid.uuid4(),
        auditor_user_id=auditor_id,
        accessed_resource="gl_entries",
        access_result="granted",
    )
    assert entry.access_result == "granted"
    assert entry.accessed_resource == "gl_entries"
    assert len(entry.chain_hash) == 64


@pytest.mark.asyncio
async def test_list_grants_active_only(async_session: AsyncSession, test_tenant):
    auditor_id = uuid.uuid4()
    grant = await grant_auditor_access(
        async_session,
        tenant_id=test_tenant.id,
        auditor_user_id=auditor_id,
        granted_by=test_tenant.id,
        scope="full",
    )
    grants = await list_grants(
        async_session, test_tenant.id, active_only=True
    )
    grant_ids = [g.id for g in grants]
    assert grant.id in grant_ids
    assert all(g.is_active for g in grants)
