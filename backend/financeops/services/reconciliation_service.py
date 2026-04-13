from __future__ import annotations

import logging
import uuid
from decimal import Decimal

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.data_quality_engine import (
    DataQualityValidationService,
    DatasetValidationRules,
    ageing_line_rules,
    inventory_snapshot_rules,
    reconciliation_cross_account_rule,
    reconciliation_gl_rules,
    reconciliation_tb_rules,
)
from financeops.db.models.reconciliation import GlEntry, ReconItem, TrialBalanceRow
from financeops.db.models.working_capital import WorkingCapitalSnapshot
from financeops.modules.working_capital.models import APLineItem, ARLineItem, WCSnapshot
from financeops.services.audit_writer import AuditEvent, AuditWriter

log = logging.getLogger(__name__)

_ZERO = Decimal("0")
_DEFAULT_AGEING_TOLERANCE = {
    "0-30": Decimal("0"),
    "31-60": Decimal("100"),
    "61-90": Decimal("500"),
    "90+": Decimal("1000"),
}
_AGEING_BUCKETS: tuple[tuple[str, int, int | None], ...] = (
    ("0-30", 0, 30),
    ("31-60", 31, 60),
    ("61-90", 61, 90),
    ("90+", 91, None),
)


async def create_gl_entry(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    period_year: int,
    period_month: int,
    entity_name: str,
    account_code: str,
    account_name: str,
    debit_amount: Decimal,
    credit_amount: Decimal,
    uploaded_by: uuid.UUID,
    description: str | None = None,
    source_ref: str | None = None,
    currency: str = "USD",
) -> GlEntry:
    """Insert a single GL entry (INSERT ONLY)."""
    entry = await AuditWriter.insert_financial_record(
        session,
        model_class=GlEntry,
        tenant_id=tenant_id,
        record_data={
            "tenant_id": str(tenant_id),
            "period_year": period_year,
            "period_month": period_month,
            "entity_name": entity_name,
            "account_code": account_code,
            "debit_amount": str(debit_amount),
            "credit_amount": str(credit_amount),
        },
        values={
            "period_year": period_year,
            "period_month": period_month,
            "entity_name": entity_name,
            "account_code": account_code,
            "account_name": account_name,
            "debit_amount": debit_amount,
            "credit_amount": credit_amount,
            "description": description,
            "source_ref": source_ref,
            "currency": currency,
            "uploaded_by": uploaded_by,
        },
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=uploaded_by,
            action="recon.gl_entry.created",
            resource_type="gl_entry",
            resource_name=account_code,
            new_value={
                "entity_name": entity_name,
                "period_year": period_year,
                "period_month": period_month,
            },
        ),
    )
    return entry


async def create_tb_row(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    period_year: int,
    period_month: int,
    entity_name: str,
    account_code: str,
    account_name: str,
    opening_balance: Decimal,
    period_debit: Decimal,
    period_credit: Decimal,
    closing_balance: Decimal,
    uploaded_by: uuid.UUID,
    currency: str = "USD",
) -> TrialBalanceRow:
    """Insert a single TB row (INSERT ONLY)."""
    row = await AuditWriter.insert_financial_record(
        session,
        model_class=TrialBalanceRow,
        tenant_id=tenant_id,
        record_data={
            "tenant_id": str(tenant_id),
            "period_year": period_year,
            "period_month": period_month,
            "entity_name": entity_name,
            "account_code": account_code,
            "closing_balance": str(closing_balance),
        },
        values={
            "period_year": period_year,
            "period_month": period_month,
            "entity_name": entity_name,
            "account_code": account_code,
            "account_name": account_name,
            "opening_balance": opening_balance,
            "period_debit": period_debit,
            "period_credit": period_credit,
            "closing_balance": closing_balance,
            "currency": currency,
            "uploaded_by": uploaded_by,
        },
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=uploaded_by,
            action="recon.tb_row.created",
            resource_type="trial_balance_row",
            resource_name=account_code,
            new_value={
                "entity_name": entity_name,
                "period_year": period_year,
                "period_month": period_month,
            },
        ),
    )
    return row


def _period_label(period_year: int, period_month: int) -> str:
    return f"{period_year:04d}-{period_month:02d}"


def _normalize_decimal(value: Decimal | str | int | None) -> Decimal:
    return Decimal(str(value if value is not None else "0"))


