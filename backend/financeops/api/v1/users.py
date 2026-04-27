from __future__ import annotations

import logging
import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import case, func, literal, or_, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import (
    get_async_session,
    get_current_user,
    require_user_plane_permission,
)
from financeops.db.models.payment import BillingPlan, TenantSubscription
from financeops.config import settings
from financeops.core.exceptions import NotFoundError, ValidationError
from financeops.db.models.tenants import IamTenant
from financeops.db.models.users import IamUser, UserRole
from financeops.modules.notifications.service import send_notification
from financeops.platform.db.models.roles import CpRole
from financeops.platform.db.models.tenants import CpTenant
from financeops.platform.db.models.user_membership import CpUserEntityAssignment
from financeops.platform.db.models.user_role_assignments import CpUserRoleAssignment
from financeops.platform.services.rbac.user_plane import is_tenant_assignable_role
from financeops.services.user_service import (
    list_tenant_users,
    list_user_orgs,
    normalize_email,
    offboard_user,
    switch_user_to_org,
    update_user_role,
)
from financeops.shared_kernel.idempotency import optional_idempotency_key

router = APIRouter()
log = logging.getLogger(__name__)

tenant_user_manage_guard = require_user_plane_permission(
    resource_type="tenant_user",
    action="manage",
    fallback_roles={
        UserRole.super_admin,
        UserRole.platform_owner,
        UserRole.platform_admin,
        UserRole.finance_leader,
    },
    fallback_error_message="finance_approver role required",
)


class OffboardUserRequest(BaseModel):
    reason: str = "Offboarded"


class InviteUserRequest(BaseModel):
    email: EmailStr
    full_name: str
    role: UserRole
    entity_ids: list[uuid.UUID] = []


class UpdateRoleRequest(BaseModel):
    role: UserRole


class UserTenantOut(BaseModel):
    id: str
    slug: str
    name: str
    role: str
    status: str
    plan: str


def _validate_tenant_assignable_role(role: UserRole) -> UserRole:
    if not is_tenant_assignable_role(role):
        raise HTTPException(
            status_code=422,
            detail="Platform roles cannot be assigned from tenant user management",
        )
    return role


def _serialize_user(user: IamUser) -> dict[str, str | bool | None]:
    return {
        "user_id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.value,
        "is_active": user.is_active,
        "mfa_enabled": user.mfa_enabled,
        "invite_accepted_at": (
            user.invite_accepted_at.isoformat() if user.invite_accepted_at else None
        ),
        "created_at": user.created_at.isoformat(),
    }


