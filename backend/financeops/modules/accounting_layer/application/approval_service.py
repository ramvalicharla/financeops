from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import AuthorizationError, NotFoundError, ValidationError
from financeops.core.intent.context import require_mutation_context
from financeops.db.models.accounting_approvals import (
    AccountingJVApproval,
    ApprovalDecision,
    ApprovalSLATimer,
)
from financeops.db.models.accounting_jv import AccountingJVAggregate, JVStatus
from financeops.modules.accounting_layer.application.jv_service import transition_jv


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def _compute_fingerprint(*parts: str) -> str:
    payload = ":".join(parts)
    return hashlib.sha256(payload.encode()).hexdigest()


def _generate_idempotency_key() -> str:
    return secrets.token_hex(32)


_THRESHOLD_L2 = Decimal("500000")
_THRESHOLD_L3 = Decimal("5000000")

ROLE_APPROVAL_LEVEL: dict[str, int] = {
    "ACCOUNTING_REVIEWER": 1,
    "ACCOUNTING_SR_REVIEWER": 2,
    "ACCOUNTING_CFO_APPROVER": 3,
    "ACCOUNTING_ADMIN": 3,
}

_ROLE_NORMALIZATION: dict[str, str] = {
    "finance_team": "ACCOUNTING_REVIEWER",
    "finance_leader": "ACCOUNTING_ADMIN",
    "director": "ACCOUNTING_CFO_APPROVER",
    "super_admin": "ACCOUNTING_ADMIN",
    "platform_owner": "ACCOUNTING_ADMIN",
    "auditor": "ACCOUNTING_AUDITOR",
}


def _normalize_role(actor_role: str) -> str:
    role_upper = actor_role.upper()
    if role_upper in ROLE_APPROVAL_LEVEL:
        return role_upper
    fallback = _ROLE_NORMALIZATION.get(actor_role.lower())
    if fallback is not None:
        return fallback
    return role_upper


def required_approval_level(total_amount: Decimal) -> int:
    if total_amount >= _THRESHOLD_L3:
        return 3
    if total_amount >= _THRESHOLD_L2:
        return 2
    return 1


def _enforce_maker_checker(
    jv: AccountingJVAggregate,
    acted_by: uuid.UUID,
    actor_role: str,
) -> None:
    _ = actor_role
    if acted_by == jv.created_by:
        raise AuthorizationError(
            "Maker-checker violation: the JV preparer cannot review or approve their own Journal Voucher."
        )


def _enforce_approval_level(jv: AccountingJVAggregate, actor_role: str) -> None:
    normalized_role = _normalize_role(actor_role)
    actor_level = ROLE_APPROVAL_LEVEL.get(normalized_role)
    if actor_level is None:
        raise AuthorizationError(
            f"Role '{actor_role}' does not have approval authority. "
            f"Valid roles: {sorted(ROLE_APPROVAL_LEVEL.keys())}"
        )
    required_level = required_approval_level(jv.total_debit)
    if actor_level < required_level:
        hint = "CFO Approver" if required_level == 3 else "Senior Reviewer"
        raise AuthorizationError(
            f"JV amount {jv.total_debit} requires approval level {required_level} "
            f"(e.g. {hint}). Your role '{actor_role}' has level {actor_level}."
        )


