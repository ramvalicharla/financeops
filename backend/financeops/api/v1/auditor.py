from __future__ import annotations

import logging
import uuid as _uuid_mod
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import (
    get_async_session,
    get_current_user,
    require_auditor_or_above,
    require_finance_leader,
)
from financeops.config import get_real_ip
from financeops.core.exceptions import AuthorizationError
from financeops.db.models.users import IamUser, UserRole
from financeops.services.auditor_service import (
    check_auditor_access,
    grant_auditor_access,
    list_access_logs,
    list_grants,
    log_auditor_access,
    revoke_auditor_access,
)

log = logging.getLogger(__name__)
router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────────────────

class GrantAccessRequest(BaseModel):
    auditor_user_id: UUID
    scope: str = "limited"  # full / limited
    allowed_modules: list[str] | None = None
    expires_at: datetime | None = None
    notes: str | None = None


class RevokeAccessRequest(BaseModel):
    notes: str | None = None


# ── Helper — enforce auditor role ──────────────────────────────────────────

def _require_auditor_role(user: IamUser) -> None:
    """Raise 403 if the user does not have the auditor role."""
    if user.role != UserRole.auditor:
        raise AuthorizationError("This endpoint requires auditor role")


# ── Finance Leader endpoints (grant/revoke/view) ───────────────────────────

@router.post("/grants", status_code=status.HTTP_201_CREATED)
async def create_auditor_grant(
    body: GrantAccessRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    """Grant an auditor access to this tenant's data (INSERT ONLY)."""
    grant = await grant_auditor_access(
        session,
        tenant_id=user.tenant_id,
        auditor_user_id=body.auditor_user_id,
        granted_by=user.id,
        scope=body.scope,
        allowed_modules=body.allowed_modules,
        expires_at=body.expires_at,
        notes=body.notes,
    )
    await session.flush()
    return {
        "grant_id": str(grant.id),
        "auditor_user_id": str(grant.auditor_user_id),
        "scope": grant.scope,
        "allowed_modules": grant.allowed_modules,
        "is_active": grant.is_active,
        "expires_at": grant.expires_at.isoformat() if grant.expires_at else None,
        "created_at": grant.created_at.isoformat(),
    }


@router.delete("/grants/{grant_id}")
async def revoke_grant(
    grant_id: UUID,
    body: RevokeAccessRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    """Revoke an auditor grant (inserts new row with is_active=False — INSERT ONLY)."""
    revoked = await revoke_auditor_access(
        session,
        tenant_id=user.tenant_id,
        grant_id=grant_id,
        revoked_by=user.id,
        notes=body.notes,
    )
    if revoked is None:
        raise HTTPException(status_code=404, detail="Grant not found or already revoked")
    await session.flush()
    return {
        "grant_id": str(revoked.id),
        "is_active": revoked.is_active,
        "revoked_at": revoked.revoked_at.isoformat() if revoked.revoked_at else None,
    }


@router.get("/grants")
async def list_auditor_grants(
    active_only: bool = True,
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    """List auditor grants for this tenant (finance leader view)."""
    grants = await list_grants(
        session,
        tenant_id=user.tenant_id,
        active_only=active_only,
        limit=limit,
        offset=offset,
    )
    return {
        "grants": [
            {
                "grant_id": str(g.id),
                "auditor_user_id": str(g.auditor_user_id),
                "scope": g.scope,
                "is_active": g.is_active,
                "expires_at": g.expires_at.isoformat() if g.expires_at else None,
                "created_at": g.created_at.isoformat(),
            }
            for g in grants
        ],
        "count": len(grants),
    }


@router.get("/access-logs")
async def get_access_logs(
    auditor_user_id: UUID | None = None,
    limit: int = 100,
    offset: int = 0,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    """View auditor access log (finance leader only — for compliance review)."""
    logs = await list_access_logs(
        session,
        tenant_id=user.tenant_id,
        auditor_user_id=auditor_user_id,
        limit=limit,
        offset=offset,
    )
    return {
        "logs": [
            {
                "log_id": str(lg.id),
                "auditor_user_id": str(lg.auditor_user_id),
                "accessed_resource": lg.accessed_resource,
                "resource_id": lg.resource_id,
                "access_result": lg.access_result,
                "ip_address": lg.ip_address,
                "created_at": lg.created_at.isoformat(),
            }
            for lg in logs
        ],
        "count": len(logs),
    }


# ── Auditor endpoints (read-only data access) ─────────────────────────────

@router.get("/me/access-check")
async def check_my_access(
    request: Request,
    module: str | None = None,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    """
    Auditor endpoint: check that current user has an active grant.
    Logs the access check event.
    """
    _require_auditor_role(user)
    try:
        grant = await check_auditor_access(
            session,
            tenant_id=user.tenant_id,
            auditor_user_id=user.id,
            module=module,
        )
        # Log the successful access
        await log_auditor_access(
            session,
            tenant_id=user.tenant_id,
            grant_id=grant.id,
            auditor_user_id=user.id,
            accessed_resource=f"access_check:{module or 'all'}",
            ip_address=get_real_ip(request),
            user_agent=request.headers.get("user-agent"),
            access_result="granted",
        )
        await session.flush()
        return {
            "access": "granted",
            "grant_id": str(grant.id),
            "scope": grant.scope,
            "allowed_modules": grant.allowed_modules.get("modules", []),
            "expires_at": grant.expires_at.isoformat() if grant.expires_at else None,
        }
    except AuthorizationError as exc:
        # Log the denied attempt (use zero UUID as sentinel — no grant found)
        await log_auditor_access(
            session,
            tenant_id=user.tenant_id,
            grant_id=_uuid_mod.UUID(int=0),
            auditor_user_id=user.id,
            accessed_resource=f"access_check:{module or 'all'}",
            ip_address=get_real_ip(request),
            user_agent=request.headers.get("user-agent"),
            access_result="denied",
        )
        await session.flush()
        raise HTTPException(status_code=403, detail="internal_error")
