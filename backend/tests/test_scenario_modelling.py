from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql
from financeops.modules.scenario_modelling.models import (
    ScenarioDefinition,
    ScenarioLineItem,
    ScenarioResult,
    ScenarioSet,
)
from financeops.modules.scenario_modelling.service import (
    compute_all_scenarios,
    compute_scenario,
    create_scenario_set,
    get_scenario_comparison,
    update_scenario_drivers,
)


async def _create_set(async_session: AsyncSession, tenant_id: uuid.UUID, user_id: uuid.UUID) -> ScenarioSet:
    return await create_scenario_set(
        async_session,
        tenant_id=tenant_id,
        name="Q3 2025 Planning Scenarios",
        base_period="2025-03",
        horizon_months=12,
        created_by=user_id,
    )


# Scenario set creation (5)
@pytest.mark.asyncio
async def test_create_scenario_set(async_session: AsyncSession, test_user) -> None:
    scenario_set = await _create_set(async_session, test_user.tenant_id, test_user.id)
    definitions = (
        await async_session.execute(
            select(ScenarioDefinition).where(ScenarioDefinition.scenario_set_id == scenario_set.id)
        )
    ).scalars().all()
    assert len(definitions) == 3


@pytest.mark.asyncio
async def test_default_scenarios_are_base_optimistic_pessimistic(async_session: AsyncSession, test_user) -> None:
    scenario_set = await _create_set(async_session, test_user.tenant_id, test_user.id)
    definitions = (
        await async_session.execute(
            select(ScenarioDefinition).where(ScenarioDefinition.scenario_set_id == scenario_set.id)
        )
    ).scalars().all()
    names = {row.scenario_name for row in definitions}
    assert {"base", "optimistic", "pessimistic"}.issubset(names)
    assert sum(1 for row in definitions if row.is_base_case) == 1


@pytest.mark.asyncio
async def test_optimistic_has_higher_growth_than_base(async_session: AsyncSession, test_user) -> None:
    scenario_set = await _create_set(async_session, test_user.tenant_id, test_user.id)
    definitions = (
        await async_session.execute(
            select(ScenarioDefinition).where(ScenarioDefinition.scenario_set_id == scenario_set.id)
        )
    ).scalars().all()
    base = next(row for row in definitions if row.scenario_name == "base")
    optimistic = next(row for row in definitions if row.scenario_name == "optimistic")
    base_growth = Decimal(str((base.driver_overrides or {}).get("revenue_growth_pct_monthly", "5.00")))
    optimistic_growth = Decimal(str(optimistic.driver_overrides["revenue_growth_pct_monthly"]))
    assert optimistic_growth > base_growth


@pytest.mark.asyncio
async def test_pessimistic_has_lower_growth_than_base(async_session: AsyncSession, test_user) -> None:
    scenario_set = await _create_set(async_session, test_user.tenant_id, test_user.id)
    definitions = (
        await async_session.execute(
            select(ScenarioDefinition).where(ScenarioDefinition.scenario_set_id == scenario_set.id)
        )
    ).scalars().all()
    base = next(row for row in definitions if row.scenario_name == "base")
    pessimistic = next(row for row in definitions if row.scenario_name == "pessimistic")
    base_growth = Decimal(str((base.driver_overrides or {}).get("revenue_growth_pct_monthly", "5.00")))
    pessimistic_growth = Decimal(str(pessimistic.driver_overrides["revenue_growth_pct_monthly"]))
    assert pessimistic_growth < base_growth


@pytest.mark.asyncio
async def test_scenario_set_is_append_only(async_session: AsyncSession, test_user) -> None:
    scenario_set = await _create_set(async_session, test_user.tenant_id, test_user.id)
    await async_session.execute(text(append_only_function_sql()))
    await async_session.execute(text(drop_trigger_sql("scenario_sets")))
    await async_session.execute(text(create_trigger_sql("scenario_sets")))
    await async_session.flush()
    with pytest.raises(Exception):
        await async_session.execute(
            text("UPDATE scenario_sets SET name = 'Changed' WHERE id = :id"),
            {"id": scenario_set.id},
        )


