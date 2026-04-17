from __future__ import annotations

import uuid
from decimal import Decimal, ROUND_HALF_UP

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.modules.working_capital.domain.exceptions import InsufficientGLDataError
from financeops.modules.working_capital.models import APLineItem, ARLineItem, WCSnapshot
from financeops.modules.working_capital.service import get_payment_probability
from tests.integration.entitlement_helpers import grant_boolean_entitlement
from tests.working_capital_helpers import compute_wc_snapshot, seed_working_capital_gl_data


@pytest_asyncio.fixture(autouse=True)
async def _grant_working_capital_entitlement(api_session_factory, test_user) -> None:
    async with api_session_factory() as db:
        await grant_boolean_entitlement(
            db,
            tenant_id=test_user.tenant_id,
            feature_name="working_capital",
            actor_user_id=test_user.id,
        )
        await db.commit()


async def _seed_default_wc_gl(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    uploaded_by: uuid.UUID,
    period: str,
    ar: Decimal | str = "365.00",
    ap: Decimal | str = "730.00",
    inventory: Decimal | str = "182.50",
    cash: Decimal | str = "1095.00",
    accrued_liabilities: Decimal | str = "365.00",
    revenue: Decimal | str = "3650.00",
    cogs: Decimal | str = "1460.00",
    prior_revenue: dict[str, Decimal | str] | None = None,
) -> None:
    await seed_working_capital_gl_data(
        session,
        tenant_id=tenant_id,
        period=period,
        uploaded_by=uploaded_by,
        ar=ar,
        ap=ap,
        inventory=inventory,
        cash=cash,
        accrued_liabilities=accrued_liabilities,
        revenue=revenue,
        cogs=cogs,
        prior_revenue=prior_revenue,
    )


@pytest.mark.asyncio
async def test_wc_snapshot_created_for_period(async_session: AsyncSession, test_user) -> None:
    await _seed_default_wc_gl(
        async_session,
        tenant_id=test_user.tenant_id,
        uploaded_by=test_user.id,
        period="2025-03",
    )
    snapshot = await compute_wc_snapshot(async_session, test_user.tenant_id, "2025-03")
    assert snapshot.period == "2025-03"


@pytest.mark.asyncio
async def test_dso_computed_with_decimal(async_session: AsyncSession, test_user) -> None:
    await _seed_default_wc_gl(
        async_session,
        tenant_id=test_user.tenant_id,
        uploaded_by=test_user.id,
        period="2025-04",
        ar="365.00",
        revenue="3650.00",
        cogs="1460.00",
    )
    snapshot = await compute_wc_snapshot(async_session, test_user.tenant_id, "2025-04")
    assert isinstance(snapshot.dso_days, Decimal)
    assert snapshot.dso_days == Decimal("36.50")


@pytest.mark.asyncio
async def test_dpo_computed_with_decimal(async_session: AsyncSession, test_user) -> None:
    await _seed_default_wc_gl(
        async_session,
        tenant_id=test_user.tenant_id,
        uploaded_by=test_user.id,
        period="2025-05",
        ap="730.00",
        cogs="1460.00",
    )
    snapshot = await compute_wc_snapshot(async_session, test_user.tenant_id, "2025-05")
    assert isinstance(snapshot.dpo_days, Decimal)
    assert snapshot.dpo_days == Decimal("182.50")


