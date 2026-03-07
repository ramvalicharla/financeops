from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import ValidationError
from financeops.platform.db.models.modules import CpModuleRegistry
from financeops.platform.services.feature_flags.flag_service import evaluate_feature_flag
from financeops.services.accounting_common.accounting_errors import AccountingValidationError
from financeops.services.accounting_common.error_codes import MISSING_LOCKED_RATE
from financeops.services.accounting_common.quantization_policy import quantize_persisted_amount, quantize_rate
from financeops.services.fixed_assets.asset_registry import RegisteredAsset
from financeops.services.fixed_assets.depreciation_methods import (
    compute_reducing_balance_rows,
    compute_straight_line_rows,
)
from financeops.services.fx import list_manual_monthly_rates, resolve_selected_rate
from financeops.services.fx.normalization import normalize_currency_code
from financeops.utils.determinism import canonical_json_dumps, sha256_hex_text

_DAILY_SELECTED_FLAG_KEY = "fixed_assets.daily_selected_rate_mode"
_MAX_REDUCING_BALANCE_PERIODS = 600


class MissingLockedRateError(AccountingValidationError):
    def __init__(self, message: str) -> None:
        super().__init__(error_code=MISSING_LOCKED_RATE, message=message)


@dataclass(frozen=True)
class GeneratedDepreciationRow:
    asset_id: UUID
    period_seq: int
    depreciation_date: date
    depreciation_period_year: int
    depreciation_period_month: int
    schedule_version_token: str
    opening_carrying_amount_reporting_currency: Decimal
    depreciation_amount_reporting_currency: Decimal
    cumulative_depreciation_reporting_currency: Decimal
    closing_carrying_amount_reporting_currency: Decimal
    fx_rate_used: Decimal
    fx_rate_date: date
    fx_rate_source: str
    schedule_status: str
    source_acquisition_reference: str
    parent_reference_id: UUID | None
    source_reference_id: UUID | None


@dataclass(frozen=True)
class DepreciationGenerationResult:
    root_schedule_version_tokens: dict[UUID, str]
    rows: list[GeneratedDepreciationRow]


def build_schedule_version_token(
    *,
    asset_id: UUID,
    depreciation_method: str,
    useful_life_months: int | None,
    reducing_balance_rate_annual: Decimal | None,
    residual_value_reporting_currency: Decimal,
    reporting_currency: str,
    rate_mode: str,
    effective_date: date,
    prior_schedule_version_token_or_root: str,
) -> str:
    payload = {
        "asset_id": str(asset_id),
        "depreciation_method": depreciation_method,
        "useful_life_months": useful_life_months,
        "reducing_balance_rate_annual": str(reducing_balance_rate_annual) if reducing_balance_rate_annual is not None else None,
        "residual_value_reporting_currency": f"{quantize_persisted_amount(residual_value_reporting_currency):.6f}",
        "reporting_currency": reporting_currency,
        "rate_mode": rate_mode,
        "effective_date": effective_date.isoformat(),
        "prior": prior_schedule_version_token_or_root,
    }
    return sha256_hex_text(canonical_json_dumps(payload))


def _month_end(value: date) -> date:
    _, day = calendar.monthrange(value.year, value.month)
    return date(value.year, value.month, day)


def _month_start(value: date) -> date:
    return date(value.year, value.month, 1)


def _add_months(value: date, months: int) -> date:
    y, m = divmod(value.year * 12 + (value.month - 1) + months, 12)
    year = y
    month = m + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


async def _tenant_allows_daily_selected(session: AsyncSession, *, tenant_id: UUID) -> bool:
    module_result = await session.execute(
        select(CpModuleRegistry.id).where(CpModuleRegistry.module_code == "fixed_assets")
    )
    module_id = module_result.scalar_one_or_none()
    if module_id is None:
        return False

    evaluation = await evaluate_feature_flag(
        session,
        tenant_id=tenant_id,
        module_id=module_id,
        flag_key=_DAILY_SELECTED_FLAG_KEY,
        request_fingerprint=f"fixed_assets:{tenant_id}",
        user_id=None,
        entity_id=None,
    )
    return bool(evaluation["compute_enabled"] and evaluation["write_enabled"])


async def _resolve_fx(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    asset_currency: str,
    reporting_currency: str,
    depreciation_date: date,
    rate_mode: str,
    daily_selected_allowed: bool,
) -> tuple[Decimal, date, str]:
    base = normalize_currency_code(asset_currency)
    quote = normalize_currency_code(reporting_currency)
    if base == quote:
        return Decimal("1.000000"), depreciation_date, "same_currency"

    if rate_mode == "month_end_locked":
        month_end = _month_end(depreciation_date)
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

    if rate_mode == "daily_selected":
        if not daily_selected_allowed:
            raise ValidationError("daily_selected override is not allowed by tenant policy")
        decision = await resolve_selected_rate(
            session,
            tenant_id=tenant_id,
            base_currency=base,
            quote_currency=quote,
            as_of_date=depreciation_date,
            redis_client=None,
        )
        return quantize_rate(decision.selected_rate), depreciation_date, decision.selected_source

    raise ValidationError(f"Unsupported rate mode {rate_mode}")


