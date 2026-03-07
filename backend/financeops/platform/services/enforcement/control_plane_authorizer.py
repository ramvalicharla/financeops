from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import NotFoundError
from financeops.platform.services.enforcement.context_token import issue_context_token
from financeops.platform.services.isolation.routing_service import resolve_isolation_route
from financeops.platform.services.quotas.quota_guard import QuotaGuard, QuotaGuardRequest
from financeops.platform.services.rbac.evaluator import evaluate_permission
from financeops.platform.services.tenancy.module_enablement import resolve_module_enablement
from financeops.platform.services.tenancy.tenant_provisioning import validate_tenant_active
from financeops.platform.services.workflows.event_service import derive_workflow_status


@dataclass(frozen=True)
class CommandContext:
    tenant_id: uuid.UUID
    user_id: uuid.UUID
    module_code: str
    resource_type: str
    resource_id: str
    action: str
    execution_mode: str
    request_fingerprint: str
    correlation_id: str
    context_scope: dict[str, str | uuid.UUID | None]


class ControlPlaneAuthorizer:
    @staticmethod
    def _bounded_token(value: str, *, max_len: int = 128) -> str:
        text = str(value)
        if len(text) <= max_len:
            return text
        return sha256(text.encode("utf-8")).hexdigest()

    @staticmethod
    async def _workflow_eligible(
        session: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        context_scope: dict[str, str | uuid.UUID | None],
    ) -> bool:
        raw_workflow_instance_id = context_scope.get("workflow_instance_id")
        if raw_workflow_instance_id is None:
            return True
        try:
            workflow_instance_id = uuid.UUID(str(raw_workflow_instance_id))
        except ValueError:
            return False
        try:
            latest = await derive_workflow_status(
                session,
                tenant_id=tenant_id,
                workflow_instance_id=workflow_instance_id,
            )
        except NotFoundError:
            return False
        return str(latest.get("status", "")) in {"instance_approved", "instance_running"}

    @staticmethod
    async def authorize(session: AsyncSession, context: CommandContext) -> dict[str, Any]:
        await validate_tenant_active(session, tenant_id=context.tenant_id)

        module_id, module_enabled = await resolve_module_enablement(
            session,
            tenant_id=context.tenant_id,
            module_code=context.module_code,
            as_of=datetime.now(UTC),
        )
        if not module_enabled:
            return {
                "decision": "deny",
                "reason_code": "MODULE_DISABLED",
                "policy_snapshot_version": 1,
                "quota_check_id": None,
                "isolation_route_version": None,
                "context_token": None,
            }

        rbac_result = await evaluate_permission(
            session,
            tenant_id=context.tenant_id,
            user_id=context.user_id,
            resource_type=context.resource_type,
            action=context.action,
            context_scope={**context.context_scope, "module": module_id},
            execution_timestamp=datetime.now(UTC),
        )
        if not rbac_result.allowed:
            return {
                "decision": "deny",
                "reason_code": "PERMISSION_DENIED",
                "policy_snapshot_version": 1,
                "quota_check_id": None,
                "isolation_route_version": None,
                "context_token": None,
            }

        workflow_eligible = await ControlPlaneAuthorizer._workflow_eligible(
            session,
            tenant_id=context.tenant_id,
            context_scope=context.context_scope,
        )
        if not workflow_eligible:
            return {
                "decision": "deny",
                "reason_code": "WORKFLOW_NOT_ELIGIBLE",
                "policy_snapshot_version": 1,
                "quota_check_id": None,
                "isolation_route_version": None,
                "context_token": None,
            }

        quota_type = {
            "api": "api_requests",
            "job": "job_submissions",
            "worker": "worker_active_jobs",
            "internal": "worker_active_jobs",
            "export": "export_bytes",
            "ai": "ai_inference_calls",
            "storage": "storage_bytes",
        }.get(context.execution_mode, "api_requests")

        request_fingerprint = ControlPlaneAuthorizer._bounded_token(
            context.request_fingerprint
        )
        idempotency_key = ControlPlaneAuthorizer._bounded_token(
            f"{context.execution_mode}:{request_fingerprint}"
        )

        quota_result = await QuotaGuard.check_and_record(
            session,
            QuotaGuardRequest(
                tenant_id=context.tenant_id,
                quota_type=quota_type,
                usage_delta=1,
                operation_id=uuid.uuid4(),
                idempotency_key=idempotency_key,
                request_fingerprint=request_fingerprint,
                source_layer=f"{context.execution_mode}_ingress",
                actor_user_id=context.user_id,
                correlation_id=context.correlation_id,
            ),
        )
        if not quota_result["allowed"]:
            mode = quota_result["enforcement_mode"]
            decision = "defer" if mode in {"queue", "throttle"} else "deny"
            return {
                "decision": decision,
                "reason_code": "QUOTA_EXCEEDED",
                "policy_snapshot_version": 1,
                "quota_check_id": None,
                "isolation_route_version": None,
                "context_token": None,
            }

        route = await resolve_isolation_route(
            session,
            tenant_id=context.tenant_id,
        )

        issued_at = datetime.now(UTC)
        expires_at = issued_at + timedelta(minutes=5)
        token = issue_context_token(
            {
                "tenant_id": str(context.tenant_id),
                "module_code": context.module_code,
                "decision": "allow",
                "policy_snapshot_version": 1,
                "quota_check_id": str(quota_result.get("usage_event_id") or ""),
                "isolation_route_version": int(route.route_version),
                "issued_at": issued_at.isoformat(),
                "expires_at": expires_at.isoformat(),
                "correlation_id": context.correlation_id,
            }
        )
        return {
            "decision": "allow",
            "reason_code": "ALLOWED",
            "policy_snapshot_version": 1,
            "quota_check_id": str(quota_result.get("usage_event_id") or ""),
            "isolation_route_version": int(route.route_version),
            "context_token": token,
        }