def _format_amount(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01")), "f")


def _classify_ageing_bucket(days_overdue: int) -> str:
    if days_overdue <= 30:
        return "0-30"
    if days_overdue <= 60:
        return "31-60"
    if days_overdue <= 90:
        return "61-90"
    return "90+"


def _resolve_ageing_tolerance(
    *, tolerance_by_bucket: dict[str, Decimal | str] | None
) -> dict[str, Decimal]:
    resolved = dict(_DEFAULT_AGEING_TOLERANCE)
    if tolerance_by_bucket:
        for bucket, value in tolerance_by_bucket.items():
            if bucket in resolved:
                resolved[bucket] = _normalize_decimal(value)
    return resolved


async def _create_recon_item(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    period_year: int,
    period_month: int,
    entity_name: str,
    account_code: str,
    account_name: str,
    gl_total: Decimal,
    tb_closing_balance: Decimal,
    difference: Decimal,
    run_by: uuid.UUID,
    recon_type: str,
    evidence: dict[str, object] | None = None,
) -> ReconItem:
    return await AuditWriter.insert_financial_record(
        session,
        model_class=ReconItem,
        tenant_id=tenant_id,
        record_data={
            "tenant_id": str(tenant_id),
            "period_year": period_year,
            "period_month": period_month,
            "entity_name": entity_name,
            "account_code": account_code,
            "gl_total": str(gl_total),
            "tb_closing_balance": str(tb_closing_balance),
            "difference": str(difference),
            "recon_type": recon_type,
        },
        values={
            "period_year": period_year,
            "period_month": period_month,
            "entity_name": entity_name,
            "account_code": account_code,
            "account_name": account_name,
            "gl_total": gl_total,
            "tb_closing_balance": tb_closing_balance,
            "difference": difference,
            "status": "open",
            "recon_type": recon_type,
            "run_by": run_by,
        },
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=run_by,
            action="recon.break.created",
            resource_type="recon_item",
            resource_name=account_code,
            new_value={
                "entity_name": entity_name,
                "period_year": period_year,
                "period_month": period_month,
                "recon_type": recon_type,
                "evidence": evidence or {},
            },
        ),
    )


async def _audit_reconciliation_run(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    run_by: uuid.UUID,
    resource_id: str,
    resource_name: str,
    reconciliation_type: str,
    validation_reports: list[dict[str, object]],
    input_datasets: dict[str, object],
    result_summary: dict[str, object],
) -> None:
    await AuditWriter.flush_with_audit(
        session,
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=run_by,
            action="recon.validation_and_run.completed",
            resource_type="reconciliation_run",
            resource_id=resource_id,
            resource_name=resource_name,
            new_value={
                "reconciliation_type": reconciliation_type,
                "input_datasets": input_datasets,
                "validation_reports": validation_reports,
                "result_summary": result_summary,
            },
        ),
    )


async def _sum_gl_balance_for_accounts(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    period_year: int,
    period_month: int,
    account_codes: list[str],
    entity_name: str | None = None,
) -> Decimal:
    if not account_codes:
        return _ZERO
    stmt = select(func.coalesce(func.sum(GlEntry.debit_amount - GlEntry.credit_amount), 0)).where(
        GlEntry.tenant_id == tenant_id,
        GlEntry.period_year == period_year,
        GlEntry.period_month == period_month,
        GlEntry.account_code.in_(account_codes),
    )
    if entity_name:
        stmt = stmt.where(GlEntry.entity_name == entity_name)
    result = await session.execute(stmt)
    return Decimal(str(result.scalar_one() or "0"))


async def _load_gl_rows_for_accounts(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    period_year: int,
    period_month: int,
    account_codes: list[str],
    entity_name: str | None = None,
) -> list[GlEntry]:
    if not account_codes:
        return []
    stmt = select(GlEntry).where(
        GlEntry.tenant_id == tenant_id,
        GlEntry.period_year == period_year,
        GlEntry.period_month == period_month,
        GlEntry.account_code.in_(account_codes),
    )
    if entity_name:
        stmt = stmt.where(GlEntry.entity_name == entity_name)
    return list((await session.execute(stmt)).scalars().all())


async def _load_ageing_snapshot(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    period: str,
    snapshot_id: uuid.UUID | None = None,
) -> WCSnapshot:
    stmt = select(WCSnapshot).where(WCSnapshot.tenant_id == tenant_id)
    if snapshot_id is not None:
        stmt = stmt.where(WCSnapshot.id == snapshot_id)
    else:
        stmt = stmt.where(WCSnapshot.period == period)
    snapshot = (
        await session.execute(
            stmt.order_by(WCSnapshot.snapshot_date.desc(), WCSnapshot.id.desc()).limit(1)
        )
    ).scalar_one_or_none()
    if snapshot is None:
        raise ValueError("Ageing snapshot not found for reconciliation")
    return snapshot


