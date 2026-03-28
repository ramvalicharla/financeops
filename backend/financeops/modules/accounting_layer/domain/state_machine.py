from __future__ import annotations

from dataclasses import dataclass

from financeops.core.exceptions import ValidationError
from financeops.db.models.accounting_jv import JVStatus


ALLOWED_TRANSITIONS: frozenset[tuple[str, str]] = frozenset(
    {
        (JVStatus.DRAFT, JVStatus.SUBMITTED),
        (JVStatus.SUBMITTED, JVStatus.PENDING_REVIEW),
        (JVStatus.PENDING_REVIEW, JVStatus.UNDER_REVIEW),
        (JVStatus.UNDER_REVIEW, JVStatus.APPROVED),
        (JVStatus.APPROVED, JVStatus.PUSH_IN_PROGRESS),
        (JVStatus.PUSH_IN_PROGRESS, JVStatus.PUSHED),
        (JVStatus.PUSH_IN_PROGRESS, JVStatus.PUSH_FAILED),
        (JVStatus.PUSH_FAILED, JVStatus.PUSH_IN_PROGRESS),
        (JVStatus.PENDING_REVIEW, JVStatus.REJECTED),
        (JVStatus.UNDER_REVIEW, JVStatus.REJECTED),
        (JVStatus.RESUBMITTED, JVStatus.REJECTED),
        (JVStatus.ESCALATED, JVStatus.REJECTED),
        (JVStatus.REJECTED, JVStatus.RESUBMITTED),
        (JVStatus.RESUBMITTED, JVStatus.PENDING_REVIEW),
        (JVStatus.RESUBMITTED, JVStatus.ESCALATED),
        (JVStatus.ESCALATED, JVStatus.UNDER_REVIEW),
        (JVStatus.DRAFT, JVStatus.VOIDED),
        (JVStatus.SUBMITTED, JVStatus.VOIDED),
        (JVStatus.PENDING_REVIEW, JVStatus.VOIDED),
        (JVStatus.UNDER_REVIEW, JVStatus.VOIDED),
        (JVStatus.APPROVED, JVStatus.VOIDED),
        (JVStatus.PUSH_FAILED, JVStatus.VOIDED),
        (JVStatus.REJECTED, JVStatus.VOIDED),
        (JVStatus.RESUBMITTED, JVStatus.VOIDED),
        (JVStatus.ESCALATED, JVStatus.VOIDED),
    }
)

MAX_RESUBMISSIONS = 3


@dataclass(frozen=True)
class TransitionRequest:
    from_status: str
    to_status: str
    triggered_by_role: str
    is_admin: bool = False
    comment: str | None = None
    resubmission_count: int = 0


@dataclass(frozen=True)
class TransitionResult:
    allowed: bool
    reason: str | None = None


def validate_transition(req: TransitionRequest) -> None:
    pair = (req.from_status, req.to_status)

    if req.from_status in JVStatus.TERMINAL_STATES:
        raise ValidationError(
            f"JV is in terminal state '{req.from_status}' and cannot transition further."
        )

    if pair not in ALLOWED_TRANSITIONS:
        raise ValidationError(
            f"Transition '{req.from_status}' -> '{req.to_status}' is not allowed. "
            f"Valid next states: {_valid_next_states(req.from_status)}"
        )

    if req.to_status == JVStatus.VOIDED and not req.is_admin:
        raise ValidationError("Only Accounting Admin can void a JV.")

    if req.to_status == JVStatus.REJECTED and not req.comment:
        raise ValidationError("A comment is required when rejecting a JV.")

    if req.to_status == JVStatus.VOIDED and not req.comment:
        raise ValidationError("A void reason is required when voiding a JV.")

    if req.to_status == JVStatus.RESUBMITTED and req.resubmission_count >= MAX_RESUBMISSIONS:
        raise ValidationError(
            f"JV reached max resubmissions ({MAX_RESUBMISSIONS}); escalate to CFO approver."
        )


def next_status_after_resubmit(resubmission_count: int) -> str:
    if resubmission_count >= MAX_RESUBMISSIONS:
        return JVStatus.ESCALATED
    return JVStatus.RESUBMITTED


def _valid_next_states(from_status: str) -> list[str]:
    return sorted(to for frm, to in ALLOWED_TRANSITIONS if frm == from_status)
