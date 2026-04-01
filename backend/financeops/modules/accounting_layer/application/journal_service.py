from __future__ import annotations

import hashlib
import logging
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal

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
from financeops.db.models.reconciliation import GlEntry
from financeops.modules.accounting_layer.application.jv_service import create_jv
from financeops.modules.accounting_layer.domain.schemas import (
    JournalCreate,
    JournalLineResponse,
    JournalResponse,
)
from financeops.modules.coa.models import TenantCoaAccount
from financeops.platform.db.models.entities import CpEntity

logger = logging.getLogger(__name__)

POSTED_STATUSES: frozenset[str] = frozenset(
    {JVStatus.APPROVED, JVStatus.PUSH_IN_PROGRESS, JVStatus.PUSHED}
)


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def _compute_hash(content: str, previous_hash: str | None) -> str:
    payload = f"{previous_hash or ''}:{content}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class _PreparedJournalLine:
    line_number: int
    account_id: uuid.UUID | None
    account_code: str
    account_name: str | None
    entry_type: str
    amount: Decimal
    memo: str | None


async def create_posted_journal(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    created_by: uuid.UUID,
    payload: JournalCreate,
) -> JournalResponse:
    entity = await _get_entity_for_tenant(
        db,
        tenant_id=tenant_id,
        entity_id=payload.org_entity_id,
    )
    prepared_lines = await _prepare_lines(
        db,
        tenant_id=tenant_id,
        payload=payload,
    )
    jv_lines = [
        {
            "account_code": line.account_code,
            "account_name": line.account_name,
            "entry_type": line.entry_type,
            "amount": line.amount,
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
        currency=entity.base_currency,
        lines=jv_lines,
    )

    posted_at = _utcnow()
    previous_status = jv.status
    jv.status = JVStatus.APPROVED
    jv.submitted_at = posted_at
    jv.first_reviewed_at = posted_at
    jv.decided_at = posted_at
    jv.updated_at = posted_at

    await _append_posted_state_event(
        db,
        jv=jv,
        from_status=previous_status,
        triggered_by=created_by,
    )
    await _append_gl_entries(
        db,
        jv=jv,
        entity=entity,
        created_by=created_by,
        journal_date=payload.journal_date,
    )
    await db.flush()

    logger.info(
        "Posted journal created",
        extra={
            "tenant_id": str(tenant_id),
            "jv_id": str(jv.id),
            "journal_number": jv.jv_number,
            "line_count": len(prepared_lines),
        },
    )
    return await get_journal(db, tenant_id=tenant_id, journal_id=jv.id)


async def list_journals(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[JournalResponse]:
    stmt = (
        select(AccountingJVAggregate)
        .options(selectinload(AccountingJVAggregate.lines))
        .where(
            AccountingJVAggregate.tenant_id == tenant_id,
            AccountingJVAggregate.status.in_(POSTED_STATUSES),
        )
        .order_by(AccountingJVAggregate.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if entity_id is not None:
        stmt = stmt.where(AccountingJVAggregate.entity_id == entity_id)
    result = await db.execute(stmt)
    rows = list(result.scalars().all())
    return await _serialize_journals(db, tenant_id=tenant_id, journals=rows)


async def get_journal(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    journal_id: uuid.UUID,
) -> JournalResponse:
    stmt = (
        select(AccountingJVAggregate)
        .options(selectinload(AccountingJVAggregate.lines))
        .where(
            AccountingJVAggregate.id == journal_id,
            AccountingJVAggregate.tenant_id == tenant_id,
            AccountingJVAggregate.status.in_(POSTED_STATUSES),
        )
    )
    result = await db.execute(stmt)
    journal = result.scalar_one_or_none()
    if journal is None:
        raise NotFoundError("Journal not found")
    payload = await _serialize_journals(db, tenant_id=tenant_id, journals=[journal])
    return payload[0]


async def _prepare_lines(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    payload: JournalCreate,
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
        prepared.append(
            _PreparedJournalLine(
                line_number=index,
                account_id=account.id,
                account_code=account.account_code,
                account_name=account.display_name,
                entry_type=entry_type,
                amount=amount,
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
        raise ValidationError(
            f"Line {line_number}: provide account_code or tenant_coa_account_id."
        )
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


async def _append_posted_state_event(
    db: AsyncSession,
    *,
    jv: AccountingJVAggregate,
    from_status: str,
    triggered_by: uuid.UUID,
) -> None:
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
    content = f"{jv.id}:{from_status}:{JVStatus.APPROVED}:{triggered_by}:{occurred_at.isoformat()}"
    chain_hash = _compute_hash(content, previous_hash)

    event = AccountingJVStateEvent(
        id=uuid.uuid4(),
        tenant_id=jv.tenant_id,
        chain_hash=chain_hash,
        previous_hash=previous_hash or "",
        jv_id=jv.id,
        jv_version=jv.version,
        from_status=from_status,
        to_status=JVStatus.APPROVED,
        triggered_by=triggered_by,
        actor_role="SYSTEM_AUTO_POST",
        comment="Auto-posted via /accounting/journals",
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
    max_version = max((line.jv_version for line in jv.lines), default=jv.version)
    lines = [line for line in jv.lines if line.jv_version == max_version]
    previous_hash: str | None = jv.chain_hash
    for line in lines:
        debit_amount = line.amount if line.entry_type == EntryType.DEBIT else Decimal("0")
        credit_amount = line.amount if line.entry_type == EntryType.CREDIT else Decimal("0")
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
            currency=jv.currency,
            uploaded_by=created_by,
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

    payload: list[JournalResponse] = []
    for journal in journals:
        max_version = max((line.jv_version for line in journal.lines), default=journal.version)
        active_lines = sorted(
            [line for line in journal.lines if line.jv_version == max_version],
            key=lambda item: item.line_number,
        )
        serialised_lines = [
            _serialize_line(line, account_id_map.get(line.account_code))
            for line in active_lines
        ]
        payload.append(
            JournalResponse(
                id=journal.id,
                org_entity_id=journal.entity_id,
                journal_number=journal.jv_number,
                journal_date=journal.period_date,
                reference=journal.reference,
                narration=journal.description,
                status="POSTED",
                posted_at=journal.decided_at or journal.updated_at,
                total_debit=journal.total_debit,
                total_credit=journal.total_credit,
                currency=journal.currency,
                lines=serialised_lines,
            )
        )
    return payload


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
    )
