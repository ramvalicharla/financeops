from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, require_finance_leader, require_finance_team
from financeops.db.models.users import IamUser
from financeops.platform.schemas.enforcement import (
    ControlPlaneAuthorizeRequest,
    FinanceExecutionProbeRequest,
    ModuleCreateRequest,
    ModuleEnablementRequest,
    PackageAssignmentRequest,
    PackageCreateRequest,
)
from financeops.platform.services.enforcement.context_token import verify_context_token
from financeops.platform.services.enforcement.control_plane_authorizer import (
    CommandContext,
    ControlPlaneAuthorizer,
)
from financeops.platform.services.enforcement.interceptors import assert_internal_command_token
from financeops.platform.services.tenancy.module_enablement import (
    create_module_registry_item,
    set_module_enablement,
)
from financeops.platform.services.tenancy.package_enablement import (
    assign_package_to_tenant,
    create_package,
)

router = APIRouter()


@router.post("/packages")
async def create_package_endpoint(
    body: PackageCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    package = await create_package(
        session,
        package_code=body.package_code,
        package_name=body.package_name,
        version=body.version,
        actor_tenant_id=user.tenant_id,
        actor_user_id=user.id,
        description=body.description,
    )
    await session.commit()
    return {"id": str(package.id), "package_code": package.package_code}


@router.post("/tenants/{tenant_id}/packages")
async def assign_package_endpoint(
    tenant_id: uuid.UUID,
    body: PackageAssignmentRequest,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    row = await assign_package_to_tenant(
        session,
        tenant_id=tenant_id,
        package_id=body.package_id,
        assignment_status=body.assignment_status,
        actor_user_id=user.id,
        correlation_id=str(getattr(request.state, "correlation_id", "") or ""),
    )
    await session.commit()
    return {"id": str(row.id), "assignment_status": row.assignment_status}


@router.post("")
async def create_module_endpoint(
    body: ModuleCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    module = await create_module_registry_item(
        session,
        module_code=body.module_code,
        module_name=body.module_name,
        engine_context=body.engine_context,
        is_financial_impacting=body.is_financial_impacting,
        actor_tenant_id=user.tenant_id,
        actor_user_id=user.id,
    )
    await session.commit()
    return {"id": str(module.id), "module_code": module.module_code}


@router.post("/tenants/{tenant_id}/enablement")
async def set_module_enablement_endpoint(
    tenant_id: uuid.UUID,
    body: ModuleEnablementRequest,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    row = await set_module_enablement(
        session,
        tenant_id=tenant_id,
        module_id=body.module_id,
        enabled=body.enabled,
        enablement_source=body.enablement_source,
        actor_user_id=user.id,
        correlation_id=str(getattr(request.state, "correlation_id", "") or ""),
    )
    await session.commit()
    return {"id": str(row.id), "enabled": row.enabled}


@router.post("/authorize")
async def authorize_finance_execution(
    body: ControlPlaneAuthorizeRequest,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict:
    correlation_id = str(getattr(request.state, "correlation_id", "") or "")
    if body.tenant_id != user.tenant_id:
        return {"decision": "deny", "reason_code": "TENANT_MISMATCH", "context_token": None}
    if body.user_id != user.id:
        return {"decision": "deny", "reason_code": "USER_MISMATCH", "context_token": None}
    decision = await ControlPlaneAuthorizer.authorize(
        session,
        CommandContext(
            tenant_id=user.tenant_id,
            user_id=user.id,
            module_code=body.module_code,
            resource_type=body.resource_type,
            resource_id=body.resource_id,
            action=body.action,
            execution_mode=body.execution_mode,
            request_fingerprint=body.request_fingerprint,
            correlation_id=correlation_id or body.correlation_id,
            context_scope=body.context_scope,
        ),
    )
    await session.commit()
    return decision


@router.post("/finance-exec-probe")
async def finance_execution_probe(
    body: FinanceExecutionProbeRequest,
    request: Request,
    user: IamUser = Depends(require_finance_team),
) -> dict:
    token = request.headers.get("X-Control-Plane-Token", "")
    claims = assert_internal_command_token(
        token=token,
        tenant_id=user.tenant_id,
        module_code=body.module_code,
    )
    # Validate signature and expiry explicitly again for deterministic API response fields.
    verified = verify_context_token(token)
    return {
        "status": "executed",
        "module_code": body.module_code,
        "tenant_id": str(user.tenant_id),
        "correlation_id": str(claims.get("correlation_id") or verified.get("correlation_id") or ""),
    }
