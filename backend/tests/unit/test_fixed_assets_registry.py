from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import pytest

from financeops.db.models.fixed_assets import Asset
from financeops.platform.db.models import CpEntity
from financeops.schemas.fixed_assets import FixedAssetInput
from financeops.services.fixed_assets.asset_registry import register_assets


def _asset_input(entity_id: str) -> FixedAssetInput:
    return FixedAssetInput.model_validate(
        {
            "asset_code": "FAR-REG-001",
            "description": "Registry asset",
            "entity_id": entity_id,
            "asset_class": "equipment",
            "asset_currency": "USD",
            "reporting_currency": "USD",
            "capitalization_date": "2026-01-01",
            "in_service_date": "2026-01-01",
            "capitalized_amount_asset_currency": "1200.000000",
            "depreciation_method": "straight_line",
            "useful_life_months": 12,
            "residual_value_reporting_currency": "200.000000",
            "rate_mode": "month_end_locked",
            "source_acquisition_reference": "SRC-FAR-REG-001",
            "source_reference_id": "00000000-0000-0000-0000-00000000f101",
            "impairments": [],
            "disposals": [],
        }
    )


@pytest.mark.asyncio
async def test_fixed_assets_registry_creates_and_reuses_records(
    async_session: AsyncSession,
    test_tenant,
    test_user,
) -> None:
    del test_user
    entity_id = await async_session.scalar(
        select(CpEntity.id).where(CpEntity.tenant_id == test_tenant.id).limit(1)
    )
    assert entity_id is not None
    payload = [_asset_input(str(entity_id))]

    first = await register_assets(
        async_session,
        tenant_id=test_tenant.id,
        user_id=test_tenant.id,
        correlation_id="00000000-0000-0000-0000-00000000f201",
        accepted_at=test_tenant.created_at,
        assets=payload,
    )
    second = await register_assets(
        async_session,
        tenant_id=test_tenant.id,
        user_id=test_tenant.id,
        correlation_id="00000000-0000-0000-0000-00000000f201",
        accepted_at=test_tenant.created_at,
        assets=payload,
    )

    assert len(first) == 1
    assert len(second) == 1
    assert first[0].asset_id == second[0].asset_id

    count = int(
        await async_session.scalar(
            select(func.count()).select_from(Asset).where(Asset.tenant_id == test_tenant.id)
        )
        or 0
    )
    assert count == 1
