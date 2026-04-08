from __future__ import annotations

import hashlib
import logging
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from financeops.core.exceptions import NotFoundError, ValidationError
from financeops.core.intent.context import require_mutation_context
from financeops.db.models.accounting_jv import (
    AccountingJVAggregate,
    AccountingJVLine,
    AccountingJVStateEvent,
    EntryType,
    JVStatus,
)
from financeops.db.models.reconciliation import GlEntry
from financeops.modules.accounting_layer.application.jv_service import create_jv
from financeops.modules.accounting_layer.application.governance_service import (
    assert_period_allows_modification,
    assert_period_allows_posting,
    enforce_distinct_poster_policy,
    enforce_maker_checker_for_approval,
    enforce_reviewer_policy,
    get_approval_policy,
    record_governance_event,
)
from financeops.modules.accounting_layer.domain.schemas import (
    JournalActionResponse,
    JournalCreate,
    JournalLineResponse,
    JournalResponse,
)
from financeops.modules.coa.models import TenantCoaAccount
from financeops.platform.db.models.entities import CpEntity
from financeops.services.fx.rate_master_service import get_required_latest_fx_rate

logger = logging.getLogger(__name__)

REVIEW_SOURCE_STATUSES: frozenset[str] = frozenset(
    {
        JVStatus.PENDING_REVIEW,
        JVStatus.UNDER_REVIEW,
        JVStatus.RESUBMITTED,
        JVStatus.ESCALATED,
    }
)


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def _compute_hash(content: str, previous_hash: str | None) -> str:
    payload = f"{previous_hash or ''}:{content}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class _PreparedJournalLine:
    line_number: int
    account_id: uuid.UUID
    account_code: str
    account_name: str
    entry_type: str
    amount: Decimal
    transaction_currency: str
    functional_currency: str
    fx_rate: Decimal | None
    base_amount: Decimal
    memo: str | None


async def create_journal_draft(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    created_by: uuid.UUID,
    payload: JournalCreate,
    source: str = "MANUAL",
    external_reference_id: str | None = None,
) -> JournalResponse:
    require_mutation_context("Journal draft creation")
    entity = await _get_entity_for_tenant(
        db,
        tenant_id=tenant_id,
        entity_id=payload.org_entity_id,
    )
    await assert_period_allows_modification(
        db,
        tenant_id=tenant_id,
        org_entity_id=entity.id,
        fiscal_year=payload.journal_date.year,
        period_number=payload.journal_date.month,
    )
    prepared_lines = await _prepare_lines(
        db,
        tenant_id=tenant_id,
        payload=payload,
        entity=entity,
    )
    base_total_debit = sum(
        line.base_amount for line in prepared_lines if line.entry_type == EntryType.DEBIT
    )
    base_total_credit = sum(
        line.base_amount for line in prepared_lines if line.entry_type == EntryType.CREDIT
    )
    if base_total_debit != base_total_credit:
        raise ValidationError(
            f"Functional-currency imbalance detected: debit={base_total_debit}, credit={base_total_credit}."
        )

    jv_lines = [
        {
            "account_code": line.account_code,
            "account_name": line.account_name,
            "entry_type": line.entry_type,
            "amount": line.amount,
            "currency": line.transaction_currency,
            "transaction_currency": line.transaction_currency,
            "functional_currency": line.functional_currency,
            "fx_rate": line.fx_rate,
            "base_amount": line.base_amount,
            "amount_inr": line.base_amount if line.functional_currency == "INR" else None,
            "entity_id": entity.id,
            "narration": line.memo,
        }
        for line in prepared_lines
    ]
    jv = await create_jv(
        db,
        tenant_id=tenant_id,
        entity_id=entity.id,
        created_by=created_by,
        period_date=payload.journal_date,
        fiscal_year=payload.journal_date.year,
        fiscal_period=payload.journal_date.month,
        description=payload.narration,
        reference=payload.reference,
        source=source,
        external_reference_id=external_reference_id,
        currency=entity.base_currency,
        lines=jv_lines,
    )
    await db.flush()
    logger.info(
        "Journal draft created",
        extra={
            "tenant_id": str(tenant_id),
            "journal_id": str(jv.id),
            "journal_number": jv.jv_number,
        },
    )
    await record_governance_event(
        db,
        tenant_id=tenant_id,
        entity_id=entity.id,
        actor_user_id=created_by,
        module="journal_workflow",
        action="journal_draft_create",
        target_id=str(jv.id),
        payload={
            "journal_id": str(jv.id),
            "journal_number": jv.jv_number,
            "fiscal_year": jv.fiscal_year,
            "fiscal_period": jv.fiscal_period,
        },
    )
    return await get_journal(db, tenant_id=tenant_id, journal_id=jv.id)


