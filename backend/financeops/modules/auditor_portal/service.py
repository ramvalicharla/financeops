from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import NotFoundError
from financeops.modules.auditor_portal.models import AuditorPortalAccess, AuditorRequest

_PBC_TEMPLATE = [
    ("financial_statements", "Trial Balance as at year end"),
    ("financial_statements", "Audited Financial Statements (prior year)"),
    ("fixed_assets", "Fixed asset register with depreciation schedule"),
    ("leases", "Lease schedule (IFRS 16/INDAS 116)"),
    ("revenue", "Revenue recognition workings"),
    ("payroll", "Payroll reconciliation"),
    ("bank_reconciliation", "Bank reconciliation statements (all accounts)"),
    ("related_party", "Related party transactions schedule"),
    ("loans", "Loans and borrowings schedule"),
    ("tax", "Tax computation and provision workings"),
    ("other", "Management representation letter"),
    ("other", "Board resolutions (key transactions)"),
]


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def grant_auditor_access(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    auditor_email: str,
    auditor_firm: str,
    engagement_name: str,
    valid_from: date,
    valid_until: date,
    modules_accessible: list[str],
    created_by: uuid.UUID,
    access_level: str = "read_only",
) -> tuple[AuditorPortalAccess, str]:
    plain_token = secrets.token_urlsafe(32)
    token_hash = _hash_token(plain_token)
    now = datetime.now(UTC)

    row = (
        await session.execute(
            select(AuditorPortalAccess).where(
                AuditorPortalAccess.tenant_id == tenant_id,
                AuditorPortalAccess.auditor_email == auditor_email,
                AuditorPortalAccess.engagement_name == engagement_name,
            )
        )
    ).scalar_one_or_none()

    if row is None:
        row = AuditorPortalAccess(
            tenant_id=tenant_id,
            auditor_email=auditor_email,
            auditor_firm=auditor_firm,
            engagement_name=engagement_name,
            access_level=access_level,
            modules_accessible=modules_accessible,
            valid_from=valid_from,
            valid_until=valid_until,
            is_active=True,
            access_token_hash=token_hash,
            created_by=created_by,
            created_at=now,
            updated_at=now,
        )
        session.add(row)
    else:
        row.auditor_firm = auditor_firm
        row.access_level = access_level
        row.modules_accessible = modules_accessible
        row.valid_from = valid_from
        row.valid_until = valid_until
        row.is_active = True
        row.access_token_hash = token_hash
        row.updated_at = now

    await session.flush()
    return row, plain_token


