from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.modules.working_capital.models import APLineItem, ARLineItem, WCSnapshot
from financeops.modules.working_capital.service import (
    compute_wc_snapshot,
    get_payment_probability,
)


@pytest.mark.asyncio
async def test_wc_snapshot_created_for_period(async_session: AsyncSession, test_user) -> None:
    """Snapshot is created for requested tenant and period."""
    snapshot = await compute_wc_snapshot(async_session, test_user.tenant_id, "2025-03")
    assert snapshot.period == "2025-03"


@pytest.mark.asyncio
async def test_dso_computed_with_decimal(async_session: AsyncSession, test_user) -> None:
    """DSO formula uses Decimal and matches expected known value."""
    snapshot = await compute_wc_snapshot(async_session, test_user.tenant_id, "2025-03")
    assert isinstance(snapshot.dso_days, Decimal)
    assert snapshot.dso_days == Decimal("6.20")


@pytest.mark.asyncio
async def test_dpo_computed_with_decimal(async_session: AsyncSession, test_user) -> None:
    """DPO is computed as Decimal without float conversion."""
    snapshot = await compute_wc_snapshot(async_session, test_user.tenant_id, "2025-03")
    assert isinstance(snapshot.dpo_days, Decimal)


@pytest.mark.asyncio
async def test_ccc_equals_dso_plus_inventory_minus_dpo(async_session: AsyncSession, test_user) -> None:
    """CCC equals DSO + inventory_days - DPO."""
    snapshot = await compute_wc_snapshot(async_session, test_user.tenant_id, "2025-03")
    assert snapshot.ccc_days == snapshot.dso_days + snapshot.inventory_days - snapshot.dpo_days


@pytest.mark.asyncio
async def test_zero_revenue_gives_zero_dso(async_session: AsyncSession, test_user, monkeypatch) -> None:
    """Zero revenue input avoids division-by-zero and yields DSO=0."""
    from financeops.modules import working_capital as wc_pkg
    from financeops.modules.working_capital import service as wc_service

    async def _fake_inputs(session, *, tenant_id, period, entity_id):
        del session, tenant_id, period, entity_id
        return {
            "ar_total": Decimal("1000000"),
            "ap_total": Decimal("500000"),
            "inventory": Decimal("0"),
            "current_assets": Decimal("2000000"),
            "current_liabilities": Decimal("1000000"),
            "revenue": Decimal("0"),
            "cogs": Decimal("2500000"),
        }

    monkeypatch.setattr(wc_service, "_load_financial_inputs", _fake_inputs)
    snapshot = await compute_wc_snapshot(async_session, test_user.tenant_id, "2025-04")
    assert snapshot.dso_days == Decimal("0.00")


@pytest.mark.asyncio
async def test_snapshot_unique_per_tenant_period(async_session: AsyncSession, test_user) -> None:
    """Repeated compute returns existing snapshot for same tenant+period."""
    first = await compute_wc_snapshot(async_session, test_user.tenant_id, "2025-03")
    second = await compute_wc_snapshot(async_session, test_user.tenant_id, "2025-03")
    assert first.id == second.id


@pytest.mark.asyncio
async def test_ar_line_items_created_with_snapshot(async_session: AsyncSession, test_user) -> None:
    """AR line items are generated when snapshot is created."""
    snapshot = await compute_wc_snapshot(async_session, test_user.tenant_id, "2025-03")
    rows = (
        await async_session.execute(
            select(ARLineItem).where(ARLineItem.snapshot_id == snapshot.id)
        )
    ).scalars().all()
    assert rows


@pytest.mark.asyncio
async def test_aging_bucket_current_for_not_overdue(async_session: AsyncSession, test_user) -> None:
    """Current AR bucket exists for not overdue records."""
    snapshot = await compute_wc_snapshot(async_session, test_user.tenant_id, "2025-03")
    row = (
        await async_session.execute(
            select(ARLineItem).where(
                ARLineItem.snapshot_id == snapshot.id,
                ARLineItem.days_overdue == 0,
            )
        )
    ).scalar_one()
    assert row.aging_bucket == "current"


@pytest.mark.asyncio
async def test_aging_bucket_days_30_for_31_to_60_overdue(async_session: AsyncSession, test_user) -> None:
    """AR row in 31-60 overdue range maps to days_30 bucket."""
    snapshot = await compute_wc_snapshot(async_session, test_user.tenant_id, "2025-03")
    row = (
        await async_session.execute(
            select(ARLineItem).where(
                ARLineItem.snapshot_id == snapshot.id,
                ARLineItem.days_overdue.between(31, 60),
            )
        )
    ).scalar_one()
    assert row.aging_bucket == "days_30"


@pytest.mark.asyncio
async def test_payment_probability_under_30_days() -> None:
    """Under-30-day overdue probability returns 0.85."""
    assert await get_payment_probability(15) == Decimal("0.8500")


