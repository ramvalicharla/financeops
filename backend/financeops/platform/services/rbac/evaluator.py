from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.platform.db.models.permissions import CpPermission
from financeops.platform.db.models.role_permissions import CpRolePermission
from financeops.platform.db.models.user_role_assignments import CpUserRoleAssignment

_SCOPE_PRECEDENCE: dict[str, int] = {
    "entity": 0,
    "organisation": 1,
    "workflow_template": 2,
    "module": 3,
    "tenant": 4,
    "platform": 5,
}


@dataclass(frozen=True)
class RbacEvaluationResult:
    allowed: bool
    reason: str
    matched_effect: str | None
    matched_scope: str | None


def _matches_scope(
    assignment: CpUserRoleAssignment,
    *,
    tenant_id: uuid.UUID,
    context_scope: dict[str, str | uuid.UUID | None],
) -> bool:
    ctype = assignment.context_type
    cid = assignment.context_id
    if ctype == "platform":
        return True
    if ctype == "tenant":
        return cid is None or cid == tenant_id
    requested = context_scope.get(ctype)
    if requested is None:
        return False
    try:
        return uuid.UUID(str(requested)) == cid
    except ValueError:
        return False


async def evaluate_permission(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    resource_type: str,
    action: str,
    context_scope: dict[str, str | uuid.UUID | None],
    execution_timestamp: datetime,
) -> RbacEvaluationResult:
    assignments_result = await session.execute(
        select(CpUserRoleAssignment).where(
            CpUserRoleAssignment.tenant_id == tenant_id,
            CpUserRoleAssignment.user_id == user_id,
            CpUserRoleAssignment.is_active.is_(True),
            CpUserRoleAssignment.effective_from <= execution_timestamp,
            (
                (CpUserRoleAssignment.effective_to.is_(None))
                | (CpUserRoleAssignment.effective_to > execution_timestamp)
            ),
        )
    )
    assignments = list(assignments_result.scalars().all())
    if not assignments:
        return RbacEvaluationResult(False, "no_role_assignments", None, None)

    permission_result = await session.execute(
        select(CpPermission.id).where(
            CpPermission.resource_type == resource_type,
            CpPermission.action == action,
        )
    )
    permission_id = permission_result.scalar_one_or_none()
    if permission_id is None:
        return RbacEvaluationResult(False, "permission_not_defined", None, None)

    matched: list[tuple[int, str, str]] = []
    for assignment in assignments:
        if not _matches_scope(assignment, tenant_id=tenant_id, context_scope=context_scope):
            continue
        grants_result = await session.execute(
            select(CpRolePermission.effect).where(
                CpRolePermission.tenant_id == tenant_id,
                CpRolePermission.role_id == assignment.role_id,
                CpRolePermission.permission_id == permission_id,
            )
        )
        effects = [str(item) for item in grants_result.scalars().all()]
        if not effects:
            continue
        precedence = _SCOPE_PRECEDENCE.get(assignment.context_type, 999)
        for effect in effects:
            matched.append((precedence, effect, assignment.context_type))

    if not matched:
        return RbacEvaluationResult(False, "no_matching_permissions", None, None)

    matched.sort(key=lambda item: item[0])
    top_precedence = matched[0][0]
    top = [item for item in matched if item[0] == top_precedence]
    top_effects = {effect for _, effect, _ in top}
    scope = top[0][2]
    if "deny" in top_effects:
        return RbacEvaluationResult(False, "deny_over_allow", "deny", scope)
    if "allow" in top_effects:
        return RbacEvaluationResult(True, "allowed", "allow", scope)
    return RbacEvaluationResult(False, "no_effective_permission", None, scope)