async def seed_pbc_checklist(
    session: AsyncSession,
    access_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> list[AuditorRequest]:
    existing = (
        await session.execute(
            select(AuditorRequest).where(AuditorRequest.access_id == access_id)
        )
    ).scalars().all()
    if existing:
        return existing

    now = datetime.now(UTC)
    rows: list[AuditorRequest] = []
    for idx, (category, description) in enumerate(_PBC_TEMPLATE, start=1):
        row = AuditorRequest(
            access_id=access_id,
            tenant_id=tenant_id,
            request_number=f"PBC-{idx:03d}",
            category=category,
            description=description,
            status="open",
            evidence_urls=[],
            created_at=now,
        )
        session.add(row)
        rows.append(row)
    await session.flush()
    return rows


async def respond_to_request(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    request_id: uuid.UUID,
    status: str,
    response_notes: str | None,
    evidence_urls: list[str],
    provided_by: uuid.UUID | None,
) -> AuditorRequest:
    source = (
        await session.execute(
            select(AuditorRequest).where(AuditorRequest.id == request_id, AuditorRequest.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if source is None:
        raise NotFoundError("PBC request not found")

    now = datetime.now(UTC)
    provided_at = now if status == "provided" else None
    row = AuditorRequest(
        access_id=source.access_id,
        tenant_id=tenant_id,
        request_number=source.request_number,
        category=source.category,
        description=source.description,
        status=status,
        due_date=source.due_date,
        response_notes=response_notes,
        evidence_urls=evidence_urls,
        provided_at=provided_at,
        provided_by=provided_by,
        created_at=now,
    )
    session.add(row)
    await session.flush()
    return row


async def get_pbc_tracker(
    session: AsyncSession,
    access_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> dict:
    access = (
        await session.execute(
            select(AuditorPortalAccess).where(AuditorPortalAccess.id == access_id, AuditorPortalAccess.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if access is None:
        raise NotFoundError("Audit engagement not found")

    rows = (
        await session.execute(
            select(AuditorRequest)
            .where(AuditorRequest.access_id == access_id, AuditorRequest.tenant_id == tenant_id)
            .order_by(desc(AuditorRequest.created_at), desc(AuditorRequest.id))
        )
    ).scalars().all()

    latest_by_number: dict[str, AuditorRequest] = {}
    recent_activity: list[AuditorRequest] = []
    status_rank = {
        "open": 1,
        "in_progress": 2,
        "provided": 3,
        "partially_provided": 2,
        "rejected": 1,
    }
    for row in rows:
        recent_activity.append(row)
        existing = latest_by_number.get(row.request_number)
        if existing is None:
            latest_by_number[row.request_number] = row
            continue
        if row.created_at > existing.created_at:
            latest_by_number[row.request_number] = row
            continue
        if row.created_at == existing.created_at:
            if status_rank.get(row.status, 0) > status_rank.get(existing.status, 0):
                latest_by_number[row.request_number] = row

    latest_rows = list(latest_by_number.values())
    total = len(latest_rows)
    open_count = sum(1 for row in latest_rows if row.status == "open")
    in_progress = sum(1 for row in latest_rows if row.status == "in_progress")
    provided = sum(1 for row in latest_rows if row.status == "provided")
    completion_pct = Decimal("0.00") if total == 0 else (Decimal(provided) * Decimal("100") / Decimal(total)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    today = date.today()
    overdue = [row for row in latest_rows if row.due_date is not None and row.due_date < today and row.status != "provided"]

    return {
        "engagement_name": access.engagement_name,
        "total_requests": total,
        "open": open_count,
        "in_progress": in_progress,
        "provided": provided,
        "completion_pct": completion_pct,
        "overdue_requests": overdue,
        "recent_activity": recent_activity[:5],
    }


async def authenticate_auditor(
    session: AsyncSession,
    access_token: str,
) -> AuditorPortalAccess | None:
    token_hash = _hash_token(access_token)
    row = (
        await session.execute(
            select(AuditorPortalAccess).where(AuditorPortalAccess.access_token_hash == token_hash)
        )
    ).scalar_one_or_none()
    if row is None:
        return None

    today = date.today()
    if not row.is_active:
        return None
    if row.valid_from > today or row.valid_until < today:
        return None

    row.last_accessed_at = datetime.now(UTC)
    row.updated_at = datetime.now(UTC)
    await session.flush()
    return row


async def revoke_access(session: AsyncSession, tenant_id: uuid.UUID, access_id: uuid.UUID) -> AuditorPortalAccess:
    row = (
        await session.execute(
            select(AuditorPortalAccess).where(AuditorPortalAccess.id == access_id, AuditorPortalAccess.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError("Access record not found")
    row.is_active = False
    row.updated_at = datetime.now(UTC)
    await session.flush()
    return row


async def list_access(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    stmt = select(AuditorPortalAccess).where(AuditorPortalAccess.tenant_id == tenant_id)
    total = int((await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one())
    rows = (
        await session.execute(
            stmt.order_by(desc(AuditorPortalAccess.created_at), desc(AuditorPortalAccess.id)).limit(limit).offset(offset)
        )
    ).scalars().all()
    return {"data": rows, "total": total, "limit": limit, "offset": offset}


async def create_auditor_request(
    session: AsyncSession,
    access: AuditorPortalAccess,
    category: str,
    description: str,
    due_date: date | None = None,
) -> AuditorRequest:
    max_no = (
        await session.execute(
            select(func.count())
            .select_from(AuditorRequest)
            .where(AuditorRequest.access_id == access.id)
        )
    ).scalar_one()
    next_no = int(max_no) + 1
    row = AuditorRequest(
        access_id=access.id,
        tenant_id=access.tenant_id,
        request_number=f"PBC-{next_no:03d}",
        category=category,
        description=description,
        status="open",
        due_date=due_date,
        evidence_urls=[],
    )
    session.add(row)
    await session.flush()
    return row


__all__ = [
    "grant_auditor_access",
    "seed_pbc_checklist",
    "respond_to_request",
    "get_pbc_tracker",
    "authenticate_auditor",
    "revoke_access",
    "list_access",
    "create_auditor_request",
]
