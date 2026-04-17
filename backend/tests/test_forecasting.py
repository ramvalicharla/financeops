from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.intent.context import MutationContext, governed_mutation_context
from financeops.core.security import create_access_token, hash_password
from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql
from financeops.db.models.users import IamUser, UserRole
from financeops.modules.budgeting.service import (
    approve_budget as _approve_budget,
    create_budget_version as _create_budget_version,
    submit_budget as _submit_budget,
    upsert_budget_line as _upsert_budget_line,
)
from financeops.modules.forecasting.models import ForecastAssumption, ForecastLineItem, ForecastRun
from financeops.modules.forecasting.service import (
    _apply_growth_rate,
    compute_forecast_lines as _compute_forecast_lines,
    create_forecast_run as _create_forecast_run,
    get_forecast_vs_budget,
    publish_forecast as _publish_forecast,
    update_assumption as _update_assumption,
)


def _governed_context(intent_type: str) -> MutationContext:
    return MutationContext(
        intent_id=uuid.uuid4(),
        job_id=uuid.uuid4(),
        actor_user_id=None,
        actor_role=UserRole.finance_leader.value,
        intent_type=intent_type,
    )


async def create_budget_version(*args, **kwargs):
    with governed_mutation_context(_governed_context("CREATE_BUDGET_VERSION")):
        return await _create_budget_version(*args, **kwargs)


async def upsert_budget_line(*args, **kwargs):
    with governed_mutation_context(_governed_context("UPSERT_BUDGET_LINE")):
        return await _upsert_budget_line(*args, **kwargs)


async def approve_budget(*args, **kwargs):
    with governed_mutation_context(_governed_context("APPROVE_BUDGET_VERSION")):
        return await _approve_budget(*args, **kwargs)


async def submit_budget(*args, **kwargs):
    with governed_mutation_context(_governed_context("SUBMIT_BUDGET_VERSION")):
        return await _submit_budget(*args, **kwargs)


async def create_forecast_run(*args, **kwargs):
    with governed_mutation_context(_governed_context("CREATE_FORECAST_RUN")):
        return await _create_forecast_run(*args, **kwargs)


async def update_assumption(*args, **kwargs):
    with governed_mutation_context(_governed_context("UPDATE_FORECAST_ASSUMPTION")):
        return await _update_assumption(*args, **kwargs)


async def compute_forecast_lines(*args, **kwargs):
    with governed_mutation_context(_governed_context("COMPUTE_FORECAST_LINES")):
        return await _compute_forecast_lines(*args, **kwargs)


async def publish_forecast(*args, **kwargs):
    with governed_mutation_context(_governed_context("PUBLISH_FORECAST")):
        return await _publish_forecast(*args, **kwargs)


async def _create_run(async_session: AsyncSession, tenant_id: uuid.UUID, user_id: uuid.UUID, *, horizon: int = 12) -> ForecastRun:
    return await create_forecast_run(
        async_session,
        tenant_id=tenant_id,
        run_name="Rolling Forecast",
        forecast_type="rolling_12",
        base_period="2025-03",
        horizon_months=horizon,
        created_by=user_id,
    )


async def _set_assumption(
    async_session: AsyncSession,
    run: ForecastRun,
    key: str,
    value: Decimal,
) -> None:
    row = (
        await async_session.execute(
            select(ForecastAssumption).where(
                ForecastAssumption.forecast_run_id == run.id,
                ForecastAssumption.assumption_key == key,
            )
        )
    ).scalar_one()
    row.assumption_value = value
    await async_session.flush()


async def _create_approved_budget(async_session: AsyncSession, test_user: IamUser) -> None:
    version = await create_budget_version(
        async_session,
        tenant_id=test_user.tenant_id,
        fiscal_year=2025,
        version_name="Budget 2025",
        created_by=test_user.id,
    )
    await upsert_budget_line(
        async_session,
        tenant_id=test_user.tenant_id,
        budget_version_id=version.id,
        mis_line_item="Revenue",
        mis_category="Revenue",
        monthly_values=[Decimal("1000000.00")] * 12,
    )
    await upsert_budget_line(
        async_session,
        tenant_id=test_user.tenant_id,
        budget_version_id=version.id,
        mis_line_item="COGS",
        mis_category="Cost of Revenue",
        monthly_values=[Decimal("600000.00")] * 12,
    )
    await submit_budget(async_session, test_user.tenant_id, version.id, test_user.id)
    await approve_budget(async_session, test_user.tenant_id, version.id, test_user.id)