@pytest.mark.asyncio
async def test_ccc_equals_dso_plus_inventory_minus_dpo(async_session: AsyncSession, test_user) -> None:
    await _seed_default_wc_gl(
        async_session,
        tenant_id=test_user.tenant_id,
        uploaded_by=test_user.id,
        period="2025-06",
    )
    snapshot = await compute_wc_snapshot(async_session, test_user.tenant_id, "2025-06")
    expected_ccc = (
        (Decimal("365.00") / Decimal("3650.00") * Decimal("365"))
        + (Decimal("182.50") / Decimal("1460.00") * Decimal("365"))
        - (Decimal("730.00") / Decimal("1460.00") * Decimal("365"))
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    assert snapshot.ccc_days == expected_ccc


@pytest.mark.asyncio
async def test_zero_revenue_gives_zero_dso(async_session: AsyncSession, test_user, monkeypatch) -> None:
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
    snapshot = await compute_wc_snapshot(async_session, test_user.tenant_id, "2025-07")
    assert snapshot.dso_days == Decimal("0.00")


@pytest.mark.asyncio
async def test_snapshot_unique_per_tenant_period(async_session: AsyncSession, test_user) -> None:
    await _seed_default_wc_gl(
        async_session,
        tenant_id=test_user.tenant_id,
        uploaded_by=test_user.id,
        period="2025-08",
    )
    first = await compute_wc_snapshot(async_session, test_user.tenant_id, "2025-08")
    second = await compute_wc_snapshot(async_session, test_user.tenant_id, "2025-08")
    assert first.id == second.id


@pytest.mark.asyncio
async def test_ar_line_items_created_with_snapshot(async_session: AsyncSession, test_user) -> None:
    await _seed_default_wc_gl(
        async_session,
        tenant_id=test_user.tenant_id,
        uploaded_by=test_user.id,
        period="2025-09",
    )
    snapshot = await compute_wc_snapshot(async_session, test_user.tenant_id, "2025-09")
    rows = (
        await async_session.execute(select(ARLineItem).where(ARLineItem.snapshot_id == snapshot.id))
    ).scalars().all()
    assert rows


@pytest.mark.asyncio
async def test_aging_bucket_current_for_not_overdue(async_session: AsyncSession, test_user) -> None:
    await _seed_default_wc_gl(
        async_session,
        tenant_id=test_user.tenant_id,
        uploaded_by=test_user.id,
        period="2025-10",
    )
    snapshot = await compute_wc_snapshot(async_session, test_user.tenant_id, "2025-10")
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
    await _seed_default_wc_gl(
        async_session,
        tenant_id=test_user.tenant_id,
        uploaded_by=test_user.id,
        period="2025-11",
    )
    snapshot = await compute_wc_snapshot(async_session, test_user.tenant_id, "2025-11")
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
    assert await get_payment_probability(15) == Decimal("0.8500")


@pytest.mark.asyncio
async def test_payment_probability_over_90_days() -> None:
    assert await get_payment_probability(95) == Decimal("0.2000")


@pytest.mark.asyncio
async def test_dashboard_endpoint_returns_structure(
    async_client: AsyncClient,
    api_session_factory,
    test_access_token: str,
    test_user,
) -> None:
    async with api_session_factory() as db:
        await _seed_default_wc_gl(
            db,
            tenant_id=test_user.tenant_id,
            uploaded_by=test_user.id,
            period="2025-12",
        )
        await db.commit()
    response = await async_client.get(
        "/api/v1/working-capital/dashboard?period=2025-12",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert {"current_snapshot", "trends", "top_overdue_ar", "discount_opportunities", "mom_changes"}.issubset(payload.keys())


@pytest.mark.asyncio
async def test_dashboard_creates_snapshot_if_missing(
    async_client: AsyncClient,
    api_session_factory,
    test_access_token: str,
    test_user,
) -> None:
    async with api_session_factory() as db:
        await _seed_default_wc_gl(
            db,
            tenant_id=test_user.tenant_id,
            uploaded_by=test_user.id,
            period="2026-01",
        )
        await db.commit()
    response = await async_client.get(
        "/api/v1/working-capital/dashboard?period=2026-01",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 200

    async with api_session_factory() as db:
        snapshot = (
            await db.execute(
                select(WCSnapshot).where(
                    WCSnapshot.tenant_id == test_user.tenant_id,
                    WCSnapshot.period == "2026-01",
                )
            )
        ).scalar_one_or_none()
    assert snapshot is not None


@pytest.mark.asyncio
async def test_ar_list_paginated(
    async_client: AsyncClient,
    api_session_factory,
    test_access_token: str,
    test_user,
) -> None:
    async with api_session_factory() as db:
        await _seed_default_wc_gl(
            db,
            tenant_id=test_user.tenant_id,
            uploaded_by=test_user.id,
            period="2026-02",
        )
        await db.commit()
    response = await async_client.get(
        "/api/v1/working-capital/ar?period=2026-02&limit=5&offset=0",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert {"data", "total", "limit", "offset"}.issubset(payload.keys())


@pytest.mark.asyncio
async def test_ar_filtered_by_aging_bucket(
    async_client: AsyncClient,
    api_session_factory,
    test_access_token: str,
    test_user,
) -> None:
    async with api_session_factory() as db:
        await _seed_default_wc_gl(
            db,
            tenant_id=test_user.tenant_id,
            uploaded_by=test_user.id,
            period="2026-03",
        )
        await db.commit()
    response = await async_client.get(
        "/api/v1/working-capital/ar?period=2026-03&aging_bucket=days_30",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 200
    rows = response.json()["data"]["data"]
    assert rows
    assert all(row["aging_bucket"] == "days_30" for row in rows)


@pytest.mark.asyncio
async def test_ap_discount_only_filter(
    async_client: AsyncClient,
    api_session_factory,
    test_access_token: str,
    test_user,
) -> None:
    async with api_session_factory() as db:
        await _seed_default_wc_gl(
            db,
            tenant_id=test_user.tenant_id,
            uploaded_by=test_user.id,
            period="2026-04",
        )
        await db.commit()
    response = await async_client.get(
        "/api/v1/working-capital/ap?period=2026-04&discount_only=true",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 200
    rows = response.json()["data"]["data"]
    assert rows
    assert all(row["early_payment_discount_available"] is True for row in rows)


@pytest.mark.asyncio
async def test_trends_returns_array(
    async_client: AsyncClient,
    api_session_factory,
    test_access_token: str,
    test_user,
) -> None:
    async with api_session_factory() as db:
        await _seed_default_wc_gl(
            db,
            tenant_id=test_user.tenant_id,
            uploaded_by=test_user.id,
            period="2026-05",
        )
        await compute_wc_snapshot(db, test_user.tenant_id, "2026-05")
        await db.commit()
    response = await async_client.get(
        "/api/v1/working-capital/trends",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 200
    assert isinstance(response.json()["data"], list)


@pytest.mark.asyncio
async def test_tenant_isolation_wc_snapshots(async_session: AsyncSession, test_user, api_session_factory) -> None:
    del async_session
    tenant_b = uuid.uuid4()
    async with api_session_factory() as db:
        await _seed_default_wc_gl(
            db,
            tenant_id=test_user.tenant_id,
            uploaded_by=test_user.id,
            period="2026-06",
            ar="111.00",
        )
        await compute_wc_snapshot(db, test_user.tenant_id, "2026-06")
        await _seed_default_wc_gl(
            db,
            tenant_id=tenant_b,
            uploaded_by=tenant_b,
            period="2026-06",
            ar="999.00",
        )
        await compute_wc_snapshot(db, tenant_b, "2026-06")
        await db.commit()

    async with api_session_factory() as db:
        rows_a = (
            await db.execute(select(WCSnapshot).where(WCSnapshot.tenant_id == test_user.tenant_id))
        ).scalars().all()
        rows_b = (
            await db.execute(select(WCSnapshot).where(WCSnapshot.tenant_id == tenant_b))
        ).scalars().all()
    assert rows_a and rows_b
    assert all(row.tenant_id == test_user.tenant_id for row in rows_a)
    assert all(row.tenant_id == tenant_b for row in rows_b)


@pytest.mark.asyncio
async def test_tenant_isolation_ar_line_items(async_session: AsyncSession, test_user, api_session_factory) -> None:
    del async_session
    tenant_b = uuid.uuid4()
    async with api_session_factory() as db:
        await _seed_default_wc_gl(
            db,
            tenant_id=test_user.tenant_id,
            uploaded_by=test_user.id,
            period="2026-07",
        )
        snapshot_a = await compute_wc_snapshot(db, test_user.tenant_id, "2026-07")
        await _seed_default_wc_gl(
            db,
            tenant_id=tenant_b,
            uploaded_by=tenant_b,
            period="2026-07",
        )
        snapshot_b = await compute_wc_snapshot(db, tenant_b, "2026-07")
        snapshot_a_id = snapshot_a.id
        snapshot_b_id = snapshot_b.id
        await db.commit()

    async with api_session_factory() as db:
        rows_a = (
            await db.execute(select(ARLineItem).where(ARLineItem.snapshot_id == snapshot_a_id))
        ).scalars().all()
        rows_b = (
            await db.execute(select(ARLineItem).where(ARLineItem.snapshot_id == snapshot_b_id))
        ).scalars().all()
    assert rows_a and rows_b
    assert all(row.tenant_id == test_user.tenant_id for row in rows_a)
    assert all(row.tenant_id == tenant_b for row in rows_b)


@pytest.mark.asyncio
async def test_all_snapshot_amounts_are_decimal(async_session: AsyncSession, test_user, api_session_factory) -> None:
    del async_session
    async with api_session_factory() as db:
        await _seed_default_wc_gl(
            db,
            tenant_id=test_user.tenant_id,
            uploaded_by=test_user.id,
            period="2026-08",
        )
        snapshot = await compute_wc_snapshot(db, test_user.tenant_id, "2026-08")
    assert isinstance(snapshot.ar_total, Decimal)
    assert isinstance(snapshot.ap_total, Decimal)
    assert isinstance(snapshot.net_working_capital, Decimal)


@pytest.mark.asyncio
async def test_compute_wc_snapshot_raises_for_new_tenant_without_gl(async_session: AsyncSession, api_session_factory) -> None:
    del async_session
    async with api_session_factory() as db:
        with pytest.raises(InsufficientGLDataError):
            await compute_wc_snapshot(db, uuid.uuid4(), "2026-09")