@pytest.mark.asyncio
async def test_payment_probability_over_90_days() -> None:
    """Over-90-day overdue probability returns 0.20."""
    assert await get_payment_probability(95) == Decimal("0.2000")


@pytest.mark.asyncio
async def test_dashboard_endpoint_returns_structure(async_client: AsyncClient, test_access_token: str) -> None:
    """Dashboard endpoint returns expected high-level keys."""
    response = await async_client.get(
        "/api/v1/working-capital/dashboard?period=2025-03",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert {"current_snapshot", "trends", "top_overdue_ar", "discount_opportunities", "mom_changes"}.issubset(payload.keys())


@pytest.mark.asyncio
async def test_dashboard_creates_snapshot_if_missing(async_client: AsyncClient, async_session: AsyncSession, test_access_token: str, test_user) -> None:
    """Dashboard call creates a snapshot when missing."""
    response = await async_client.get(
        "/api/v1/working-capital/dashboard?period=2025-05",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 200
    snapshot = (
        await async_session.execute(
            select(WCSnapshot).where(
                WCSnapshot.tenant_id == test_user.tenant_id,
                WCSnapshot.period == "2025-05",
            )
        )
    ).scalar_one_or_none()
    assert snapshot is not None


@pytest.mark.asyncio
async def test_ar_list_paginated(async_client: AsyncClient, test_access_token: str) -> None:
    """AR list endpoint returns paginated envelope."""
    response = await async_client.get(
        "/api/v1/working-capital/ar?period=2025-03&limit=5&offset=0",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert {"data", "total", "limit", "offset"}.issubset(payload.keys())


@pytest.mark.asyncio
async def test_ar_filtered_by_aging_bucket(async_client: AsyncClient, test_access_token: str) -> None:
    """AR list filter by aging bucket returns only matching rows."""
    response = await async_client.get(
        "/api/v1/working-capital/ar?period=2025-03&aging_bucket=days_30",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 200
    rows = response.json()["data"]["data"]
    assert all(row["aging_bucket"] == "days_30" for row in rows)


@pytest.mark.asyncio
async def test_ap_discount_only_filter(async_client: AsyncClient, test_access_token: str) -> None:
    """AP list discount_only filter returns only discount-eligible rows."""
    response = await async_client.get(
        "/api/v1/working-capital/ap?period=2025-03&discount_only=true",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 200
    rows = response.json()["data"]["data"]
    assert all(row["early_payment_discount_available"] is True for row in rows)


@pytest.mark.asyncio
async def test_trends_returns_array(async_client: AsyncClient, test_access_token: str) -> None:
    """Trends endpoint returns a list payload."""
    response = await async_client.get(
        "/api/v1/working-capital/trends",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 200
    assert isinstance(response.json()["data"], list)


@pytest.mark.asyncio
async def test_tenant_isolation_wc_snapshots(async_session: AsyncSession, test_user) -> None:
    """Different tenants have isolated working-capital snapshots."""
    await compute_wc_snapshot(async_session, test_user.tenant_id, "2025-03")
    tenant_b = uuid.uuid4()
    await compute_wc_snapshot(async_session, tenant_b, "2025-03")

    rows_a = (
        await async_session.execute(
            select(WCSnapshot).where(WCSnapshot.tenant_id == test_user.tenant_id)
        )
    ).scalars().all()
    rows_b = (
        await async_session.execute(
            select(WCSnapshot).where(WCSnapshot.tenant_id == tenant_b)
        )
    ).scalars().all()
    assert rows_a and rows_b
    assert all(row.tenant_id == test_user.tenant_id for row in rows_a)
    assert all(row.tenant_id == tenant_b for row in rows_b)


@pytest.mark.asyncio
async def test_tenant_isolation_ar_line_items(async_session: AsyncSession, test_user) -> None:
    """AR line items are tenant-scoped per snapshot."""
    snapshot_a = await compute_wc_snapshot(async_session, test_user.tenant_id, "2025-03")
    tenant_b = uuid.uuid4()
    snapshot_b = await compute_wc_snapshot(async_session, tenant_b, "2025-03")

    rows_a = (
        await async_session.execute(
            select(ARLineItem).where(ARLineItem.snapshot_id == snapshot_a.id)
        )
    ).scalars().all()
    rows_b = (
        await async_session.execute(
            select(ARLineItem).where(ARLineItem.snapshot_id == snapshot_b.id)
        )
    ).scalars().all()

    assert rows_a and rows_b
    assert all(row.tenant_id == test_user.tenant_id for row in rows_a)
    assert all(row.tenant_id == tenant_b for row in rows_b)


@pytest.mark.asyncio
async def test_all_snapshot_amounts_are_decimal(async_session: AsyncSession, test_user) -> None:
    """All key snapshot amount fields remain Decimal typed."""
    snapshot = await compute_wc_snapshot(async_session, test_user.tenant_id, "2025-03")
    assert isinstance(snapshot.ar_total, Decimal)
    assert isinstance(snapshot.ap_total, Decimal)
    assert isinstance(snapshot.net_working_capital, Decimal)
