from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.services.working_capital_service import (
    create_snapshot,
    get_latest_snapshot,
    list_snapshots,
)


@pytest.mark.asyncio
async def test_create_snapshot_basic(async_session: AsyncSession, test_tenant):
    snap = await create_snapshot(
        async_session,
        tenant_id=test_tenant.id,
        period_year=2025,
        period_month=3,
        entity_name="WC_Entity",
        created_by=test_tenant.id,
        cash_and_equivalents=Decimal("10000"),
        accounts_receivable=Decimal("5000"),
        accounts_payable=Decimal("3000"),
    )
    assert snap.entity_name == "WC_Entity"
    assert snap.total_current_assets == Decimal("15000")
    assert snap.total_current_liabilities == Decimal("3000")
    assert snap.working_capital == Decimal("12000")
    assert len(snap.chain_hash) == 64


@pytest.mark.asyncio
async def test_create_snapshot_ratios(async_session: AsyncSession, test_tenant):
    """Verify current_ratio, quick_ratio, cash_ratio are computed correctly."""
    snap = await create_snapshot(
        async_session,
        tenant_id=test_tenant.id,
        period_year=2025,
        period_month=4,
        entity_name="Ratios_Entity",
        created_by=test_tenant.id,
        cash_and_equivalents=Decimal("2000"),
        accounts_receivable=Decimal("3000"),
        inventory=Decimal("1000"),
        accounts_payable=Decimal("2000"),
    )
    # total_current_assets = 6000, total_current_liabilities = 2000
    # current_ratio = 6000/2000 = 3.0
    # quick_ratio = (6000 - 1000) / 2000 = 2.5
    # cash_ratio = 2000 / 2000 = 1.0
    assert snap.current_ratio == Decimal("3.0000")
    assert snap.quick_ratio == Decimal("2.5000")
    assert snap.cash_ratio == Decimal("1.0000")


@pytest.mark.asyncio
async def test_create_snapshot_zero_liabilities(async_session: AsyncSession, test_tenant):
    """Zero liabilities → ratios are 0 (safe division)."""
    snap = await create_snapshot(
        async_session,
        tenant_id=test_tenant.id,
        period_year=2025,
        period_month=5,
        entity_name="ZeroLiab_Entity",
        created_by=test_tenant.id,
        cash_and_equivalents=Decimal("5000"),
        # all liabilities = 0
    )
    assert snap.current_ratio == Decimal("0")
    assert snap.quick_ratio == Decimal("0")
    assert snap.cash_ratio == Decimal("0")


@pytest.mark.asyncio
async def test_get_latest_snapshot_returns_most_recent(
    async_session: AsyncSession, test_tenant
):
    entity = "Latest_Entity"
    await create_snapshot(
        async_session,
        tenant_id=test_tenant.id,
        period_year=2025,
        period_month=1,
        entity_name=entity,
        created_by=test_tenant.id,
        cash_and_equivalents=Decimal("1000"),
    )
    await create_snapshot(
        async_session,
        tenant_id=test_tenant.id,
        period_year=2025,
        period_month=3,
        entity_name=entity,
        created_by=test_tenant.id,
        cash_and_equivalents=Decimal("9999"),
    )
    latest = await get_latest_snapshot(async_session, test_tenant.id, entity)
    # Most recent period should be returned
    assert latest is not None
    assert latest.period_month == 3
    assert latest.cash_and_equivalents == Decimal("9999")


@pytest.mark.asyncio
async def test_list_snapshots_filter(async_session: AsyncSession, test_tenant):
    entity = "Filter_WC"
    await create_snapshot(
        async_session,
        tenant_id=test_tenant.id,
        period_year=2025,
        period_month=6,
        entity_name=entity,
        created_by=test_tenant.id,
        cash_and_equivalents=Decimal("500"),
    )
    result = await list_snapshots(
        async_session, test_tenant.id, entity_name=entity
    )
    assert len(result) >= 1
    assert all(s.entity_name == entity for s in result)
