from __future__ import annotations

from decimal import Decimal
import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.intent.context import MutationContext, governed_mutation_context
from financeops.core.security import create_access_token
from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql
from financeops.db.models.users import IamUser
from financeops.modules.budgeting.models import BudgetLineItem, BudgetVersion
from financeops.modules.multi_gaap.models import MultiGAAPRun
from financeops.modules.multi_gaap.service import (
    compute_gaap_view as _compute_gaap_view,
    get_gaap_comparison,
    get_or_create_config as _get_or_create_config,
    update_config as _update_config,
)


def _auth_headers(user: IamUser) -> dict[str, str]:
    token = create_access_token(user.id, user.tenant_id, user.role.value)
    return {"Authorization": f"Bearer {token}"}


def _governed_context(intent_type: str) -> MutationContext:
    return MutationContext(
        intent_id=uuid.uuid4(),
        job_id=uuid.uuid4(),
        actor_user_id=None,
        actor_role="finance_leader",
        intent_type=intent_type,
    )


async def get_or_create_config(*args, **kwargs):
    with governed_mutation_context(_governed_context("ENSURE_MULTI_GAAP_CONFIG")):
        return await _get_or_create_config(*args, **kwargs)


async def update_config(*args, **kwargs):
    with governed_mutation_context(_governed_context("UPDATE_MULTI_GAAP_CONFIG")):
        return await _update_config(*args, **kwargs)


async def compute_gaap_view(*args, **kwargs):
    with governed_mutation_context(_governed_context("COMPUTE_MULTI_GAAP_VIEW")):
        return await _compute_gaap_view(*args, **kwargs)


async def _seed_budget(async_session: AsyncSession, test_user: IamUser, annual_total: Decimal) -> None:
    version = BudgetVersion(
        tenant_id=test_user.tenant_id,
        fiscal_year=2026,
        version_name="GAAP Base",
        version_number=1,
        status="approved",
        is_board_approved=True,
        created_by=test_user.id,
    )
    async_session.add(version)
    await async_session.flush()

    monthly = (annual_total / Decimal("12")).quantize(Decimal("0.01"))
    month_12 = (annual_total - monthly * Decimal("11")).quantize(Decimal("0.01"))
    line = BudgetLineItem(
        budget_version_id=version.id,
        tenant_id=test_user.tenant_id,
        entity_id=None,
        mis_line_item="Revenue",
        mis_category="revenue",
        month_01=monthly,
        month_02=monthly,
        month_03=monthly,
        month_04=monthly,
        month_05=monthly,
        month_06=monthly,
        month_07=monthly,
        month_08=monthly,
        month_09=monthly,
        month_10=monthly,
        month_11=monthly,
        month_12=month_12,
        basis="seed",
    )
    async_session.add(line)
    await async_session.flush()


@pytest.mark.asyncio
async def test_compute_management_gaap(async_session: AsyncSession, test_user: IamUser) -> None:
    await _seed_budget(async_session, test_user, Decimal("1000.00"))
    indas = await compute_gaap_view(async_session, test_user.tenant_id, "2026-03", "INDAS", test_user.id)
    management = await compute_gaap_view(async_session, test_user.tenant_id, "2026-03", "MANAGEMENT", test_user.id)
    assert management.ebitda > indas.ebitda


@pytest.mark.asyncio
async def test_all_gaap_amounts_decimal(async_session: AsyncSession, test_user: IamUser) -> None:
    row = await compute_gaap_view(async_session, test_user.tenant_id, "2026-03", "INDAS", test_user.id)
    assert isinstance(row.revenue, Decimal)
    assert isinstance(row.ebitda, Decimal)


@pytest.mark.asyncio
async def test_gaap_run_append_only(async_session: AsyncSession, test_user: IamUser) -> None:
    row = await compute_gaap_view(async_session, test_user.tenant_id, "2026-03", "INDAS", test_user.id)
    await async_session.execute(text(append_only_function_sql()))
    await async_session.execute(text(drop_trigger_sql("multi_gaap_runs")))
    await async_session.execute(text(create_trigger_sql("multi_gaap_runs")))
    await async_session.flush()
    with pytest.raises(Exception):
        await async_session.execute(text("UPDATE multi_gaap_runs SET revenue=0 WHERE id=:id"), {"id": row.id})


