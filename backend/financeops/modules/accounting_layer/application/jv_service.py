from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from financeops.core.exceptions import NotFoundError, ValidationError
from financeops.db.models.accounting_jv import (
    AccountingJVAggregate,
    AccountingJVLine,
    AccountingJVStateEvent,
    EntryType,
    JVStatus,
)
from financeops.modules.accounting_layer.domain.state_machine import (
    TransitionRequest,
    next_status_after_resubmit,
    validate_transition,
)


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def _compute_hash(content: str, previous_hash: str | None) -> str:
    payload = f"{previous_hash or ''}:{content}"
    return hashlib.sha256(payload.encode()).hexdigest()


def _to_decimal(value: Any, field: str) -> Decimal:
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, TypeError) as exc:
        raise ValidationError(f"Field '{field}' must be a valid decimal number.") from exc
    if decimal_value < 0:
        raise ValidationError(f"Field '{field}' must be non-negative.")
    return decimal_value


async def create_jv(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    created_by: uuid.UUID,
    period_date: Any,
    fiscal_year: int,
    fiscal_period: int,
    description: str | None = None,
    reference: str | None = None,
    currency: str = "INR",
    location_id: uuid.UUID | None = None,
    cost_centre_id: uuid.UUID | None = None,
    workflow_instance_id: uuid.UUID | None = None,
    lines: list[dict[str, Any]] | None = None,
) -> AccountingJVAggregate:
    jv_number = await _generate_jv_number(db, tenant_id, fiscal_year, fiscal_period)

    jv_id = uuid.uuid4()
    chain_hash = _compute_hash(str(jv_id), None)

    jv = AccountingJVAggregate(
        id=jv_id,
        tenant_id=tenant_id,
        chain_hash=chain_hash,
        previous_hash="",
        entity_id=entity_id,
        location_id=location_id,
        cost_centre_id=cost_centre_id,
        jv_number=jv_number,
        status=JVStatus.DRAFT,
        version=1,
        period_date=period_date,
        fiscal_year=fiscal_year,
        fiscal_period=fiscal_period,
        description=description,
        reference=reference,
        currency=currency,
        created_by=created_by,
        total_debit=Decimal("0"),
        total_credit=Decimal("0"),
        resubmission_count=0,
        workflow_instance_id=workflow_instance_id,
        updated_at=_utcnow(),
    )
    db.add(jv)
    await db.flush()

    if lines:
        await _append_lines(db, jv=jv, lines=lines)

    return jv


async def update_jv_lines(
    db: AsyncSession,
    *,
    jv_id: uuid.UUID,
    tenant_id: uuid.UUID,
    lines: list[dict[str, Any]],
    expected_version: int,
) -> AccountingJVAggregate:
    jv = await _get_jv(db, jv_id, tenant_id)

    if jv.status != JVStatus.DRAFT:
        raise ValidationError(
            f"JV lines can only be edited in DRAFT status. Current status: '{jv.status}'"
        )

    _check_optimistic_lock(jv, expected_version)

    jv.version += 1
    jv.updated_at = _utcnow()

    await _append_lines(db, jv=jv, lines=lines)
    await db.flush()
    return jv


