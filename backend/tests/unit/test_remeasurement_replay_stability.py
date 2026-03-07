from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from financeops.services.fixed_assets.depreciation_engine import (
    build_schedule_version_token as far_build_token,
)
from financeops.services.lease.remeasurement import (
    build_schedule_version_token as lease_build_token,
)
from financeops.services.prepaid.adjustments import (
    build_schedule_version_token as prepaid_build_token,
)
from financeops.services.revenue.remeasurement import (
    build_schedule_version_token as revenue_build_token,
)


def _uuid(value: str) -> UUID:
    return UUID(value)


def test_cross_engine_schedule_version_token_generation_is_deterministic() -> None:
    revenue_token_1 = revenue_build_token(
        contract_id=_uuid("00000000-0000-0000-0000-000000000101"),
        modification_payload_normalized={
            "effective_date": "2026-06-30",
            "adjustment_type": "contract_modification",
            "adjustment_reason": "scope_increase",
            "new_total_contract_value": "180.000000",
            "requires_catch_up": True,
        },
        reporting_currency="USD",
        rate_mode="daily",
        prior_version_token_or_root="root",
    )
    revenue_token_2 = revenue_build_token(
        contract_id=_uuid("00000000-0000-0000-0000-000000000101"),
        modification_payload_normalized={
            "effective_date": "2026-06-30",
            "adjustment_type": "contract_modification",
            "adjustment_reason": "scope_increase",
            "new_total_contract_value": "180.000000",
            "requires_catch_up": True,
        },
        reporting_currency="USD",
        rate_mode="daily",
        prior_version_token_or_root="root",
    )
    assert revenue_token_1 == revenue_token_2

    lease_token_1 = lease_build_token(
        lease_id=_uuid("00000000-0000-0000-0000-000000000201"),
        modification_payload_normalized={
            "effective_date": "2026-07-01",
            "modification_type": "term_change",
            "modification_reason": "extend",
            "new_discount_rate": "0.120000",
            "new_end_date": "2027-03-31",
            "remeasurement_delta_reporting_currency": "5.000000",
        },
        reporting_currency="USD",
        rate_mode="month_end_locked",
        prior_version_token_or_root="root",
    )
    lease_token_2 = lease_build_token(
        lease_id=_uuid("00000000-0000-0000-0000-000000000201"),
        modification_payload_normalized={
            "effective_date": "2026-07-01",
            "modification_type": "term_change",
            "modification_reason": "extend",
            "new_discount_rate": "0.120000",
            "new_end_date": "2027-03-31",
            "remeasurement_delta_reporting_currency": "5.000000",
        },
        reporting_currency="USD",
        rate_mode="month_end_locked",
        prior_version_token_or_root="root",
    )
    assert lease_token_1 == lease_token_2

    prepaid_token_1 = prepaid_build_token(
        prepaid_id=_uuid("00000000-0000-0000-0000-000000000301"),
        pattern_normalized_json={
            "pattern_type": "straight_line",
            "period_frequency": "monthly",
            "periods": [],
        },
        reporting_currency="USD",
        rate_mode="month_end_locked",
        adjustment_effective_date=date(2026, 1, 1),
        prior_schedule_version_token_or_root="root",
    )
    prepaid_token_2 = prepaid_build_token(
        prepaid_id=_uuid("00000000-0000-0000-0000-000000000301"),
        pattern_normalized_json={
            "pattern_type": "straight_line",
            "period_frequency": "monthly",
            "periods": [],
        },
        reporting_currency="USD",
        rate_mode="month_end_locked",
        adjustment_effective_date=date(2026, 1, 1),
        prior_schedule_version_token_or_root="root",
    )
    assert prepaid_token_1 == prepaid_token_2

    far_token_1 = far_build_token(
        asset_id=_uuid("00000000-0000-0000-0000-000000000401"),
        depreciation_method="reducing_balance",
        useful_life_months=None,
        reducing_balance_rate_annual=Decimal("0.180000"),
        residual_value_reporting_currency=Decimal("100.000000"),
        reporting_currency="USD",
        rate_mode="month_end_locked",
        effective_date=date(2026, 1, 1),
        prior_schedule_version_token_or_root="root",
    )
    far_token_2 = far_build_token(
        asset_id=_uuid("00000000-0000-0000-0000-000000000401"),
        depreciation_method="reducing_balance",
        useful_life_months=None,
        reducing_balance_rate_annual=Decimal("0.180000"),
        residual_value_reporting_currency=Decimal("100.000000"),
        reporting_currency="USD",
        rate_mode="month_end_locked",
        effective_date=date(2026, 1, 1),
        prior_schedule_version_token_or_root="root",
    )
    assert far_token_1 == far_token_2


def test_schedule_version_token_changes_with_prior_version_chain() -> None:
    token_a = prepaid_build_token(
        prepaid_id=_uuid("00000000-0000-0000-0000-000000000511"),
        pattern_normalized_json={"pattern_type": "straight_line", "period_frequency": "monthly", "periods": []},
        reporting_currency="USD",
        rate_mode="month_end_locked",
        adjustment_effective_date=date(2026, 4, 1),
        prior_schedule_version_token_or_root="root",
    )
    token_b = prepaid_build_token(
        prepaid_id=_uuid("00000000-0000-0000-0000-000000000511"),
        pattern_normalized_json={"pattern_type": "straight_line", "period_frequency": "monthly", "periods": []},
        reporting_currency="USD",
        rate_mode="month_end_locked",
        adjustment_effective_date=date(2026, 4, 1),
        prior_schedule_version_token_or_root="v1",
    )
    assert token_a != token_b