async def _load_inventory_snapshot(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    period_year: int,
    period_month: int,
    entity_name: str | None,
) -> WorkingCapitalSnapshot:
    stmt = select(WorkingCapitalSnapshot).where(
        WorkingCapitalSnapshot.tenant_id == tenant_id,
        WorkingCapitalSnapshot.period_year == period_year,
        WorkingCapitalSnapshot.period_month == period_month,
    )
    if entity_name:
        stmt = stmt.where(WorkingCapitalSnapshot.entity_name == entity_name)
    snapshot = (
        await session.execute(
            stmt.order_by(WorkingCapitalSnapshot.created_at.desc(), WorkingCapitalSnapshot.id.desc()).limit(1)
        )
    ).scalar_one_or_none()
    if snapshot is None:
        raise ValueError("Inventory valuation snapshot not found for reconciliation")
    return snapshot


async def run_ageing_gl_reconciliation(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    period_year: int,
    period_month: int,
    ageing_type: str,
    gl_account_mapping: dict[str, list[str]],
    run_by: uuid.UUID,
    entity_name: str | None = None,
    tolerance_by_bucket: dict[str, Decimal | str] | None = None,
    snapshot_id: uuid.UUID | None = None,
) -> dict[str, object]:
    if ageing_type not in {"ar", "ap"}:
        raise ValueError("ageing_type must be 'ar' or 'ap'")

    period = _period_label(period_year, period_month)
    snapshot = await _load_ageing_snapshot(
        session,
        tenant_id=tenant_id,
        period=period,
        snapshot_id=snapshot_id,
    )
    line_model = ARLineItem if ageing_type == "ar" else APLineItem
    party_field = "customer_name" if ageing_type == "ar" else "vendor_name"
    line_rows = list(
        (
            await session.execute(
                select(line_model).where(
                    line_model.tenant_id == tenant_id,
                    line_model.snapshot_id == snapshot.id,
                )
            )
        ).scalars().all()
    )

    validation_service = DataQualityValidationService()
    ageing_validation = validation_service.validate_dataset(
        rules=ageing_line_rules(
            table_name="ar_line_items" if ageing_type == "ar" else "ap_line_items",
            party_field=party_field,
        ),
        rows=line_rows,
    )
    validation_service.raise_if_fail(report=ageing_validation)

    tolerance_map = _resolve_ageing_tolerance(tolerance_by_bucket=tolerance_by_bucket)
    bucket_totals = {bucket: _ZERO for bucket, _, _ in _AGEING_BUCKETS}
    bucket_evidence: dict[str, list[dict[str, object]]] = {bucket: [] for bucket, _, _ in _AGEING_BUCKETS}

    for row in line_rows:
        bucket = _classify_ageing_bucket(int(row.days_overdue))
        amount = _normalize_decimal(row.amount_base_currency)
        bucket_totals[bucket] += amount
        bucket_evidence[bucket].append(
            {
                "invoice_number": row.invoice_number,
                "days_overdue": int(row.days_overdue),
                "amount_base_currency": format(amount, "f"),
                "currency": row.currency,
            }
        )

    bucket_results: list[dict[str, object]] = []
    items: list[ReconItem] = []
    gl_validation_reports: list[dict[str, object]] = []

    for bucket, _, _ in _AGEING_BUCKETS:
        account_codes = sorted(gl_account_mapping.get(bucket, []))
        gl_rows = await _load_gl_rows_for_accounts(
            session,
            tenant_id=tenant_id,
            period_year=period_year,
            period_month=period_month,
            account_codes=account_codes,
            entity_name=entity_name,
        )
        gl_validation = validation_service.validate_dataset(
            rules=reconciliation_gl_rules(),
            rows=gl_rows,
        )
        validation_service.raise_if_fail(report=gl_validation)
        gl_validation_reports.append(gl_validation["validation_report"])

        ageing_total = bucket_totals[bucket]
        gl_balance = await _sum_gl_balance_for_accounts(
            session,
            tenant_id=tenant_id,
            period_year=period_year,
            period_month=period_month,
            account_codes=account_codes,
            entity_name=entity_name,
        )
        variance = ageing_total - gl_balance
        tolerance = tolerance_map[bucket]
        within_tolerance = variance.copy_abs() <= tolerance
        result = {
            "bucket": bucket,
            f"{ageing_type}_total": _format_amount(ageing_total),
            "gl_balance": _format_amount(gl_balance),
            "variance": _format_amount(variance),
            "within_tolerance": within_tolerance,
            "tolerance": _format_amount(tolerance),
            "evidence": bucket_evidence[bucket],
            "gl_account_codes": account_codes,
        }
        bucket_results.append(result)

        if not within_tolerance:
            item = await _create_recon_item(
                session,
                tenant_id=tenant_id,
                period_year=period_year,
                period_month=period_month,
                entity_name=entity_name or "working_capital",
                account_code=f"{ageing_type.upper()}_AGEING_{bucket}",
                account_name=f"{ageing_type.upper()} ageing bucket {bucket}",
                gl_total=gl_balance,
                tb_closing_balance=ageing_total,
                difference=variance,
                run_by=run_by,
                recon_type=f"{ageing_type}_ageing_gl",
                evidence={
                    "bucket": bucket,
                    "tolerance": _format_amount(tolerance),
                    "source_snapshot_id": str(snapshot.id),
                    "gl_account_codes": account_codes,
                    "bucket_evidence": bucket_evidence[bucket],
                },
            )
            items.append(item)

    validation_reports = [ageing_validation["validation_report"], *gl_validation_reports]
    await _audit_reconciliation_run(
        session,
        tenant_id=tenant_id,
        run_by=run_by,
        resource_id=f"{ageing_type}:{period}:{entity_name or 'working_capital'}",
        resource_name=entity_name or "working_capital",
        reconciliation_type=f"{ageing_type}_ageing_gl",
        validation_reports=validation_reports,
        input_datasets={
            "ageing_snapshot_id": str(snapshot.id),
            "gl_account_mapping": gl_account_mapping,
            "entity_name": entity_name,
        },
        result_summary={
            "bucket_results": bucket_results,
            "breaks_found": len(items),
        },
    )
    return {
        "bucket_results": bucket_results,
        "items": items,
        "validation_reports": validation_reports,
    }


