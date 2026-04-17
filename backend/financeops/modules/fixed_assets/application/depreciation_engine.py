from __future__ import annotations

from enum import StrEnum
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from financeops.modules.fixed_assets.domain.exceptions import DepreciationCalculationError
from financeops.modules.fixed_assets.models import FaAsset

_QUANT = Decimal("0.0001")
IT_ACT_S32_THRESHOLD = Decimal("5000")


class DepreciationMethod(StrEnum):
    SLM = "SLM"
    WDV = "WDV"
    DOUBLE_DECLINING = "DOUBLE_DECLINING"
    UOP = "UOP"
    BLOCK_IT_ACT_S32 = "BLOCK_IT_ACT_S32"


def _q4(value: Decimal) -> Decimal:
    return Decimal(str(value)).quantize(_QUANT, rounding=ROUND_HALF_UP)


def calculate_slm(
    original_cost: Decimal,
    residual_value: Decimal,
    useful_life_years: Decimal,
    period_days: int,
    days_in_year: int = 365,
) -> Decimal:
    depreciable_amount = Decimal(str(original_cost)) - Decimal(str(residual_value))
    annual_dep = depreciable_amount / Decimal(str(useful_life_years))
    return _q4((annual_dep * Decimal(period_days)) / Decimal(days_in_year))


def calculate_wdv(
    opening_nbv: Decimal,
    rate: Decimal,
    period_days: int,
    days_in_year: int = 365,
) -> Decimal:
    annual_dep = Decimal(str(opening_nbv)) * Decimal(str(rate))
    return _q4((annual_dep * Decimal(period_days)) / Decimal(days_in_year))


def calculate_double_declining(
    opening_nbv: Decimal,
    useful_life_years: Decimal,
    residual_value: Decimal,
    period_days: int,
    days_in_year: int = 365,
) -> Decimal:
    rate = Decimal("2") / Decimal(str(useful_life_years))
    annual_dep = Decimal(str(opening_nbv)) * rate
    dep = _q4((annual_dep * Decimal(period_days)) / Decimal(days_in_year))
    max_dep = Decimal(str(opening_nbv)) - Decimal(str(residual_value))
    return min(dep, max_dep)


def calculate_uop(
    original_cost: Decimal,
    residual_value: Decimal,
    total_units: Decimal,
    units_this_period: Decimal,
) -> Decimal:
    dep_per_unit = (Decimal(str(original_cost)) - Decimal(str(residual_value))) / Decimal(str(total_units))
    return _q4(dep_per_unit * Decimal(str(units_this_period)))


def calculate_it_act_wdv(
    opening_block_value: Decimal,
    additions: Decimal,
    disposals: Decimal,
    rate: Decimal,
    half_year_additions: Decimal = Decimal("0"),
) -> Decimal:
    del additions, disposals
    full_year_dep = Decimal(str(opening_block_value)) * Decimal(str(rate))
    half_year_dep = Decimal(str(half_year_additions)) * Decimal(str(rate)) / Decimal("2")
    return _q4(full_year_dep + half_year_dep)


def calculate_it_act_section_32(
    *,
    asset_id: object,
    asset_cost: Decimal | None,
    acquisition_date: date | None,
    period_year: int | None,
) -> Decimal:
    if acquisition_date is None:
        raise DepreciationCalculationError(asset_id, "missing acquisition_date")
    if asset_cost is None or Decimal(str(asset_cost)) <= Decimal("0"):
        raise DepreciationCalculationError(asset_id, "invalid asset_cost")
    if period_year is None:
        raise DepreciationCalculationError(asset_id, "missing period_year")
    if acquisition_date.year != period_year:
        return Decimal("0.0000")

    year_end = date(period_year, 3, 31)
    if acquisition_date > year_end:
        return Decimal("0.0000")

    days_in_service = (year_end - acquisition_date).days + 1
    depreciation = (Decimal(days_in_service) / Decimal("365")) * Decimal(str(asset_cost))
    return _q4(depreciation)


def _days_in_period(period_start: date, period_end: date) -> int:
    return max((period_end - period_start).days + 1, 0)


def get_depreciation(
    asset: FaAsset,
    opening_nbv: Decimal,
    period_start: date,
    period_end: date,
    gaap: str,
) -> Decimal:
    overrides = asset.gaap_overrides or {}
    gaap_key = gaap.upper()
    override_values = overrides.get(gaap_key, {}) if isinstance(overrides, dict) else {}

    useful_life_years = Decimal(str(override_values.get("useful_life_years", asset.useful_life_years)))
    residual_value = Decimal(str(override_values.get("residual_value", asset.residual_value)))
    dep_method = str(override_values.get("depreciation_method", asset.depreciation_method)).upper()

    period_days = _days_in_period(period_start, period_end)
    if period_days <= 0:
        return Decimal("0.0000")

    if dep_method == DepreciationMethod.BLOCK_IT_ACT_S32:
        acquisition_date = asset.capitalisation_date or asset.purchase_date
        asset_cost = Decimal(str(asset.original_cost)) if asset.original_cost is not None else None
        section_32_dep = calculate_it_act_section_32(
            asset_id=getattr(asset, "id", "unknown"),
            asset_cost=asset_cost,
            acquisition_date=acquisition_date,
            period_year=period_end.year if period_end is not None else None,
        )
        if asset_cost is not None and asset_cost <= IT_ACT_S32_THRESHOLD:
            return section_32_dep
        return section_32_dep

    if gaap_key == "IT_ACT":
        rate_value = override_values.get("depreciation_rate")
        if rate_value is None:
            rate_value = Decimal("0")
        rate = Decimal(str(rate_value))
        half_year_additions = Decimal("0")
        if asset.capitalisation_date.month >= 10:
            half_year_additions = Decimal(str(asset.original_cost))
        return calculate_it_act_wdv(
            opening_block_value=Decimal(str(opening_nbv)),
            additions=Decimal("0"),
            disposals=Decimal("0"),
            rate=rate,
            half_year_additions=half_year_additions,
        )

    if dep_method == DepreciationMethod.SLM:
        return calculate_slm(
            original_cost=Decimal(str(asset.original_cost)),
            residual_value=residual_value,
            useful_life_years=useful_life_years,
            period_days=period_days,
        )
    if dep_method == DepreciationMethod.WDV:
        rate = Decimal(str(override_values.get("depreciation_rate", Decimal("0"))))
        return calculate_wdv(
            opening_nbv=Decimal(str(opening_nbv)),
            rate=rate,
            period_days=period_days,
        )
    if dep_method == DepreciationMethod.DOUBLE_DECLINING:
        return calculate_double_declining(
            opening_nbv=Decimal(str(opening_nbv)),
            useful_life_years=useful_life_years,
            residual_value=residual_value,
            period_days=period_days,
        )
    if dep_method == DepreciationMethod.UOP:
        total_units = Decimal(str(override_values.get("total_units", Decimal("1"))))
        units_this_period = Decimal(str(override_values.get("units_this_period", Decimal("0"))))
        return calculate_uop(
            original_cost=Decimal(str(asset.original_cost)),
            residual_value=residual_value,
            total_units=total_units,
            units_this_period=units_this_period,
        )

    return Decimal("0.0000")


__all__ = [
    "DepreciationMethod",
    "IT_ACT_S32_THRESHOLD",
    "calculate_slm",
    "calculate_wdv",
    "calculate_double_declining",
    "calculate_uop",
    "calculate_it_act_wdv",
    "calculate_it_act_section_32",
    "get_depreciation",
]