# Driver overrides (4)
@pytest.mark.asyncio
async def test_update_driver_override(async_session: AsyncSession, test_user) -> None:
    scenario_set = await _create_set(async_session, test_user.tenant_id, test_user.id)
    definition = (
        await async_session.execute(
            select(ScenarioDefinition).where(
                ScenarioDefinition.scenario_set_id == scenario_set.id,
                ScenarioDefinition.scenario_name == "base",
            )
        )
    ).scalar_one()
    updated = await update_scenario_drivers(
        async_session,
        tenant_id=test_user.tenant_id,
        scenario_definition_id=definition.id,
        driver_overrides={"revenue_growth_pct_monthly": "10.00"},
    )
    assert updated.driver_overrides["revenue_growth_pct_monthly"] == "10.00"


@pytest.mark.asyncio
async def test_driver_override_invalid_decimal_rejected(async_session: AsyncSession, test_user) -> None:
    scenario_set = await _create_set(async_session, test_user.tenant_id, test_user.id)
    definition = (
        await async_session.execute(
            select(ScenarioDefinition).where(
                ScenarioDefinition.scenario_set_id == scenario_set.id,
                ScenarioDefinition.scenario_name == "base",
            )
        )
    ).scalar_one()
    with pytest.raises(ValueError):
        await update_scenario_drivers(
            async_session,
            tenant_id=test_user.tenant_id,
            scenario_definition_id=definition.id,
            driver_overrides={"revenue_growth_pct_monthly": "not_a_number"},
        )


@pytest.mark.asyncio
async def test_driver_override_applied_over_base(async_session: AsyncSession, test_user) -> None:
    scenario_set = await _create_set(async_session, test_user.tenant_id, test_user.id)
    definition = (
        await async_session.execute(
            select(ScenarioDefinition).where(
                ScenarioDefinition.scenario_set_id == scenario_set.id,
                ScenarioDefinition.scenario_name == "base",
            )
        )
    ).scalar_one()
    await update_scenario_drivers(
        async_session,
        tenant_id=test_user.tenant_id,
        scenario_definition_id=definition.id,
        driver_overrides={"revenue_growth_pct_monthly": "10.00"},
    )
    result = await compute_scenario(async_session, test_user.tenant_id, definition.id)
    revenue_row = (
        await async_session.execute(
            select(ScenarioLineItem).where(
                ScenarioLineItem.scenario_result_id == result.id,
                ScenarioLineItem.period == "2025-04",
                ScenarioLineItem.mis_line_item == "Revenue",
            )
        )
    ).scalar_one()
    assert revenue_row.amount == Decimal("1100000.00")


@pytest.mark.asyncio
async def test_driver_overrides_stored_as_strings_in_jsonb(async_session: AsyncSession, test_user) -> None:
    scenario_set = await _create_set(async_session, test_user.tenant_id, test_user.id)
    definition = (
        await async_session.execute(
            select(ScenarioDefinition).where(
                ScenarioDefinition.scenario_set_id == scenario_set.id,
                ScenarioDefinition.scenario_name == "base",
            )
        )
    ).scalar_one()
    await update_scenario_drivers(
        async_session,
        tenant_id=test_user.tenant_id,
        scenario_definition_id=definition.id,
        driver_overrides={"revenue_growth_pct_monthly": "10.00"},
    )
    refreshed = await async_session.get(ScenarioDefinition, definition.id)
    assert isinstance(refreshed.driver_overrides["revenue_growth_pct_monthly"], str)


# Computation (8)
@pytest.mark.asyncio
async def test_compute_single_scenario(async_session: AsyncSession, test_user) -> None:
    scenario_set = await _create_set(async_session, test_user.tenant_id, test_user.id)
    definition = (
        await async_session.execute(
            select(ScenarioDefinition).where(
                ScenarioDefinition.scenario_set_id == scenario_set.id,
                ScenarioDefinition.scenario_name == "base",
            )
        )
    ).scalar_one()
    result = await compute_scenario(async_session, test_user.tenant_id, definition.id)
    lines = (
        await async_session.execute(select(ScenarioLineItem).where(ScenarioLineItem.scenario_result_id == result.id))
    ).scalars().all()
    assert lines


@pytest.mark.asyncio
async def test_compute_all_scenarios_parallel(async_session: AsyncSession, test_user) -> None:
    scenario_set = await _create_set(async_session, test_user.tenant_id, test_user.id)
    results = await compute_all_scenarios(async_session, test_user.tenant_id, scenario_set.id)
    assert len(results) == 3
    for result in results:
        count = (
            await async_session.execute(
                select(func.count()).select_from(ScenarioLineItem).where(ScenarioLineItem.scenario_result_id == result.id)
            )
        ).scalar_one()
        assert count > 0


