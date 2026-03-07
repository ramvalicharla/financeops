from __future__ import annotations

import calendar
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from typing import Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import ValidationError
from financeops.platform.db.models.modules import CpModuleRegistry
from financeops.platform.services.feature_flags.flag_service import evaluate_feature_flag
from financeops.schemas.prepaid import PrepaidRateMode
from financeops.services.accounting_common.accounting_errors import AccountingValidationError
from financeops.services.accounting_common.error_codes import MISSING_LOCKED_RATE
from financeops.services.accounting_common.quantization_policy import (
    quantize_persisted_amount,
    quantize_rate,
)
from financeops.services.fx import list_manual_monthly_rates, resolve_selected_rate
from financeops.services.fx.normalization import normalize_currency_code
from financeops.services.prepaid.adjustments import PersistedAdjustment, build_schedule_version_token
from financeops.services.prepaid.prepaid_registry import RegisteredPrepaid

_DAILY_SELECTED_FLAG_KEY = "prepaid.daily_selected_rate_mode"


class MissingLockedRateError(AccountingValidationError):
    def __init__(self, message: str) -> None:
        super().__init__(error_code=MISSING_LOCKED_RATE, message=message)


@dataclass(frozen=True)
class GeneratedScheduleRow:
    prepaid_id: UUID
    period_seq: int
    amortization_date: date
    recognition_period_year: int
    recognition_period_month: int
    schedule_version_token: str
    base_amount_contract_currency: Decimal
    amortized_amount_reporting_currency: Decimal
    cumulative_amortized_reporting_currency: Decimal
    fx_rate_used: Decimal
    fx_rate_date: date
    fx_rate_source: str
    schedule_status: str
    source_expense_reference: str
    parent_reference_id: UUID | None
    source_reference_id: UUID | None


@dataclass(frozen=True)
class PrepaidScheduleOutput:
    root_schedule_version_tokens: dict[UUID, str]
    rows: list[GeneratedScheduleRow]


def _month_end(value: date) -> date:
    _, day = calendar.monthrange(value.year, value.month)
    return date(value.year, value.month, day)


async def _tenant_allows_daily_selected(session: AsyncSession, *, tenant_id: UUID) -> bool:
    module_result = await session.execute(
        select(CpModuleRegistry.id).where(CpModuleRegistry.module_code == "prepaid")
    )
    module_id = module_result.scalar_one_or_none()
    if module_id is None:
        return False

    evaluation = await evaluate_feature_flag(
        session,
        tenant_id=tenant_id,
        module_id=module_id,
        flag_key=_DAILY_SELECTED_FLAG_KEY,
        request_fingerprint=f"prepaid:{tenant_id}",
        user_id=None,
        entity_id=None,
    )
    return bool(evaluation["compute_enabled"] and evaluation["write_enabled"])


def _allocate_base_amounts(*, prepaid: RegisteredPrepaid) -> dict[int, Decimal]:
    periods = prepaid.normalized_pattern.periods
    base_total = quantize_persisted_amount(prepaid.base_amount_contract_currency)

    provisional: dict[int, Decimal] = {}
    if prepaid.pattern_type == "straight_line":
        equal = quantize_persisted_amount(base_total / Decimal(str(len(periods))))
        provisional = {item.period_seq: equal for item in periods}
    elif prepaid.pattern_type == "weighted_period":
        total_weight = sum((item.weight or Decimal("0") for item in periods), start=Decimal("0"))
        if total_weight <= Decimal("0"):
            raise ValidationError("weighted_period total weight must be positive")
        provisional = {
            item.period_seq: quantize_persisted_amount(base_total * ((item.weight or Decimal("0")) / total_weight))
            for item in periods
        }
    elif prepaid.pattern_type == "explicit_percentages":
        provisional = {
            item.period_seq: quantize_persisted_amount(base_total * (item.percentage or Decimal("0")))
            for item in periods
        }
    elif prepaid.pattern_type == "explicit_amounts":
        provisional = {
            item.period_seq: quantize_persisted_amount(item.amount or Decimal("0"))
            for item in periods
        }
    else:
        raise ValidationError(f"Unsupported pattern type {prepaid.pattern_type}")

    reconciled = quantize_persisted_amount(sum(provisional.values(), start=Decimal("0")))
    residual = quantize_persisted_amount(base_total - reconciled)
    if residual != Decimal("0.000000"):
        anchor_seq = min(provisional)
        provisional[anchor_seq] = quantize_persisted_amount(provisional[anchor_seq] + residual)
    return provisional


async def _resolve_fx(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    prepaid_currency: str,
    reporting_currency: str,
    amortization_date: date,
    rate_mode: str,
    daily_selected_allowed: bool,
) -> tuple[Decimal, date, str]:
    base = normalize_currency_code(prepaid_currency)
    quote = normalize_currency_code(reporting_currency)
    if base == quote:
        return Decimal("1.000000"), amortization_date, "same_currency_1_0"

    if rate_mode == PrepaidRateMode.month_end_locked.value:
        month_end = _month_end(amortization_date)
        monthly = await list_manual_monthly_rates(
            session,
            tenant_id=tenant_id,
            period_year=month_end.year,
            period_month=month_end.month,
            base_currency=base,
            quote_currency=quote,
            limit=100,
            offset=0,
        )
        locked = next((row for row in monthly if bool(row.is_month_end_locked)), None)
        if locked is None:
            raise MissingLockedRateError(
                f"Missing locked month-end selected rate for {base}/{quote} in {month_end.year}-{month_end.month:02d}"
            )
        return quantize_rate(locked.rate), month_end, "locked_selection"

    if rate_mode == PrepaidRateMode.daily_selected.value:
        if not daily_selected_allowed:
            raise ValidationError("daily_selected override is not allowed by tenant policy")
        decision = await resolve_selected_rate(
            session,
            tenant_id=tenant_id,
            base_currency=base,
            quote_currency=quote,
            as_of_date=amortization_date,
            redis_client=None,
        )
        return quantize_rate(decision.selected_rate), amortization_date, decision.selected_source

    raise ValidationError(f"Unsupported rate mode {rate_mode}")