# Forecast run creation (5)
@pytest.mark.asyncio
async def test_create_forecast_run(async_session: AsyncSession, test_user: IamUser) -> None:
    run = await _create_run(async_session, test_user.tenant_id, test_user.id)
    assert run.status == "draft"


@pytest.mark.asyncio
async def test_default_assumptions_seeded(async_session: AsyncSession, test_user: IamUser) -> None:
    run = await _create_run(async_session, test_user.tenant_id, test_user.id)
    assumptions = (
        await async_session.execute(select(ForecastAssumption).where(ForecastAssumption.forecast_run_id == run.id))
    ).scalars().all()
    keys = {row.assumption_key for row in assumptions}
    assert {"revenue_growth_pct_monthly", "cogs_pct_of_revenue", "opex_growth_pct_monthly"}.issubset(keys)
    assert all(isinstance(row.assumption_value, Decimal) for row in assumptions)


@pytest.mark.asyncio
async def test_forecast_run_is_append_only(async_session: AsyncSession, test_user: IamUser) -> None:
    run = await _create_run(async_session, test_user.tenant_id, test_user.id)
    await async_session.execute(text(append_only_function_sql()))
    await async_session.execute(text(drop_trigger_sql("forecast_runs")))
    await async_session.execute(text(create_trigger_sql("forecast_runs")))
    await async_session.flush()
    with pytest.raises(Exception):
        await async_session.execute(
            text("UPDATE forecast_runs SET run_name = 'changed' WHERE id = :id"),
            {"id": run.id},
        )


@pytest.mark.asyncio
async def test_publish_supersedes_previous(async_session: AsyncSession, test_user: IamUser) -> None:
    first = await _create_run(async_session, test_user.tenant_id, test_user.id)
    second = await _create_run(async_session, test_user.tenant_id, test_user.id)
    await publish_forecast(async_session, test_user.tenant_id, first.id, test_user.id)
    await publish_forecast(async_session, test_user.tenant_id, second.id, test_user.id)
    refreshed_first = await async_session.get(ForecastRun, first.id)
    refreshed_second = await async_session.get(ForecastRun, second.id)
    assert refreshed_first.status == "superseded"
    assert refreshed_second.status == "published"


@pytest.mark.asyncio
async def test_only_one_published_at_a_time(async_session: AsyncSession, test_user: IamUser) -> None:
    first = await _create_run(async_session, test_user.tenant_id, test_user.id)
    second = await _create_run(async_session, test_user.tenant_id, test_user.id)
    await publish_forecast(async_session, test_user.tenant_id, first.id, test_user.id)
    await publish_forecast(async_session, test_user.tenant_id, second.id, test_user.id)
    count = (
        await async_session.execute(
            select(func.count()).select_from(ForecastRun).where(
                ForecastRun.tenant_id == test_user.tenant_id,
                ForecastRun.is_published.is_(True),
            )
        )
    ).scalar_one()
    assert count == 1


# Computation (8)
@pytest.mark.asyncio
async def test_compute_forecast_lines_created(async_session: AsyncSession, test_user: IamUser) -> None:
    run = await _create_run(async_session, test_user.tenant_id, test_user.id, horizon=12)
    rows = await compute_forecast_lines(async_session, test_user.tenant_id, run.id)
    forecast_rows = [row for row in rows if not row.is_actual]
    assert len(forecast_rows) == 12 * 5


@pytest.mark.asyncio
async def test_revenue_growth_applied_correctly(async_session: AsyncSession, test_user: IamUser) -> None:
    run = await _create_run(async_session, test_user.tenant_id, test_user.id)
    await _set_assumption(async_session, run, "revenue_growth_pct_monthly", Decimal("5.000000"))
    await compute_forecast_lines(async_session, test_user.tenant_id, run.id)
    row = (
        await async_session.execute(
            select(ForecastLineItem).where(
                ForecastLineItem.forecast_run_id == run.id,
                ForecastLineItem.period == "2025-04",
                ForecastLineItem.mis_line_item == "Revenue",
                ForecastLineItem.is_actual.is_(False),
            )
        )
    ).scalar_one()
    assert row.amount == Decimal("1050000.00")


