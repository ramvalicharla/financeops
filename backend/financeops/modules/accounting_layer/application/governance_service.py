from __future__ import annotations

import calendar
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import AuthorizationError, NotFoundError, ValidationError
from financeops.db.models.accounting_governance import (
    AccountingGovernanceAuditEvent,
    AccountingPeriod,
    AccountingPeriodStatus,
    ApprovalPolicy,
    CloseChecklist,
    CloseChecklistStatus,
)
from financeops.db.models.accounting_jv import JVStatus
from financeops.db.models.consolidation import ConsolidationRun
from financeops.db.models.fx_ias21 import AccountingFxRevaluationRun, ConsolidationTranslationRun
from financeops.db.models.reconciliation import GlEntry
from financeops.db.models.users import UserRole
from financeops.modules.coa.models import TenantCoaAccount
from financeops.modules.org_setup.models import OrgEntity
from financeops.services.audit_writer import AuditWriter

_SOFT_LOCK = AccountingPeriodStatus.SOFT_CLOSED
_HARD_LOCK = AccountingPeriodStatus.HARD_CLOSED
_BLOCKING_JOURNAL_STATES = {
    JVStatus.DRAFT,
    JVStatus.SUBMITTED,
    JVStatus.PENDING_REVIEW,
    JVStatus.UNDER_REVIEW,
    JVStatus.RESUBMITTED,
    JVStatus.ESCALATED,
    JVStatus.APPROVED,
}


@dataclass(frozen=True)
class EffectivePeriodLock:
    status: str
    period_id: uuid.UUID | None
    reason: str | None
    locked_at: datetime | None
    locked_by: uuid.UUID | None
    org_entity_id: uuid.UUID | None

    @property
    def is_hard_closed(self) -> bool:
        return self.status == _HARD_LOCK

    @property
    def is_soft_closed(self) -> bool:
        return self.status == _SOFT_LOCK


@dataclass(frozen=True)
class ApprovalPolicyConfig:
    require_reviewer: bool
    require_distinct_approver: bool
    require_distinct_poster: bool


def _period_range(fiscal_year: int, period_number: int) -> tuple[date, date]:
    if period_number < 1 or period_number > 12:
        raise ValidationError("period_number must be between 1 and 12.")
    start = date(fiscal_year, period_number, 1)
    end = date(fiscal_year, period_number, calendar.monthrange(fiscal_year, period_number)[1])
    return start, end


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)


def _normalize_lock_type(value: str) -> str:
    normalized = (value or "").strip().upper()
    if normalized not in {_SOFT_LOCK, _HARD_LOCK}:
        raise ValidationError("lock_type must be SOFT_CLOSED or HARD_CLOSED.")
    return normalized


async def _append_audit_event(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID | None,
    actor_user_id: uuid.UUID,
    module: str,
    action: str,
    target_id: str,
    payload: dict[str, Any],
) -> None:
    await AuditWriter.insert_financial_record(
        db,
        model_class=AccountingGovernanceAuditEvent,
        tenant_id=tenant_id,
        record_data={
            "module": module,
            "action": action,
            "target_id": target_id,
            "actor_user_id": str(actor_user_id),
        },
        values={
            "id": uuid.uuid4(),
            "entity_id": entity_id,
            "module": module,
            "action": action,
            "actor_user_id": actor_user_id,
            "target_id": target_id,
            "payload_json": payload,
        },
    )


async def record_governance_event(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID | None,
    actor_user_id: uuid.UUID,
    module: str,
    action: str,
    target_id: str,
    payload: dict[str, Any],
) -> None:
    await _append_audit_event(
        db,
        tenant_id=tenant_id,
        entity_id=entity_id,
        actor_user_id=actor_user_id,
        module=module,
        action=action,
        target_id=target_id,
        payload=payload,
    )


