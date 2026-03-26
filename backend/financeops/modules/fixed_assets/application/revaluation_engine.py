from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from financeops.modules.fixed_assets.models import FaAsset

_QUANT = Decimal("0.0001")


def _q4(value: Decimal) -> Decimal:
    return Decimal(str(value)).quantize(_QUANT, rounding=ROUND_HALF_UP)


def _asset_accumulated_dep(asset: FaAsset) -> Decimal:
    overrides = asset.gaap_overrides or {}
    if isinstance(overrides, dict):
        raw = overrides.get("_accumulated_dep", Decimal("0"))
        return Decimal(str(raw))
    return Decimal("0")


def _asset_nbv(asset: FaAsset) -> Decimal:
    return Decimal(str(asset.original_cost)) - _asset_accumulated_dep(asset)


def apply_proportional_method(
    asset: FaAsset,
    fair_value: Decimal,
    revaluation_date: date,
) -> dict[str, Decimal | date]:
    del revaluation_date
    asset_nbv = _asset_nbv(asset)
    if asset_nbv == Decimal("0"):
        gross_factor = Decimal("1")
    else:
        gross_factor = Decimal(str(fair_value)) / asset_nbv
    new_cost = Decimal(str(asset.original_cost)) * gross_factor
    new_accum_dep = _asset_accumulated_dep(asset) * gross_factor
    surplus = Decimal(str(fair_value)) - asset_nbv
    return {
        "new_cost": _q4(new_cost),
        "new_accum_dep": _q4(new_accum_dep),
        "surplus": _q4(surplus),
    }


def apply_elimination_method(
    asset: FaAsset,
    fair_value: Decimal,
    revaluation_date: date,
) -> dict[str, Decimal | date]:
    del revaluation_date
    asset_nbv = _asset_nbv(asset)
    surplus = Decimal(str(fair_value)) - asset_nbv
    return {
        "new_cost": _q4(Decimal(str(fair_value))),
        "new_accum_dep": Decimal("0.0000"),
        "surplus": _q4(surplus),
    }


__all__ = ["apply_proportional_method", "apply_elimination_method"]