async def submit_approval(
    db: AsyncSession,
    *,
    jv_id: uuid.UUID,
    tenant_id: uuid.UUID,
    acted_by: uuid.UUID,
    actor_role: str,
    decision: str,
    decision_reason: str | None = None,
    expected_version: int,
    delegated_from: uuid.UUID | None = None,
    idempotency_key: str | None = None,
) -> AccountingJVApproval:
    mutation_context = require_mutation_context("Journal approval decision")
    decision_upper = decision.upper()
    if decision_upper not in (ApprovalDecision.APPROVED, ApprovalDecision.REJECTED):
        raise ValidationError(f"Invalid decision '{decision}'. Must be APPROVED or REJECTED.")

    if decision_upper == ApprovalDecision.REJECTED and not decision_reason:
        raise ValidationError("A decision_reason is required when rejecting a JV.")

    result = await db.execute(
        select(AccountingJVAggregate).where(
            AccountingJVAggregate.id == jv_id,
            AccountingJVAggregate.tenant_id == tenant_id,
        )
    )
    jv = result.scalar_one_or_none()
    if jv is None:
        raise NotFoundError(f"JV {jv_id} not found")

    normalized_role = _normalize_role(actor_role)

    _enforce_maker_checker(jv, acted_by, normalized_role)

    if decision_upper == ApprovalDecision.APPROVED:
        _enforce_approval_level(jv, normalized_role)

    valid_states_for_decision: dict[str, set[str]] = {
        ApprovalDecision.APPROVED: {JVStatus.UNDER_REVIEW},
        ApprovalDecision.REJECTED: {
            JVStatus.PENDING_REVIEW,
            JVStatus.UNDER_REVIEW,
            JVStatus.RESUBMITTED,
            JVStatus.ESCALATED,
        },
    }
    if jv.status not in valid_states_for_decision[decision_upper]:
        raise ValidationError(
            f"Cannot record '{decision_upper}' decision on JV in status '{jv.status}'. "
            f"Valid states: {sorted(valid_states_for_decision[decision_upper])}"
        )

    idem_key = idempotency_key or _generate_idempotency_key()
    fingerprint = _compute_fingerprint(str(jv_id), str(acted_by), decision_upper, str(jv.version))

    dup_result = await db.execute(
        select(AccountingJVApproval).where(
            AccountingJVApproval.jv_id == jv_id,
            AccountingJVApproval.tenant_id == tenant_id,
            AccountingJVApproval.request_fingerprint == fingerprint,
        )
    )
    if dup_result.scalar_one_or_none() is not None:
        raise ValidationError(
            "Duplicate approval decision detected (idempotency). This decision has already been recorded."
        )

    actor_level = ROLE_APPROVAL_LEVEL.get(normalized_role, 1)

    approval = AccountingJVApproval(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        chain_hash=None,
        previous_hash=None,
        jv_id=jv_id,
        jv_version=jv.version,
        acted_by=acted_by,
        delegated_from=delegated_from,
        actor_role=normalized_role,
        decision=decision_upper,
        decision_reason=decision_reason,
        approval_level=actor_level,
        amount_threshold=jv.total_debit,
        created_by_intent_id=mutation_context.intent_id,
        recorded_by_job_id=mutation_context.job_id,
        idempotency_key=idem_key,
        request_fingerprint=fingerprint,
        acted_at=_utcnow(),
    )
    db.add(approval)
    await db.flush()

    to_status = JVStatus.APPROVED if decision_upper == ApprovalDecision.APPROVED else JVStatus.REJECTED
    is_admin = normalized_role == "ACCOUNTING_ADMIN"

    await transition_jv(
        db,
        jv_id=jv_id,
        tenant_id=tenant_id,
        to_status=to_status,
        triggered_by=acted_by,
        actor_role=normalized_role,
        expected_version=expected_version,
        comment=decision_reason,
        is_admin=is_admin,
    )

    return approval


