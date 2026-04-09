from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import NotFoundError
from financeops.core.intent.context import apply_mutation_linkage, require_mutation_context
from financeops.modules.statutory.models import StatutoryFiling, StatutoryRegisterEntry
from financeops.platform.db.models.entities import CpEntity

_STANDARD_FORMS = [
    ("MGT-7", "Annual Return"),
    ("AOC-4", "Financial Statements"),
    ("ADT-1", "Auditor Appointment"),
    ("DIR-3 KYC", "Director KYC"),
    ("MSME-1", "MSME Payment dues"),
    ("DPT-3", "Return of Deposits"),
    ("BEN-2", "Beneficial Ownership"),
]


def _fy_dates(fiscal_year: int) -> list[tuple[str, str, date]]:
    return [
        ("MGT-7", "Annual Return", date(fiscal_year, 11, 30)),
        ("AOC-4", "Financial Statements", date(fiscal_year, 10, 31)),
        ("ADT-1", "Auditor Appointment", date(fiscal_year, 10, 15)),
        ("DIR-3 KYC", "Director KYC", date(fiscal_year, 9, 30)),
        ("MSME-1", "MSME Payment dues", date(fiscal_year, 4, 30)),
        ("MSME-1", "MSME Payment dues", date(fiscal_year, 10, 31)),
        ("DPT-3", "Return of Deposits", date(fiscal_year, 6, 30)),
        ("BEN-2", "Beneficial Ownership", date(fiscal_year, 12, 31)),
    ]


async def _resolve_entity_id(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID | None,
) -> uuid.UUID:
    if entity_id is not None:
        return entity_id
    resolved = (
        await session.execute(
            select(CpEntity.id)
            .where(
                CpEntity.tenant_id == tenant_id,
                CpEntity.status == "active",
            )
            .order_by(CpEntity.created_at.asc(), CpEntity.id.asc())
        )
    ).scalars().first()
    if resolved is not None:
        return resolved
    fallback = (
        await session.execute(
            select(CpEntity.id)
            .where(CpEntity.status == "active")
            .order_by(CpEntity.created_at.asc(), CpEntity.id.asc())
        )
    ).scalars().first()
    if fallback is None:
        raise NotFoundError("No active entity available")
    return fallback


async def ensure_standard_filings(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID | None,
    fiscal_year: int,
) -> None:
    require_mutation_context("Statutory filing calendar bootstrap")
    resolved_entity_id = await _resolve_entity_id(session, tenant_id, entity_id)
    existing_count = int(
        (
            await session.execute(
                select(func.count())
                .select_from(StatutoryFiling)
                .where(
                    StatutoryFiling.tenant_id == tenant_id,
                    StatutoryFiling.entity_id == resolved_entity_id,
                    StatutoryFiling.due_date >= date(fiscal_year, 1, 1),
                    StatutoryFiling.due_date <= date(fiscal_year, 12, 31),
                )
            )
        ).scalar_one()
    )
    if existing_count > 0:
        return

    now = datetime.now(UTC)
    for form_number, form_description, due_date in _fy_dates(fiscal_year):
        row = StatutoryFiling(
                tenant_id=tenant_id,
                entity_id=resolved_entity_id,
                form_number=form_number,
                form_description=form_description,
                due_date=due_date,
                status="pending",
                penalty_amount=Decimal("0.00"),
                created_at=now,
            )
        apply_mutation_linkage(row)
        session.add(row)
    await session.flush()


async def get_compliance_calendar(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    fiscal_year: int,
    entity_id: uuid.UUID | None = None,
) -> list[dict]:
    resolved_entity_id = await _resolve_entity_id(session, tenant_id, entity_id)
    rows = (
        await session.execute(
            select(StatutoryFiling)
            .where(
                StatutoryFiling.tenant_id == tenant_id,
                StatutoryFiling.entity_id == resolved_entity_id,
                StatutoryFiling.due_date >= date(fiscal_year, 1, 1),
                StatutoryFiling.due_date <= date(fiscal_year, 12, 31),
            )
            .order_by(StatutoryFiling.due_date, StatutoryFiling.created_at)
        )
    ).scalars().all()

    today = date.today()
    payload: list[dict] = []
    for row in rows:
        is_overdue = row.status != "filed" and row.due_date < today
        days_until_due = (row.due_date - today).days
        status = "overdue" if is_overdue else row.status
        payload.append(
            {
                "id": str(row.id),
                "form_number": row.form_number,
                "form_description": row.form_description,
                "due_date": row.due_date,
                "filed_date": row.filed_date,
                "status": status,
                "days_until_due": days_until_due,
                "is_overdue": is_overdue,
            }
        )
    return payload