async def _get_tenant_user_or_404(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
) -> IamUser:
    user = (
        await session.execute(
            select(IamUser).where(
                IamUser.id == user_id,
                IamUser.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def _active_membership_filters(model: type, *, user_id: uuid.UUID, now: datetime):
    return (
        model.user_id == user_id,
        model.is_active.is_(True),
        model.effective_from <= now,
        or_(model.effective_to.is_(None), model.effective_to > now),
    )


def _build_user_tenants_stmt(
    *,
    current_user: IamUser,
):
    now = datetime.now(UTC)
    direct_membership = select(
        literal(current_user.tenant_id).label("tenant_id"),
        literal(current_user.role.value).label("role_code"),
        literal(1).label("source_priority"),
        literal(current_user.created_at).label("created_at"),
        literal(current_user.id).label("ordering_id"),
    )
    explicit_tenant_roles = (
        select(
            CpUserRoleAssignment.tenant_id.label("tenant_id"),
            CpRole.role_code.label("role_code"),
            literal(0).label("source_priority"),
            CpUserRoleAssignment.created_at.label("created_at"),
            CpUserRoleAssignment.id.label("ordering_id"),
        )
        .join(
            CpRole,
            (CpRole.id == CpUserRoleAssignment.role_id)
            & (CpRole.tenant_id == CpUserRoleAssignment.tenant_id),
        )
        .where(*_active_membership_filters(CpUserRoleAssignment, user_id=current_user.id, now=now))
        .where(CpUserRoleAssignment.context_type == "tenant")
        .where(CpUserRoleAssignment.context_id.is_not(None))
        .where(CpUserRoleAssignment.context_id == CpUserRoleAssignment.tenant_id)
        .where(CpRole.is_active.is_(True))
    )
    candidate_tenants = union_all(direct_membership, explicit_tenant_roles).subquery(
        "candidate_tenants"
    )

    ranked_roles = select(
        candidate_tenants.c.tenant_id,
        candidate_tenants.c.role_code,
        func.row_number()
        .over(
            partition_by=candidate_tenants.c.tenant_id,
            # deterministic rule: latest assignment wins
            order_by=(
                candidate_tenants.c.source_priority.asc(),
                candidate_tenants.c.created_at.desc(),
                candidate_tenants.c.ordering_id.desc(),
            ),
        )
        .label("rn"),
    ).cte("ranked_roles")
    resolved_roles = (
        select(
            ranked_roles.c.tenant_id,
            ranked_roles.c.role_code.label("role"),
        )
        .where(ranked_roles.c.rn == 1)
        .cte("resolved_roles")
    )

    ranked_subscriptions = select(
        TenantSubscription.tenant_id,
        BillingPlan.plan_tier.label("plan_tier"),
        func.row_number()
        .over(
            partition_by=TenantSubscription.tenant_id,
            order_by=(
                TenantSubscription.created_at.desc(),
                TenantSubscription.id.desc(),
            ),
        )
        .label("rn"),
    ).join(
        BillingPlan,
        BillingPlan.id == TenantSubscription.plan_id,
        isouter=True,
    ).cte("ranked_subscriptions")
    resolved_subscriptions = (
        select(
            ranked_subscriptions.c.tenant_id,
            ranked_subscriptions.c.plan_tier,
        )
        .where(ranked_subscriptions.c.rn == 1)
        .cte("resolved_subscriptions")
    )

    ranked_cp_tenants = select(
        CpTenant.tenant_id,
        CpTenant.billing_tier,
        func.row_number()
        .over(
            partition_by=CpTenant.tenant_id,
            order_by=(CpTenant.created_at.desc(), CpTenant.id.desc()),
        )
        .label("rn"),
    ).cte("ranked_cp_tenants")
    resolved_cp_tenants = (
        select(
            ranked_cp_tenants.c.tenant_id,
            ranked_cp_tenants.c.billing_tier,
        )
        .where(ranked_cp_tenants.c.rn == 1)
        .cte("resolved_cp_tenants")
    )

    return (
        select(
            IamTenant.id.label("id"),
            IamTenant.slug.label("slug"),
            IamTenant.display_name.label("name"),
            resolved_roles.c.role.label("role"),
            # status represents tenant lifecycle status.
            IamTenant.status.label("status"),
            func.coalesce(
                resolved_subscriptions.c.plan_tier,
                resolved_cp_tenants.c.billing_tier,
                literal("free"),
            ).label("plan"),
            case(
                (resolved_subscriptions.c.plan_tier.is_(None), True),
                else_=False,
            ).label("plan_fallback_applied"),
        )
        .join(resolved_roles, resolved_roles.c.tenant_id == IamTenant.id)
        .outerjoin(
            resolved_subscriptions,
            resolved_subscriptions.c.tenant_id == IamTenant.id,
        )
        .outerjoin(
            resolved_cp_tenants,
            resolved_cp_tenants.c.tenant_id == IamTenant.id,
        )
        .order_by(IamTenant.display_name.asc(), IamTenant.id.asc())
    )


@router.get("/user/tenants", response_model=list[UserTenantOut])
async def list_user_tenants(
    session: AsyncSession = Depends(get_async_session),
    current_user: IamUser = Depends(get_current_user),
) -> list[UserTenantOut]:
    rows = (await session.execute(_build_user_tenants_stmt(current_user=current_user))).all()
    if not rows:
        log.info("User tenants resolved user_id=%s tenant_count=0", current_user.id)
        return []

    resolved: list[UserTenantOut] = []
    for row in rows:
        status_value = row.status.value if hasattr(row.status, "value") else str(row.status)
        payload = {
            "id": str(row.id) if row.id is not None else "",
            "slug": str(row.slug or "").strip(),
            "name": str(row.name or "").strip(),
            "role": str(row.role or "").strip(),
            "status": str(status_value or "").strip(),
            "plan": str(row.plan or "").strip(),
        }
        if any(not value for value in payload.values()):
            raise ValueError("Invalid tenant response shape")
        if row.plan_fallback_applied:
            log.warning("Tenant plan fallback applied tenant_id=%s", payload["id"])
        resolved.append(UserTenantOut(**payload))

    log.info(
        "User tenants resolved user_id=%s tenant_count=%s",
        current_user.id,
        len(resolved),
    )
    return resolved


@router.get("/users")
async def list_users(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(tenant_user_manage_guard),
) -> dict:
    users = await list_tenant_users(session, user.tenant_id)
    return {
        "users": [_serialize_user(row) for row in users],
        "total": len(users),
    }


@router.post("/users", status_code=status.HTTP_201_CREATED)
async def invite_user(
    body: InviteUserRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(tenant_user_manage_guard),
    _: str | None = Depends(optional_idempotency_key),
) -> dict:
    _validate_tenant_assignable_role(body.role)

    tenant = await session.get(IamTenant, user.tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    if not tenant.org_setup_complete:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "ORG_SETUP_REQUIRED",
                "message": (
                    "Organisation setup must be completed before inviting team members."
                ),
                "current_step": tenant.org_setup_step,
            },
        )

    invite_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(invite_token.encode("utf-8")).hexdigest()
    new_user = IamUser(
        tenant_id=user.tenant_id,
        email=normalize_email(body.email),
        full_name=body.full_name.strip(),
        role=body.role,
        hashed_password="INVITE_PENDING",
        force_mfa_setup=True,
        is_active=False,
        invite_token_hash=token_hash,
        invite_expires_at=datetime.now(UTC) + timedelta(hours=48),
    )
    session.add(new_user)
    await session.flush()

    for entity_id in body.entity_ids:
        session.add(
            CpUserEntityAssignment(
                tenant_id=user.tenant_id,
                user_id=new_user.id,
                entity_id=entity_id,
                is_active=True,
            )
        )

    frontend_base = str(getattr(settings, "FRONTEND_URL", "http://localhost:3000")).rstrip("/")
    invite_url = f"{frontend_base}/accept-invite?token={invite_token}"
    await send_notification(
        session,
        tenant_id=user.tenant_id,
        recipient_user_id=new_user.id,
        notification_type="user_invited",
        title="You've been invited to FinanceOps",
        body=(
            f"{user.full_name} invited you to join {tenant.display_name}. "
            f"Accept invitation: {invite_url}"
        ),
        action_url=invite_url,
        metadata={
            "invitee_name": body.full_name,
            "inviter_name": user.full_name,
            "company_name": tenant.display_name,
            "invite_url": invite_url,
            "unsubscribe_url": f"{frontend_base}/settings/privacy",
        },
    )
    await session.flush()
    return {
        "user_id": str(new_user.id),
        "email": new_user.email,
        "role": new_user.role.value,
        "message": f"Invitation queued for {new_user.email}",
    }


class UserOrgItem(BaseModel):
    org_id: str
    org_name: str
    org_slug: str
    org_status: str
    role: str
    is_primary: bool
    joined_at: str


class UserOrgsListResponse(BaseModel):
    items: list[UserOrgItem]
    total: int


class SwitchTargetOrg(BaseModel):
    id: str
    name: str
    role: str


class SwitchOrgResponse(BaseModel):
    switch_token: str
    target_org: SwitchTargetOrg


@router.get("/users/me/orgs", response_model=UserOrgsListResponse)
async def get_my_orgs(
    session: AsyncSession = Depends(get_async_session),
    current_user: IamUser = Depends(get_current_user),
) -> UserOrgsListResponse:
    rows = await list_user_orgs(session, user_id=current_user.id)
    items = [
        UserOrgItem(
            org_id=str(row.org_id),
            org_name=row.org_name or "",
            org_slug=row.org_slug or "",
            org_status=str(row.org_status.value if hasattr(row.org_status, "value") else row.org_status),
            role=str(row.role.value if hasattr(row.role, "value") else row.role),
            is_primary=row.is_primary,
            joined_at=row.joined_at.isoformat(),
        )
        for row in rows
    ]
    return UserOrgsListResponse(items=items, total=len(items))


@router.post("/users/me/orgs/{tenant_id}/switch", response_model=SwitchOrgResponse)
async def switch_org(
    tenant_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    current_user: IamUser = Depends(get_current_user),
) -> SwitchOrgResponse:
    result = await switch_user_to_org(session, user=current_user, target_tenant_id=tenant_id)
    return SwitchOrgResponse(
        switch_token=result["switch_token"],
        target_org=SwitchTargetOrg(
            id=result["target_tenant_id"],
            name=result["target_tenant_name"],
            role=result["role"],
        ),
    )


class UserPreferencesResponse(BaseModel):
    sidebar_collapsed: bool | None


class UpdateUserPreferencesRequest(BaseModel):
    sidebar_collapsed: bool | None = None


@router.get("/users/me/preferences", response_model=UserPreferencesResponse)
async def get_my_preferences(
    current_user: IamUser = Depends(get_current_user),
) -> UserPreferencesResponse:
    return UserPreferencesResponse(sidebar_collapsed=current_user.sidebar_collapsed)


@router.patch("/users/me/preferences", response_model=UserPreferencesResponse)
async def update_my_preferences(
    body: UpdateUserPreferencesRequest,
    session: AsyncSession = Depends(get_async_session),
    current_user: IamUser = Depends(get_current_user),
) -> UserPreferencesResponse:
    if "sidebar_collapsed" in body.model_fields_set:
        current_user.sidebar_collapsed = body.sidebar_collapsed
    await session.flush()
    return UserPreferencesResponse(sidebar_collapsed=current_user.sidebar_collapsed)


@router.get("/users/{user_id}")
async def get_user(
    user_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(tenant_user_manage_guard),
) -> dict:
    row = await _get_tenant_user_or_404(session, tenant_id=user.tenant_id, user_id=user_id)
    return _serialize_user(row)


@router.patch("/users/{user_id}/role")
async def update_user_role_endpoint(
    user_id: uuid.UUID,
    body: UpdateRoleRequest,
    session: AsyncSession = Depends(get_async_session),
    current_user: IamUser = Depends(tenant_user_manage_guard),
) -> dict:
    _validate_tenant_assignable_role(body.role)
    try:
        updated = await update_user_role(
            session,
            tenant_id=current_user.tenant_id,
            user_id=user_id,
            new_role=body.role,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail="User not found") from exc
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    await session.flush()
    return {
        "user_id": str(updated.id),
        "role": updated.role.value,
        "updated": True,
    }


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    current_user: IamUser = Depends(tenant_user_manage_guard),
) -> dict:
    try:
        return await offboard_user(
            session=session,
            tenant_id=current_user.tenant_id,
            user_id=user_id,
            offboarded_by=current_user.id,
            reason="Offboarded via /users route",
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail="User not found") from exc
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc


@router.post("/users/{user_id}/offboard", status_code=status.HTTP_200_OK)
async def offboard_user_endpoint(
    user_id: uuid.UUID,
    body: OffboardUserRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(tenant_user_manage_guard),
) -> dict:
    try:
        return await offboard_user(
            session=session,
            tenant_id=user.tenant_id,
            user_id=user_id,
            offboarded_by=user.id,
            reason=body.reason,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail="User not found") from exc
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
