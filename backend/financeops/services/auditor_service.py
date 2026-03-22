from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import AuthorizationError
from financeops.db.models.auditor import AuditorGrant, AuditorAccessLog
from financeops.utils.chain_hash import compute_chain_hash, get_previous_hash_locked

log = logging.getLogger(__name__)


async def grant_auditor_access(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    auditor_user_id: uuid.UUID,
    granted_by: uuid.UUID,
    scope: str = "limited",
    allowed_modules: list[str] | None = None,
    expires_at: datetime | None = None,
    notes: str | None = None,
) -> AuditorGrant:
    """
    Grant an auditor access to this tenant's data (INSERT ONLY).
    Replaces any existing active grant for the same auditor.
    """
    modules_payload: dict[str, Any] = {"modules": allowed_modules or []}

    previous_hash = await get_previous_hash_locked(session, AuditorGrant, tenant_id)
    record_data = {
        "tenant_id": str(tenant_id),
        "auditor_user_id": str(auditor_user_id),
        "scope": scope,
        "is_active": True,
        "granted_by": str(granted_by),
    }
    chain_hash = compute_chain_hash(record_data, previous_hash)

    grant = AuditorGrant(
        tenant_id=tenant_id,
        auditor_user_id=auditor_user_id,
        scope=scope,
        allowed_modules=modules_payload,
        expires_at=expires_at,
        is_active=True,
        granted_by=granted_by,
        notes=notes,
        chain_hash=chain_hash,
        previous_hash=previous_hash,
    )
    session.add(grant)
    await session.flush()
    log.info(
        "AuditorGrant created: tenant=%s auditor=%s scope=%s",
        str(tenant_id)[:8], str(auditor_user_id)[:8], scope,
    )
    return grant


async def revoke_auditor_access(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    grant_id: uuid.UUID,
    revoked_by: uuid.UUID,
    notes: str | None = None,
) -> AuditorGrant | None:
    """
    Revoke an auditor grant.
    Since AuditorGrant is FinancialBase (INSERT ONLY), we create a new row
    with is_active=False and revoked_at set.
    """
    result = await session.execute(
        select(AuditorGrant).where(
            AuditorGrant.id == grant_id,
            AuditorGrant.tenant_id == tenant_id,
            AuditorGrant.is_active.is_(True),
        )
    )
    existing = result.scalar_one_or_none()
    if existing is None:
        return None

    now = datetime.now(timezone.utc)
    previous_hash = await get_previous_hash_locked(session, AuditorGrant, tenant_id)
    record_data = {
        "tenant_id": str(tenant_id),
        "auditor_user_id": str(existing.auditor_user_id),
        "scope": existing.scope,
        "is_active": False,
        "revoked_by": str(revoked_by),
    }
    chain_hash = compute_chain_hash(record_data, previous_hash)

    revoked = AuditorGrant(
        tenant_id=tenant_id,
        auditor_user_id=existing.auditor_user_id,
        scope=existing.scope,
        allowed_modules=existing.allowed_modules,
        expires_at=existing.expires_at,
        is_active=False,
        granted_by=existing.granted_by,
        revoked_at=now,
        revoked_by=revoked_by,
        notes=notes or existing.notes,
        chain_hash=chain_hash,
        previous_hash=previous_hash,
    )
    session.add(revoked)
    await session.flush()
    return revoked


async def check_auditor_access(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    auditor_user_id: uuid.UUID,
    module: str | None = None,
) -> AuditorGrant:
    """
    Verify the auditor has an active, non-expired grant for this tenant.
    Optionally checks that the module is in the allowed_modules list.
    Raises AuthorizationError if no valid grant exists.
    """
    now = datetime.now(timezone.utc)
    result = await session.execute(
        select(AuditorGrant)
        .where(
            AuditorGrant.tenant_id == tenant_id,
            AuditorGrant.auditor_user_id == auditor_user_id,
            AuditorGrant.is_active.is_(True),
        )
        .order_by(desc(AuditorGrant.created_at))
        .limit(1)
    )
    grant = result.scalar_one_or_none()

    if grant is None:
        raise AuthorizationError("No active auditor grant for this tenant")

    if grant.expires_at and grant.expires_at < now:
        raise AuthorizationError("Auditor grant has expired")

    if module and grant.scope == "limited":
        allowed = grant.allowed_modules.get("modules", [])
        if module not in allowed:
            raise AuthorizationError(f"Auditor not permitted to access module: {module}")

    return grant


async def log_auditor_access(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    grant_id: uuid.UUID,
    auditor_user_id: uuid.UUID,
    accessed_resource: str,
    resource_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    access_result: str = "granted",
) -> AuditorAccessLog:
    """Log an auditor access event (INSERT ONLY — immutable)."""
    previous_hash = await get_previous_hash_locked(session, AuditorAccessLog, tenant_id)
    record_data = {
        "tenant_id": str(tenant_id),
        "grant_id": str(grant_id),
        "auditor_user_id": str(auditor_user_id),
        "accessed_resource": accessed_resource,
        "access_result": access_result,
    }
    chain_hash = compute_chain_hash(record_data, previous_hash)

    entry = AuditorAccessLog(
        tenant_id=tenant_id,
        grant_id=grant_id,
        auditor_user_id=auditor_user_id,
        accessed_resource=accessed_resource,
        resource_id=resource_id,
        ip_address=ip_address,
        user_agent=user_agent,
        access_result=access_result,
        chain_hash=chain_hash,
        previous_hash=previous_hash,
    )
    session.add(entry)
    await session.flush()
    return entry


async def list_grants(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    active_only: bool = True,
    limit: int = 50,
    offset: int = 0,
) -> list[AuditorGrant]:
    stmt = select(AuditorGrant).where(AuditorGrant.tenant_id == tenant_id)
    if active_only:
        stmt = stmt.where(AuditorGrant.is_active.is_(True))
    stmt = stmt.order_by(desc(AuditorGrant.created_at)).limit(limit).offset(offset)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def list_access_logs(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    auditor_user_id: uuid.UUID | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[AuditorAccessLog]:
    stmt = select(AuditorAccessLog).where(AuditorAccessLog.tenant_id == tenant_id)
    if auditor_user_id:
        stmt = stmt.where(AuditorAccessLog.auditor_user_id == auditor_user_id)
    stmt = stmt.order_by(desc(AuditorAccessLog.created_at)).limit(limit).offset(offset)
    result = await session.execute(stmt)
    return list(result.scalars().all())