async def mark_as_filed(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    filing_id: uuid.UUID,
    filed_date: date,
    filing_reference: str,
    entity_id: uuid.UUID | None = None,
) -> StatutoryFiling:
    require_mutation_context("Statutory filing mark-as-filed")
    resolved_entity_id = await _resolve_entity_id(session, tenant_id, entity_id)
    current = (
        await session.execute(
            select(StatutoryFiling).where(
                StatutoryFiling.id == filing_id,
                StatutoryFiling.tenant_id == tenant_id,
                StatutoryFiling.entity_id == resolved_entity_id,
            )
        )
    ).scalar_one_or_none()
    if current is None:
        raise NotFoundError("Filing not found")

    row = StatutoryFiling(
        tenant_id=tenant_id,
        entity_id=resolved_entity_id,
        form_number=current.form_number,
        form_description=current.form_description,
        due_date=current.due_date,
        filed_date=filed_date,
        status="filed",
        filing_reference=filing_reference,
        penalty_amount=current.penalty_amount,
        notes=current.notes,
    )
    apply_mutation_linkage(row)
    session.add(row)
    await session.flush()
    return row


async def get_register(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    register_type: str,
    entity_id: uuid.UUID | None = None,
    skip: int = 0,
    limit: int = 100,
    offset: int | None = None,
) -> dict:
    resolved_entity_id = await _resolve_entity_id(session, tenant_id, entity_id)
    effective_skip = offset if offset is not None else skip
    bounded_limit = max(1, min(limit, 1000))
    stmt = select(StatutoryRegisterEntry).where(
        StatutoryRegisterEntry.tenant_id == tenant_id,
        StatutoryRegisterEntry.entity_id == resolved_entity_id,
        StatutoryRegisterEntry.register_type == register_type,
    )
    total = int((await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one())
    rows = (
        await session.execute(
            stmt.order_by(desc(StatutoryRegisterEntry.entry_date), desc(StatutoryRegisterEntry.id))
            .limit(bounded_limit)
            .offset(effective_skip)
        )
    ).scalars().all()
    return {"data": rows, "total": total, "limit": bounded_limit, "offset": effective_skip}


async def add_register_entry(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    register_type: str,
    entry_date: date,
    entry_description: str,
    entity_id: uuid.UUID | None = None,
    folio_number: str | None = None,
    amount: Decimal | None = None,
    currency: str | None = None,
    reference_document: str | None = None,
) -> StatutoryRegisterEntry:
    require_mutation_context("Statutory register entry creation")
    resolved_entity_id = await _resolve_entity_id(session, tenant_id, entity_id)
    now = datetime.now(UTC)
    row = StatutoryRegisterEntry(
        tenant_id=tenant_id,
        entity_id=resolved_entity_id,
        register_type=register_type,
        entry_date=entry_date,
        entry_description=entry_description,
        folio_number=folio_number,
        amount=amount,
        currency=currency,
        reference_document=reference_document,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    apply_mutation_linkage(row)
    session.add(row)
    await session.flush()
    return row


async def list_filings(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID | None = None,
    status: str | None = None,
    fiscal_year: int | None = None,
    skip: int = 0,
    limit: int = 100,
    offset: int | None = None,
) -> dict:
    resolved_entity_id = await _resolve_entity_id(session, tenant_id, entity_id)
    effective_skip = offset if offset is not None else skip
    bounded_limit = max(1, min(limit, 1000))
    stmt = select(StatutoryFiling).where(
        StatutoryFiling.tenant_id == tenant_id,
        StatutoryFiling.entity_id == resolved_entity_id,
    )
    if status:
        stmt = stmt.where(StatutoryFiling.status == status)
    if fiscal_year:
        stmt = stmt.where(StatutoryFiling.due_date >= date(fiscal_year, 1, 1), StatutoryFiling.due_date <= date(fiscal_year, 12, 31))

    total = int((await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one())
    rows = (
        await session.execute(
            stmt.order_by(StatutoryFiling.due_date, desc(StatutoryFiling.created_at))
            .limit(bounded_limit)
            .offset(effective_skip)
        )
    ).scalars().all()
    return {"data": rows, "total": total, "limit": bounded_limit, "offset": effective_skip}


__all__ = [
    "get_compliance_calendar",
    "mark_as_filed",
    "get_register",
    "add_register_entry",
    "list_filings",
    "ensure_standard_filings",
]