async def get_or_create_accounting_period(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    org_entity_id: uuid.UUID | None,
    fiscal_year: int,
    period_number: int,
) -> AccountingPeriod:
    stmt = select(AccountingPeriod).where(
        AccountingPeriod.tenant_id == tenant_id,
        AccountingPeriod.org_entity_id == org_entity_id,
        AccountingPeriod.fiscal_year == fiscal_year,
        AccountingPeriod.period_number == period_number,
    )
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is not None:
        return row

    period_start, period_end = _period_range(fiscal_year, period_number)
    row = AccountingPeriod(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        org_entity_id=org_entity_id,
        fiscal_year=fiscal_year,
        period_number=period_number,
        period_start=period_start,
        period_end=period_end,
        status=AccountingPeriodStatus.OPEN,
    )
    db.add(row)
    await db.flush()
    return row


async def resolve_effective_period_lock(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    org_entity_id: uuid.UUID | None,
    fiscal_year: int,
    period_number: int,
) -> EffectivePeriodLock:
    base_filters = [
        AccountingPeriod.tenant_id == tenant_id,
        AccountingPeriod.fiscal_year == fiscal_year,
        AccountingPeriod.period_number == period_number,
    ]
    if org_entity_id is None:
        filters = [*base_filters, AccountingPeriod.org_entity_id.is_(None)]
    else:
        filters = [
            *base_filters,
            or_(
                AccountingPeriod.org_entity_id == org_entity_id,
                AccountingPeriod.org_entity_id.is_(None),
            ),
        ]

    rows = (
        await db.execute(
            select(AccountingPeriod).where(*filters).order_by(AccountingPeriod.org_entity_id.is_(None))
        )
    ).scalars().all()
    if not rows:
        return EffectivePeriodLock(
            status=AccountingPeriodStatus.OPEN,
            period_id=None,
            reason=None,
            locked_at=None,
            locked_by=None,
            org_entity_id=org_entity_id,
        )

    # Hard close wins over soft close. Entity-specific wins over global for same status.
    ordered = sorted(
        rows,
        key=lambda item: (
            0 if item.status == _HARD_LOCK else 1 if item.status == _SOFT_LOCK else 2,
            0 if item.org_entity_id is not None else 1,
        ),
    )
    chosen = ordered[0]
    return EffectivePeriodLock(
        status=chosen.status,
        period_id=chosen.id,
        reason=chosen.notes,
        locked_at=chosen.locked_at,
        locked_by=chosen.locked_by,
        org_entity_id=chosen.org_entity_id,
    )


def _allow_soft_close_override(actor_role: str | None) -> bool:
    if actor_role is None:
        return False
    normalized = actor_role.strip().lower()
    return normalized in {
        UserRole.super_admin.value,
        UserRole.finance_leader.value,
        UserRole.platform_owner.value,
        UserRole.platform_admin.value,
    }


async def assert_period_allows_modification(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    org_entity_id: uuid.UUID | None,
    fiscal_year: int,
    period_number: int,
) -> None:
    lock_state = await resolve_effective_period_lock(
        db,
        tenant_id=tenant_id,
        org_entity_id=org_entity_id,
        fiscal_year=fiscal_year,
        period_number=period_number,
    )
    if lock_state.is_hard_closed:
        raise ValidationError("Period is HARD_CLOSED. No modifications are allowed.")


async def assert_period_allows_posting(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    org_entity_id: uuid.UUID | None,
    fiscal_year: int,
    period_number: int,
    actor_role: str | None,
) -> None:
    lock_state = await resolve_effective_period_lock(
        db,
        tenant_id=tenant_id,
        org_entity_id=org_entity_id,
        fiscal_year=fiscal_year,
        period_number=period_number,
    )
    if lock_state.is_hard_closed:
        raise ValidationError("Period is HARD_CLOSED. Posting is blocked.")
    if lock_state.is_soft_closed and not _allow_soft_close_override(actor_role):
        raise ValidationError("Period is SOFT_CLOSED. Posting requires admin override.")


