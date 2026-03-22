from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from financeops.db.models.revenue import RevenueSchedule
from financeops.services.accounting_common.journal_namespace import build_journal_reference
from financeops.services.accounting_common.quantization_policy import quantize_persisted_amount


@dataclass(frozen=True)
class JournalPreviewRow:
    schedule_id: UUID
    contract_id: UUID
    obligation_id: UUID
    journal_reference: str
    entry_date: object
    debit_account: str
    credit_account: str
    amount_reporting_currency: Decimal
    source_contract_reference: str
    parent_reference_id: UUID
    source_reference_id: UUID


def build_revenue_journal_preview(
    *,
    run_id: UUID,
    schedules: list[RevenueSchedule],
) -> list[JournalPreviewRow]:
    ordered = sorted(
        schedules,
        key=lambda row: (
            row.recognition_date,
            str(row.contract_id),
            str(row.obligation_id),
            str(row.id),
        ),
    )
    rows: list[JournalPreviewRow] = []
    for index, schedule in enumerate(ordered, start=1):
        rows.append(
            JournalPreviewRow(
                schedule_id=schedule.id,
                contract_id=schedule.contract_id,
                obligation_id=schedule.obligation_id,
                journal_reference=build_journal_reference(
                    engine_namespace="REV",
                    run_id=run_id,
                    sequence=index,
                ),
                entry_date=schedule.recognition_date,
                debit_account="Accounts Receivable",
                credit_account="Revenue",
                amount_reporting_currency=quantize_persisted_amount(
                    schedule.recognized_amount_reporting_currency
                ),
                source_contract_reference=schedule.source_contract_reference,
                parent_reference_id=schedule.id,
                source_reference_id=schedule.contract_line_item_id,
            )
        )
    return rows