async def run_inventory_gl_reconciliation(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    period_year: int,
    period_month: int,
    entity_name: str,
    gl_account_codes: list[str],
    run_by: uuid.UUID,
) -> dict[str, object]:
    if not gl_account_codes:
        raise ValueError("Explicit GL account mapping is required for inventory reconciliation")

    snapshot = await _load_inventory_snapshot(
        session,
        tenant_id=tenant_id,
        period_year=period_year,
        period_month=period_month,
        entity_name=entity_name,
    )
    validation_service = DataQualityValidationService()
    inventory_validation = validation_service.validate_dataset(
        rules=inventory_snapshot_rules(),
        rows=[snapshot],
    )
    validation_service.raise_if_fail(report=inventory_validation)

    gl_rows = await _load_gl_rows_for_accounts(
        session,
        tenant_id=tenant_id,
        period_year=period_year,
        period_month=period_month,
        account_codes=gl_account_codes,
        entity_name=entity_name,
    )
    gl_validation = validation_service.validate_dataset(
        rules=reconciliation_gl_rules(),
        rows=gl_rows,
    )
    validation_service.raise_if_fail(report=gl_validation)

    inventory_value = _normalize_decimal(snapshot.inventory)
    gl_balance = await _sum_gl_balance_for_accounts(
        session,
        tenant_id=tenant_id,
        period_year=period_year,
        period_month=period_month,
        account_codes=gl_account_codes,
        entity_name=entity_name,
    )
    variance = inventory_value - gl_balance
    status = "MATCH" if variance == _ZERO else "MISMATCH"
    item: ReconItem | None = None
    if status == "MISMATCH":
        item = await _create_recon_item(
            session,
            tenant_id=tenant_id,
            period_year=period_year,
            period_month=period_month,
            entity_name=entity_name,
            account_code="INVENTORY_GL",
            account_name="Inventory valuation vs GL",
            gl_total=gl_balance,
            tb_closing_balance=inventory_value,
            difference=variance,
            run_by=run_by,
            recon_type="inventory_gl",
            evidence={
                "inventory_snapshot_id": str(snapshot.id),
                "gl_account_codes": gl_account_codes,
                "inventory_value": format(inventory_value, "f"),
                "gl_balance": format(gl_balance, "f"),
            },
        )

    validation_reports = [
        inventory_validation["validation_report"],
        gl_validation["validation_report"],
    ]
    result = {
        "inventory_value": _format_amount(inventory_value),
        "gl_balance": _format_amount(gl_balance),
        "variance": _format_amount(variance),
        "status": status,
        "gl_account_codes": gl_account_codes,
    }
    await _audit_reconciliation_run(
        session,
        tenant_id=tenant_id,
        run_by=run_by,
        resource_id=f"inventory:{period_year:04d}-{period_month:02d}:{entity_name}",
        resource_name=entity_name,
        reconciliation_type="inventory_gl",
        validation_reports=validation_reports,
        input_datasets={
            "inventory_snapshot_id": str(snapshot.id),
            "gl_account_codes": gl_account_codes,
        },
        result_summary=result,
    )
    return {
        "result": result,
        "item": item,
        "validation_reports": validation_reports,
    }