async def approve_journal(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    journal_id: uuid.UUID,
    acted_by: uuid.UUID,
    actor_role: str | None = None,
) -> JournalActionResponse:
    require_mutation_context("Journal approval")
    jv = await _get_journal_aggregate(
        db,
        tenant_id=tenant_id,
        journal_id=journal_id,
    )
    await assert_period_allows_modification(
        db,
        tenant_id=tenant_id,
        org_entity_id=jv.entity_id,
        fiscal_year=jv.fiscal_year,
        period_number=jv.fiscal_period,
    )
    if _is_posted_status(jv.status):
        raise ValidationError("Posted journals cannot be re-approved.")
    if jv.status == JVStatus.APPROVED:
        return JournalActionResponse(id=jv.id, status="APPROVED", posted_at=None)
    if jv.status not in {JVStatus.SUBMITTED, *REVIEW_SOURCE_STATUSES}:
        raise ValidationError(f"Journal cannot be approved from status '{jv.status}'.")

    policy = await get_approval_policy(db, tenant_id=tenant_id)
    enforce_maker_checker_for_approval(
        created_by=jv.created_by,
        approved_by=acted_by,
        policy=policy,
    )
    enforce_reviewer_policy(
        has_review_marker=jv.first_reviewed_at is not None or jv.status in REVIEW_SOURCE_STATUSES,
        policy=policy,
    )

    from_status = jv.status
    now = _utcnow()
    jv.status = JVStatus.APPROVED
    jv.submitted_at = jv.submitted_at or now
    jv.first_reviewed_at = jv.first_reviewed_at or now
    jv.decided_at = now
    jv.updated_at = now

    await _append_state_event(
        db,
        jv=jv,
        from_status=from_status,
        to_status=JVStatus.APPROVED,
        triggered_by=acted_by,
        actor_role="ACCOUNTING_APPROVER",
        comment="Approved via /accounting/journals/{id}/approve",
    )
    await record_governance_event(
        db,
        tenant_id=tenant_id,
        entity_id=jv.entity_id,
        actor_user_id=acted_by,
        module="journal_workflow",
        action="journal_approve",
        target_id=str(jv.id),
        payload={
            "journal_id": str(jv.id),
            "journal_number": jv.jv_number,
            "from_status": from_status,
            "to_status": JVStatus.APPROVED,
            "actor_role": actor_role,
        },
    )
    await db.flush()
    return JournalActionResponse(id=jv.id, status="APPROVED", posted_at=None)


async def submit_journal(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    journal_id: uuid.UUID,
    acted_by: uuid.UUID,
    actor_role: str | None = None,
) -> JournalActionResponse:
    require_mutation_context("Journal submission")
    jv = await _get_journal_aggregate(
        db,
        tenant_id=tenant_id,
        journal_id=journal_id,
    )
    await assert_period_allows_modification(
        db,
        tenant_id=tenant_id,
        org_entity_id=jv.entity_id,
        fiscal_year=jv.fiscal_year,
        period_number=jv.fiscal_period,
    )
    if _is_posted_status(jv.status):
        raise ValidationError("Posted journals cannot be submitted again.")
    if jv.status != JVStatus.DRAFT:
        raise ValidationError(f"Journal cannot be submitted from status '{jv.status}'.")

    from_status = jv.status
    now = _utcnow()
    jv.status = JVStatus.SUBMITTED
    jv.submitted_at = now
    jv.updated_at = now
    await _append_state_event(
        db,
        jv=jv,
        from_status=from_status,
        to_status=JVStatus.SUBMITTED,
        triggered_by=acted_by,
        actor_role=actor_role or "ACCOUNTING_SUBMITTER",
        comment="Submitted via /accounting/journals/{id}/submit",
    )
    await record_governance_event(
        db,
        tenant_id=tenant_id,
        entity_id=jv.entity_id,
        actor_user_id=acted_by,
        module="journal_workflow",
        action="journal_submit",
        target_id=str(jv.id),
        payload={
            "journal_id": str(jv.id),
            "journal_number": jv.jv_number,
        },
    )
    await db.flush()
    return JournalActionResponse(id=jv.id, status="SUBMITTED", posted_at=None)


