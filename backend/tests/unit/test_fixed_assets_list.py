from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _fake_fa_asset(tenant_id: uuid.UUID, asset_id: uuid.UUID | None = None) -> MagicMock:
    a = MagicMock()
    a.id = asset_id or uuid.uuid4()
    a.tenant_id = tenant_id
    a.entity_id = uuid.uuid4()
    a.asset_class_id = uuid.uuid4()
    a.asset_code = "FA-001"
    a.asset_name = "Test Asset"
    a.description = None
    a.location = None
    a.serial_number = None
    a.purchase_date = date(2024, 1, 1)
    a.capitalisation_date = date(2024, 1, 1)
    a.original_cost = Decimal("10000.0000")
    a.residual_value = Decimal("0.0000")
    a.useful_life_years = Decimal("5.0000")
    a.depreciation_method = "SLM"
    a.it_act_block_number = None
    a.status = "ACTIVE"
    a.disposal_date = None
    a.disposal_proceeds = None
    a.gaap_overrides = None
    a.location_id = None
    a.cost_centre_id = None
    a.is_active = True
    a.intent_id = None
    a.job_id = None
    a.created_at = datetime(2024, 1, 1)
    a.updated_at = None
    return a


async def test_list_fixed_assets_returns_tenant_assets() -> None:
    from financeops.api.v1.fixed_assets import list_fixed_assets

    tenant_id = uuid.uuid4()
    entity_id = uuid.uuid4()
    fake_asset = _fake_fa_asset(tenant_id)
    fake_payload = {
        "items": [fake_asset],
        "total": 1,
        "skip": 0,
        "limit": 20,
        "has_more": False,
    }

    mock_session = MagicMock()
    mock_user = MagicMock()
    mock_user.tenant_id = tenant_id

    with patch("financeops.api.v1.fixed_assets.FixedAssetService") as MockService:
        MockService.return_value.get_assets = AsyncMock(return_value=fake_payload)
        result = await list_fixed_assets(
            entity_id=entity_id,
            status=None,
            location_id=None,
            cost_centre_id=None,
            skip=0,
            limit=20,
            session=mock_session,
            user=mock_user,
        )

    assert result.total == 1
    assert len(result.items) == 1
    assert result.items[0].tenant_id == tenant_id


async def test_get_fixed_asset_by_id_returns_correct_asset() -> None:
    from financeops.api.v1.fixed_assets import get_fixed_asset

    tenant_id = uuid.uuid4()
    asset_id = uuid.uuid4()
    fake_asset = _fake_fa_asset(tenant_id, asset_id)

    mock_session = MagicMock()
    mock_user = MagicMock()
    mock_user.tenant_id = tenant_id

    with patch("financeops.api.v1.fixed_assets.FixedAssetService") as MockService:
        MockService.return_value.get_asset = AsyncMock(return_value=fake_asset)
        result = await get_fixed_asset(
            asset_id=asset_id,
            session=mock_session,
            user=mock_user,
        )

    assert result.id == asset_id
    assert result.tenant_id == tenant_id


async def test_get_fixed_asset_wrong_tenant_returns_404() -> None:
    from financeops.core.exceptions import NotFoundError
    from financeops.modules.fixed_assets.application.fixed_asset_service import FixedAssetService

    wrong_tenant_id = uuid.uuid4()
    asset_id = uuid.uuid4()

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session = MagicMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    service = FixedAssetService(mock_session)
    with pytest.raises(NotFoundError):
        await service.get_asset(wrong_tenant_id, asset_id)