def _apply_adjustment_versions(
    *,
    root_rows: list[GeneratedScheduleRow],
    adjustments: list[PersistedAdjustment],
) -> list[GeneratedScheduleRow]:
    version_rows: dict[str, list[GeneratedScheduleRow]] = {}
    if not root_rows:
        return []
    root_token = root_rows[0].schedule_version_token
    version_rows[root_token] = list(sorted(root_rows, key=lambda row: row.period_seq))
    emitted: list[GeneratedScheduleRow] = list(root_rows)

    for adjustment in adjustments:
        prior_rows = list(version_rows.get(adjustment.prior_schedule_version_token, []))
        if not prior_rows:
            continue

        historic = [row for row in prior_rows if row.amortization_date < adjustment.effective_date]
        forward_source = [row for row in prior_rows if row.amortization_date >= adjustment.effective_date]
        if not forward_source:
            version_rows[adjustment.new_schedule_version_token] = prior_rows
            continue

        cumulative_anchor = (
            historic[-1].cumulative_amortized_reporting_currency if historic else Decimal("0.000000")
        )
        running = cumulative_anchor

        regenerated: list[GeneratedScheduleRow] = []
        for idx, source_row in enumerate(sorted(forward_source, key=lambda row: row.period_seq)):
            amount = source_row.amortized_amount_reporting_currency
            if idx == 0 and adjustment.catch_up_amount_reporting_currency != Decimal("0.000000"):
                amount = quantize_persisted_amount(amount + adjustment.catch_up_amount_reporting_currency)
            running = quantize_persisted_amount(running + amount)
            regenerated.append(
                replace(
                    source_row,
                    schedule_version_token=adjustment.new_schedule_version_token,
                    amortized_amount_reporting_currency=amount,
                    cumulative_amortized_reporting_currency=running,
                    schedule_status="regenerated",
                )
            )

        version_rows[adjustment.new_schedule_version_token] = historic + regenerated
        emitted.extend(regenerated)

    return emitted


async def generate_schedule_rows(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    prepaids: Iterable[RegisteredPrepaid],
    adjustment_map: dict[UUID, list[PersistedAdjustment]],
) -> PrepaidScheduleOutput:
    prepaid_rows = sorted(prepaids, key=lambda row: (row.prepaid_code, str(row.prepaid_id)))
    root_tokens: dict[UUID, str] = {}
    generated: list[GeneratedScheduleRow] = []
    daily_selected_allowed = await _tenant_allows_daily_selected(session, tenant_id=tenant_id)

    for prepaid in prepaid_rows:
        periods = prepaid.normalized_pattern.periods
        if not periods:
            raise ValidationError("Prepaid pattern produced zero periods")

        allocations = _allocate_base_amounts(prepaid=prepaid)
        root_token = build_schedule_version_token(
            prepaid_id=prepaid.prepaid_id,
            pattern_normalized_json=prepaid.normalized_pattern.canonical_json,
            reporting_currency=prepaid.reporting_currency,
            rate_mode=prepaid.rate_mode,
            adjustment_effective_date=prepaid.term_start_date,
            prior_schedule_version_token_or_root="root",
        )
        root_tokens[prepaid.prepaid_id] = root_token

        cumulative = Decimal("0.000000")
        root_rows: list[GeneratedScheduleRow] = []
        for period in periods:
            amount_contract = allocations[period.period_seq]
            fx_rate, fx_rate_date, fx_source = await _resolve_fx(
                session,
                tenant_id=tenant_id,
                prepaid_currency=prepaid.prepaid_currency,
                reporting_currency=prepaid.reporting_currency,
                amortization_date=period.recognition_date,
                rate_mode=prepaid.rate_mode,
                daily_selected_allowed=daily_selected_allowed,
            )
            amortized_reporting = quantize_persisted_amount(amount_contract * fx_rate)
            cumulative = quantize_persisted_amount(cumulative + amortized_reporting)
            root_rows.append(
                GeneratedScheduleRow(
                    prepaid_id=prepaid.prepaid_id,
                    period_seq=period.period_seq,
                    amortization_date=period.recognition_date,
                    recognition_period_year=period.recognition_date.year,
                    recognition_period_month=period.recognition_date.month,
                    schedule_version_token=root_token,
                    base_amount_contract_currency=amount_contract,
                    amortized_amount_reporting_currency=amortized_reporting,
                    cumulative_amortized_reporting_currency=cumulative,
                    fx_rate_used=fx_rate,
                    fx_rate_date=fx_rate_date,
                    fx_rate_source=fx_source,
                    schedule_status="scheduled",
                    source_expense_reference=prepaid.source_expense_reference,
                    parent_reference_id=prepaid.prepaid_id,
                    source_reference_id=prepaid.source_reference_id,
                )
            )

        regenerated = _apply_adjustment_versions(
            root_rows=root_rows,
            adjustments=adjustment_map.get(prepaid.prepaid_id, []),
        )
        generated.extend(regenerated)

    generated.sort(
        key=lambda row: (
            str(row.prepaid_id),
            row.schedule_version_token,
            row.period_seq,
            row.amortization_date,
        )
    )
    return PrepaidScheduleOutput(root_schedule_version_tokens=root_tokens, rows=generated)