async def review_journal(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    journal_id: uuid.UUID,
    acted_by: uuid.UUID,
    actor_role: str | None = None,
) -> JournalActionResponse:
    require_mutation_context("Journal review")
    jv = await _get_journal_aggregate(
        db,
        tenant_id=tenant_id,
        journal_id=journal_id,
    )
    await assert_period_allows_modification(
        db,
        tenant_id=tenant_id,
        org_entity_id=jv.entity_id,
        fiscal_year=jv.fiscal_year,
        period_number=jv.fiscal_period,
    )
    if _is_posted_status(jv.status):
        raise ValidationError("Posted journals cannot be reviewed.")
    if jv.status not in {JVStatus.SUBMITTED, JVStatus.PENDING_REVIEW, JVStatus.RESUBMITTED}:
        raise ValidationError(f"Journal cannot be reviewed from status '{jv.status}'.")

    from_status = jv.status
    now = _utcnow()
    jv.status = JVStatus.UNDER_REVIEW
    jv.first_reviewed_at = jv.first_reviewed_at or now
    jv.updated_at = now

    await _append_state_event(
        db,
        jv=jv,
        from_status=from_status,
        to_status=JVStatus.UNDER_REVIEW,
        triggered_by=acted_by,
        actor_role=actor_role or "ACCOUNTING_REVIEWER",
        comment="Reviewed via /accounting/journals/{id}/review",
    )
    await record_governance_event(
        db,
        tenant_id=tenant_id,
        entity_id=jv.entity_id,
        actor_user_id=acted_by,
        module="journal_workflow",
        action="journal_review",
        target_id=str(jv.id),
        payload={
            "journal_id": str(jv.id),
            "journal_number": jv.jv_number,
        },
    )
    await db.flush()
    return JournalActionResponse(id=jv.id, status="REVIEWED", posted_at=None)


async def post_journal(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    journal_id: uuid.UUID,
    acted_by: uuid.UUID,
    actor_role: str | None = None,
) -> JournalActionResponse:
    require_mutation_context("Journal posting")
    jv = await _get_journal_aggregate(
        db,
        tenant_id=tenant_id,
        journal_id=journal_id,
    )
    if _is_posted_status(jv.status):
        posted_at = await _resolve_posted_at(db, jv)
        return JournalActionResponse(id=jv.id, status="POSTED", posted_at=posted_at)
    if jv.status != JVStatus.APPROVED:
        raise ValidationError("Only APPROVED journals can be posted.")
    await assert_period_allows_posting(
        db,
        tenant_id=tenant_id,
        org_entity_id=jv.entity_id,
        fiscal_year=jv.fiscal_year,
        period_number=jv.fiscal_period,
        actor_role=actor_role,
    )
    policy = await get_approval_policy(db, tenant_id=tenant_id)
    reviewed_by = await _resolve_last_triggered_by_for_status(
        db,
        jv_id=jv.id,
        to_status=JVStatus.UNDER_REVIEW,
    )
    enforce_distinct_poster_policy(
        reviewed_by=reviewed_by,
        posted_by=acted_by,
        policy=policy,
    )
    await _assert_balanced_active_lines(jv)

    existing_gl_entries = await _count_gl_entries_for_journal(
        db,
        tenant_id=tenant_id,
        journal_number=jv.jv_number,
    )
    if existing_gl_entries > 0:
        raise ValidationError("GL entries already exist for this journal; posting is append-only.")

    entity = await _get_entity_for_tenant(
        db,
        tenant_id=tenant_id,
        entity_id=jv.entity_id,
    )
    posted_at = _utcnow()
    await _append_gl_entries(
        db,
        jv=jv,
        entity=entity,
        created_by=acted_by,
        journal_date=jv.period_date,
    )
    from_status = jv.status
    jv.status = JVStatus.PUSHED
    jv.updated_at = posted_at
    jv.decided_at = jv.decided_at or posted_at

    await _append_state_event(
        db,
        jv=jv,
        from_status=from_status,
        to_status=JVStatus.PUSHED,
        triggered_by=acted_by,
        actor_role="ACCOUNTING_POSTER",
        comment="Posted via /accounting/journals/{id}/post",
    )
    await record_governance_event(
        db,
        tenant_id=tenant_id,
        entity_id=jv.entity_id,
        actor_user_id=acted_by,
        module="journal_workflow",
        action="journal_post",
        target_id=str(jv.id),
        payload={
            "journal_id": str(jv.id),
            "journal_number": jv.jv_number,
            "actor_role": actor_role,
            "posted_at": posted_at.isoformat(),
        },
    )
    await db.flush()
    return JournalActionResponse(id=jv.id, status="POSTED", posted_at=posted_at)