async def assert_period_allows_revaluation(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    org_entity_id: uuid.UUID,
    as_of_date: date,
    actor_role: str | None,
) -> None:
    await assert_period_allows_posting(
        db,
        tenant_id=tenant_id,
        org_entity_id=org_entity_id,
        fiscal_year=as_of_date.year,
        period_number=as_of_date.month,
        actor_role=actor_role,
    )


async def assert_group_period_not_hard_closed(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    org_group_id: uuid.UUID,
    as_of_date: date,
) -> None:
    rows = (
        await db.execute(
            select(OrgEntity.cp_entity_id).where(
                OrgEntity.tenant_id == tenant_id,
                OrgEntity.org_group_id == org_group_id,
                OrgEntity.is_active.is_(True),
                OrgEntity.cp_entity_id.is_not(None),
            )
        )
    ).scalars().all()
    entity_ids = [uuid.UUID(str(item)) for item in rows]

    lock_stmt = select(AccountingPeriod.id).where(
        AccountingPeriod.tenant_id == tenant_id,
        AccountingPeriod.fiscal_year == as_of_date.year,
        AccountingPeriod.period_number == as_of_date.month,
        AccountingPeriod.status == _HARD_LOCK,
    )
    if entity_ids:
        lock_stmt = lock_stmt.where(
            or_(
                AccountingPeriod.org_entity_id.is_(None),
                AccountingPeriod.org_entity_id.in_(entity_ids),
            )
        )
    else:
        lock_stmt = lock_stmt.where(AccountingPeriod.org_entity_id.is_(None))

    locked = (await db.execute(lock_stmt.limit(1))).scalar_one_or_none()
    if locked is not None:
        raise ValidationError("Period is HARD_CLOSED. Consolidation rerun is blocked.")


async def lock_period(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    org_entity_id: uuid.UUID | None,
    fiscal_year: int,
    period_number: int,
    lock_type: str,
    reason: str | None,
    actor_user_id: uuid.UUID,
) -> dict[str, Any]:
    normalized_lock = _normalize_lock_type(lock_type)
    period = await get_or_create_accounting_period(
        db,
        tenant_id=tenant_id,
        org_entity_id=org_entity_id,
        fiscal_year=fiscal_year,
        period_number=period_number,
    )
    now = _utcnow()
    period.status = normalized_lock
    period.locked_by = actor_user_id
    period.locked_at = now
    period.notes = reason
    period.updated_at = now

    await _append_audit_event(
        db,
        tenant_id=tenant_id,
        entity_id=org_entity_id,
        actor_user_id=actor_user_id,
        module="period_close",
        action="period_lock",
        target_id=str(period.id),
        payload={
            "org_entity_id": str(org_entity_id) if org_entity_id else None,
            "fiscal_year": fiscal_year,
            "period_number": period_number,
            "lock_type": normalized_lock,
            "reason": reason,
        },
    )
    await db.flush()
    return {
        "period_id": str(period.id),
        "status": period.status,
        "org_entity_id": str(period.org_entity_id) if period.org_entity_id else None,
        "fiscal_year": period.fiscal_year,
        "period_number": period.period_number,
        "locked_by": str(period.locked_by) if period.locked_by else None,
        "locked_at": period.locked_at.isoformat() if period.locked_at else None,
        "reason": period.notes,
    }


def ensure_unlock_role(role: UserRole) -> None:
    allowed = {
        UserRole.platform_owner,
        UserRole.platform_admin,
        UserRole.super_admin,
        UserRole.finance_leader,
    }
    if role not in allowed:
        raise AuthorizationError("Only platform/admin approvers can unlock a closed period.")


