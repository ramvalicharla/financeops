from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from financeops.db.models.prepaid import PrepaidAmortizationSchedule
from financeops.services.accounting_common.journal_namespace import build_journal_reference
from financeops.services.accounting_common.quantization_policy import quantize_persisted_amount


@dataclass(frozen=True)
class PrepaidJournalPreviewRow:
    prepaid_id: UUID
    schedule_id: UUID
    journal_reference: str
    entry_date: date
    debit_account: str
    credit_account: str
    amount_reporting_currency: Decimal
    source_expense_reference: str
    parent_reference_id: UUID
    source_reference_id: UUID | None


def build_prepaid_journal_preview(
    *,
    run_id: UUID,
    schedule_rows: list[PrepaidAmortizationSchedule],
) -> list[PrepaidJournalPreviewRow]:
    ordered = sorted(
        schedule_rows,
        key=lambda row: (
            row.amortization_date,
            str(row.prepaid_id),
            row.period_seq,
            str(row.id),
        ),
    )
    preview: list[PrepaidJournalPreviewRow] = []
    for index, row in enumerate(ordered, start=1):
        preview.append(
            PrepaidJournalPreviewRow(
                prepaid_id=row.prepaid_id,
                schedule_id=row.id,
                journal_reference=build_journal_reference(
                    engine_namespace="PPD",
                    run_id=run_id,
                    sequence=index,
                ),
                entry_date=row.amortization_date,
                debit_account="Prepaid Expense",
                credit_account="Prepaid Asset",
                amount_reporting_currency=quantize_persisted_amount(
                    row.amortized_amount_reporting_currency
                ),
                source_expense_reference=row.source_expense_reference,
                parent_reference_id=row.id,
                source_reference_id=row.source_reference_id,
            )
        )
    return preview

