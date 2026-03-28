from __future__ import annotations

import csv
import io
import uuid
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.accounting_approvals import AccountingJVApproval
from financeops.db.models.accounting_jv import AccountingJVAggregate
from financeops.db.models.accounting_notifications import (
    AccountingAuditExportRun,
    ExportFormat,
    ExportType,
)
from financeops.db.models.erp_push import ErpPushRun


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


async def create_audit_export(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID | None,
    export_type: str,
    export_format: str,
    requested_by: uuid.UUID,
    fiscal_year: int | None = None,
    fiscal_period_from: int | None = None,
    fiscal_period_to: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    filters: dict[str, Any] | None = None,
) -> AccountingAuditExportRun:
    run_id = uuid.uuid4()
    now = _utcnow()

    status = "FAILED"
    r2_key: str | None = None
    row_count: int | None = None
    error_message: str | None = None

    try:
        csv_content, row_count = await _generate_export(
            db,
            tenant_id=tenant_id,
            entity_id=entity_id,
            export_type=export_type,
            fiscal_year=fiscal_year,
            date_from=date_from,
            date_to=date_to,
        )
        export_format_upper = export_format.upper()
        if export_format_upper == ExportFormat.PDF:
            payload = _csv_to_pdf_stub(csv_content).encode("utf-8")
            extension = "pdf"
            content_type = "application/pdf"
        else:
            payload = csv_content.encode("utf-8")
            extension = "csv"
            content_type = "text/csv"

        r2_key = (
            f"audit_exports/{tenant_id}/{run_id}/"
            f"{export_type.lower()}_{now.strftime('%Y%m%d_%H%M%S')}.{extension}"
        )
        from financeops.storage.provider import get_storage

        storage = get_storage()
        storage.upload_file(
            file_bytes=payload,
            key=r2_key,
            content_type=content_type,
            tenant_id=str(tenant_id),
            uploaded_by=str(requested_by),
        )
        status = "COMPLETED"
    except Exception as exc:  # noqa: BLE001
        error_message = str(exc)

    run = AccountingAuditExportRun(
        id=run_id,
        tenant_id=tenant_id,
        chain_hash="",
        previous_hash="",
        entity_id=entity_id,
        export_type=export_type,
        export_format=export_format.upper(),
        fiscal_year=fiscal_year,
        fiscal_period_from=fiscal_period_from,
        fiscal_period_to=fiscal_period_to,
        date_from=date_from,
        date_to=date_to,
        filters=filters,
        status=status,
        r2_key=r2_key,
        row_count=row_count,
        error_message=error_message,
        requested_by=requested_by,
        completed_at=_utcnow(),
        created_at=now,
    )
    db.add(run)
    await db.flush()
    return run


def _csv_to_pdf_stub(csv_content: str) -> str:
    return (
        "FinanceOps Audit Export (PDF Stub)\n"
        "Rendering of tabular PDF layout is planned post-v3.\n\n"
        f"{csv_content}"
    )


async def _generate_export(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID | None,
    export_type: str,
    fiscal_year: int | None,
    date_from: date | None,
    date_to: date | None,
) -> tuple[str, int]:
    if export_type == ExportType.JV_LIFECYCLE:
        return await _export_jv_lifecycle(
            db,
            tenant_id=tenant_id,
            entity_id=entity_id,
            fiscal_year=fiscal_year,
            date_from=date_from,
            date_to=date_to,
        )
    if export_type == ExportType.APPROVALS:
        return await _export_approvals(
            db,
            tenant_id=tenant_id,
            entity_id=entity_id,
            date_from=date_from,
            date_to=date_to,
        )
    if export_type == ExportType.ERP_PUSH:
        return await _export_push_runs(
            db,
            tenant_id=tenant_id,
            entity_id=entity_id,
            date_from=date_from,
            date_to=date_to,
        )
    return "no_data\n", 0