@pytest.mark.asyncio
async def test_optimistic_revenue_higher_than_base(async_session: AsyncSession, test_user) -> None:
    scenario_set = await _create_set(async_session, test_user.tenant_id, test_user.id)
    await compute_all_scenarios(async_session, test_user.tenant_id, scenario_set.id)
    comparison = await get_scenario_comparison(async_session, test_user.tenant_id, scenario_set.id)
    base = next(row for row in comparison["scenarios"] if row["scenario_name"] == "base")
    optimistic = next(row for row in comparison["scenarios"] if row["scenario_name"] == "optimistic")
    assert optimistic["summary"]["revenue_total"] > base["summary"]["revenue_total"]


@pytest.mark.asyncio
async def test_pessimistic_revenue_lower_than_base(async_session: AsyncSession, test_user) -> None:
    scenario_set = await _create_set(async_session, test_user.tenant_id, test_user.id)
    await compute_all_scenarios(async_session, test_user.tenant_id, scenario_set.id)
    comparison = await get_scenario_comparison(async_session, test_user.tenant_id, scenario_set.id)
    base = next(row for row in comparison["scenarios"] if row["scenario_name"] == "base")
    pessimistic = next(row for row in comparison["scenarios"] if row["scenario_name"] == "pessimistic")
    assert pessimistic["summary"]["revenue_total"] < base["summary"]["revenue_total"]


@pytest.mark.asyncio
async def test_all_computed_amounts_are_decimal(async_session: AsyncSession, test_user) -> None:
    scenario_set = await _create_set(async_session, test_user.tenant_id, test_user.id)
    results = await compute_all_scenarios(async_session, test_user.tenant_id, scenario_set.id)
    rows = (
        await async_session.execute(
            select(ScenarioLineItem).where(ScenarioLineItem.scenario_result_id == results[0].id)
        )
    ).scalars().all()
    assert all(isinstance(row.amount, Decimal) for row in rows)


@pytest.mark.asyncio
async def test_ebitda_margin_decimal(async_session: AsyncSession, test_user) -> None:
    scenario_set = await _create_set(async_session, test_user.tenant_id, test_user.id)
    await compute_all_scenarios(async_session, test_user.tenant_id, scenario_set.id)
    comparison = await get_scenario_comparison(async_session, test_user.tenant_id, scenario_set.id)
    assert all(isinstance(row["summary"]["ebitda_margin_pct"], Decimal) for row in comparison["scenarios"])


@pytest.mark.asyncio
async def test_waterfall_impacts_sum_to_spread(async_session: AsyncSession, test_user) -> None:
    scenario_set = await _create_set(async_session, test_user.tenant_id, test_user.id)
    await compute_all_scenarios(async_session, test_user.tenant_id, scenario_set.id)
    comparison = await get_scenario_comparison(async_session, test_user.tenant_id, scenario_set.id)
    waterfall = comparison["waterfall"]
    driver_sum = sum((row["impact"] for row in waterfall["drivers"]), start=Decimal("0"))
    assert abs((waterfall["base_ebitda"] + driver_sum) - waterfall["optimistic_ebitda"]) <= Decimal("0.01")


@pytest.mark.asyncio
async def test_compute_is_idempotent_history(async_session: AsyncSession, test_user) -> None:
    scenario_set = await _create_set(async_session, test_user.tenant_id, test_user.id)
    definition = (
        await async_session.execute(
            select(ScenarioDefinition).where(
                ScenarioDefinition.scenario_set_id == scenario_set.id,
                ScenarioDefinition.scenario_name == "base",
            )
        )
    ).scalar_one()
    await compute_scenario(async_session, test_user.tenant_id, definition.id)
    await compute_scenario(async_session, test_user.tenant_id, definition.id)
    results = (
        await async_session.execute(
            select(ScenarioResult).where(ScenarioResult.scenario_definition_id == definition.id)
        )
    ).scalars().all()
    assert len(results) == 2


