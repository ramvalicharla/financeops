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
from financeops.modules.tax_provision.models import TaxPosition, TaxProvisionRun
from financeops.modules.tax_provision.service import (
    compute_tax_provision as _compute_tax_provision,
    get_tax_provision_schedule,
    upsert_tax_position as _upsert_tax_position,
)


def _auth_headers(user: IamUser) -> dict[str, str]:
    token = create_access_token(user.id, user.tenant_id, user.role.value)
    return {"Authorization": f"Bearer {token}"}


def _governed_context(intent_type: str) -> MutationContext:
    return MutationContext(
        intent_id=uuid.uuid4(),
        job_id=uuid.uuid4(),
        actor_user_id=None,
        actor_role=_default_actor_role(),
        intent_type=intent_type,
    )


def _default_actor_role() -> str:
    return "finance_leader"


async def compute_tax_provision(*args, **kwargs):
    with governed_mutation_context(_governed_context("COMPUTE_TAX_PROVISION")):
        return await _compute_tax_provision(*args, **kwargs)


async def upsert_tax_position(*args, **kwargs):
    with governed_mutation_context(_governed_context("UPSERT_TAX_POSITION")):
        return await _upsert_tax_position(*args, **kwargs)


async def _seed_budget(async_session: AsyncSession, test_user: IamUser, fiscal_year: int, annual_total: Decimal) -> None:
    version = BudgetVersion(
        tenant_id=test_user.tenant_id,
        fiscal_year=fiscal_year,
        version_name="Tax Base",
        version_number=1,
        status="approved",
        is_board_approved=True,
        created_by=test_user.id,
    )
    async_session.add(version)
    await async_session.flush()

    monthly = (annual_total / Decimal("12")).quantize(Decimal("0.01"))
    month_12 = (annual_total - (monthly * Decimal("11"))).quantize(Decimal("0.01"))
    line = BudgetLineItem(
        budget_version_id=version.id,
        tenant_id=test_user.tenant_id,
        entity_id=None,
        mis_line_item="PBT",
        mis_category="profit",
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
async def test_compute_tax_provision_basic(async_session: AsyncSession, test_user: IamUser) -> None:
    await _seed_budget(async_session, test_user, 2026, Decimal("1000000.00"))
    row = await compute_tax_provision(
        async_session,
        tenant_id=test_user.tenant_id,
        period="2026-03",
        entity_id=None,
        applicable_tax_rate=Decimal("0.2500"),
        created_by=test_user.id,
    )
    assert row.current_tax_expense == Decimal("250000.00")


@pytest.mark.asyncio
async def test_taxable_income_adds_permanent_differences(async_session: AsyncSession, test_user: IamUser) -> None:
    await _seed_budget(async_session, test_user, 2026, Decimal("1000000.00"))
    await upsert_tax_position(
        async_session,
        tenant_id=test_user.tenant_id,
        position_name="Nondeductible",
        position_type="permanent_difference",
        carrying_amount=Decimal("100000.00"),
        tax_base=Decimal("0.00"),
        is_asset=False,
        tax_rate=Decimal("0.2500"),
    )
    row = await compute_tax_provision(
        async_session,
        tenant_id=test_user.tenant_id,
        period="2026-04",
        entity_id=None,
        applicable_tax_rate=Decimal("0.2500"),
        created_by=test_user.id,
    )
    assert row.taxable_income == Decimal("1100000.00")
    assert row.current_tax_expense == Decimal("275000.00")


@pytest.mark.asyncio
async def test_effective_tax_rate_computed(async_session: AsyncSession, test_user: IamUser) -> None:
    await _seed_budget(async_session, test_user, 2026, Decimal("1000000.00"))
    row = await compute_tax_provision(
        async_session,
        tenant_id=test_user.tenant_id,
        period="2026-05",
        entity_id=None,
        applicable_tax_rate=Decimal("0.2500"),
        created_by=test_user.id,
    )
    assert row.effective_tax_rate == Decimal("0.2500")


@pytest.mark.asyncio
async def test_effective_tax_rate_zero_when_no_profit(async_session: AsyncSession, test_user: IamUser) -> None:
    row = await compute_tax_provision(
        async_session,
        tenant_id=test_user.tenant_id,
        period="2026-06",
        entity_id=None,
        applicable_tax_rate=Decimal("0.2500"),
        created_by=test_user.id,
    )
    assert row.effective_tax_rate == Decimal("0.0000")


@pytest.mark.asyncio
async def test_net_deferred_tax_dta_minus_dtl(async_session: AsyncSession, test_user: IamUser) -> None:
    await _seed_budget(async_session, test_user, 2026, Decimal("1000000.00"))
    await upsert_tax_position(
        async_session,
        tenant_id=test_user.tenant_id,
        position_name="DTA",
        position_type="temporary_difference",
        carrying_amount=Decimal("200000.00"),
        tax_base=Decimal("0.00"),
        is_asset=True,
        tax_rate=Decimal("0.2500"),
    )
    await upsert_tax_position(
        async_session,
        tenant_id=test_user.tenant_id,
        position_name="DTL",
        position_type="temporary_difference",
        carrying_amount=Decimal("120000.00"),
        tax_base=Decimal("0.00"),
        is_asset=False,
        tax_rate=Decimal("0.2500"),
    )
    row = await compute_tax_provision(
        async_session,
        tenant_id=test_user.tenant_id,
        period="2026-07",
        entity_id=None,
        applicable_tax_rate=Decimal("0.2500"),
        created_by=test_user.id,
    )
    assert row.net_deferred_tax == Decimal("20000.00")


@pytest.mark.asyncio
async def test_net_deferred_negative_when_dtl_exceeds_dta(async_session: AsyncSession, test_user: IamUser) -> None:
    await _seed_budget(async_session, test_user, 2026, Decimal("1000000.00"))
    await upsert_tax_position(
        async_session,
        tenant_id=test_user.tenant_id,
        position_name="DTA",
        position_type="temporary_difference",
        carrying_amount=Decimal("40000.00"),
        tax_base=Decimal("0.00"),
        is_asset=True,
        tax_rate=Decimal("0.2500"),
    )
    await upsert_tax_position(
        async_session,
        tenant_id=test_user.tenant_id,
        position_name="DTL",
        position_type="temporary_difference",
        carrying_amount=Decimal("200000.00"),
        tax_base=Decimal("0.00"),
        is_asset=False,
        tax_rate=Decimal("0.2500"),
    )
    row = await compute_tax_provision(
        async_session,
        tenant_id=test_user.tenant_id,
        period="2026-08",
        entity_id=None,
        applicable_tax_rate=Decimal("0.2500"),
        created_by=test_user.id,
    )
    assert row.net_deferred_tax == Decimal("-40000.00")


@pytest.mark.asyncio
async def test_all_provision_amounts_decimal(async_session: AsyncSession, test_user: IamUser) -> None:
    await _seed_budget(async_session, test_user, 2026, Decimal("1000.00"))
    row = await compute_tax_provision(async_session, test_user.tenant_id, "2026-09", None, Decimal("0.2500"), test_user.id)
    assert isinstance(row.total_tax_expense, Decimal)


@pytest.mark.asyncio
async def test_provision_run_append_only(async_session: AsyncSession, test_user: IamUser) -> None:
    await _seed_budget(async_session, test_user, 2026, Decimal("1000.00"))
    row = await compute_tax_provision(async_session, test_user.tenant_id, "2026-10", None, Decimal("0.2500"), test_user.id)
    await async_session.execute(text(append_only_function_sql()))
    await async_session.execute(text(drop_trigger_sql("tax_provision_runs")))
    await async_session.execute(text(create_trigger_sql("tax_provision_runs")))
    await async_session.flush()
    with pytest.raises(Exception):
        await async_session.execute(text("UPDATE tax_provision_runs SET period='2026-11' WHERE id=:id"), {"id": row.id})


@pytest.mark.asyncio
async def test_provision_rls(async_session: AsyncSession, test_user: IamUser) -> None:
    row = TaxProvisionRun(
        tenant_id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
        entity_id=None,
        period="2026-01",
        fiscal_year=2026,
        applicable_tax_rate=Decimal("0.2500"),
        accounting_profit_before_tax=Decimal("100.00"),
        permanent_differences=Decimal("0.00"),
        timing_differences=Decimal("0.00"),
        taxable_income=Decimal("100.00"),
        current_tax_expense=Decimal("25.00"),
        deferred_tax_asset=Decimal("0.00"),
        deferred_tax_liability=Decimal("0.00"),
        net_deferred_tax=Decimal("0.00"),
        total_tax_expense=Decimal("25.00"),
        effective_tax_rate=Decimal("0.2500"),
        created_by=test_user.id,
    )
    async_session.add(row)
    await async_session.flush()

    schedule = await get_tax_provision_schedule(async_session, test_user.tenant_id, 2026)
    assert all(item.tenant_id == test_user.tenant_id for item in schedule["periods"])


@pytest.mark.asyncio
async def test_tax_position_dta_vs_dtl(async_session: AsyncSession, test_user: IamUser) -> None:
    dta = await upsert_tax_position(
        async_session,
        tenant_id=test_user.tenant_id,
        position_name="DTA test",
        position_type="temporary_difference",
        carrying_amount=Decimal("100000.00"),
        tax_base=Decimal("80000.00"),
        is_asset=True,
        tax_rate=Decimal("0.2500"),
    )
    dtl = await upsert_tax_position(
        async_session,
        tenant_id=test_user.tenant_id,
        position_name="DTL test",
        position_type="temporary_difference",
        carrying_amount=Decimal("80000.00"),
        tax_base=Decimal("100000.00"),
        is_asset=False,
        tax_rate=Decimal("0.2500"),
    )
    assert dta.is_asset is True
    assert dtl.is_asset is False


@pytest.mark.asyncio
async def test_temporary_difference_computed(async_session: AsyncSession, test_user: IamUser) -> None:
    row = await upsert_tax_position(
        async_session,
        tenant_id=test_user.tenant_id,
        position_name="Temp diff",
        position_type="temporary_difference",
        carrying_amount=Decimal("100000.00"),
        tax_base=Decimal("80000.00"),
        is_asset=True,
        tax_rate=Decimal("0.2500"),
    )
    assert row.temporary_difference == Decimal("20000.00")


@pytest.mark.asyncio
async def test_annual_schedule_structure(async_session: AsyncSession, test_user: IamUser) -> None:
    payload = await get_tax_provision_schedule(async_session, test_user.tenant_id, 2026)
    assert {"fiscal_year", "periods", "ytd_current_tax", "deferred_tax_positions"}.issubset(payload)


@pytest.mark.asyncio
async def test_ytd_totals_correct(async_session: AsyncSession, test_user: IamUser) -> None:
    await _seed_budget(async_session, test_user, 2026, Decimal("1000000.00"))
    await compute_tax_provision(async_session, test_user.tenant_id, "2026-01", None, Decimal("0.2500"), test_user.id)
    await compute_tax_provision(async_session, test_user.tenant_id, "2026-02", None, Decimal("0.2500"), test_user.id)
    payload = await get_tax_provision_schedule(async_session, test_user.tenant_id, 2026)
    assert payload["ytd_current_tax"] == Decimal("500000.00")


@pytest.mark.asyncio
async def test_api_compute_provision(async_client, async_session: AsyncSession, test_user: IamUser) -> None:
    await _seed_budget(async_session, test_user, 2026, Decimal("1000000.00"))
    response = await async_client.post(
        "/api/v1/tax/provision/compute",
        headers=_auth_headers(test_user),
        json={"period": "2026-03", "applicable_tax_rate": "0.2500", "entity_id": None},
    )
    assert response.status_code == 200
    assert response.json()["data"]["current_tax_expense"] == "250000.00"


@pytest.mark.asyncio
async def test_api_positions_endpoint(async_client, test_user: IamUser) -> None:
    response = await async_client.post(
        "/api/v1/tax/positions",
        headers=_auth_headers(test_user),
        json={
            "position_name": "API Position",
            "position_type": "temporary_difference",
            "carrying_amount": "100.00",
            "tax_base": "80.00",
            "is_asset": True,
            "tax_rate": "0.2500",
        },
    )
    assert response.status_code == 200
    list_response = await async_client.get("/api/v1/tax/positions", headers=_auth_headers(test_user))
    assert list_response.status_code == 200
    assert list_response.json()["data"]["total"] >= 1
