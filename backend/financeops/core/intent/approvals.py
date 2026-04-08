from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.governance.approvals import (
    ApprovalPolicyResolver as CanonicalApprovalPolicyResolver,
    ApprovalRequest,
)
from financeops.db.models.intent_pipeline import CanonicalIntent


@dataclass(frozen=True)
class ApprovalResolution:
    approval_required: bool
    next_action: str
    is_granted: bool
    required_role: str | None
    policy_id: str | None
    reason: str


class ApprovalResolver:
    def __init__(self) -> None:
        self._resolver = CanonicalApprovalPolicyResolver()

    async def resolve(
        self,
        db: AsyncSession,
        *,
        intent: CanonicalIntent,
        actor_role: str | None,
    ) -> ApprovalResolution:
        payload = dict(intent.payload_json or {})
        amount = Decimal("0")
        if intent.intent_type == "CREATE_JOURNAL":
            amount = sum(
                Decimal(str(line.get("debit", 0) or 0)) + Decimal(str(line.get("credit", 0) or 0))
                for line in payload.get("lines", [])
            )
        evaluation = await self._resolver.resolve_mutation(
            db,
            request=ApprovalRequest(
                tenant_id=intent.tenant_id,
                module_key=intent.module_key,
                mutation_type=intent.intent_type,
                entity_id=intent.entity_id,
                actor_user_id=intent.requested_by_user_id,
                actor_role=actor_role,
                amount=amount,
                source_type=str(payload.get("source") or payload.get("source_type") or ""),
                subject_type="intent",
                subject_id=str(intent.id),
            ),
        )
        return ApprovalResolution(
            approval_required=evaluation.approval_required,
            next_action=evaluation.next_action,
            is_granted=evaluation.is_granted,
            required_role=evaluation.required_role,
            policy_id=str(evaluation.policy_id) if evaluation.policy_id else None,
            reason=evaluation.reason,
        )
