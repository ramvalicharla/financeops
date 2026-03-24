from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.security import create_access_token
from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql
from financeops.db.models.users import IamUser
from financeops.modules.cash_flow_forecast.models import CashFlowForecastAssumption, CashFlowForecastRun
from financeops.modules.cash_flow_forecast.service import (
    create_forecast_run,
    get_forecast_summary,
    publish_forecast,
    seed_from_historical,
    update_week_assumptions,
)


def _auth_headers(user: IamUser) -> dict[str, str]:
    token = create_access_token(user.id, user.tenant_id, user.role.value)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_create_forecast_seeds_13_weeks(async_session: AsyncSession, test_user: IamUser) -> None:
    run = await create_forecast_run(
        async_session,
        tenant_id=test_user.tenant_id,
        run_name="Treasury Base",
        base_date=date(2026, 3, 2),
        opening_cash_balance=Decimal("100000.00"),
        currency="INR",
        created_by=test_user.id,
    )
    rows = (
        await async_session.execute(
            select(CashFlowForecastAssumption).where(CashFlowForecastAssumption.forecast_run_id == run.id)
        )
    ).scalars().all()
    assert len(rows) == 13


@pytest.mark.asyncio
async def test_week_start_dates_correct(async_session: AsyncSession, test_user: IamUser) -> None:
    base = date(2026, 3, 2)
    run = await create_forecast_run(
        async_session,
        tenant_id=test_user.tenant_id,
        run_name="Dates",
        base_date=base,
        opening_cash_balance=Decimal("1000.00"),
        currency="INR",
        created_by=test_user.id,
    )
    rows = (
        await async_session.execute(
            select(CashFlowForecastAssumption)
            .where(CashFlowForecastAssumption.forecast_run_id == run.id)
            .order_by(CashFlowForecastAssumption.week_number)
        )
    ).scalars().all()
    assert rows[0].week_start_date == base
    assert rows[1].week_start_date == base + timedelta(days=7)


@pytest.mark.asyncio
async def test_closing_balance_cascades(async_session: AsyncSession, test_user: IamUser) -> None:
    run = await create_forecast_run(
        async_session,
        tenant_id=test_user.tenant_id,
        run_name="Cascade",
        base_date=date(2026, 3, 2),
        opening_cash_balance=Decimal("100.00"),
        currency="INR",
        created_by=test_user.id,
    )
    await update_week_assumptions(
        async_session,
        tenant_id=test_user.tenant_id,
        forecast_run_id=run.id,
        week_number=3,
        assumption_updates={"customer_collections": Decimal("50.00")},
    )
    rows = (
        await async_session.execute(
            select(CashFlowForecastAssumption)
            .where(CashFlowForecastAssumption.forecast_run_id == run.id)
            .order_by(CashFlowForecastAssumption.week_number)
        )
    ).scalars().all()
    assert rows[2].closing_balance == Decimal("150.00")
    assert rows[3].closing_balance == Decimal("150.00")


@pytest.mark.asyncio
async def test_closing_balance_week1_correct(async_session: AsyncSession, test_user: IamUser) -> None:
    run = await create_forecast_run(
        async_session,
        tenant_id=test_user.tenant_id,
        run_name="Week1",
        base_date=date(2026, 3, 2),
        opening_cash_balance=Decimal("100.00"),
        currency="INR",
        created_by=test_user.id,
    )
    week = await update_week_assumptions(
        async_session,
        tenant_id=test_user.tenant_id,
        forecast_run_id=run.id,
        week_number=1,
        assumption_updates={"customer_collections": Decimal("20.00")},
    )
    assert week.closing_balance == Decimal("120.00")