async def transition_jv(
    db: AsyncSession,
    *,
    jv_id: uuid.UUID,
    tenant_id: uuid.UUID,
    to_status: str,
    triggered_by: uuid.UUID,
    actor_role: str,
    expected_version: int,
    comment: str | None = None,
    is_admin: bool = False,
) -> AccountingJVAggregate:
    jv = await _get_jv(db, jv_id, tenant_id)
    _check_optimistic_lock(jv, expected_version)

    target_status = to_status.upper()
    if target_status == JVStatus.RESUBMITTED:
        target_status = next_status_after_resubmit(jv.resubmission_count)

    validate_transition(
        TransitionRequest(
            from_status=jv.status,
            to_status=target_status,
            triggered_by_role=actor_role,
            is_admin=is_admin,
            comment=comment,
            resubmission_count=jv.resubmission_count,
        )
    )

    if target_status == JVStatus.SUBMITTED:
        _validate_ready_to_submit(jv)

    now = _utcnow()
    from_status = jv.status

    jv.status = target_status
    jv.version += 1
    jv.updated_at = now

    if target_status == JVStatus.SUBMITTED and jv.submitted_at is None:
        jv.submitted_at = now
    if target_status == JVStatus.UNDER_REVIEW and jv.first_reviewed_at is None:
        jv.first_reviewed_at = now
    if target_status in (JVStatus.APPROVED, JVStatus.REJECTED):
        jv.decided_at = now

    if target_status in (JVStatus.RESUBMITTED, JVStatus.ESCALATED):
        jv.resubmission_count += 1

    if target_status == JVStatus.VOIDED:
        jv.voided_by = triggered_by
        jv.void_reason = comment
        jv.voided_at = now

    await _append_state_event(
        db,
        jv=jv,
        from_status=from_status,
        to_status=target_status,
        triggered_by=triggered_by,
        actor_role=actor_role,
        comment=comment,
    )

    await db.flush()
    return jv