async def _export_jv_lifecycle(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID | None,
    fiscal_year: int | None,
    date_from: date | None,
    date_to: date | None,
) -> tuple[str, int]:
    stmt = select(AccountingJVAggregate).where(AccountingJVAggregate.tenant_id == tenant_id)
    if entity_id is not None:
        stmt = stmt.where(AccountingJVAggregate.entity_id == entity_id)
    if fiscal_year is not None:
        stmt = stmt.where(AccountingJVAggregate.fiscal_year == fiscal_year)
    if date_from is not None:
        stmt = stmt.where(AccountingJVAggregate.period_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(AccountingJVAggregate.period_date <= date_to)

    rows = list((await db.execute(stmt)).scalars().all())

    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "jv_number",
            "status",
            "period_date",
            "fiscal_year",
            "fiscal_period",
            "total_debit",
            "total_credit",
            "currency",
            "created_by",
            "submitted_at",
            "first_reviewed_at",
            "decided_at",
            "resubmission_count",
        ],
    )
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                "jv_number": row.jv_number,
                "status": row.status,
                "period_date": str(row.period_date),
                "fiscal_year": row.fiscal_year,
                "fiscal_period": row.fiscal_period,
                "total_debit": str(row.total_debit),
                "total_credit": str(row.total_credit),
                "currency": row.currency,
                "created_by": str(row.created_by),
                "submitted_at": str(row.submitted_at) if row.submitted_at else "",
                "first_reviewed_at": str(row.first_reviewed_at) if row.first_reviewed_at else "",
                "decided_at": str(row.decided_at) if row.decided_at else "",
                "resubmission_count": row.resubmission_count,
            }
        )
    return output.getvalue(), len(rows)


async def _export_approvals(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID | None,
    date_from: date | None,
    date_to: date | None,
) -> tuple[str, int]:
    stmt = select(AccountingJVApproval).where(AccountingJVApproval.tenant_id == tenant_id)
    if entity_id is not None:
        stmt = stmt.join(AccountingJVAggregate, AccountingJVAggregate.id == AccountingJVApproval.jv_id).where(
            AccountingJVAggregate.entity_id == entity_id
        )
    if date_from is not None:
        stmt = stmt.where(AccountingJVApproval.acted_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(AccountingJVApproval.acted_at <= date_to)

    rows = list((await db.execute(stmt)).scalars().all())

    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "jv_id",
            "jv_version",
            "acted_by",
            "actor_role",
            "decision",
            "decision_reason",
            "approval_level",
            "amount_threshold",
            "acted_at",
        ],
    )
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                "jv_id": str(row.jv_id),
                "jv_version": row.jv_version,
                "acted_by": str(row.acted_by),
                "actor_role": row.actor_role,
                "decision": row.decision,
                "decision_reason": row.decision_reason or "",
                "approval_level": row.approval_level,
                "amount_threshold": str(row.amount_threshold) if row.amount_threshold is not None else "",
                "acted_at": str(row.acted_at),
            }
        )
    return output.getvalue(), len(rows)


async def _export_push_runs(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID | None,
    date_from: date | None,
    date_to: date | None,
) -> tuple[str, int]:
    stmt = select(ErpPushRun).where(ErpPushRun.tenant_id == tenant_id)
    if entity_id is not None:
        stmt = stmt.join(AccountingJVAggregate, AccountingJVAggregate.id == ErpPushRun.jv_id).where(
            AccountingJVAggregate.entity_id == entity_id
        )
    if date_from is not None:
        stmt = stmt.where(ErpPushRun.created_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(ErpPushRun.created_at <= date_to)

    rows = list((await db.execute(stmt)).scalars().all())

    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "jv_id",
            "connector_type",
            "status",
            "external_journal_id",
            "error_code",
            "error_category",
            "attempt_number",
            "created_at",
        ],
    )
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                "jv_id": str(row.jv_id),
                "connector_type": row.connector_type,
                "status": row.status,
                "external_journal_id": row.external_journal_id or "",
                "error_code": row.error_code or "",
                "error_category": row.error_category or "",
                "attempt_number": row.attempt_number,
                "created_at": str(row.created_at),
            }
        )
    return output.getvalue(), len(rows)