async def run_gl_tb_reconciliation(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    period_year: int,
    period_month: int,
    entity_name: str,
    run_by: uuid.UUID,
) -> list[ReconItem]:
    """
    Compare GL entry sums vs TB closing balances for the period.
    Creates a ReconItem for every account with a non-zero difference.
    Returns list of ReconItems created (only breaks where difference != 0).
    """
    validation_service = DataQualityValidationService()
    gl_entry_rows = list(
        (
            await session.execute(
                select(GlEntry).where(
                    GlEntry.tenant_id == tenant_id,
                    GlEntry.period_year == period_year,
                    GlEntry.period_month == period_month,
                    GlEntry.entity_name == entity_name,
                )
            )
        ).scalars().all()
    )
    tb_rows = list(
        (
            await session.execute(
                select(TrialBalanceRow).where(
                    TrialBalanceRow.tenant_id == tenant_id,
                    TrialBalanceRow.period_year == period_year,
                    TrialBalanceRow.period_month == period_month,
                    TrialBalanceRow.entity_name == entity_name,
                )
            )
        ).scalars().all()
    )
    gl_validation = validation_service.validate_dataset(
        rules=reconciliation_gl_rules(),
        rows=gl_entry_rows,
    )
    validation_service.raise_if_fail(report=gl_validation)
    tb_validation = validation_service.validate_dataset(
        rules=reconciliation_tb_rules(),
        rows=tb_rows,
    )
    validation_service.raise_if_fail(report=tb_validation)
    gl_cross_validation = validation_service.validate_dataset(
        rules=DatasetValidationRules(
            table="gl_entries",
            dataset_rules=(
                reconciliation_cross_account_rule(
                    other_rows=[validation_service._normalize_row(row) for row in tb_rows],
                    other_table="trial_balance_rows",
                ),
            ),
        ),
        rows=gl_entry_rows,
    )
    tb_cross_validation = validation_service.validate_dataset(
        rules=DatasetValidationRules(
            table="trial_balance_rows",
            dataset_rules=(
                reconciliation_cross_account_rule(
                    other_rows=[validation_service._normalize_row(row) for row in gl_entry_rows],
                    other_table="gl_entries",
                ),
            ),
        ),
        rows=tb_rows,
    )
    if any(
        report["validation_report"]["status"] != "PASS"
        for report in (gl_validation, tb_validation, gl_cross_validation, tb_cross_validation)
    ):
        await AuditWriter.flush_with_audit(
            session,
            audit=AuditEvent(
                tenant_id=tenant_id,
                user_id=run_by,
                action="recon.data_quality.validated",
                resource_type="reconciliation_run",
                resource_id=f"{entity_name}:{period_year}-{period_month:02d}",
                resource_name=entity_name,
                new_value={
                    "reports": [
                        gl_validation["validation_report"],
                        tb_validation["validation_report"],
                        gl_cross_validation["validation_report"],
                        tb_cross_validation["validation_report"],
                    ]
                },
            ),
        )

    # Sum GL entries per account
    gl_result = await session.execute(
        select(
            GlEntry.account_code,
            GlEntry.account_name,
            func.sum(GlEntry.debit_amount - GlEntry.credit_amount).label("net"),
        )
        .where(
            GlEntry.tenant_id == tenant_id,
            GlEntry.period_year == period_year,
            GlEntry.period_month == period_month,
            GlEntry.entity_name == entity_name,
        )
        .group_by(GlEntry.account_code, GlEntry.account_name)
    )
    gl_by_account: dict[str, tuple[str, Decimal]] = {
        row.account_code: (row.account_name, row.net or Decimal("0"))
        for row in gl_result
    }

    # Get TB closing balances per account
    tb_result = await session.execute(
        select(
            TrialBalanceRow.account_code,
            TrialBalanceRow.account_name,
            TrialBalanceRow.closing_balance,
        )
        .where(
            TrialBalanceRow.tenant_id == tenant_id,
            TrialBalanceRow.period_year == period_year,
            TrialBalanceRow.period_month == period_month,
            TrialBalanceRow.entity_name == entity_name,
        )
    )
    tb_by_account: dict[str, tuple[str, Decimal]] = {
        row.account_code: (row.account_name, row.closing_balance)
        for row in tb_result
    }

    # Find all accounts (union of GL and TB)
    all_accounts = set(gl_by_account.keys()) | set(tb_by_account.keys())

    items: list[ReconItem] = []
    for account_code in sorted(all_accounts):
        gl_account_name, gl_total = gl_by_account.get(account_code, ("", Decimal("0")))
        tb_account_name, tb_closing = tb_by_account.get(
            account_code, ("", Decimal("0"))
        )
        account_name = gl_account_name or tb_account_name

        difference = tb_closing - gl_total
        # Only create items where there's a break (difference != 0)
        if difference != Decimal("0"):
            item = await _create_recon_item(
                session,
                tenant_id=tenant_id,
                period_year=period_year,
                period_month=period_month,
                entity_name=entity_name,
                account_code=account_code,
                account_name=account_name,
                gl_total=gl_total,
                tb_closing_balance=tb_closing,
                difference=difference,
                run_by=run_by,
                recon_type="gl_tb",
            )
            items.append(item)

    await _audit_reconciliation_run(
        session,
        tenant_id=tenant_id,
        run_by=run_by,
        resource_id=f"gl_tb:{entity_name}:{period_year:04d}-{period_month:02d}",
        resource_name=entity_name,
        reconciliation_type="gl_tb",
        validation_reports=[
            gl_validation["validation_report"],
            tb_validation["validation_report"],
            gl_cross_validation["validation_report"],
            tb_cross_validation["validation_report"],
        ],
        input_datasets={
            "entity_name": entity_name,
            "period": _period_label(period_year, period_month),
            "gl_accounts": sorted(gl_by_account.keys()),
            "tb_accounts": sorted(tb_by_account.keys()),
        },
        result_summary={
            "breaks_found": len(items),
            "account_count": len(all_accounts),
        },
    )

    log.info(
        "Reconciliation run: tenant=%s entity=%s period=%d/%d breaks=%d",
        str(tenant_id)[:8], entity_name, period_year, period_month, len(items),
    )
    return items


