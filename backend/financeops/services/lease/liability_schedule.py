from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import ValidationError
from financeops.services.accounting_common.accounting_errors import AccountingValidationError
from financeops.services.accounting_common.error_codes import MISSING_LOCKED_RATE
from financeops.schemas.lease import LeaseRateMode
from financeops.services.accounting_common.quantization_policy import (
    quantize_persisted_amount,
    quantize_rate,
)
from financeops.services.fx import list_manual_monthly_rates, resolve_selected_rate
from financeops.services.fx.normalization import normalize_currency_code
from financeops.services.lease.interest_engine import compute_period_interest
from financeops.services.lease.lease_registry import RegisteredLease
from financeops.services.lease.payment_schedule import RegisteredLeasePayment, build_payment_timeline
from financeops.services.lease.pv_calculator import PresentValueResult, calculate_present_value
from financeops.services.lease.remeasurement import build_schedule_version_token


class MissingLockedRateError(AccountingValidationError):
    def __init__(self, message: str) -> None:
        super().__init__(error_code=MISSING_LOCKED_RATE, message=message)


@dataclass(frozen=True)
class LeaseLiabilityScheduleRow:
    lease_id: UUID
    payment_id: UUID | None
    period_seq: int
    schedule_date: date
    period_year: int
    period_month: int
    opening_liability_reporting_currency: Decimal
    interest_expense_reporting_currency: Decimal
    payment_amount_reporting_currency: Decimal
    closing_liability_reporting_currency: Decimal
    schedule_version_token: str
    fx_rate_used: Decimal
    source_lease_reference: str
    parent_reference_id: UUID
    source_reference_id: UUID


@dataclass(frozen=True)
class LeaseLiabilityGenerationOutput:
    rows: list[LeaseLiabilityScheduleRow]
    present_values: dict[UUID, PresentValueResult]
    root_schedule_version_tokens: dict[UUID, str]


def _month_end_for(value: date) -> date:
    _, last_day = calendar.monthrange(value.year, value.month)
    return date(value.year, value.month, last_day)


async def resolve_lease_fx_rate(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    lease_currency: str,
    reporting_currency: str,
    schedule_date: date,
    rate_mode: LeaseRateMode,
) -> Decimal:
    base = normalize_currency_code(lease_currency)
    quote = normalize_currency_code(reporting_currency)
    if base == quote:
        return Decimal("1.000000")

    if rate_mode == LeaseRateMode.month_end_locked:
        month_end = _month_end_for(schedule_date)
        rows = await list_manual_monthly_rates(
            session,
            tenant_id=tenant_id,
            period_year=month_end.year,
            period_month=month_end.month,
            base_currency=base,
            quote_currency=quote,
            limit=100,
            offset=0,
        )
        if not any(row.is_month_end_locked for row in rows):
            raise MissingLockedRateError(
                "Missing locked month-end selected rate "
                f"for {base}/{quote} in {month_end.year}-{month_end.month:02d}"
            )
        decision = await resolve_selected_rate(
            session,
            tenant_id=tenant_id,
            base_currency=base,
            quote_currency=quote,
            as_of_date=month_end,
            redis_client=None,
        )
        return quantize_rate(decision.selected_rate)

    decision = await resolve_selected_rate(
        session,
        tenant_id=tenant_id,
        base_currency=base,
        quote_currency=quote,
        as_of_date=schedule_date,
        redis_client=None,
    )
    return quantize_rate(decision.selected_rate)


async def generate_liability_schedule_rows(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    leases: Iterable[RegisteredLease],
    payments: Iterable[RegisteredLeasePayment],
    reporting_currency: str,
    rate_mode: LeaseRateMode,
) -> LeaseLiabilityGenerationOutput:
    lease_rows = sorted(leases, key=lambda item: item.lease_number)
    payment_rows = list(payments)
    generated: list[LeaseLiabilityScheduleRow] = []
    present_values: dict[UUID, PresentValueResult] = {}
    root_tokens: dict[UUID, str] = {}

    for lease in lease_rows:
        root_token = build_schedule_version_token(
            lease_id=lease.lease_id,
            modification_payload_normalized={"kind": "root"},
            reporting_currency=reporting_currency,
            rate_mode=rate_mode.value,
            prior_version_token_or_root="root",
        )
        root_tokens[lease.lease_id] = root_token
        timeline = build_payment_timeline(lease_id=lease.lease_id, payments=payment_rows)

        commencement_rate = await resolve_lease_fx_rate(
            session,
            tenant_id=tenant_id,
            lease_currency=lease.lease_currency,
            reporting_currency=reporting_currency,
            schedule_date=lease.commencement_date,
            rate_mode=rate_mode,
        )
        pv_result = calculate_present_value(
            lease_id=lease.lease_id,
            payments=timeline,
            annual_discount_rate=lease.initial_discount_rate,
            payment_frequency=lease.payment_frequency,
            conversion_rate=commencement_rate,
        )
        present_values[lease.lease_id] = pv_result

        opening = pv_result.present_value_reporting_currency

        if not timeline:
            generated.append(
                LeaseLiabilityScheduleRow(
                    lease_id=lease.lease_id,
                    payment_id=None,
                    period_seq=1,
                    schedule_date=lease.commencement_date,
                    period_year=lease.commencement_date.year,
                    period_month=lease.commencement_date.month,
                    opening_liability_reporting_currency=opening,
                    interest_expense_reporting_currency=Decimal("0.000000"),
                    payment_amount_reporting_currency=Decimal("0.000000"),
                    closing_liability_reporting_currency=opening,
                    schedule_version_token=root_token,
                    fx_rate_used=commencement_rate,
                    source_lease_reference=lease.source_lease_reference,
                    parent_reference_id=lease.lease_id,
                    source_reference_id=lease.lease_id,
                )
            )
            continue

        for index, payment in enumerate(timeline, start=1):
            fx_rate = await resolve_lease_fx_rate(
                session,
                tenant_id=tenant_id,
                lease_currency=lease.lease_currency,
                reporting_currency=reporting_currency,
                schedule_date=payment.payment_date,
                rate_mode=rate_mode,
            )
            interest_amount = compute_period_interest(
                opening_liability_reporting_currency=opening,
                annual_discount_rate=lease.initial_discount_rate,
                payment_frequency=lease.payment_frequency,
            )
            payment_reporting = quantize_persisted_amount(payment.payment_amount_lease_currency * fx_rate)
            closing = quantize_persisted_amount(opening + interest_amount - payment_reporting)

            generated.append(
                LeaseLiabilityScheduleRow(
                    lease_id=lease.lease_id,
                    payment_id=payment.payment_id,
                    period_seq=index,
                    schedule_date=payment.payment_date,
                    period_year=payment.payment_date.year,
                    period_month=payment.payment_date.month,
                    opening_liability_reporting_currency=opening,
                    interest_expense_reporting_currency=interest_amount,
                    payment_amount_reporting_currency=payment_reporting,
                    closing_liability_reporting_currency=closing,
                    schedule_version_token=root_token,
                    fx_rate_used=fx_rate,
                    source_lease_reference=lease.source_lease_reference,
                    parent_reference_id=lease.lease_id,
                    source_reference_id=payment.payment_id,
                )
            )
            opening = closing

    generated.sort(key=lambda item: (str(item.lease_id), item.schedule_date, str(item.source_reference_id)))
    return LeaseLiabilityGenerationOutput(
        rows=generated,
        present_values=present_values,
        root_schedule_version_tokens=root_tokens,
    )

