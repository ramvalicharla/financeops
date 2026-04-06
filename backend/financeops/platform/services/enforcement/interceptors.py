from __future__ import annotations

import uuid
from collections.abc import Callable

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
from financeops.core.exceptions import AuthenticationError, AuthorizationError
from financeops.db.models.users import IamUser
from financeops.platform.services.enforcement.auth_modes import AuthMode
from financeops.platform.services.enforcement.context_token import verify_context_token
from financeops.platform.services.enforcement.control_plane_authorizer import (
    CommandContext,
    ControlPlaneAuthorizer,
)
from financeops.platform.services.enforcement.service_token import verify_service_token


def _mark_auth_mode(request: Request, mode: AuthMode) -> None:
    request.state.auth_mode = mode.value


def _read_control_plane_token(request: Request) -> str:
    return request.headers.get("X-Control-Plane-Token") or str(
        getattr(request.state, "control_plane_context_token", "") or ""
    )


def _validate_control_plane_token(
    *,
    request: Request,
    module_code: str | None = None,
) -> dict:
    token = _read_control_plane_token(request)
    if not token:
        raise AuthenticationError("CONTROL_PLANE_CONTEXT_REQUIRED")
    claims = verify_context_token(token)
    if claims.get("decision") != "allow":
        raise AuthenticationError("Control-plane token does not allow execution")
    tenant_id = str(getattr(request.state, "tenant_id", "") or "")
    if tenant_id and claims.get("tenant_id") != tenant_id:
        raise AuthenticationError("Control-plane token tenant mismatch")
    if module_code and claims.get("module_code") != module_code:
        raise AuthenticationError("Control-plane token module mismatch")
    request.state.control_plane_context_token = token
    _mark_auth_mode(request, AuthMode.CONTROL_PLANE)
    return claims


def _build_context_scope(request: Request) -> dict[str, str | uuid.UUID | None]:
    context_scope: dict[str, str | uuid.UUID | None] = {}
    entity_header = request.headers.get("X-Entity-ID")
    org_header = request.headers.get("X-Organisation-ID")
    workflow_template_header = request.headers.get("X-Workflow-Template-ID")
    workflow_instance_header = request.headers.get("X-Workflow-Instance-ID")
    if entity_header:
        context_scope["entity"] = entity_header
    if org_header:
        context_scope["organisation"] = org_header
    if workflow_template_header:
        context_scope["workflow_template"] = workflow_template_header
    if workflow_instance_header:
        context_scope["workflow_instance_id"] = workflow_instance_header
    return context_scope


async def _authorize_control_plane_request(
    *,
    request: Request,
    session: AsyncSession,
    user: IamUser,
    module_code: str,
    resource_type: str,
    action: str,
    execution_mode: str,
) -> dict:
    correlation_id = str(getattr(request.state, "correlation_id", "") or "")
    fingerprint = f"{request.method}:{request.url.path}:{user.id}"
    decision = await ControlPlaneAuthorizer.authorize(
        session,
        CommandContext(
            tenant_id=user.tenant_id,
            user_id=user.id,
            module_code=module_code,
            resource_type=resource_type,
            resource_id=request.path_params.get("id", "request"),
            action=action,
            execution_mode=execution_mode,
            request_fingerprint=fingerprint,
            correlation_id=correlation_id,
            context_scope=_build_context_scope(request),
        ),
    )
    if decision["decision"] != "allow":
        raise AuthorizationError(decision["reason_code"])

    request.state.control_plane_context_token = str(decision["context_token"])
    _mark_auth_mode(request, AuthMode.USER)
    billing_warning = decision.get("billing_warning_header")
    if billing_warning:
        request.state.billing_warning = str(billing_warning)
    return decision


def control_plane_guard(
    *,
    module_code: str,
    resource_type: str,
    action: str,
    execution_mode: str = "api",
) -> Callable:
    async def _dependency(
        request: Request,
        session: AsyncSession = Depends(get_async_session),
        user: IamUser = Depends(get_current_user),
    ) -> dict:
        return await _authorize_control_plane_request(
            request=request,
            session=session,
            user=user,
            module_code=module_code,
            resource_type=resource_type,
            action=action,
            execution_mode=execution_mode,
        )

    return _dependency


def require_control_plane_token(*, module_code: str | None = None) -> Callable:
    async def _dependency(request: Request) -> dict:
        return _validate_control_plane_token(request=request, module_code=module_code)

    return _dependency


def require_valid_context_token(*, module_code: str | None = None) -> Callable:
    return require_control_plane_token(module_code=module_code)


def validate_optional_control_plane_token(*, module_code: str | None = None) -> Callable:
    async def _dependency(request: Request) -> dict | None:
        token = _read_control_plane_token(request)
        if not token:
            return None
        return _validate_control_plane_token(request=request, module_code=module_code)

    return _dependency


def ensure_module_governance(
    *,
    module_code: str,
    resource_type: str,
    action: str,
    execution_mode: str = "api",
) -> Callable:
    async def _dependency(
        request: Request,
        session: AsyncSession = Depends(get_async_session),
        user: IamUser = Depends(get_current_user),
    ) -> dict:
        token = _read_control_plane_token(request)
        if token:
            return _validate_control_plane_token(request=request, module_code=module_code)

        return await _authorize_control_plane_request(
            request=request,
            session=session,
            user=user,
            module_code=module_code,
            resource_type=resource_type,
            action=action,
            execution_mode=execution_mode,
        )

    return _dependency


def ensure_control_plane_access(
    *,
    module_code: str,
    resource_type: str,
    action: str,
    execution_mode: str = "api",
) -> Callable:
    return ensure_module_governance(
        module_code=module_code,
        resource_type=resource_type,
        action=action,
        execution_mode=execution_mode,
    )


def require_service_token(
    *,
    module_code: str | None = None,
    required_scope: str | None = None,
) -> Callable:
    async def _dependency(request: Request) -> dict:
        token = request.headers.get("X-Service-Token", "")
        if not token:
            raise AuthenticationError("SERVICE_AUTH_REQUIRED")
        claims = verify_service_token(token)
        if module_code and claims.get("module_code") != module_code:
            raise AuthenticationError("Service token module mismatch")
        if required_scope and claims.get("scope") != required_scope:
            raise AuthenticationError("Service token scope mismatch")
        tenant_id = str(claims.get("tenant_id") or "")
        if tenant_id:
            request.state.tenant_id = tenant_id
        request.state.service_id = str(claims.get("service_id") or "")
        _mark_auth_mode(request, AuthMode.SERVICE)
        return claims

    return _dependency


def assert_internal_command_token(*, token: str, tenant_id: uuid.UUID, module_code: str) -> dict:
    claims = verify_service_token(token)
    if claims.get("tenant_id") != str(tenant_id):
        raise AuthenticationError("Service token tenant mismatch")
    if claims.get("module_code") != module_code:
        raise AuthenticationError("Service token module mismatch")
    if claims.get("scope") != "finance.execute":
        raise AuthenticationError("Service token scope mismatch")
    return claims