async def get_jv(
    db: AsyncSession,
    *,
    jv_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> AccountingJVAggregate:
    return await _get_jv(db, jv_id, tenant_id)


async def list_jvs(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID | None = None,
    status: str | None = None,
    fiscal_year: int | None = None,
    fiscal_period: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[AccountingJVAggregate]:
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
    if status is not None:
        stmt = stmt.where(AccountingJVAggregate.status == status)
    if fiscal_year is not None:
        stmt = stmt.where(AccountingJVAggregate.fiscal_year == fiscal_year)
    if fiscal_period is not None:
        stmt = stmt.where(AccountingJVAggregate.fiscal_period == fiscal_period)

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_jv_state_history(
    db: AsyncSession,
    *,
    jv_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> list[AccountingJVStateEvent]:
    await _get_jv(db, jv_id, tenant_id)

    stmt = (
        select(AccountingJVStateEvent)
        .where(
            AccountingJVStateEvent.jv_id == jv_id,
            AccountingJVStateEvent.tenant_id == tenant_id,
        )
        .order_by(AccountingJVStateEvent.occurred_at.asc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def _get_jv(
    db: AsyncSession,
    jv_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> AccountingJVAggregate:
    stmt = (
        select(AccountingJVAggregate)
        .options(selectinload(AccountingJVAggregate.lines))
        .where(
            AccountingJVAggregate.id == jv_id,
            AccountingJVAggregate.tenant_id == tenant_id,
        )
    )
    result = await db.execute(stmt)
    jv = result.scalar_one_or_none()
    if jv is None:
        raise NotFoundError(f"JV {jv_id} not found")
    return jv


def _check_optimistic_lock(jv: AccountingJVAggregate, expected_version: int) -> None:
    if jv.version != expected_version:
        raise ValidationError(
            f"JV version conflict: expected {expected_version}, got {jv.version}. Reload and retry."
        )


def _validate_ready_to_submit(jv: AccountingJVAggregate) -> None:
    if not jv.lines:
        raise ValidationError("JV must have at least one line before submission.")

    active = [line for line in jv.lines if line.jv_version == jv.version]
    if len(active) < 2:
        raise ValidationError("JV must have at least 2 lines (one debit, one credit).")

    total_debit = sum(line.amount for line in active if line.entry_type == EntryType.DEBIT)
    total_credit = sum(line.amount for line in active if line.entry_type == EntryType.CREDIT)
    if total_debit != total_credit:
        raise ValidationError(
            f"JV is not balanced. Total debit: {total_debit}, total credit: {total_credit}."
        )


async def _append_lines(
    db: AsyncSession,
    *,
    jv: AccountingJVAggregate,
    lines: list[dict[str, Any]],
) -> None:
    if not lines:
        raise ValidationError("JV must have at least one line.")

    total_debit = Decimal("0")
    total_credit = Decimal("0")
    previous_hash = jv.chain_hash

    for idx, line_data in enumerate(lines, start=1):
        entry_type = str(line_data.get("entry_type", "")).upper()
        if entry_type not in (EntryType.DEBIT, EntryType.CREDIT):
            raise ValidationError(f"Line {idx}: entry_type must be DEBIT or CREDIT.")

        amount = _to_decimal(line_data.get("amount", 0), f"line {idx} amount")
        if amount <= 0:
            raise ValidationError(f"Line {idx}: amount must be greater than zero.")

        currency = str(line_data.get("currency", jv.currency)).upper()
        transaction_currency = str(line_data.get("transaction_currency", currency)).upper()
        functional_currency = str(line_data.get("functional_currency", jv.currency)).upper()
        fx_rate = None
        amount_inr = amount
        if currency != "INR":
            fx_rate = _to_decimal(line_data.get("fx_rate", 1), f"line {idx} fx_rate")
            amount_inr = (amount * fx_rate).quantize(Decimal("0.0001"))

        base_amount = _to_decimal(
            line_data.get("base_amount", amount_inr if amount_inr is not None else amount),
            f"line {idx} base_amount",
        )

        line_hash_content = f"{jv.id}:{jv.version}:{idx}:{entry_type}:{amount}"
        chain_hash = _compute_hash(line_hash_content, previous_hash)

        line = AccountingJVLine(
            id=uuid.uuid4(),
            tenant_id=jv.tenant_id,
            chain_hash=chain_hash,
            previous_hash=previous_hash or "",
            jv_id=jv.id,
            jv_version=jv.version,
            line_number=idx,
            account_code=str(line_data.get("account_code", "")),
            account_name=line_data.get("account_name"),
            entry_type=entry_type,
            amount=amount,
            currency=currency,
            transaction_currency=transaction_currency,
            functional_currency=functional_currency,
            fx_rate=fx_rate,
            amount_inr=amount_inr,
            base_amount=base_amount,
            entity_id=line_data.get("entity_id", jv.entity_id),
            location_id=line_data.get("location_id", jv.location_id),
            cost_centre_id=line_data.get("cost_centre_id", jv.cost_centre_id),
            narration=line_data.get("narration"),
            tax_code=line_data.get("tax_code"),
            is_tax_line=bool(line_data.get("is_tax_line", False)),
        )
        db.add(line)

        previous_hash = chain_hash

        if entry_type == EntryType.DEBIT:
            total_debit += amount
        else:
            total_credit += amount

    jv.total_debit = total_debit
    jv.total_credit = total_credit


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
    previous_hash = None
    previous_stmt = (
        select(AccountingJVStateEvent)
        .where(AccountingJVStateEvent.jv_id == jv.id)
        .order_by(AccountingJVStateEvent.occurred_at.desc())
        .limit(1)
    )
    previous_result = await db.execute(previous_stmt)
    previous_event = previous_result.scalar_one_or_none()
    if previous_event is not None:
        previous_hash = previous_event.chain_hash

    content = f"{jv.id}:{from_status}:{to_status}:{triggered_by}:{_utcnow().isoformat()}"
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
        occurred_at=_utcnow(),
    )
    db.add(event)


async def _generate_jv_number(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    fiscal_year: int,
    fiscal_period: int,
) -> str:
    stmt = select(AccountingJVAggregate.id).where(
        AccountingJVAggregate.tenant_id == tenant_id,
        AccountingJVAggregate.fiscal_year == fiscal_year,
        AccountingJVAggregate.fiscal_period == fiscal_period,
    )
    result = await db.execute(stmt)
    sequence = len(result.scalars().all()) + 1
    return f"JV-{fiscal_year}-{str(fiscal_period).zfill(2)}-{str(sequence).zfill(4)}"