@pytest.mark.asyncio
async def test_cogs_pct_applied_correctly(async_session: AsyncSession, test_user: IamUser) -> None:
    run = await _create_run(async_session, test_user.tenant_id, test_user.id)
    await _set_assumption(async_session, run, "revenue_growth_pct_monthly", Decimal("0.000000"))
    await _set_assumption(async_session, run, "cogs_pct_of_revenue", Decimal("60.000000"))
    await compute_forecast_lines(async_session, test_user.tenant_id, run.id)
    row = (
        await async_session.execute(
            select(ForecastLineItem).where(
                ForecastLineItem.forecast_run_id == run.id,
                ForecastLineItem.period == "2025-04",
                ForecastLineItem.mis_line_item == "COGS",
                ForecastLineItem.is_actual.is_(False),
            )
        )
    ).scalar_one()
    assert row.amount == Decimal("600000.00")


@pytest.mark.asyncio
async def test_ebitda_computed_correctly(async_session: AsyncSession, test_user: IamUser) -> None:
    run = await _create_run(async_session, test_user.tenant_id, test_user.id)
    await _set_assumption(async_session, run, "revenue_growth_pct_monthly", Decimal("0.000000"))
    await _set_assumption(async_session, run, "cogs_pct_of_revenue", Decimal("60.000000"))
    await _set_assumption(async_session, run, "opex_growth_pct_monthly", Decimal("0.000000"))
    await compute_forecast_lines(async_session, test_user.tenant_id, run.id)
    gp = (
        await async_session.execute(
            select(ForecastLineItem).where(
                ForecastLineItem.forecast_run_id == run.id,
                ForecastLineItem.period == "2025-04",
                ForecastLineItem.mis_line_item == "Gross Profit",
                ForecastLineItem.is_actual.is_(False),
            )
        )
    ).scalar_one()
    opex = (
        await async_session.execute(
            select(ForecastLineItem).where(
                ForecastLineItem.forecast_run_id == run.id,
                ForecastLineItem.period == "2025-04",
                ForecastLineItem.mis_line_item == "Operating Expenses",
                ForecastLineItem.is_actual.is_(False),
            )
        )
    ).scalar_one()
    ebitda = (
        await async_session.execute(
            select(ForecastLineItem).where(
                ForecastLineItem.forecast_run_id == run.id,
                ForecastLineItem.period == "2025-04",
                ForecastLineItem.mis_line_item == "EBITDA",
                ForecastLineItem.is_actual.is_(False),
            )
        )
    ).scalar_one()
    assert ebitda.amount == gp.amount - opex.amount


@pytest.mark.asyncio
async def test_no_float_in_forecast_computation(async_session: AsyncSession, test_user: IamUser) -> None:
    run = await _create_run(async_session, test_user.tenant_id, test_user.id)
    await compute_forecast_lines(async_session, test_user.tenant_id, run.id)
    rows = (
        await async_session.execute(select(ForecastLineItem).where(ForecastLineItem.forecast_run_id == run.id))
    ).scalars().all()
    assert rows
    assert all(isinstance(row.amount, Decimal) for row in rows)


@pytest.mark.asyncio
async def test_historical_actuals_included_as_context(async_session: AsyncSession, test_user: IamUser) -> None:
    run = await _create_run(async_session, test_user.tenant_id, test_user.id)
    await compute_forecast_lines(async_session, test_user.tenant_id, run.id)
    actual_rows = (
        await async_session.execute(
            select(ForecastLineItem).where(
                ForecastLineItem.forecast_run_id == run.id,
                ForecastLineItem.is_actual.is_(True),
            )
        )
    ).scalars().all()
    assert actual_rows
    periods = {row.period for row in actual_rows}
    assert len(periods) == 6


@pytest.mark.asyncio
async def test_zero_division_handled(async_session: AsyncSession, test_user: IamUser) -> None:
    run = await _create_run(async_session, test_user.tenant_id, test_user.id)
    await _set_assumption(async_session, run, "revenue_growth_pct_monthly", Decimal("-100.000000"))
    rows = await compute_forecast_lines(async_session, test_user.tenant_id, run.id)
    assert rows


@pytest.mark.asyncio
async def test_assumption_update_triggers_recompute(async_session: AsyncSession, test_user: IamUser) -> None:
    run = await _create_run(async_session, test_user.tenant_id, test_user.id)
    await compute_forecast_lines(async_session, test_user.tenant_id, run.id)
    before_count = (
        await async_session.execute(
            select(func.count()).select_from(ForecastLineItem).where(ForecastLineItem.forecast_run_id == run.id)
        )
    ).scalar_one()
    await update_assumption(
        async_session,
        tenant_id=test_user.tenant_id,
        forecast_run_id=run.id,
        assumption_key="revenue_growth_pct_monthly",
        new_value=Decimal("7.000000"),
    )
    after_count = (
        await async_session.execute(
            select(func.count()).select_from(ForecastLineItem).where(ForecastLineItem.forecast_run_id == run.id)
        )
    ).scalar_one()
    assert after_count > before_count