async def get_jv_approvals(
    db: AsyncSession,
    *,
    jv_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> list[AccountingJVApproval]:
    result = await db.execute(
        select(AccountingJVApproval)
        .where(
            AccountingJVApproval.jv_id == jv_id,
            AccountingJVApproval.tenant_id == tenant_id,
        )
        .order_by(AccountingJVApproval.acted_at.asc())
    )
    return list(result.scalars().all())


async def create_sla_timer(
    db: AsyncSession,
    *,
    jv_id: uuid.UUID,
    tenant_id: uuid.UUID,
    review_sla_hours: int = 24,
    approval_sla_hours: int = 48,
) -> ApprovalSLATimer:
    existing_result = await db.execute(select(ApprovalSLATimer).where(ApprovalSLATimer.jv_id == jv_id))
    existing = existing_result.scalar_one_or_none()
    if existing is not None:
        return existing

    timer = ApprovalSLATimer(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        jv_id=jv_id,
        review_sla_hours=review_sla_hours,
        approval_sla_hours=approval_sla_hours,
        review_breached=False,
        approval_breached=False,
        nudge_24h_sent=False,
        nudge_48h_sent=False,
        updated_at=_utcnow(),
    )
    db.add(timer)
    await db.flush()
    return timer


async def check_and_update_sla_breaches(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
) -> list[ApprovalSLATimer]:
    now = _utcnow()
    newly_breached: list[ApprovalSLATimer] = []

    result = await db.execute(
        select(ApprovalSLATimer, AccountingJVAggregate)
        .join(AccountingJVAggregate, AccountingJVAggregate.id == ApprovalSLATimer.jv_id)
        .where(
            ApprovalSLATimer.tenant_id == tenant_id,
            AccountingJVAggregate.tenant_id == tenant_id,
            AccountingJVAggregate.status.not_in(
                [JVStatus.PUSHED, JVStatus.VOIDED, JVStatus.APPROVED, JVStatus.REJECTED]
            ),
        )
    )

    for timer, jv in result.all():
        if jv.submitted_at is None:
            continue

        breached = False

        if not timer.review_breached:
            review_deadline = jv.submitted_at + timedelta(hours=timer.review_sla_hours)
            if now > review_deadline and jv.status in {
                JVStatus.PENDING_REVIEW,
                JVStatus.UNDER_REVIEW,
                JVStatus.RESUBMITTED,
                JVStatus.ESCALATED,
            }:
                timer.review_breached = True
                timer.review_breached_at = now
                breached = True

        if not timer.approval_breached:
            approval_deadline = jv.submitted_at + timedelta(hours=timer.approval_sla_hours)
            if now > approval_deadline:
                timer.approval_breached = True
                timer.approval_breached_at = now
                breached = True

        if breached:
            timer.updated_at = now
            newly_breached.append(timer)

    await db.flush()
    return newly_breached


async def get_sla_metrics(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID | None = None,
    fiscal_year: int | None = None,
    fiscal_period: int | None = None,
) -> dict[str, Any]:
    stmt = select(AccountingJVAggregate).where(AccountingJVAggregate.tenant_id == tenant_id)
    if entity_id is not None:
        stmt = stmt.where(AccountingJVAggregate.entity_id == entity_id)
    if fiscal_year is not None:
        stmt = stmt.where(AccountingJVAggregate.fiscal_year == fiscal_year)
    if fiscal_period is not None:
        stmt = stmt.where(AccountingJVAggregate.fiscal_period == fiscal_period)

    jvs_result = await db.execute(stmt)
    jvs = list(jvs_result.scalars().all())

    total = len(jvs)
    approved = sum(1 for item in jvs if item.status == JVStatus.APPROVED)
    rejected = sum(1 for item in jvs if item.status == JVStatus.REJECTED)
    pending = sum(
        1
        for item in jvs
        if item.status
        in {JVStatus.PENDING_REVIEW, JVStatus.UNDER_REVIEW, JVStatus.RESUBMITTED, JVStatus.ESCALATED}
    )

    review_durations: list[float] = []
    decision_durations: list[float] = []
    for item in jvs:
        if item.submitted_at and item.first_reviewed_at:
            review_durations.append((item.first_reviewed_at - item.submitted_at).total_seconds() / 3600)
        if item.submitted_at and item.decided_at:
            decision_durations.append((item.decided_at - item.submitted_at).total_seconds() / 3600)

    return {
        "total_jvs": total,
        "approved": approved,
        "rejected": rejected,
        "pending": pending,
        "avg_review_hours": (sum(review_durations) / len(review_durations)) if review_durations else None,
        "avg_decision_hours": (sum(decision_durations) / len(decision_durations)) if decision_durations else None,
    }