async def reverse_journal(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    journal_id: uuid.UUID,
    acted_by: uuid.UUID,
    actor_role: str | None = None,
) -> JournalResponse:
    require_mutation_context("Journal reversal")
    original = await _get_journal_aggregate(
        db,
        tenant_id=tenant_id,
        journal_id=journal_id,
    )
    if not _is_posted_status(original.status):
        raise ValidationError("Only POSTED journals can be reversed.")
    await assert_period_allows_posting(
        db,
        tenant_id=tenant_id,
        org_entity_id=original.entity_id,
        fiscal_year=date.today().year,
        period_number=date.today().month,
        actor_role=actor_role,
    )

    entity = await _get_entity_for_tenant(
        db,
        tenant_id=tenant_id,
        entity_id=original.entity_id,
    )
    active_lines = _active_journal_lines(original)
    if len(active_lines) < 2:
        raise ValidationError("Journal has no active lines to reverse.")

    reverse_lines_payload: list[dict[str, object]] = []
    for line in active_lines:
        reverse_entry_type = EntryType.CREDIT if line.entry_type == EntryType.DEBIT else EntryType.DEBIT
        reverse_lines_payload.append(
            {
                "account_code": line.account_code,
                "account_name": line.account_name,
                "entry_type": reverse_entry_type,
                "amount": line.amount,
                "currency": line.transaction_currency or line.currency,
                "transaction_currency": line.transaction_currency or line.currency,
                "functional_currency": line.functional_currency or entity.base_currency,
                "fx_rate": line.fx_rate,
                "base_amount": line.base_amount or line.amount,
                "amount_inr": line.amount_inr,
                "entity_id": original.entity_id,
                "narration": f"Reversal of {original.jv_number}",
            }
        )

    reversal = await create_jv(
        db,
        tenant_id=tenant_id,
        entity_id=original.entity_id,
        created_by=acted_by,
        period_date=date.today(),
        fiscal_year=date.today().year,
        fiscal_period=date.today().month,
        description=f"Reversal of journal {original.jv_number}",
        reference=f"REVERSAL_OF:{original.jv_number}",
        currency=entity.base_currency,
        lines=reverse_lines_payload,
    )
    await db.flush()
    # Ensure lines are eagerly available in async context before lifecycle actions
    # that inspect reversal.lines, avoiding lazy-load MissingGreenlet failures.
    reversal = await _get_journal_aggregate(
        db,
        tenant_id=tenant_id,
        journal_id=reversal.id,
    )
    await _set_approved(
        db,
        jv=reversal,
        acted_by=acted_by,
        comment=f"Auto-approved reversal for {original.jv_number}",
    )
    await _post_approved_journal(
        db,
        jv=reversal,
        entity=entity,
        acted_by=acted_by,
        comment=f"Auto-posted reversal for {original.jv_number}",
    )
    from_status = original.status
    original.status = JVStatus.VOIDED
    original.voided_by = acted_by
    original.void_reason = f"Reversed by journal {reversal.jv_number}"
    original.voided_at = _utcnow()
    await _append_state_event(
        db,
        jv=original,
        from_status=from_status,
        to_status=JVStatus.VOIDED,
        triggered_by=acted_by,
        actor_role=actor_role or "ACCOUNTING_POSTER",
        comment=f"Reversed via {reversal.jv_number}",
    )
    await record_governance_event(
        db,
        tenant_id=tenant_id,
        entity_id=original.entity_id,
        actor_user_id=acted_by,
        module="journal_workflow",
        action="journal_reverse",
        target_id=str(original.id),
        payload={
            "journal_id": str(original.id),
            "journal_number": original.jv_number,
            "reversal_journal_id": str(reversal.id),
            "reversal_journal_number": reversal.jv_number,
        },
    )
    await db.flush()
    return await get_journal(db, tenant_id=tenant_id, journal_id=reversal.id)