@pytest.mark.asyncio
async def test_gaap_unique_per_tenant_period_framework(async_session: AsyncSession, test_user: IamUser) -> None:
    await compute_gaap_view(async_session, test_user.tenant_id, "2026-03", "INDAS", test_user.id)
    await compute_gaap_view(async_session, test_user.tenant_id, "2026-03", "INDAS", test_user.id)
    rows = (
        await async_session.execute(
            select(MultiGAAPRun).where(
                MultiGAAPRun.tenant_id == test_user.tenant_id,
                MultiGAAPRun.period == "2026-03",
                MultiGAAPRun.gaap_framework == "INDAS",
            )
        )
    ).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_gaap_comparison_structure(async_session: AsyncSession, test_user: IamUser) -> None:
    await compute_gaap_view(async_session, test_user.tenant_id, "2026-03", "INDAS", test_user.id)
    payload = await get_gaap_comparison(async_session, test_user.tenant_id, "2026-03")
    assert {"period", "frameworks", "differences"}.issubset(payload)


@pytest.mark.asyncio
async def test_differences_computed_correctly(async_session: AsyncSession, test_user: IamUser) -> None:
    await _seed_budget(async_session, test_user, Decimal("1000.00"))
    await compute_gaap_view(async_session, test_user.tenant_id, "2026-03", "INDAS", test_user.id)
    await update_config(async_session, test_user.tenant_id, {"financial_instruments_policy": {"IFRS": "-20.00"}})
    await compute_gaap_view(async_session, test_user.tenant_id, "2026-03", "IFRS", test_user.id)
    payload = await get_gaap_comparison(async_session, test_user.tenant_id, "2026-03")
    assert payload["differences"]["revenue_vs_indas"]["IFRS"] == Decimal("-20.00")


@pytest.mark.asyncio
async def test_management_removes_noncash(async_session: AsyncSession, test_user: IamUser) -> None:
    row = await compute_gaap_view(async_session, test_user.tenant_id, "2026-03", "MANAGEMENT", test_user.id)
    assert any("depreciation" in adj["description"].lower() for adj in row.adjustments)


@pytest.mark.asyncio
async def test_gaap_rls(async_session: AsyncSession, test_user: IamUser) -> None:
    payload = await get_gaap_comparison(async_session, test_user.tenant_id, "2026-03")
    assert isinstance(payload["frameworks"], list)


@pytest.mark.asyncio
async def test_api_compute_gaap(async_client, test_user: IamUser) -> None:
    response = await async_client.post(
        "/api/v1/gaap/compute",
        headers=_auth_headers(test_user),
        json={"period": "2026-03", "gaap_framework": "INDAS"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_api_comparison_endpoint(async_client, test_user: IamUser) -> None:
    response = await async_client.get("/api/v1/gaap/comparison?period=2026-03", headers=_auth_headers(test_user))
    assert response.status_code == 200
    assert "frameworks" in response.json()["data"]


@pytest.mark.asyncio
async def test_config_policy_elections_stored(async_session: AsyncSession, test_user: IamUser) -> None:
    await update_config(async_session, test_user.tenant_id, {"secondary_gaaps": ["IFRS", "USGAAP"]})
    cfg = await get_or_create_config(async_session, test_user.tenant_id)
    assert "IFRS" in (cfg.secondary_gaaps or [])


@pytest.mark.asyncio
async def test_zero_adjustment_when_same_framework(async_session: AsyncSession, test_user: IamUser) -> None:
    await compute_gaap_view(async_session, test_user.tenant_id, "2026-03", "INDAS", test_user.id)
    payload = await get_gaap_comparison(async_session, test_user.tenant_id, "2026-03")
    assert payload["differences"]["revenue_vs_indas"] == {}