@pytest.mark.asyncio
async def test_closing_balance_week2_uses_week1_closing(async_session: AsyncSession, test_user: IamUser) -> None:
    run = await create_forecast_run(
        async_session,
        tenant_id=test_user.tenant_id,
        run_name="Week2",
        base_date=date(2026, 3, 2),
        opening_cash_balance=Decimal("100.00"),
        currency="INR",
        created_by=test_user.id,
    )
    await update_week_assumptions(
        async_session,
        tenant_id=test_user.tenant_id,
        forecast_run_id=run.id,
        week_number=1,
        assumption_updates={"customer_collections": Decimal("20.00")},
    )
    week2 = await update_week_assumptions(
        async_session,
        tenant_id=test_user.tenant_id,
        forecast_run_id=run.id,
        week_number=2,
        assumption_updates={"supplier_payments": Decimal("30.00")},
    )
    assert week2.closing_balance == Decimal("90.00")


@pytest.mark.asyncio
async def test_all_amounts_decimal(async_session: AsyncSession, test_user: IamUser) -> None:
    run = await create_forecast_run(
        async_session,
        tenant_id=test_user.tenant_id,
        run_name="Decimals",
        base_date=date(2026, 3, 2),
        opening_cash_balance=Decimal("500.00"),
        currency="INR",
        created_by=test_user.id,
    )
    row = (
        await async_session.execute(
            select(CashFlowForecastAssumption)
            .where(CashFlowForecastAssumption.forecast_run_id == run.id, CashFlowForecastAssumption.week_number == 1)
        )
    ).scalar_one()
    assert isinstance(row.total_inflows, Decimal)
    assert isinstance(row.closing_balance, Decimal)


@pytest.mark.asyncio
async def test_minimum_balance_identified_correctly(async_session: AsyncSession, test_user: IamUser) -> None:
    run = await create_forecast_run(
        async_session,
        tenant_id=test_user.tenant_id,
        run_name="Minimum",
        base_date=date(2026, 3, 2),
        opening_cash_balance=Decimal("100.00"),
        currency="INR",
        created_by=test_user.id,
    )
    await update_week_assumptions(
        async_session,
        tenant_id=test_user.tenant_id,
        forecast_run_id=run.id,
        week_number=5,
        assumption_updates={"supplier_payments": Decimal("200.00")},
    )
    summary = await get_forecast_summary(async_session, test_user.tenant_id, run.id)
    assert summary["minimum_balance_week"] == 5


@pytest.mark.asyncio
async def test_weeks_below_zero_detected(async_session: AsyncSession, test_user: IamUser) -> None:
    run = await create_forecast_run(
        async_session,
        tenant_id=test_user.tenant_id,
        run_name="Negative",
        base_date=date(2026, 3, 2),
        opening_cash_balance=Decimal("10.00"),
        currency="INR",
        created_by=test_user.id,
    )
    await update_week_assumptions(
        async_session,
        tenant_id=test_user.tenant_id,
        forecast_run_id=run.id,
        week_number=5,
        assumption_updates={"supplier_payments": Decimal("20.00")},
    )
    summary = await get_forecast_summary(async_session, test_user.tenant_id, run.id)
    assert 5 in summary["weeks_below_zero"]


@pytest.mark.asyncio
async def test_seed_from_historical_uses_decimal(async_session: AsyncSession, test_user: IamUser) -> None:
    run = await create_forecast_run(
        async_session,
        tenant_id=test_user.tenant_id,
        run_name="Seed",
        base_date=date(2026, 3, 2),
        opening_cash_balance=Decimal("1000.00"),
        currency="INR",
        created_by=test_user.id,
    )
    rows = await seed_from_historical(async_session, test_user.tenant_id, run.id)
    assert isinstance(rows[0].customer_collections, Decimal)


@pytest.mark.asyncio
async def test_forecast_run_append_only(async_session: AsyncSession, test_user: IamUser) -> None:
    run = await create_forecast_run(
        async_session,
        tenant_id=test_user.tenant_id,
        run_name="AppendOnly",
        base_date=date(2026, 3, 2),
        opening_cash_balance=Decimal("100.00"),
        currency="INR",
        created_by=test_user.id,
    )
    await async_session.execute(text(append_only_function_sql()))
    await async_session.execute(text(drop_trigger_sql("cash_flow_forecast_runs")))
    await async_session.execute(text(create_trigger_sql("cash_flow_forecast_runs")))
    await async_session.flush()

    with pytest.raises(Exception):
        await async_session.execute(
            text("UPDATE cash_flow_forecast_runs SET run_name = 'X' WHERE id = :id"),
            {"id": run.id},
        )


