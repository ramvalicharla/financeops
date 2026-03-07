from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from financeops.db.models.fixed_assets import (
    AssetDepreciationSchedule,
    AssetDisposal,
    AssetImpairment,
)
from financeops.services.accounting_common.journal_namespace import build_journal_reference
from financeops.services.accounting_common.quantization_policy import quantize_persisted_amount


@dataclass(frozen=True)
class FarJournalPreviewRow:
    asset_id: UUID
    depreciation_schedule_id: UUID | None
    impairment_id: UUID | None
    disposal_id: UUID | None
    journal_reference: str
    line_seq: int
    entry_date: date
    debit_account: str
    credit_account: str
    amount_reporting_currency: Decimal
    source_acquisition_reference: str
    parent_reference_id: UUID | None
    source_reference_id: UUID | None


def build_far_journal_preview(
    *,
    run_id: UUID,
    schedule_rows: list[AssetDepreciationSchedule],
    impairment_rows: list[AssetImpairment],
    disposal_rows: list[AssetDisposal],
) -> list[FarJournalPreviewRow]:
    preview: list[FarJournalPreviewRow] = []
    sequence = 1

    for schedule in sorted(
        schedule_rows,
        key=lambda row: (str(row.asset_id), row.depreciation_date, row.period_seq, row.schedule_version_token),
    ):
        amount = quantize_persisted_amount(schedule.depreciation_amount_reporting_currency)
        if amount == Decimal("0.000000"):
            continue
        preview.append(
            FarJournalPreviewRow(
                asset_id=schedule.asset_id,
                depreciation_schedule_id=schedule.id,
                impairment_id=None,
                disposal_id=None,
                journal_reference=build_journal_reference(
                    engine_namespace="fixed_assets",
                    run_id=run_id,
                    sequence=sequence,
                ),
                line_seq=1,
                entry_date=schedule.depreciation_date,
                debit_account="Depreciation Expense",
                credit_account="Accumulated Depreciation",
                amount_reporting_currency=amount,
                source_acquisition_reference=schedule.source_acquisition_reference,
                parent_reference_id=schedule.parent_reference_id,
                source_reference_id=schedule.source_reference_id,
            )
        )
        sequence += 1

    for impairment in sorted(
        impairment_rows,
        key=lambda row: (row.impairment_date, row.created_at, row.id),
    ):
        preview.append(
            FarJournalPreviewRow(
                asset_id=impairment.asset_id,
                depreciation_schedule_id=None,
                impairment_id=impairment.id,
                disposal_id=None,
                journal_reference=build_journal_reference(
                    engine_namespace="fixed_assets",
                    run_id=run_id,
                    sequence=sequence,
                ),
                line_seq=1,
                entry_date=impairment.impairment_date,
                debit_account="Impairment Loss",
                credit_account="Accumulated Impairment",
                amount_reporting_currency=quantize_persisted_amount(impairment.impairment_amount_reporting_currency),
                source_acquisition_reference=impairment.source_acquisition_reference,
                parent_reference_id=impairment.parent_reference_id,
                source_reference_id=impairment.source_reference_id,
            )
        )
        sequence += 1

    for disposal in sorted(
        disposal_rows,
        key=lambda row: (row.disposal_date, row.created_at, row.id),
    ):
        preview.append(
            FarJournalPreviewRow(
                asset_id=disposal.asset_id,
                depreciation_schedule_id=None,
                impairment_id=None,
                disposal_id=disposal.id,
                journal_reference=build_journal_reference(
                    engine_namespace="fixed_assets",
                    run_id=run_id,
                    sequence=sequence,
                ),
                line_seq=1,
                entry_date=disposal.disposal_date,
                debit_account="Cash and Bank",
                credit_account="Fixed Asset Disposal",
                amount_reporting_currency=quantize_persisted_amount(
                    abs(disposal.gain_loss_reporting_currency)
                ),
                source_acquisition_reference=disposal.source_acquisition_reference,
                parent_reference_id=disposal.parent_reference_id,
                source_reference_id=disposal.source_reference_id,
            )
        )
        sequence += 1

    return preview