async def list_journals(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[JournalResponse]:
    stmt = (
        select(AccountingJVAggregate)
        .options(selectinload(AccountingJVAggregate.lines))
        .where(AccountingJVAggregate.tenant_id == tenant_id)
        .order_by(AccountingJVAggregate.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if entity_id is not None:
        stmt = stmt.where(AccountingJVAggregate.entity_id == entity_id)
    result = await db.execute(stmt)
    rows = list(result.scalars().all())
    payload = await _serialize_journals(db, tenant_id=tenant_id, journals=rows)
    if status is None:
        return payload
    normalized_status = status.upper()
    return [item for item in payload if item.status == normalized_status]


async def get_journal(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    journal_id: uuid.UUID,
) -> JournalResponse:
    journal = await _get_journal_aggregate(
        db,
        tenant_id=tenant_id,
        journal_id=journal_id,
    )
    payload = await _serialize_journals(db, tenant_id=tenant_id, journals=[journal])
    return payload[0]


async def _prepare_lines(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    payload: JournalCreate,
    entity: CpEntity,
) -> list[_PreparedJournalLine]:
    prepared: list[_PreparedJournalLine] = []
    for index, line in enumerate(payload.lines, start=1):
        account = await _resolve_tenant_account(
            db,
            tenant_id=tenant_id,
            line_number=index,
            account_id=line.tenant_coa_account_id,
            account_code=line.account_code,
        )
        entry_type = EntryType.DEBIT if line.debit > 0 else EntryType.CREDIT
        amount = line.debit if line.debit > 0 else line.credit
        functional_currency = (line.functional_currency or entity.base_currency).upper()
        transaction_currency = (line.transaction_currency or functional_currency).upper()
        resolved_fx_rate: Decimal | None = None
        base_amount = amount

        if transaction_currency != functional_currency:
            if line.fx_rate is not None:
                resolved_fx_rate = line.fx_rate
            else:
                spot_rate = await get_required_latest_fx_rate(
                    db,
                    tenant_id=tenant_id,
                    from_currency=transaction_currency,
                    to_currency=functional_currency,
                    rate_type="SPOT",
                    as_of_date=payload.journal_date,
                )
                resolved_fx_rate = Decimal(str(spot_rate.rate))
            base_amount = (amount * resolved_fx_rate).quantize(Decimal("0.0001"))
        elif line.base_amount is not None:
            base_amount = line.base_amount.quantize(Decimal("0.0001"))

        prepared.append(
            _PreparedJournalLine(
                line_number=index,
                account_id=account.id,
                account_code=account.account_code,
                account_name=account.display_name,
                entry_type=entry_type,
                amount=amount,
                transaction_currency=transaction_currency,
                functional_currency=functional_currency,
                fx_rate=resolved_fx_rate,
                base_amount=base_amount,
                memo=line.memo,
            )
        )
    return prepared


async def _resolve_tenant_account(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    line_number: int,
    account_id: uuid.UUID | None,
    account_code: str | None,
) -> TenantCoaAccount:
    by_id: TenantCoaAccount | None = None
    by_code: TenantCoaAccount | None = None

    if account_id is not None:
        by_id_stmt = select(TenantCoaAccount).where(
            TenantCoaAccount.id == account_id,
            TenantCoaAccount.tenant_id == tenant_id,
            TenantCoaAccount.is_active.is_(True),
        )
        by_id_result = await db.execute(by_id_stmt)
        by_id = by_id_result.scalar_one_or_none()
        if by_id is None:
            raise ValidationError(
                f"Line {line_number}: tenant_coa_account_id does not exist or is inactive."
            )

    if account_code:
        normalized_code = account_code.strip()
        by_code_stmt = select(TenantCoaAccount).where(
            TenantCoaAccount.account_code == normalized_code,
            TenantCoaAccount.tenant_id == tenant_id,
            TenantCoaAccount.is_active.is_(True),
        )
        by_code_result = await db.execute(by_code_stmt)
        by_code = by_code_result.scalar_one_or_none()
        if by_code is None:
            raise ValidationError(
                f"Line {line_number}: account_code '{normalized_code}' does not exist or is inactive."
            )

    account = by_id or by_code
    if account is None:
        raise ValidationError(f"Line {line_number}: provide account_code or tenant_coa_account_id.")
    if by_id is not None and by_code is not None and by_id.id != by_code.id:
        raise ValidationError(
            f"Line {line_number}: account_code does not match tenant_coa_account_id."
        )
    return account


async def _get_entity_for_tenant(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
) -> CpEntity:
    stmt = select(CpEntity).where(
        CpEntity.id == entity_id,
        CpEntity.tenant_id == tenant_id,
    )
    result = await db.execute(stmt)
    entity = result.scalar_one_or_none()
    if entity is None:
        raise ValidationError("Entity does not belong to tenant.")
    return entity


async def _get_journal_aggregate(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    journal_id: uuid.UUID,
) -> AccountingJVAggregate:
    stmt = (
        select(AccountingJVAggregate)
        .options(selectinload(AccountingJVAggregate.lines))
        .where(
            AccountingJVAggregate.id == journal_id,
            AccountingJVAggregate.tenant_id == tenant_id,
        )
    )
    result = await db.execute(stmt)
    journal = result.scalar_one_or_none()
    if journal is None:
        raise NotFoundError("Journal not found")
    return journal


def _active_journal_lines(jv: AccountingJVAggregate) -> list[AccountingJVLine]:
    max_version = max((line.jv_version for line in jv.lines), default=jv.version)
    return sorted(
        [line for line in jv.lines if line.jv_version == max_version],
        key=lambda item: item.line_number,
    )


async def _assert_balanced_active_lines(jv: AccountingJVAggregate) -> None:
    lines = _active_journal_lines(jv)
    if len(lines) < 2:
        raise ValidationError("Journal must have at least two lines.")
    total_debit = sum(
        (line.base_amount if line.base_amount is not None else line.amount)
        for line in lines
        if line.entry_type == EntryType.DEBIT
    )
    total_credit = sum(
        (line.base_amount if line.base_amount is not None else line.amount)
        for line in lines
        if line.entry_type == EntryType.CREDIT
    )
    if total_debit != total_credit:
        raise ValidationError(
            f"Journal imbalance detected: debit={total_debit}, credit={total_credit}."
        )


async def _count_gl_entries_for_journal(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    journal_number: str,
) -> int:
    stmt = select(func.count(GlEntry.id)).where(
        GlEntry.tenant_id == tenant_id,
        GlEntry.source_ref == journal_number,
    )
    result = await db.execute(stmt)
    return int(result.scalar_one() or 0)


async def _resolve_posted_at(db: AsyncSession, jv: AccountingJVAggregate) -> datetime | None:
    stmt = (
        select(GlEntry.created_at)
        .where(GlEntry.tenant_id == jv.tenant_id, GlEntry.source_ref == jv.jv_number)
        .order_by(GlEntry.created_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def _resolve_last_triggered_by_for_status(
    db: AsyncSession,
    *,
    jv_id: uuid.UUID,
    to_status: str,
) -> uuid.UUID | None:
    stmt = (
        select(AccountingJVStateEvent.triggered_by)
        .where(
            AccountingJVStateEvent.jv_id == jv_id,
            AccountingJVStateEvent.to_status == to_status,
        )
        .order_by(AccountingJVStateEvent.occurred_at.desc())
        .limit(1)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def _set_approved(
    db: AsyncSession,
    *,
    jv: AccountingJVAggregate,
    acted_by: uuid.UUID,
    comment: str,
) -> None:
    now = _utcnow()
    from_status = jv.status
    jv.status = JVStatus.APPROVED
    jv.submitted_at = jv.submitted_at or now
    jv.first_reviewed_at = jv.first_reviewed_at or now
    jv.decided_at = now
    jv.updated_at = now
    await _append_state_event(
        db,
        jv=jv,
        from_status=from_status,
        to_status=JVStatus.APPROVED,
        triggered_by=acted_by,
        actor_role="ACCOUNTING_APPROVER",
        comment=comment,
    )


async def _post_approved_journal(
    db: AsyncSession,
    *,
    jv: AccountingJVAggregate,
    entity: CpEntity,
    acted_by: uuid.UUID,
    comment: str,
) -> datetime:
    await _assert_balanced_active_lines(jv)
    existing_gl_entries = await _count_gl_entries_for_journal(
        db,
        tenant_id=jv.tenant_id,
        journal_number=jv.jv_number,
    )
    if existing_gl_entries > 0:
        raise ValidationError("GL entries already exist for this journal; posting is append-only.")

    posted_at = _utcnow()
    await _append_gl_entries(
        db,
        jv=jv,
        entity=entity,
        created_by=acted_by,
        journal_date=jv.period_date,
    )
    from_status = jv.status
    jv.status = JVStatus.PUSHED
    jv.updated_at = posted_at
    jv.decided_at = jv.decided_at or posted_at
    await _append_state_event(
        db,
        jv=jv,
        from_status=from_status,
        to_status=JVStatus.PUSHED,
        triggered_by=acted_by,
        actor_role="ACCOUNTING_POSTER",
        comment=comment,
    )
    return posted_at


async def _append_state_event(
    db: AsyncSession,
    *,
    jv: AccountingJVAggregate,
    from_status: str,
    to_status: str,
    triggered_by: uuid.UUID,
    actor_role: str,
    comment: str | None,
) -> None:
    mutation_context = require_mutation_context("Journal state event append")
    previous_stmt = (
        select(AccountingJVStateEvent)
        .where(AccountingJVStateEvent.jv_id == jv.id)
        .order_by(AccountingJVStateEvent.occurred_at.desc())
        .limit(1)
    )
    previous_result = await db.execute(previous_stmt)
    previous_event = previous_result.scalar_one_or_none()
    previous_hash = previous_event.chain_hash if previous_event is not None else None
    occurred_at = _utcnow()
    content = f"{jv.id}:{from_status}:{to_status}:{triggered_by}:{occurred_at.isoformat()}"
    chain_hash = _compute_hash(content, previous_hash)

    event = AccountingJVStateEvent(
        id=uuid.uuid4(),
        tenant_id=jv.tenant_id,
        chain_hash=chain_hash,
        previous_hash=previous_hash or "",
        jv_id=jv.id,
        jv_version=jv.version,
        from_status=from_status,
        to_status=to_status,
        triggered_by=triggered_by,
        actor_role=actor_role,
        comment=comment,
        created_by_intent_id=mutation_context.intent_id,
        recorded_by_job_id=mutation_context.job_id,
        occurred_at=occurred_at,
    )
    db.add(event)


async def _append_gl_entries(
    db: AsyncSession,
    *,
    jv: AccountingJVAggregate,
    entity: CpEntity,
    created_by: uuid.UUID,
    journal_date: date,
) -> None:
    mutation_context = require_mutation_context("GL append")
    lines = _active_journal_lines(jv)
    total_debit = sum(
        (line.base_amount if line.base_amount is not None else line.amount)
        for line in lines
        if line.entry_type == EntryType.DEBIT
    )
    total_credit = sum(
        (line.base_amount if line.base_amount is not None else line.amount)
        for line in lines
        if line.entry_type == EntryType.CREDIT
    )
    if total_debit != total_credit:
        raise ValidationError(
            f"GL integrity check failed: debit={total_debit}, credit={total_credit}."
        )

    previous_hash: str | None = jv.chain_hash
    for line in lines:
        base_amount = line.base_amount if line.base_amount is not None else line.amount
        debit_amount = base_amount if line.entry_type == EntryType.DEBIT else Decimal("0")
        credit_amount = base_amount if line.entry_type == EntryType.CREDIT else Decimal("0")
        content = (
            f"{jv.id}:{line.line_number}:{line.account_code}:"
            f"{debit_amount}:{credit_amount}:{journal_date.isoformat()}"
        )
        chain_hash = _compute_hash(content, previous_hash)
        row = GlEntry(
            id=uuid.uuid4(),
            tenant_id=jv.tenant_id,
            chain_hash=chain_hash,
            previous_hash=previous_hash or "",
            entity_id=entity.id,
            period_year=journal_date.year,
            period_month=journal_date.month,
            entity_name=entity.entity_name,
            account_code=line.account_code,
            account_name=line.account_name or line.account_code,
            debit_amount=debit_amount,
            credit_amount=credit_amount,
            description=jv.description,
            source_ref=jv.jv_number,
            currency=line.functional_currency or jv.currency,
            uploaded_by=created_by,
            created_by_intent_id=mutation_context.intent_id,
            recorded_by_job_id=mutation_context.job_id,
        )
        db.add(row)
        previous_hash = chain_hash


async def _serialize_journals(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    journals: list[AccountingJVAggregate],
) -> list[JournalResponse]:
    account_codes = {
        line.account_code
        for journal in journals
        for line in journal.lines
    }
    account_id_map: dict[str, uuid.UUID] = {}
    if account_codes:
        account_stmt = select(TenantCoaAccount).where(
            TenantCoaAccount.tenant_id == tenant_id,
            TenantCoaAccount.account_code.in_(sorted(account_codes)),
        )
        account_result = await db.execute(account_stmt)
        account_rows = account_result.scalars().all()
        account_id_map = {row.account_code: row.id for row in account_rows}

    jv_numbers = [journal.jv_number for journal in journals]
    posted_refs: set[str] = set()
    if jv_numbers:
        gl_stmt = select(GlEntry.source_ref).where(
            GlEntry.tenant_id == tenant_id,
            GlEntry.source_ref.in_(jv_numbers),
        )
        gl_result = await db.execute(gl_stmt)
        posted_refs = {row for row in gl_result.scalars().all() if row}

    payload: list[JournalResponse] = []
    for journal in journals:
        active_lines = _active_journal_lines(journal)
        serialised_lines = [
            _serialize_line(line, account_id_map.get(line.account_code))
            for line in active_lines
        ]
        is_posted = journal.jv_number in posted_refs or _is_posted_status(journal.status)
        journal_status = _map_journal_status(journal.status, is_posted)
        payload.append(
            JournalResponse(
                id=journal.id,
                org_entity_id=journal.entity_id,
                journal_number=journal.jv_number,
                journal_date=journal.period_date,
                reference=journal.reference,
                narration=journal.description,
                status=journal_status,
                posted_at=journal.updated_at if journal_status == "POSTED" else None,
                total_debit=_q4(journal.total_debit),
                total_credit=_q4(journal.total_credit),
                currency=journal.currency,
                lines=serialised_lines,
            )
        )
    return payload


def _is_posted_status(status: str) -> bool:
    return status in {JVStatus.PUSHED, JVStatus.PUSH_IN_PROGRESS}


def _map_journal_status(status: str, is_posted: bool) -> str:
    if is_posted:
        return "POSTED"
    if status == JVStatus.VOIDED:
        return "REVERSED"
    if status == JVStatus.SUBMITTED:
        return "SUBMITTED"
    if status == JVStatus.APPROVED:
        return "APPROVED"
    if status in REVIEW_SOURCE_STATUSES:
        return "REVIEWED"
    return "DRAFT"


def _serialize_line(
    line: AccountingJVLine,
    tenant_coa_account_id: uuid.UUID | None,
) -> JournalLineResponse:
    debit = line.amount if line.entry_type == EntryType.DEBIT else Decimal("0")
    credit = line.amount if line.entry_type == EntryType.CREDIT else Decimal("0")
    return JournalLineResponse(
        line_number=line.line_number,
        tenant_coa_account_id=tenant_coa_account_id,
        account_code=line.account_code,
        account_name=line.account_name,
        debit=debit,
        credit=credit,
        memo=line.narration,
        transaction_currency=line.transaction_currency or line.currency,
        functional_currency=line.functional_currency,
        fx_rate=line.fx_rate,
        base_amount=line.base_amount or line.amount_inr,
    )


def _q4(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0000"))