# Forecast vs budget (4)
@pytest.mark.asyncio
async def test_forecast_vs_budget_structure(async_session: AsyncSession, test_user: IamUser) -> None:
    await _create_approved_budget(async_session, test_user)
    run = await _create_run(async_session, test_user.tenant_id, test_user.id)
    await compute_forecast_lines(async_session, test_user.tenant_id, run.id)
    payload = await get_forecast_vs_budget(async_session, test_user.tenant_id, run.id, 2025)
    assert "rows" in payload
    assert payload["rows"]


@pytest.mark.asyncio
async def test_variance_decimal_not_float(async_session: AsyncSession, test_user: IamUser) -> None:
    await _create_approved_budget(async_session, test_user)
    run = await _create_run(async_session, test_user.tenant_id, test_user.id)
    await compute_forecast_lines(async_session, test_user.tenant_id, run.id)
    payload = await get_forecast_vs_budget(async_session, test_user.tenant_id, run.id, 2025)
    assert all(isinstance(row["variance"], Decimal) for row in payload["rows"])


@pytest.mark.asyncio
async def test_forecast_higher_than_budget_positive_variance(async_session: AsyncSession, test_user: IamUser) -> None:
    await _create_approved_budget(async_session, test_user)
    run = await _create_run(async_session, test_user.tenant_id, test_user.id)
    await _set_assumption(async_session, run, "revenue_growth_pct_monthly", Decimal("10.000000"))
    await compute_forecast_lines(async_session, test_user.tenant_id, run.id)
    payload = await get_forecast_vs_budget(async_session, test_user.tenant_id, run.id, 2025)
    revenue_row = next(row for row in payload["rows"] if row["mis_line_item"] == "Revenue")
    assert revenue_row["variance"] > Decimal("0")


@pytest.mark.asyncio
async def test_forecast_lower_than_budget_negative_variance(async_session: AsyncSession, test_user: IamUser) -> None:
    await _create_approved_budget(async_session, test_user)
    run = await _create_run(async_session, test_user.tenant_id, test_user.id)
    await _set_assumption(async_session, run, "revenue_growth_pct_monthly", Decimal("-10.000000"))
    await compute_forecast_lines(async_session, test_user.tenant_id, run.id)
    payload = await get_forecast_vs_budget(async_session, test_user.tenant_id, run.id, 2025)
    revenue_row = next(row for row in payload["rows"] if row["mis_line_item"] == "Revenue")
    assert revenue_row["variance"] < Decimal("0")


# API (5)
@pytest.mark.asyncio
async def test_create_forecast_via_api(async_client: AsyncClient, api_test_access_token: str) -> None:
    response = await async_client.post(
        "/api/v1/forecast",
        headers={"Authorization": f"Bearer {api_test_access_token}"},
        json={
            "run_name": "Rolling Forecast",
            "forecast_type": "rolling_12",
            "base_period": "2025-03",
            "horizon_months": 12,
        },
    )
    assert response.status_code == 201
    assert "run" in response.json()["data"]