async def unlock_period(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    org_entity_id: uuid.UUID | None,
    fiscal_year: int,
    period_number: int,
    reason: str,
    actor_user_id: uuid.UUID,
) -> dict[str, Any]:
    if not reason.strip():
        raise ValidationError("Unlock reason is required.")
    period = await get_or_create_accounting_period(
        db,
        tenant_id=tenant_id,
        org_entity_id=org_entity_id,
        fiscal_year=fiscal_year,
        period_number=period_number,
    )
    now = _utcnow()
    period.status = AccountingPeriodStatus.REOPENED
    period.reopened_by = actor_user_id
    period.reopened_at = now
    period.notes = reason
    period.updated_at = now

    await _append_audit_event(
        db,
        tenant_id=tenant_id,
        entity_id=org_entity_id,
        actor_user_id=actor_user_id,
        module="period_close",
        action="period_unlock",
        target_id=str(period.id),
        payload={
            "org_entity_id": str(org_entity_id) if org_entity_id else None,
            "fiscal_year": fiscal_year,
            "period_number": period_number,
            "reason": reason,
        },
    )
    await db.flush()
    return {
        "period_id": str(period.id),
        "status": period.status,
        "org_entity_id": str(period.org_entity_id) if period.org_entity_id else None,
        "fiscal_year": period.fiscal_year,
        "period_number": period.period_number,
        "reopened_by": str(period.reopened_by) if period.reopened_by else None,
        "reopened_at": period.reopened_at.isoformat() if period.reopened_at else None,
        "reason": period.notes,
    }


async def get_period_status(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    org_entity_id: uuid.UUID | None,
    fiscal_year: int,
    period_number: int,
) -> dict[str, Any]:
    lock_state = await resolve_effective_period_lock(
        db,
        tenant_id=tenant_id,
        org_entity_id=org_entity_id,
        fiscal_year=fiscal_year,
        period_number=period_number,
    )
    period_start, period_end = _period_range(fiscal_year, period_number)
    return {
        "period_id": str(lock_state.period_id) if lock_state.period_id else None,
        "org_entity_id": str(org_entity_id) if org_entity_id else None,
        "fiscal_year": fiscal_year,
        "period_number": period_number,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "status": lock_state.status,
        "reason": lock_state.reason,
        "locked_at": lock_state.locked_at.isoformat() if lock_state.locked_at else None,
        "locked_by": str(lock_state.locked_by) if lock_state.locked_by else None,
    }


