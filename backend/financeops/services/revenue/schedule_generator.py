from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import ValidationError
from financeops.schemas.revenue import RevenueRateMode, RevenueRecognitionMethod
from financeops.services.accounting_common.accounting_errors import AccountingValidationError
from financeops.services.accounting_common.error_codes import MISSING_LOCKED_RATE
from financeops.services.accounting_common.quantization_policy import (
    quantize_persisted_amount,
    quantize_rate,
)
from financeops.services.fx import list_manual_monthly_rates, resolve_selected_rate
from financeops.services.fx.normalization import normalize_currency_code
from financeops.services.revenue.allocation_engine import ObligationAllocation
from financeops.services.revenue.contract_registry import RegisteredContract
from financeops.services.revenue.obligation_tracker import RegisteredLineItem
from financeops.services.revenue.remeasurement import build_schedule_version_token


@dataclass(frozen=True)
class GeneratedScheduleRow:
    contract_id: UUID
    obligation_id: UUID
    contract_line_item_id: UUID
    period_seq: int
    recognition_date: date
    recognition_period_year: int
    recognition_period_month: int
    recognition_method: str
    base_amount_contract_currency: Decimal
    fx_rate_used: Decimal
    recognized_amount_reporting_currency: Decimal
    cumulative_recognized_reporting_currency: Decimal
    schedule_version_token: str
    schedule_status: str
    source_contract_reference: str
    parent_reference_id: UUID
    source_reference_id: UUID


@dataclass(frozen=True)
class ScheduleGenerationOutput:
    root_schedule_version_tokens: dict[UUID, str]
    rows: list[GeneratedScheduleRow]


def _month_end_for(value: date) -> date:
    _, last_day = calendar.monthrange(value.year, value.month)
    return date(value.year, value.month, last_day)


def _month_points(start_date: date, end_date: date) -> list[date]:
    points: list[date] = []
    year = start_date.year
    month = start_date.month
    while (year, month) <= (end_date.year, end_date.month):
        points.append(_month_end_for(date(year, month, 1)))
        if month == 12:
            year += 1
            month = 1
        else:
            month += 1
    return points


async def _resolve_fx_rate(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    base_currency: str,
    reporting_currency: str,
    recognition_date: date,
    rate_mode: RevenueRateMode,
) -> Decimal:
    base = normalize_currency_code(base_currency)
    quote = normalize_currency_code(reporting_currency)
    if base == quote:
        return Decimal("1.000000")

    if rate_mode == RevenueRateMode.month_end_locked:
        month_end = _month_end_for(recognition_date)
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
            raise AccountingValidationError(
                error_code=MISSING_LOCKED_RATE,
                message=(
                    "Missing locked month-end selected rate "
                    f"for {base}/{quote} in {month_end.year}-{month_end.month:02d}"
                ),
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
        as_of_date=recognition_date,
        redis_client=None,
    )
    return quantize_rate(decision.selected_rate)


def _line_base_allocation(
    *,
    line_items: list[RegisteredLineItem],
    obligation_allocation: Decimal,
) -> dict[UUID, Decimal]:
    total_line_amount = quantize_persisted_amount(
        sum((line.line_amount for line in line_items), start=Decimal("0"))
    )
    if total_line_amount <= Decimal("0"):
        even_share = quantize_persisted_amount(obligation_allocation / Decimal(str(len(line_items))))
        provisional = {line.line_item_id: even_share for line in line_items}
    else:
        provisional = {
            line.line_item_id: quantize_persisted_amount(obligation_allocation * (line.line_amount / total_line_amount))
            for line in line_items
        }

    reconciled = quantize_persisted_amount(sum(provisional.values(), start=Decimal("0")))
    residual = quantize_persisted_amount(obligation_allocation - reconciled)
    if residual != Decimal("0.000000"):
        anchor_line_id = sorted(provisional, key=str)[0]
        provisional[anchor_line_id] = quantize_persisted_amount(provisional[anchor_line_id] + residual)
    return provisional


