from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.governance.events import GovernanceActor, emit_governance_event
from financeops.db.models.governance_control import GovernanceApprovalPolicy
from financeops.db.models.users import UserRole

_ROLE_RANK: dict[str, int] = {
    UserRole.read_only.value: 10,
    UserRole.auditor.value: 20,
    UserRole.entity_user.value: 30,
    UserRole.employee.value: 40,
    UserRole.hr_manager.value: 45,
    UserRole.finance_team.value: 60,
    UserRole.director.value: 70,
    UserRole.finance_leader.value: 80,
    UserRole.platform_support.value: 85,
    UserRole.platform_admin.value: 90,
    UserRole.platform_owner.value: 95,
    UserRole.super_admin.value: 100,
}

_DEFAULT_RULES: dict[str, tuple[str, Decimal | None]] = {
    "APPROVE_JOURNAL": (UserRole.finance_leader.value, None),
    "POST_JOURNAL": (UserRole.finance_leader.value, None),
    "REVERSE_JOURNAL": (UserRole.finance_leader.value, None),
    "PERIOD_HARD_CLOSE": (UserRole.finance_leader.value, None),
    "PERIOD_UNLOCK": (UserRole.finance_leader.value, None),
    "FX_REVALUATION_RUN": (UserRole.finance_leader.value, None),
    "GST_RETURN_SUBMIT": (UserRole.finance_leader.value, Decimal("100000.0000")),
}


@dataclass(frozen=True)
class ApprovalRequest:
    tenant_id: uuid.UUID
    module_key: str
    mutation_type: str
    entity_id: uuid.UUID | None
    actor_user_id: uuid.UUID | None
    actor_role: str | None
    amount: Decimal | None = None
    source_type: str | None = None
    subject_type: str = "governed_mutation"
    subject_id: str = ""


@dataclass(frozen=True)
class ApprovalEvaluation:
    approval_required: bool
    is_granted: bool
    required_role: str | None
    policy_id: uuid.UUID | None
    next_action: str
    reason: str


def _role_satisfies(actor_role: str | None, required_role: str | None) -> bool:
    if required_role is None:
        return True
    actor_rank = _ROLE_RANK.get((actor_role or "").strip().lower(), 0)
    required_rank = _ROLE_RANK.get(required_role.strip().lower(), 10**6)
    return actor_rank >= required_rank


class ApprovalPolicyResolver:
    async def resolve_mutation(
        self,
        db: AsyncSession,
        *,
        request: ApprovalRequest,
    ) -> ApprovalEvaluation:
        stmt = (
            select(GovernanceApprovalPolicy)
            .where(
                GovernanceApprovalPolicy.tenant_id == request.tenant_id,
                GovernanceApprovalPolicy.module_key == request.module_key,
                GovernanceApprovalPolicy.mutation_type == request.mutation_type,
                GovernanceApprovalPolicy.active_flag.is_(True),
            )
            .order_by(
                GovernanceApprovalPolicy.priority.asc(),
                GovernanceApprovalPolicy.entity_id.is_(None),
                GovernanceApprovalPolicy.threshold_amount.desc().nullslast(),
            )
        )
        rows = (await db.execute(stmt)).scalars().all()

        selected: GovernanceApprovalPolicy | None = None
        amount = Decimal(str(request.amount)) if request.amount is not None else Decimal("0")
        for row in rows:
            if row.entity_id is not None and row.entity_id != request.entity_id:
                continue
            if row.source_type and row.source_type != request.source_type:
                continue
            if row.threshold_amount is not None and amount < Decimal(str(row.threshold_amount)):
                continue
            selected = row
            break

        if selected is None:
            default_rule = _DEFAULT_RULES.get(request.mutation_type)
            if default_rule is None:
                evaluation = ApprovalEvaluation(
                    approval_required=False,
                    is_granted=True,
                    required_role=None,
                    policy_id=None,
                    next_action="NONE",
                    reason="No active approval policy matched.",
                )
            else:
                required_role, threshold = default_rule
                approval_required = threshold is None or amount >= threshold
                granted = _role_satisfies(request.actor_role, required_role)
                evaluation = ApprovalEvaluation(
                    approval_required=approval_required,
                    is_granted=(not approval_required) or granted,
                    required_role=required_role if approval_required else None,
                    policy_id=None,
                    next_action="NONE" if (not approval_required or granted) else "APPROVAL_REQUIRED",
                    reason=(
                        "Default approval policy did not require approval for this request amount."
                        if not approval_required
                        else (
                            f"Default approval policy matched and actor role satisfies '{required_role}'."
                            if granted
                            else f"Default approval policy requires role '{required_role}'."
                        )
                    ),
                )
        else:
            granted = _role_satisfies(request.actor_role, selected.required_approver_role)
            evaluation = ApprovalEvaluation(
                approval_required=True,
                is_granted=granted,
                required_role=selected.required_approver_role,
                policy_id=selected.id,
                next_action="NONE" if granted else "APPROVAL_REQUIRED",
                reason=(
                    f"Approval policy '{selected.policy_name}' matched and actor role satisfies requirement."
                    if granted
                    else f"Approval policy '{selected.policy_name}' requires role '{selected.required_approver_role}'."
                ),
            )

        actor = GovernanceActor(user_id=request.actor_user_id, role=request.actor_role)
        await emit_governance_event(
            db,
            tenant_id=request.tenant_id,
            module_key=request.module_key,
            subject_type=request.subject_type,
            subject_id=request.subject_id or request.mutation_type,
            event_type="APPROVAL_REQUIRED" if evaluation.approval_required else "APPROVAL_NOT_REQUIRED",
            actor=actor,
            entity_id=request.entity_id,
            payload={
                "policy_id": str(evaluation.policy_id) if evaluation.policy_id else None,
                "required_role": evaluation.required_role,
                "granted": evaluation.is_granted,
                "reason": evaluation.reason,
                "mutation_type": request.mutation_type,
                "source_type": request.source_type,
                "amount": str(amount),
            },
        )
        if evaluation.approval_required and evaluation.is_granted:
            await emit_governance_event(
                db,
                tenant_id=request.tenant_id,
                module_key=request.module_key,
                subject_type=request.subject_type,
                subject_id=request.subject_id or request.mutation_type,
                event_type="APPROVAL_GRANTED",
                actor=actor,
                entity_id=request.entity_id,
                payload={
                    "policy_id": str(evaluation.policy_id) if evaluation.policy_id else None,
                    "required_role": evaluation.required_role,
                    "mutation_type": request.mutation_type,
                },
            )
        return evaluation