@pytest.mark.asyncio
async def test_publish_supersedes_previous(async_session: AsyncSession, test_user: IamUser) -> None:
    run1 = await create_forecast_run(
        async_session,
        tenant_id=test_user.tenant_id,
        run_name="R1",
        base_date=date(2026, 3, 2),
        opening_cash_balance=Decimal("100.00"),
        currency="INR",
        created_by=test_user.id,
    )
    run2 = await create_forecast_run(
        async_session,
        tenant_id=test_user.tenant_id,
        run_name="R2",
        base_date=date(2026, 3, 9),
        opening_cash_balance=Decimal("100.00"),
        currency="INR",
        created_by=test_user.id,
    )
    await publish_forecast(async_session, test_user.tenant_id, run1.id)
    await publish_forecast(async_session, test_user.tenant_id, run2.id)
    assert run2.status == "published"
    assert run1.status == "superseded"


@pytest.mark.asyncio
async def test_forecast_rls(async_client, async_session: AsyncSession, test_user: IamUser) -> None:
    other_run = CashFlowForecastRun(
        tenant_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        run_name="Other",
        base_date=date(2026, 3, 2),
        weeks=13,
        opening_cash_balance=Decimal("10.00"),
        currency="INR",
        status="draft",
        is_published=False,
        created_by=test_user.id,
    )
    async_session.add(other_run)
    await async_session.flush()

    response = await async_client.get("/api/v1/treasury/forecasts", headers=_auth_headers(test_user))
    assert response.status_code == 200
    rows = response.json()["data"]["data"]
    assert all(row["tenant_id"] == str(test_user.tenant_id) for row in rows)


@pytest.mark.asyncio
async def test_api_create_forecast(async_client, test_user: IamUser) -> None:
    response = await async_client.post(
        "/api/v1/treasury/forecasts",
        headers=_auth_headers(test_user),
        json={
            "run_name": "API Forecast",
            "base_date": "2026-03-02",
            "opening_cash_balance": "1000.00",
            "currency": "INR",
            "weeks": 13,
            "seed_historical": False,
        },
    )
    assert response.status_code == 200
    assert response.json()["data"]["run"]["run_name"] == "API Forecast"


@pytest.mark.asyncio
async def test_api_update_week(async_client, test_user: IamUser) -> None:
    create = await async_client.post(
        "/api/v1/treasury/forecasts",
        headers=_auth_headers(test_user),
        json={
            "run_name": "Update Week",
            "base_date": "2026-03-02",
            "opening_cash_balance": "1000.00",
            "currency": "INR",
            "weeks": 13,
            "seed_historical": False,
        },
    )
    forecast_id = create.json()["data"]["run"]["id"]
    response = await async_client.patch(
        f"/api/v1/treasury/forecasts/{forecast_id}/weeks/1",
        headers=_auth_headers(test_user),
        json={"customer_collections": "200.00"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["closing_balance"] == "1200.00"


@pytest.mark.asyncio
async def test_api_summary_structure(async_client, test_user: IamUser) -> None:
    create = await async_client.post(
        "/api/v1/treasury/forecasts",
        headers=_auth_headers(test_user),
        json={
            "run_name": "Summary",
            "base_date": "2026-03-02",
            "opening_cash_balance": "1000.00",
            "currency": "INR",
            "weeks": 13,
            "seed_historical": False,
        },
    )
    forecast_id = create.json()["data"]["run"]["id"]
    response = await async_client.get(f"/api/v1/treasury/forecasts/{forecast_id}", headers=_auth_headers(test_user))
    assert response.status_code == 200
    payload = response.json()["data"]
    assert {"run", "weeks", "opening_balance", "closing_balance_week_13"}.issubset(payload)