def _recognition_points_for_line(
    *,
    line: RegisteredLineItem,
    contract: RegisteredContract,
) -> list[tuple[date, Decimal, str]]:
    method = line.recognition_method
    if method == RevenueRecognitionMethod.percentage_of_completion:
        ratio = Decimal(str(line.completion_percentage or Decimal("0")))
        ratio = max(Decimal("0"), min(Decimal("1"), ratio))
        recognized_ratio = quantize_persisted_amount(ratio)
        recognition_date = line.recognition_date or contract.contract_end_date
        status = "recognized" if recognized_ratio > Decimal("0") else "pending"
        return [(recognition_date, recognized_ratio, status)]

    if method == RevenueRecognitionMethod.completed_service:
        recognized_ratio = Decimal("1.000000") if bool(line.completed_flag) else Decimal("0.000000")
        recognition_date = line.recognition_date or contract.contract_end_date
        status = "recognized" if recognized_ratio > Decimal("0") else "pending"
        return [(recognition_date, recognized_ratio, status)]

    if method == RevenueRecognitionMethod.milestone_based:
        recognized_ratio = Decimal("1.000000") if bool(line.milestone_achieved) else Decimal("0.000000")
        recognition_date = line.recognition_date or contract.contract_end_date
        status = "recognized" if recognized_ratio > Decimal("0") else "pending"
        return [(recognition_date, recognized_ratio, status)]

    if method == RevenueRecognitionMethod.usage_based:
        usage_ratio = Decimal(str(line.usage_quantity or Decimal("0")))
        usage_ratio = max(Decimal("0"), min(Decimal("1"), usage_ratio))
        usage_ratio = quantize_persisted_amount(usage_ratio)
        recognition_date = line.recognition_date or contract.contract_end_date
        status = "recognized" if usage_ratio > Decimal("0") else "pending"
        return [(recognition_date, usage_ratio, status)]

    if method == RevenueRecognitionMethod.straight_line:
        start_date = line.recognition_start_date or contract.contract_start_date
        end_date = line.recognition_end_date or contract.contract_end_date
        if end_date < start_date:
            raise ValidationError("Straight-line recognition_end_date must be on or after recognition_start_date")

        points = _month_points(start_date, end_date)
        if not points:
            raise ValidationError("Straight-line recognition period produced zero points")

        base_ratio = quantize_persisted_amount(Decimal("1") / Decimal(str(len(points))))
        ratios = [base_ratio for _ in points]
        residual = quantize_persisted_amount(Decimal("1.000000") - sum(ratios, start=Decimal("0")))
        ratios[0] = quantize_persisted_amount(ratios[0] + residual)
        return [(point, ratio, "recognized") for point, ratio in zip(points, ratios, strict=True)]

    raise ValidationError(f"Unsupported recognition method {method}")