async def list_recon_items(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    period_year: int | None = None,
    period_month: int | None = None,
    entity_name: str | None = None,
    status: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[ReconItem]:
    stmt = select(ReconItem).where(ReconItem.tenant_id == tenant_id)
    if period_year is not None:
        stmt = stmt.where(ReconItem.period_year == period_year)
    if period_month is not None:
        stmt = stmt.where(ReconItem.period_month == period_month)
    if entity_name:
        stmt = stmt.where(ReconItem.entity_name == entity_name)
    if status:
        stmt = stmt.where(ReconItem.status == status)
    stmt = stmt.order_by(desc(ReconItem.created_at)).limit(limit).offset(offset)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def list_gl_entries(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    period_year: int | None = None,
    period_month: int | None = None,
    entity_name: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[GlEntry]:
    stmt = select(GlEntry).where(GlEntry.tenant_id == tenant_id)
    if period_year is not None:
        stmt = stmt.where(GlEntry.period_year == period_year)
    if period_month is not None:
        stmt = stmt.where(GlEntry.period_month == period_month)
    if entity_name:
        stmt = stmt.where(GlEntry.entity_name == entity_name)
    stmt = stmt.order_by(desc(GlEntry.created_at)).limit(limit).offset(offset)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def list_tb_rows(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    period_year: int | None = None,
    period_month: int | None = None,
    entity_name: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[TrialBalanceRow]:
    stmt = select(TrialBalanceRow).where(TrialBalanceRow.tenant_id == tenant_id)
    if period_year is not None:
        stmt = stmt.where(TrialBalanceRow.period_year == period_year)
    if period_month is not None:
        stmt = stmt.where(TrialBalanceRow.period_month == period_month)
    if entity_name:
        stmt = stmt.where(TrialBalanceRow.entity_name == entity_name)
    stmt = stmt.order_by(TrialBalanceRow.account_code).limit(limit).offset(offset)
    result = await session.execute(stmt)
    return list(result.scalars().all())