def _build_periods_for_asset(asset: RegisteredAsset) -> list[tuple[int, date, date, date]]:
    start = asset.in_service_date
    periods: list[tuple[int, date, date, date]] = []

    if asset.depreciation_method == "straight_line":
        if asset.useful_life_months is None:
            raise ValidationError("useful_life_months is required for straight_line")
        life_end = _add_months(start, asset.useful_life_months) - timedelta(days=1)
        cursor = start
        seq = 1
        while cursor <= life_end:
            period_start = cursor
            period_end = min(_month_end(cursor), life_end)
            periods.append((seq, period_start, period_end, period_end))
            cursor = period_end + timedelta(days=1)
            seq += 1
        return periods

    if asset.depreciation_method == "reducing_balance":
        if asset.useful_life_months is not None:
            horizon_end = _add_months(start, asset.useful_life_months) - timedelta(days=1)
            cursor = start
            seq = 1
            while cursor <= horizon_end:
                period_start = cursor
                period_end = min(_month_end(cursor), horizon_end)
                periods.append((seq, period_start, period_end, period_end))
                cursor = period_end + timedelta(days=1)
                seq += 1
            return periods

        # Open-ended reducing balance schedules are capped for deterministic runtime.
        cursor = start
        for seq in range(1, _MAX_REDUCING_BALANCE_PERIODS + 1):
            period_start = cursor
            period_end = _month_end(cursor)
            periods.append((seq, period_start, period_end, period_end))
            cursor = period_end + timedelta(days=1)
        return periods

    return []


async def generate_base_depreciation_rows(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    assets: Iterable[RegisteredAsset],
) -> DepreciationGenerationResult:
    asset_list = sorted(assets, key=lambda row: (row.asset_code, str(row.asset_id)))
    daily_selected_allowed = await _tenant_allows_daily_selected(session, tenant_id=tenant_id)

    root_tokens: dict[UUID, str] = {}
    generated: list[GeneratedDepreciationRow] = []

    for asset in asset_list:
        root_token = build_schedule_version_token(
            asset_id=asset.asset_id,
            depreciation_method=asset.depreciation_method,
            useful_life_months=asset.useful_life_months,
            reducing_balance_rate_annual=asset.reducing_balance_rate_annual,
            residual_value_reporting_currency=asset.residual_value_reporting_currency,
            reporting_currency=asset.reporting_currency,
            rate_mode=asset.rate_mode,
            effective_date=asset.in_service_date,
            prior_schedule_version_token_or_root="root",
        )
        root_tokens[asset.asset_id] = root_token

        if asset.depreciation_method == "non_depreciable":
            continue

        periods = _build_periods_for_asset(asset)
        if not periods:
            continue

        first_rate, _, _ = await _resolve_fx(
            session,
            tenant_id=tenant_id,
            asset_currency=asset.asset_currency,
            reporting_currency=asset.reporting_currency,
            depreciation_date=asset.in_service_date,
            rate_mode=asset.rate_mode,
            daily_selected_allowed=daily_selected_allowed,
        )
        opening = quantize_persisted_amount(asset.capitalized_amount_asset_currency * first_rate)
        residual = quantize_persisted_amount(asset.residual_value_reporting_currency)

        if opening < residual:
            raise ValidationError("Residual value cannot exceed opening carrying amount")

        if asset.depreciation_method == "straight_line":
            method_rows = compute_straight_line_rows(
                opening_carrying_amount_reporting_currency=opening,
                residual_value_reporting_currency=residual,
                useful_life_months=int(asset.useful_life_months or 0),
                periods=periods,
            )
        elif asset.depreciation_method == "reducing_balance":
            if asset.reducing_balance_rate_annual is None:
                raise ValidationError("reducing_balance_rate_annual is required for reducing_balance")
            method_rows = compute_reducing_balance_rows(
                opening_carrying_amount_reporting_currency=opening,
                residual_value_reporting_currency=residual,
                annual_rate=asset.reducing_balance_rate_annual,
                periods=periods,
            )
        else:
            raise ValidationError(f"Unsupported depreciation method {asset.depreciation_method}")

        cumulative = Decimal("0.000000")
        running_opening = opening

        for row in method_rows:
            if running_opening <= residual:
                break
            max_allowed = quantize_persisted_amount(running_opening - residual)
            depreciation_amount = row.depreciation_amount_reporting_currency
            if depreciation_amount > max_allowed:
                depreciation_amount = max_allowed
            depreciation_amount = quantize_persisted_amount(max(depreciation_amount, Decimal("0.000000")))
            closing = quantize_persisted_amount(running_opening - depreciation_amount)
            if closing < residual:
                closing = residual
            cumulative = quantize_persisted_amount(cumulative + depreciation_amount)

            fx_rate, fx_rate_date, fx_rate_source = await _resolve_fx(
                session,
                tenant_id=tenant_id,
                asset_currency=asset.asset_currency,
                reporting_currency=asset.reporting_currency,
                depreciation_date=row.depreciation_date,
                rate_mode=asset.rate_mode,
                daily_selected_allowed=daily_selected_allowed,
            )

            generated.append(
                GeneratedDepreciationRow(
                    asset_id=asset.asset_id,
                    period_seq=row.period_seq,
                    depreciation_date=row.depreciation_date,
                    depreciation_period_year=row.depreciation_date.year,
                    depreciation_period_month=row.depreciation_date.month,
                    schedule_version_token=root_token,
                    opening_carrying_amount_reporting_currency=running_opening,
                    depreciation_amount_reporting_currency=depreciation_amount,
                    cumulative_depreciation_reporting_currency=cumulative,
                    closing_carrying_amount_reporting_currency=closing,
                    fx_rate_used=fx_rate,
                    fx_rate_date=fx_rate_date,
                    fx_rate_source=fx_rate_source,
                    schedule_status="scheduled",
                    source_acquisition_reference=asset.source_acquisition_reference,
                    parent_reference_id=asset.asset_id,
                    source_reference_id=asset.source_reference_id,
                )
            )
            running_opening = closing

    generated.sort(
        key=lambda row: (
            str(row.asset_id),
            row.schedule_version_token,
            row.period_seq,
            row.depreciation_date,
        )
    )
    return DepreciationGenerationResult(root_schedule_version_tokens=root_tokens, rows=generated)