@pytest.mark.asyncio
async def test_update_assumption_via_api(async_client: AsyncClient, api_test_access_token: str) -> None:
    create_response = await async_client.post(
        "/api/v1/forecast",
        headers={"Authorization": f"Bearer {api_test_access_token}"},
        json={
            "run_name": "Rolling Forecast",
            "forecast_type": "rolling_12",
            "base_period": "2025-03",
            "horizon_months": 12,
        },
    )
    run_id = create_response.json()["data"]["run"]["id"]
    response = await async_client.patch(
        f"/api/v1/forecast/{run_id}/assumptions/revenue_growth_pct_monthly",
        headers={"Authorization": f"Bearer {api_test_access_token}"},
        json={"value": "6.500000"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["assumption"]["assumption_key"] == "revenue_growth_pct_monthly"


@pytest.mark.asyncio
async def test_compute_endpoint_creates_lines(async_client: AsyncClient, api_test_access_token: str) -> None:
    create_response = await async_client.post(
        "/api/v1/forecast",
        headers={"Authorization": f"Bearer {api_test_access_token}"},
        json={
            "run_name": "Rolling Forecast",
            "forecast_type": "rolling_12",
            "base_period": "2025-03",
            "horizon_months": 12,
        },
    )
    run_id = create_response.json()["data"]["run"]["id"]
    response = await async_client.post(
        f"/api/v1/forecast/{run_id}/compute",
        headers={"Authorization": f"Bearer {api_test_access_token}"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["line_items_created"] > 0


@pytest.mark.asyncio
async def test_publish_requires_finance_leader(
    async_client: AsyncClient,
    api_session_factory,
    api_test_user: IamUser,
) -> None:
    async with api_session_factory() as session:
        run = await _create_run(session, api_test_user.tenant_id, api_test_user.id)
        employee = IamUser(
            tenant_id=api_test_user.tenant_id,
        email=f"forecast-emp-{uuid.uuid4().hex[:6]}@example.com",
        hashed_password=hash_password("TestPass123!"),
        full_name="Forecast Emp",
        role=UserRole.employee,
        is_active=True,
        mfa_enabled=False,
        )
        session.add(employee)
        await session.flush()
        employee_token = create_access_token(employee.id, employee.tenant_id, employee.role.value)
        await session.commit()
    response = await async_client.post(
        f"/api/v1/forecast/{run.id}/publish",
        headers={"Authorization": f"Bearer {employee_token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_export_returns_xlsx(
    async_client: AsyncClient,
    api_session_factory,
    api_test_user: IamUser,
    api_test_access_token: str,
) -> None:
    async with api_session_factory() as session:
        run = await _create_run(session, api_test_user.tenant_id, api_test_user.id)
        await compute_forecast_lines(session, api_test_user.tenant_id, run.id)
        await session.commit()
    response = await async_client.get(
        f"/api/v1/forecast/{run.id}/export",
        headers={"Authorization": f"Bearer {api_test_access_token}"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


# Isolation (3)
@pytest.mark.asyncio
async def test_tenant_isolation_forecast_runs(api_session_factory, test_user: IamUser) -> None:
    tenant_b = uuid.uuid4()
    async with api_session_factory() as session:
        await _create_run(session, test_user.tenant_id, test_user.id)
        await _create_run(session, tenant_b, test_user.id)
        await session.commit()
    async with api_session_factory() as session:
        rows = (
            await session.execute(select(ForecastRun).where(ForecastRun.tenant_id == test_user.tenant_id))
        ).scalars().all()
    assert rows
    assert all(row.tenant_id == test_user.tenant_id for row in rows)


@pytest.mark.asyncio
async def test_tenant_isolation_forecast_lines(api_session_factory, test_user: IamUser) -> None:
    tenant_b = uuid.uuid4()
    async with api_session_factory() as session:
        run_a = await _create_run(session, test_user.tenant_id, test_user.id)
        await compute_forecast_lines(session, test_user.tenant_id, run_a.id)
        run_b = await _create_run(session, tenant_b, test_user.id)
        await compute_forecast_lines(session, tenant_b, run_b.id)
        await session.commit()
    async with api_session_factory() as session:
        rows = (
            await session.execute(select(ForecastLineItem).where(ForecastLineItem.tenant_id == test_user.tenant_id))
        ).scalars().all()
    assert rows
    assert all(row.tenant_id == test_user.tenant_id for row in rows)


@pytest.mark.asyncio
async def test_tenant_isolation_assumptions(api_session_factory, test_user: IamUser) -> None:
    tenant_b = uuid.uuid4()
    async with api_session_factory() as session:
        run_a = await _create_run(session, test_user.tenant_id, test_user.id)
        run_b = await _create_run(session, tenant_b, test_user.id)
        await session.commit()
    async with api_session_factory() as session:
        assumptions_a = (
            await session.execute(
                select(ForecastAssumption).where(ForecastAssumption.forecast_run_id == run_a.id)
            )
        ).scalars().all()
        assumptions_b = (
            await session.execute(
                select(ForecastAssumption).where(ForecastAssumption.forecast_run_id == run_b.id)
            )
        ).scalars().all()
    assert assumptions_a and assumptions_b
    assert all(row.tenant_id == test_user.tenant_id for row in assumptions_a)
    assert all(row.tenant_id == tenant_b for row in assumptions_b)


def test_apply_growth_rate_helper_decimal() -> None:
    base = Decimal("1000000")
    rate = Decimal("5.00")
    assert _apply_growth_rate(base, rate) == Decimal("1050000.00")