async def generate_schedule_rows(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    contracts: Iterable[RegisteredContract],
    line_items: Iterable[RegisteredLineItem],
    allocations: Iterable[ObligationAllocation],
    reporting_currency: str,
    rate_mode: RevenueRateMode,
) -> ScheduleGenerationOutput:
    contract_map = {item.contract_id: item for item in contracts}
    line_items_by_obligation: dict[UUID, list[RegisteredLineItem]] = {}
    for line in line_items:
        line_items_by_obligation.setdefault(line.obligation_id, []).append(line)

    reporting = normalize_currency_code(reporting_currency)
    generated: list[GeneratedScheduleRow] = []
    root_tokens: dict[UUID, str] = {}
    period_seq_by_contract: dict[UUID, int] = {}

    for allocation in allocations:
        contract = contract_map.get(allocation.contract_id)
        if contract is None:
            raise ValidationError("Allocation references unknown contract")
        root_token = root_tokens.get(contract.contract_id)
        if root_token is None:
            root_token = build_schedule_version_token(
                contract_id=contract.contract_id,
                modification_payload_normalized={"kind": "root"},
                reporting_currency=reporting,
                rate_mode=rate_mode.value,
                prior_version_token_or_root="root",
            )
            root_tokens[contract.contract_id] = root_token

        obligation_lines = sorted(
            line_items_by_obligation.get(allocation.obligation_id, []),
            key=lambda item: item.line_code,
        )
        if not obligation_lines:
            raise ValidationError("Obligation has no contract line items for schedule generation")

        base_amount_by_line = _line_base_allocation(
            line_items=obligation_lines,
            obligation_allocation=allocation.allocated_amount_contract_currency,
        )

        for line in obligation_lines:
            points = _recognition_points_for_line(line=line, contract=contract)
            ratio_total = quantize_persisted_amount(
                sum((ratio for _, ratio, _ in points), start=Decimal("0"))
            )
            base_total = base_amount_by_line[line.line_item_id]
            line_rows: list[GeneratedScheduleRow] = []
            cumulative = Decimal("0.000000")
            for recognition_date, ratio, status in points:
                base_amount = quantize_persisted_amount(base_total * ratio)
                fx_rate = await _resolve_fx_rate(
                    session,
                    tenant_id=tenant_id,
                    base_currency=line.line_currency,
                    reporting_currency=reporting,
                    recognition_date=recognition_date,
                    rate_mode=rate_mode,
                )
                recognized_reporting = quantize_persisted_amount(base_amount * fx_rate)
                cumulative = quantize_persisted_amount(cumulative + recognized_reporting)
                line_rows.append(
                    GeneratedScheduleRow(
                        contract_id=line.contract_id,
                        obligation_id=line.obligation_id,
                        contract_line_item_id=line.line_item_id,
                        period_seq=0,
                        recognition_date=recognition_date,
                        recognition_period_year=recognition_date.year,
                        recognition_period_month=recognition_date.month,
                        recognition_method=line.recognition_method.value,
                        base_amount_contract_currency=base_amount,
                        fx_rate_used=fx_rate,
                        recognized_amount_reporting_currency=recognized_reporting,
                        cumulative_recognized_reporting_currency=cumulative,
                        schedule_version_token=root_token,
                        schedule_status=status,
                        source_contract_reference=line.source_contract_reference,
                        parent_reference_id=line.obligation_id,
                        source_reference_id=line.line_item_id,
                    )
                )

            reconciled_reporting = quantize_persisted_amount(
                sum((row.recognized_amount_reporting_currency for row in line_rows), start=Decimal("0"))
            )
            for idx, row in enumerate(line_rows):
                if idx == len(line_rows) - 1:
                    continue
                generated.append(row)

            if line_rows:
                expected_total = quantize_persisted_amount(
                    sum((row.base_amount_contract_currency for row in line_rows), start=Decimal("0"))
                )
                base_residual = (
                    quantize_persisted_amount(base_total - expected_total)
                    if ratio_total == Decimal("1.000000")
                    else Decimal("0.000000")
                )
                tail = line_rows[-1]
                adjusted_base = quantize_persisted_amount(tail.base_amount_contract_currency + base_residual)
                adjusted_reporting = quantize_persisted_amount(adjusted_base * tail.fx_rate_used)
                adjusted_tail = GeneratedScheduleRow(
                    contract_id=tail.contract_id,
                    obligation_id=tail.obligation_id,
                    contract_line_item_id=tail.contract_line_item_id,
                    period_seq=0,
                    recognition_date=tail.recognition_date,
                    recognition_period_year=tail.recognition_period_year,
                    recognition_period_month=tail.recognition_period_month,
                    recognition_method=tail.recognition_method,
                    base_amount_contract_currency=adjusted_base,
                    fx_rate_used=tail.fx_rate_used,
                    recognized_amount_reporting_currency=adjusted_reporting,
                    cumulative_recognized_reporting_currency=quantize_persisted_amount(
                        reconciled_reporting - tail.recognized_amount_reporting_currency + adjusted_reporting
                    ),
                    schedule_version_token=tail.schedule_version_token,
                    schedule_status=tail.schedule_status,
                    source_contract_reference=tail.source_contract_reference,
                    parent_reference_id=tail.parent_reference_id,
                    source_reference_id=tail.source_reference_id,
                )
                generated.append(adjusted_tail)

    generated.sort(
        key=lambda item: (
            str(item.contract_id),
            item.schedule_version_token,
            str(item.obligation_id),
            str(item.contract_line_item_id),
            item.recognition_date,
        )
    )
    sequenced_rows: list[GeneratedScheduleRow] = []
    for row in generated:
        next_seq = period_seq_by_contract.get(row.contract_id, 0) + 1
        period_seq_by_contract[row.contract_id] = next_seq
        sequenced_rows.append(
            GeneratedScheduleRow(
                contract_id=row.contract_id,
                obligation_id=row.obligation_id,
                contract_line_item_id=row.contract_line_item_id,
                period_seq=next_seq,
                recognition_date=row.recognition_date,
                recognition_period_year=row.recognition_period_year,
                recognition_period_month=row.recognition_period_month,
                recognition_method=row.recognition_method,
                base_amount_contract_currency=row.base_amount_contract_currency,
                fx_rate_used=row.fx_rate_used,
                recognized_amount_reporting_currency=row.recognized_amount_reporting_currency,
                cumulative_recognized_reporting_currency=row.cumulative_recognized_reporting_currency,
                schedule_version_token=row.schedule_version_token,
                schedule_status=row.schedule_status,
                source_contract_reference=row.source_contract_reference,
                parent_reference_id=row.parent_reference_id,
                source_reference_id=row.source_reference_id,
            )
        )
    return ScheduleGenerationOutput(root_schedule_version_tokens=root_tokens, rows=sequenced_rows)