async def get_approval_policy(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    module_name: str = "ACCOUNTING_JOURNALS",
) -> ApprovalPolicyConfig:
    row = (
        await db.execute(
            select(ApprovalPolicy).where(
                ApprovalPolicy.tenant_id == tenant_id,
                ApprovalPolicy.module_name == module_name,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        return ApprovalPolicyConfig(
            require_reviewer=True,
            require_distinct_approver=True,
            require_distinct_poster=False,
        )
    return ApprovalPolicyConfig(
        require_reviewer=bool(row.require_reviewer),
        require_distinct_approver=bool(row.require_distinct_approver),
        require_distinct_poster=bool(row.require_distinct_poster),
    )


def enforce_maker_checker_for_approval(
    *,
    created_by: uuid.UUID,
    approved_by: uuid.UUID,
    policy: ApprovalPolicyConfig,
) -> None:
    if created_by == approved_by:
        raise ValidationError("Maker-checker violation: maker cannot approve own journal.")
    if policy.require_distinct_approver and created_by == approved_by:
        raise ValidationError("Policy violation: approver must be distinct from maker.")


def enforce_reviewer_policy(
    *,
    has_review_marker: bool,
    policy: ApprovalPolicyConfig,
) -> None:
    if policy.require_reviewer and not has_review_marker:
        raise ValidationError("Journal must be reviewed before approval.")


def enforce_distinct_poster_policy(
    *,
    reviewed_by: uuid.UUID | None,
    posted_by: uuid.UUID,
    policy: ApprovalPolicyConfig,
) -> None:
    if policy.require_distinct_poster and reviewed_by is not None and reviewed_by == posted_by:
        raise ValidationError("Policy violation: reviewer and poster must be distinct users.")


def _period_window_dates(fiscal_year: int, period_number: int) -> tuple[date, date]:
    start, end = _period_range(fiscal_year, period_number)
    return start, end


async def _readiness_data(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    org_entity_id: uuid.UUID,
    fiscal_year: int,
    period_number: int,
) -> dict[str, Any]:
    period_start, period_end = _period_window_dates(fiscal_year, period_number)

    from financeops.db.models.accounting_jv import AccountingJVAggregate, AccountingJVLine

    pending_count = int(
        (
            await db.execute(
                select(func.count()).where(
                    AccountingJVAggregate.tenant_id == tenant_id,
                    AccountingJVAggregate.entity_id == org_entity_id,
                    AccountingJVAggregate.fiscal_year == fiscal_year,
                    AccountingJVAggregate.fiscal_period == period_number,
                    AccountingJVAggregate.status.in_(_BLOCKING_JOURNAL_STATES),
                )
            )
        ).scalar_one()
        or 0
    )

    tb_totals = (
        await db.execute(
            select(
                func.coalesce(func.sum(GlEntry.debit_amount), Decimal("0")),
                func.coalesce(func.sum(GlEntry.credit_amount), Decimal("0")),
            ).where(
                GlEntry.tenant_id == tenant_id,
                GlEntry.entity_id == org_entity_id,
                GlEntry.period_year == fiscal_year,
                GlEntry.period_month == period_number,
            )
        )
    ).one()
    total_debit = Decimal(str(tb_totals[0] or "0"))
    total_credit = Decimal(str(tb_totals[1] or "0"))

    fx_entities_exist = bool(
        (
            await db.execute(
                select(func.count()).select_from(AccountingJVLine).where(
                    AccountingJVLine.tenant_id == tenant_id,
                    AccountingJVLine.entity_id == org_entity_id,
                    AccountingJVLine.transaction_currency.is_not(None),
                    AccountingJVLine.functional_currency.is_not(None),
                    AccountingJVLine.transaction_currency != AccountingJVLine.functional_currency,
                )
            )
        ).scalar_one()
        or 0
    )

    revaluation_done = bool(
        (
            await db.execute(
                select(AccountingFxRevaluationRun.id).where(
                    AccountingFxRevaluationRun.tenant_id == tenant_id,
                    AccountingFxRevaluationRun.entity_id == org_entity_id,
                    AccountingFxRevaluationRun.as_of_date >= period_start,
                    AccountingFxRevaluationRun.as_of_date <= period_end,
                    AccountingFxRevaluationRun.status.in_(["COMPLETED", "COMPLETED_NO_ADJUSTMENT"]),
                )
            )
        ).scalar_one_or_none()
        is not None
    )

    group_row = (
        await db.execute(
            select(OrgEntity.org_group_id).where(
                OrgEntity.tenant_id == tenant_id,
                OrgEntity.cp_entity_id == org_entity_id,
                OrgEntity.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    group_exists = group_row is not None
    group_entity_count = 0
    if group_exists:
        group_entity_count = int(
            (
                await db.execute(
                    select(func.count()).select_from(OrgEntity).where(
                        OrgEntity.tenant_id == tenant_id,
                        OrgEntity.org_group_id == group_row,
                        OrgEntity.is_active.is_(True),
                    )
                )
            ).scalar_one()
            or 0
        )

    consolidation_done = True
    if group_exists and group_entity_count > 1:
        consolidation_done = bool(
            (
                await db.execute(
                    select(ConsolidationRun.id).where(
                        ConsolidationRun.tenant_id == tenant_id,
                        ConsolidationRun.period_year == fiscal_year,
                        ConsolidationRun.period_month == period_number,
                        ConsolidationRun.status == "SUCCESS",
                    )
                )
            ).scalar_one_or_none()
            is not None
        )

    translation_done = True
    if fx_entities_exist and group_exists:
        translation_done = bool(
            (
                await db.execute(
                    select(ConsolidationTranslationRun.id).where(
                        ConsolidationTranslationRun.tenant_id == tenant_id,
                        ConsolidationTranslationRun.as_of_date >= period_start,
                        ConsolidationTranslationRun.as_of_date <= period_end,
                        ConsolidationTranslationRun.status.in_(["COMPLETED", "SUCCESS"]),
                    )
                )
            ).scalar_one_or_none()
            is not None
        )

    coa_present = bool(
        (
            await db.execute(
                select(func.count()).select_from(TenantCoaAccount).where(
                    TenantCoaAccount.tenant_id == tenant_id,
                    TenantCoaAccount.is_active.is_(True),
                )
            )
        ).scalar_one()
        or 0
    )

    return {
        "pending_count": pending_count,
        "total_debit": total_debit,
        "total_credit": total_credit,
        "fx_entities_exist": fx_entities_exist,
        "revaluation_done": revaluation_done,
        "translation_done": translation_done,
        "group_exists": group_exists and group_entity_count > 1,
        "consolidation_done": consolidation_done,
        "coa_present": coa_present,
    }


async def run_close_readiness(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    org_entity_id: uuid.UUID,
    fiscal_year: int,
    period_number: int,
) -> dict[str, Any]:
    data = await _readiness_data(
        db,
        tenant_id=tenant_id,
        org_entity_id=org_entity_id,
        fiscal_year=fiscal_year,
        period_number=period_number,
    )

    blockers: list[str] = []
    warnings: list[str] = []

    if data["pending_count"] > 0:
        blockers.append("Unposted or unapproved journals exist for the period.")
    if data["total_debit"] != data["total_credit"]:
        blockers.append("Trial balance is not balanced for the selected period.")
    if data["fx_entities_exist"] and not data["revaluation_done"]:
        blockers.append("FX revaluation is pending for the selected period.")
    if data["fx_entities_exist"] and data["group_exists"] and not data["translation_done"]:
        blockers.append("FX translation is pending for group reporting.")
    if data["group_exists"] and not data["consolidation_done"]:
        blockers.append("Consolidation run is pending for the group period close.")
    if not data["coa_present"]:
        blockers.append("Chart of Accounts is missing for tenant/entity scope.")

    warnings.append("Financial statements are generated on-demand; ensure reports are exported.")

    return {
        "pass": len(blockers) == 0,
        "blockers": blockers,
        "warnings": warnings,
        "metrics": {
            "pending_journals": data["pending_count"],
            "trial_balance_total_debit": str(data["total_debit"]),
            "trial_balance_total_credit": str(data["total_credit"]),
            "fx_entities_exist": data["fx_entities_exist"],
            "revaluation_done": data["revaluation_done"],
            "translation_done": data["translation_done"],
            "group_exists": data["group_exists"],
            "consolidation_done": data["consolidation_done"],
            "coa_present": data["coa_present"],
        },
    }


_CHECKLIST_ITEMS: tuple[str, ...] = (
    "all_journals_posted",
    "no_pending_journals",
    "trial_balance_balanced",
    "revaluation_completed",
    "translation_completed",
    "consolidation_completed",
    "financial_statements_generated",
    "coa_present",
    "no_unmapped_required_accounts",
)


async def get_close_checklist(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    org_entity_id: uuid.UUID,
    fiscal_year: int,
    period_number: int,
) -> dict[str, Any]:
    period = await get_or_create_accounting_period(
        db,
        tenant_id=tenant_id,
        org_entity_id=org_entity_id,
        fiscal_year=fiscal_year,
        period_number=period_number,
    )
    readiness = await run_close_readiness(
        db,
        tenant_id=tenant_id,
        org_entity_id=org_entity_id,
        fiscal_year=fiscal_year,
        period_number=period_number,
    )

    rows = (
        await db.execute(
            select(CloseChecklist).where(
                CloseChecklist.tenant_id == tenant_id,
                CloseChecklist.org_entity_id == org_entity_id,
                CloseChecklist.period_id == period.id,
            )
        )
    ).scalars().all()
    latest_by_type: dict[str, CloseChecklist] = {}
    for row in rows:
        latest_by_type[row.checklist_type] = row

    blockers_text = " ".join(readiness["blockers"]).lower()
    metrics = readiness["metrics"]
    items: list[dict[str, Any]] = []
    for item in _CHECKLIST_ITEMS:
        existing = latest_by_type.get(item)
        status = existing.checklist_status if existing is not None else CloseChecklistStatus.PENDING
        if item == "all_journals_posted" and metrics["pending_journals"] == 0:
            status = CloseChecklistStatus.COMPLETED
        if item == "no_pending_journals" and metrics["pending_journals"] == 0:
            status = CloseChecklistStatus.COMPLETED
        if item == "trial_balance_balanced" and (
            metrics["trial_balance_total_debit"] == metrics["trial_balance_total_credit"]
        ):
            status = CloseChecklistStatus.COMPLETED
        if item == "revaluation_completed" and (
            not metrics["fx_entities_exist"] or metrics["revaluation_done"]
        ):
            status = CloseChecklistStatus.COMPLETED
        if item == "translation_completed" and (
            not metrics["group_exists"] or not metrics["fx_entities_exist"] or metrics["translation_done"]
        ):
            status = CloseChecklistStatus.COMPLETED
        if item == "consolidation_completed" and (
            not metrics["group_exists"] or metrics["consolidation_done"]
        ):
            status = CloseChecklistStatus.COMPLETED
        if item == "financial_statements_generated":
            status = CloseChecklistStatus.COMPLETED if readiness["pass"] else status
        if item == "coa_present" and metrics["coa_present"]:
            status = CloseChecklistStatus.COMPLETED
        if item == "no_unmapped_required_accounts":
            status = CloseChecklistStatus.COMPLETED

        if status == CloseChecklistStatus.PENDING and item.replace("_", " ") in blockers_text:
            status = CloseChecklistStatus.FAILED
        items.append(
            {
                "checklist_type": item,
                "checklist_status": status,
                "completed_by": str(existing.completed_by) if existing and existing.completed_by else None,
                "completed_at": existing.completed_at.isoformat() if existing and existing.completed_at else None,
                "evidence_json": existing.evidence_json if existing else None,
            }
        )

    return {
        "period_id": str(period.id),
        "fiscal_year": fiscal_year,
        "period_number": period_number,
        "org_entity_id": str(org_entity_id),
        "items": items,
        "readiness": readiness,
    }


async def complete_checklist_item(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    org_entity_id: uuid.UUID,
    fiscal_year: int,
    period_number: int,
    checklist_type: str,
    evidence_json: dict[str, Any] | None,
    actor_user_id: uuid.UUID,
) -> dict[str, Any]:
    if checklist_type not in _CHECKLIST_ITEMS:
        raise ValidationError("Unknown checklist_type.")
    period = await get_or_create_accounting_period(
        db,
        tenant_id=tenant_id,
        org_entity_id=org_entity_id,
        fiscal_year=fiscal_year,
        period_number=period_number,
    )
    now = _utcnow()
    row = CloseChecklist(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        org_entity_id=org_entity_id,
        period_id=period.id,
        checklist_type=checklist_type,
        checklist_status=CloseChecklistStatus.COMPLETED,
        evidence_json=evidence_json,
        completed_by=actor_user_id,
        completed_at=now,
    )
    db.add(row)
    await _append_audit_event(
        db,
        tenant_id=tenant_id,
        entity_id=org_entity_id,
        actor_user_id=actor_user_id,
        module="period_close",
        action="checklist_complete",
        target_id=str(row.id),
        payload={
            "period_id": str(period.id),
            "fiscal_year": fiscal_year,
            "period_number": period_number,
            "checklist_type": checklist_type,
            "evidence_json": evidence_json or {},
        },
    )
    await db.flush()
    return {
        "checklist_id": str(row.id),
        "checklist_type": row.checklist_type,
        "checklist_status": row.checklist_status,
        "completed_by": str(row.completed_by) if row.completed_by else None,
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
    }


async def get_period_or_raise(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    period_id: uuid.UUID,
) -> AccountingPeriod:
    row = (
        await db.execute(
            select(AccountingPeriod).where(
                AccountingPeriod.id == period_id,
                AccountingPeriod.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError("Accounting period not found.")
    return row
