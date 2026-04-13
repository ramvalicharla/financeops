from __future__ import annotations

from typing import Literal

from financeops.db.models.accounting_jv import JVStatus

JournalStatusLiteral = Literal[
    JVStatus.DRAFT,
    JVStatus.SUBMITTED,
    JVStatus.PENDING_REVIEW,
    JVStatus.UNDER_REVIEW,
    JVStatus.APPROVED,
    JVStatus.RESUBMITTED,
    JVStatus.REJECTED,
    JVStatus.PUSH_IN_PROGRESS,
    JVStatus.PUSHED,
    JVStatus.PUSH_FAILED,
    JVStatus.ESCALATED,
    JVStatus.VOIDED,
]

JOURNAL_STATUS_LABELS: dict[str, str] = {
    JVStatus.DRAFT: "Draft",
    JVStatus.SUBMITTED: "Submitted",
    JVStatus.PENDING_REVIEW: "Pending review",
    JVStatus.UNDER_REVIEW: "Under review",
    JVStatus.APPROVED: "Approved",
    JVStatus.RESUBMITTED: "Resubmitted",
    JVStatus.REJECTED: "Rejected",
    JVStatus.PUSH_IN_PROGRESS: "Posting",
    JVStatus.PUSHED: "Posted",
    JVStatus.PUSH_FAILED: "Post failed",
    JVStatus.ESCALATED: "Escalated",
    JVStatus.VOIDED: "Voided",
}

__all__ = ["JOURNAL_STATUS_LABELS", "JournalStatusLiteral"]
