from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable
from uuid import UUID

from financeops.services.accounting_common.quantization_policy import quantize_persisted_amount
from financeops.services.lease.lease_registry import RegisteredLease
from financeops.services.lease.liability_schedule import LeaseLiabilityScheduleRow


@dataclass(frozen=True)
class LeaseRouScheduleRow:
    lease_id: UUID
    period_seq: int
    schedule_date: date
    period_year: int
    period_month: int
    opening_rou_reporting_currency: Decimal
    amortization_expense_reporting_currency: Decimal
    impairment_amount_reporting_currency: Decimal
    closing_rou_reporting_currency: Decimal
    schedule_version_token: str
    fx_rate_used: Decimal
    source_lease_reference: str
    parent_reference_id: UUID
    source_reference_id: UUID


def generate_rou_schedule_rows(
    *,
    leases: Iterable[RegisteredLease],
    liability_rows: Iterable[LeaseLiabilityScheduleRow],
    impairments_by_lease: dict[UUID, dict[date, Decimal]] | None = None,
) -> list[LeaseRouScheduleRow]:
    impairment_lookup = impairments_by_lease or {}
    lease_items = sorted(leases, key=lambda item: item.lease_number)
    liability_list = list(liability_rows)

    generated: list[LeaseRouScheduleRow] = []
    for lease in lease_items:
        rows_for_lease = sorted(
            [row for row in liability_list if row.lease_id == lease.lease_id],
            key=lambda row: (row.schedule_date, str(row.source_reference_id)),
        )
        if not rows_for_lease:
            continue

        opening = rows_for_lease[0].opening_liability_reporting_currency
        for idx, liability_row in enumerate(rows_for_lease):
            remaining_periods = max(len(rows_for_lease) - idx, 1)
            amortization = quantize_persisted_amount(opening / Decimal(str(remaining_periods)))
            impairment_amount = quantize_persisted_amount(
                impairment_lookup.get(lease.lease_id, {}).get(liability_row.schedule_date, Decimal("0"))
            )
            closing = quantize_persisted_amount(opening - amortization - impairment_amount)
            generated.append(
                LeaseRouScheduleRow(
                    lease_id=lease.lease_id,
                    period_seq=liability_row.period_seq,
                    schedule_date=liability_row.schedule_date,
                    period_year=liability_row.period_year,
                    period_month=liability_row.period_month,
                    opening_rou_reporting_currency=opening,
                    amortization_expense_reporting_currency=amortization,
                    impairment_amount_reporting_currency=impairment_amount,
                    closing_rou_reporting_currency=closing,
                    schedule_version_token=liability_row.schedule_version_token,
                    fx_rate_used=liability_row.fx_rate_used,
                    source_lease_reference=lease.source_lease_reference,
                    parent_reference_id=lease.lease_id,
                    source_reference_id=liability_row.source_reference_id,
                )
            )
            opening = closing

    generated.sort(key=lambda item: (str(item.lease_id), item.schedule_date, str(item.source_reference_id)))
    return generated