# Comparison (4)
@pytest.mark.asyncio
async def test_comparison_returns_all_3_scenarios(async_session: AsyncSession, test_user) -> None:
    scenario_set = await _create_set(async_session, test_user.tenant_id, test_user.id)
    await compute_all_scenarios(async_session, test_user.tenant_id, scenario_set.id)
    comparison = await get_scenario_comparison(async_session, test_user.tenant_id, scenario_set.id)
    assert len(comparison["scenarios"]) == 3


@pytest.mark.asyncio
async def test_comparison_monthly_data_correct_period_count(async_session: AsyncSession, test_user) -> None:
    scenario_set = await _create_set(async_session, test_user.tenant_id, test_user.id)
    await compute_all_scenarios(async_session, test_user.tenant_id, scenario_set.id)
    comparison = await get_scenario_comparison(async_session, test_user.tenant_id, scenario_set.id)
    assert all(len(row["monthly"]) == 12 for row in comparison["scenarios"])


@pytest.mark.asyncio
async def test_waterfall_structure(async_session: AsyncSession, test_user) -> None:
    scenario_set = await _create_set(async_session, test_user.tenant_id, test_user.id)
    await compute_all_scenarios(async_session, test_user.tenant_id, scenario_set.id)
    comparison = await get_scenario_comparison(async_session, test_user.tenant_id, scenario_set.id)
    assert {"base_ebitda", "drivers", "optimistic_ebitda", "pessimistic_ebitda"}.issubset(comparison["waterfall"].keys())


@pytest.mark.asyncio
async def test_all_comparison_values_decimal(async_session: AsyncSession, test_user) -> None:
    scenario_set = await _create_set(async_session, test_user.tenant_id, test_user.id)
    await compute_all_scenarios(async_session, test_user.tenant_id, scenario_set.id)
    comparison = await get_scenario_comparison(async_session, test_user.tenant_id, scenario_set.id)
    for row in comparison["scenarios"]:
        assert isinstance(row["summary"]["revenue_total"], Decimal)
        assert isinstance(row["summary"]["ebitda_total"], Decimal)


# API (4)
@pytest.mark.asyncio
async def test_create_scenario_set_via_api(async_client: AsyncClient, test_access_token: str) -> None:
    response = await async_client.post(
        "/api/v1/scenarios",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "name": "Q3 2025 Planning Scenarios",
            "base_period": "2025-03",
            "horizon_months": 12,
        },
    )
    assert response.status_code == 201
    payload = response.json()["data"]
    assert "scenario_set" in payload


@pytest.mark.asyncio
async def test_update_drivers_via_api(async_client: AsyncClient, test_access_token: str) -> None:
    create_response = await async_client.post(
        "/api/v1/scenarios",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "name": "Q3 2025 Planning Scenarios",
            "base_period": "2025-03",
            "horizon_months": 12,
        },
    )
    set_id = create_response.json()["data"]["scenario_set"]["id"]
    definition_id = create_response.json()["data"]["scenario_definitions"][0]["id"]
    response = await async_client.patch(
        f"/api/v1/scenarios/{set_id}/scenarios/{definition_id}",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={"driver_overrides": {"revenue_growth_pct_monthly": "9.00"}},
    )
    assert response.status_code == 200
    assert response.json()["data"]["driver_overrides"]["revenue_growth_pct_monthly"] == "9.00"


@pytest.mark.asyncio
async def test_compute_endpoint(async_client: AsyncClient, test_access_token: str) -> None:
    create_response = await async_client.post(
        "/api/v1/scenarios",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "name": "Q3 2025 Planning Scenarios",
            "base_period": "2025-03",
            "horizon_months": 12,
        },
    )
    set_id = create_response.json()["data"]["scenario_set"]["id"]
    response = await async_client.post(
        f"/api/v1/scenarios/{set_id}/compute",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 200
    assert len(response.json()["data"]["results"]) == 3


@pytest.mark.asyncio
async def test_comparison_endpoint_structure(async_client: AsyncClient, test_access_token: str) -> None:
    create_response = await async_client.post(
        "/api/v1/scenarios",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "name": "Q3 2025 Planning Scenarios",
            "base_period": "2025-03",
            "horizon_months": 12,
        },
    )
    set_id = create_response.json()["data"]["scenario_set"]["id"]
    await async_client.post(
        f"/api/v1/scenarios/{set_id}/compute",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    response = await async_client.get(
        f"/api/v1/scenarios/{set_id}/comparison",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert {"scenario_set_name", "base_period", "scenarios", "waterfall"}.issubset(payload.keys())

