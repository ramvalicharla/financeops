from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import ValidationError
from financeops.services.fixed_assets.asset_registry import RegisteredAsset
from financeops.services.fixed_assets.depreciation_engine import (
    MissingLockedRateError,
    generate_base_depreciation_rows,
)


def _uuid(value: str) -> UUID:
    return UUID(value)


def _asset(*, method: str, rate_mode: str, asset_currency: str, reporting_currency: str) -> RegisteredAsset:
    return RegisteredAsset(
        asset_id=_uuid("00000000-0000-0000-0000-00000000f301"),
        asset_code="FAR-DEP-1",
        description="depreciation asset",
        entity_id="00000000-0000-0000-0000-00000000e005",
        asset_class="equipment",
        asset_currency=asset_currency,
        reporting_currency=reporting_currency,
        capitalization_date=date(2026, 1, 1),
        in_service_date=date(2026, 1, 1),
        capitalized_amount_asset_currency=Decimal("1200.000000"),
        depreciation_method=method,
        useful_life_months=12 if method == "straight_line" else None,
        reducing_balance_rate_annual=Decimal("0.240000") if method == "reducing_balance" else None,
        residual_value_reporting_currency=Decimal("0.000000"),
        rate_mode=rate_mode,
        source_acquisition_reference="SRC-FAR-DEP-1",
        parent_reference_id=_uuid("00000000-0000-0000-0000-00000000f302"),
        source_reference_id=_uuid("00000000-0000-0000-0000-00000000f303"),
        impairments=[],
        disposals=[],
    )


@pytest.mark.asyncio
async def test_generate_base_rows_straight_line_deterministic(async_session: AsyncSession, test_tenant) -> None:
    output = await generate_base_depreciation_rows(
        async_session,
        tenant_id=test_tenant.id,
        assets=[_asset(method="straight_line", rate_mode="month_end_locked", asset_currency="USD", reporting_currency="USD")],
    )

    assert output.rows
    assert len(output.root_schedule_version_tokens) == 1
    assert output.rows[0].depreciation_amount_reporting_currency > Decimal("0")


@pytest.mark.asyncio
async def test_generate_base_rows_missing_month_end_lock_raises(async_session: AsyncSession, test_tenant) -> None:
    asset = _asset(method="straight_line", rate_mode="month_end_locked", asset_currency="EUR", reporting_currency="USD")
    with patch(
        "financeops.services.fixed_assets.depreciation_engine.list_manual_monthly_rates",
        new=AsyncMock(return_value=[]),
    ):
        with pytest.raises(MissingLockedRateError):
            await generate_base_depreciation_rows(
                async_session,
                tenant_id=test_tenant.id,
                assets=[asset],
            )


@pytest.mark.asyncio
async def test_generate_base_rows_daily_selected_uses_selected_rate_surface(
    async_session: AsyncSession,
    test_tenant,
) -> None:
    asset = _asset(method="straight_line", rate_mode="daily_selected", asset_currency="EUR", reporting_currency="USD")
    with patch(
        "financeops.services.fixed_assets.depreciation_engine._tenant_allows_daily_selected",
        new=AsyncMock(return_value=True),
    ), patch(
        "financeops.services.fixed_assets.depreciation_engine.resolve_selected_rate",
        new=AsyncMock(
            return_value=SimpleNamespace(
                selected_rate=Decimal("1.250000"),
                selected_source="provider_consensus",
            )
        ),
    ) as selected_spy:
        output = await generate_base_depreciation_rows(
            async_session,
            tenant_id=test_tenant.id,
            assets=[asset],
        )
    assert output.rows
    assert selected_spy.await_count >= 1


@pytest.mark.asyncio
async def test_generate_base_rows_rejects_daily_selected_when_policy_disallows(
    async_session: AsyncSession,
    test_tenant,
) -> None:
    asset = _asset(method="straight_line", rate_mode="daily_selected", asset_currency="EUR", reporting_currency="USD")
    with patch(
        "financeops.services.fixed_assets.depreciation_engine._tenant_allows_daily_selected",
        new=AsyncMock(return_value=False),
    ):
        with pytest.raises(ValidationError):
            await generate_base_depreciation_rows(
                async_session,
                tenant_id=test_tenant.id,
                assets=[asset],
            )
