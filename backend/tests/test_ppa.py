from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql
from financeops.db.models.users import IamUser
from financeops.modules.ppa.models import PPAAllocation, PPAEngagement, PPAIntangible
from financeops.modules.ppa.service import (
    compute_intangible_fair_value,
    create_ppa_engagement,
    get_ppa_report,
    identify_intangibles,
    run_ppa,
)
from financeops.services.credit_service import add_credits


async def _fund(async_session: AsyncSession, tenant_id: uuid.UUID, amount: str = "10000.00") -> None:
    await add_credits(async_session, tenant_id, Decimal(amount), "test_ppa_fund")
    await async_session.flush()


async def _create_engagement(async_session: AsyncSession, user: IamUser, purchase_price: str = "1000.00") -> PPAEngagement:
    return await create_ppa_engagement(
        async_session,
        tenant_id=user.tenant_id,
        engagement_name="PPA Engagement",
        target_company_name="Target Co",
        acquisition_date=date(2025, 1, 15),
        purchase_price=Decimal(purchase_price),
        purchase_price_currency="INR",
        accounting_standard="IFRS3",
        created_by=user.id,
    )


def _contains_float(value: Any) -> bool:
    if isinstance(value, float):
        return True
    if isinstance(value, list):
        return any(_contains_float(item) for item in value)
    if isinstance(value, dict):
        return any(_contains_float(item) for item in value.values())
    return False


# Engagement (3)
@pytest.mark.asyncio
async def test_create_ppa_engagement_reserves_credits(async_session: AsyncSession, test_user: IamUser) -> None:
    await _fund(async_session, test_user.tenant_id)
    engagement = await _create_engagement(async_session, test_user)
    assert engagement.credit_cost == 2000
    assert engagement.status == "draft"


@pytest.mark.asyncio
async def test_purchase_price_stored_as_decimal(async_session: AsyncSession, test_user: IamUser) -> None:
    await _fund(async_session, test_user.tenant_id)
    engagement = await _create_engagement(async_session, test_user, purchase_price="1500.50")
    assert isinstance(engagement.purchase_price, Decimal)
    assert engagement.purchase_price == Decimal("1500.50")


@pytest.mark.asyncio
async def test_ppa_engagement_rls(async_session: AsyncSession, test_user: IamUser) -> None:
    await _fund(async_session, test_user.tenant_id)
    engagement_a = await _create_engagement(async_session, test_user)
    tenant_b = uuid.uuid4()
    await _fund(async_session, tenant_b)
    engagement_b = await create_ppa_engagement(
        async_session,
        tenant_id=tenant_b,
        engagement_name="B",
        target_company_name="B",
        acquisition_date=date(2025, 1, 1),
        purchase_price=Decimal("1000.00"),
        purchase_price_currency="INR",
        accounting_standard="IFRS3",
        created_by=test_user.id,
    )
    rows = (
        await async_session.execute(
            select(PPAEngagement).where(PPAEngagement.tenant_id == test_user.tenant_id)
        )
    ).scalars().all()
    assert engagement_a.id in {row.id for row in rows}
    assert engagement_b.id not in {row.id for row in rows}


# Fair value computation (5)
@pytest.mark.asyncio
async def test_relief_from_royalty_computation() -> None:
    result = await compute_intangible_fair_value(
        "technology",
        "relief_from_royalty",
        {
            "revenue": "1000000",
            "royalty_rate": "0.05",
            "discount_rate": "0.12",
            "useful_life_years": "5",
        },
    )
    assert isinstance(result, Decimal)
    assert result > Decimal("0")


@pytest.mark.asyncio
async def test_excess_earnings_computation() -> None:
    result = await compute_intangible_fair_value(
        "customer_relationships",
        "excess_earnings",
        {
            "earnings": "500000",
            "contributory_asset_charges": "100000",
            "discount_rate": "0.10",
            "useful_life_years": "4",
        },
    )
    assert isinstance(result, Decimal)
    assert result > Decimal("0")


@pytest.mark.asyncio
async def test_fair_value_all_decimal() -> None:
    assumptions = {
        "revenue": "1200000",
        "royalty_rate": "0.04",
        "discount_rate": "0.11",
        "useful_life_years": "6",
    }
    result = await compute_intangible_fair_value("brand", "relief_from_royalty", assumptions)
    assert isinstance(result, Decimal)
    assert not _contains_float({"value": result})


@pytest.mark.asyncio
async def test_zero_royalty_rate_returns_zero() -> None:
    result = await compute_intangible_fair_value(
        "technology",
        "relief_from_royalty",
        {
            "revenue": "1000000",
            "royalty_rate": "0",
            "discount_rate": "0.12",
            "useful_life_years": "5",
        },
    )
    assert result == Decimal("0")


@pytest.mark.asyncio
async def test_discount_rate_reduces_fair_value() -> None:
    low_rate = await compute_intangible_fair_value(
        "brand",
        "relief_from_royalty",
        {
            "revenue": "1000000",
            "royalty_rate": "0.05",
            "discount_rate": "0.08",
            "useful_life_years": "5",
        },
    )
    high_rate = await compute_intangible_fair_value(
        "brand",
        "relief_from_royalty",
        {
            "revenue": "1000000",
            "royalty_rate": "0.05",
            "discount_rate": "0.20",
            "useful_life_years": "5",
        },
    )
    assert low_rate > high_rate


# Allocation (6)
@pytest.mark.asyncio
async def test_goodwill_computation_correct(
    async_session: AsyncSession,
    test_user: IamUser,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _fund(async_session, test_user.tenant_id)
    engagement = await _create_engagement(async_session, test_user, purchase_price="1000.00")

    async def _fixed_fair_value(*args, **kwargs):  # noqa: ANN001, ANN002
        del args, kwargs
        return Decimal("300.00")

    from financeops.modules import ppa as ppa_module

    monkeypatch.setattr(ppa_module.service, "compute_intangible_fair_value", _fixed_fair_value)
    allocation = await run_ppa(
        async_session,
        tenant_id=test_user.tenant_id,
        engagement_id=engagement.id,
        intangibles_input=[
            {
                "name": "Tech",
                "category": "technology",
                "valuation_method": "relief_from_royalty",
                "useful_life_years": "5",
                "assumptions": {},
                "tax_basis": "0",
                "applicable_tax_rate": "0.20",
            }
        ],
    )
    assert allocation.goodwill == Decimal("160.00")


@pytest.mark.asyncio
async def test_purchase_price_reconciles(
    async_session: AsyncSession,
    test_user: IamUser,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _fund(async_session, test_user.tenant_id)
    engagement = await _create_engagement(async_session, test_user, purchase_price="1000.00")

    async def _fixed_fair_value(*args, **kwargs):  # noqa: ANN001, ANN002
        del args, kwargs
        return Decimal("300.00")

    from financeops.modules import ppa as ppa_module

    monkeypatch.setattr(ppa_module.service, "compute_intangible_fair_value", _fixed_fair_value)
    allocation = await run_ppa(
        async_session,
        tenant_id=test_user.tenant_id,
        engagement_id=engagement.id,
        intangibles_input=[
            {
                "name": "Customer",
                "category": "customer_relationships",
                "valuation_method": "excess_earnings",
                "useful_life_years": "5",
                "assumptions": {},
                "tax_basis": "0",
                "applicable_tax_rate": "0.20",
            }
        ],
    )
    reconciled = Decimal(str(allocation.purchase_price_reconciliation["reconciled_total"]))
    assert reconciled == Decimal("1000.00")


@pytest.mark.asyncio
async def test_ppa_allocations_append_only(async_session: AsyncSession, test_user: IamUser) -> None:
    await _fund(async_session, test_user.tenant_id)
    engagement = await _create_engagement(async_session, test_user)
    allocation = PPAAllocation(
        engagement_id=engagement.id,
        tenant_id=test_user.tenant_id,
        allocation_version=1,
        net_identifiable_assets=Decimal("600.00"),
        total_intangibles_identified=Decimal("300.00"),
        goodwill=Decimal("160.00"),
        deferred_tax_liability=Decimal("60.00"),
        purchase_price_reconciliation={"reconciled_total": "1000.00"},
    )
    async_session.add(allocation)
    await async_session.flush()
    await async_session.execute(text(append_only_function_sql()))
    await async_session.execute(text(drop_trigger_sql("ppa_allocations")))
    await async_session.execute(text(create_trigger_sql("ppa_allocations")))
    await async_session.flush()
    with pytest.raises(Exception):
        await async_session.execute(
            text("UPDATE ppa_allocations SET goodwill = :goodwill WHERE id = :id"),
            {"goodwill": Decimal("999.00"), "id": allocation.id},
        )


@pytest.mark.asyncio
async def test_ppa_intangibles_append_only(async_session: AsyncSession, test_user: IamUser) -> None:
    await _fund(async_session, test_user.tenant_id)
    engagement = await _create_engagement(async_session, test_user)
    allocation = PPAAllocation(
        engagement_id=engagement.id,
        tenant_id=test_user.tenant_id,
        allocation_version=1,
        net_identifiable_assets=Decimal("600.00"),
        total_intangibles_identified=Decimal("300.00"),
        goodwill=Decimal("160.00"),
        deferred_tax_liability=Decimal("60.00"),
        purchase_price_reconciliation={"reconciled_total": "1000.00"},
    )
    async_session.add(allocation)
    await async_session.flush()
    row = PPAIntangible(
        engagement_id=engagement.id,
        allocation_id=allocation.id,
        tenant_id=test_user.tenant_id,
        intangible_name="Tech",
        intangible_category="technology",
        fair_value=Decimal("300.00"),
        useful_life_years=Decimal("5.00"),
        amortisation_method="straight_line",
        annual_amortisation=Decimal("60.00"),
        tax_basis=Decimal("0"),
        deferred_tax_liability=Decimal("60.00"),
        valuation_method="relief_from_royalty",
        valuation_assumptions={},
    )
    async_session.add(row)
    await async_session.flush()
    await async_session.execute(text(append_only_function_sql()))
    await async_session.execute(text(drop_trigger_sql("ppa_intangibles")))
    await async_session.execute(text(create_trigger_sql("ppa_intangibles")))
    await async_session.flush()
    with pytest.raises(Exception):
        await async_session.execute(
            text("UPDATE ppa_intangibles SET fair_value = :fair_value WHERE id = :id"),
            {"fair_value": Decimal("999.00"), "id": row.id},
        )


@pytest.mark.asyncio
async def test_all_allocation_amounts_decimal(
    async_session: AsyncSession,
    test_user: IamUser,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _fund(async_session, test_user.tenant_id)
    engagement = await _create_engagement(async_session, test_user, purchase_price="1000.00")

    async def _fixed_fair_value(*args, **kwargs):  # noqa: ANN001, ANN002
        del args, kwargs
        return Decimal("300.00")

    from financeops.modules import ppa as ppa_module

    monkeypatch.setattr(ppa_module.service, "compute_intangible_fair_value", _fixed_fair_value)
    allocation = await run_ppa(
        async_session,
        tenant_id=test_user.tenant_id,
        engagement_id=engagement.id,
        intangibles_input=[
            {
                "name": "Tech",
                "category": "technology",
                "valuation_method": "relief_from_royalty",
                "useful_life_years": "5",
                "assumptions": {},
                "tax_basis": "0",
                "applicable_tax_rate": "0.20",
            }
        ],
    )
    assert isinstance(allocation.net_identifiable_assets, Decimal)
    assert isinstance(allocation.total_intangibles_identified, Decimal)
    assert isinstance(allocation.goodwill, Decimal)
    assert isinstance(allocation.deferred_tax_liability, Decimal)


@pytest.mark.asyncio
async def test_amortisation_schedule_sums_to_fair_value(
    async_session: AsyncSession,
    test_user: IamUser,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _fund(async_session, test_user.tenant_id)
    engagement = await _create_engagement(async_session, test_user, purchase_price="1000.00")

    async def _fixed_fair_value(*args, **kwargs):  # noqa: ANN001, ANN002
        del args, kwargs
        return Decimal("300.00")

    from financeops.modules import ppa as ppa_module

    monkeypatch.setattr(ppa_module.service, "compute_intangible_fair_value", _fixed_fair_value)
    await run_ppa(
        async_session,
        tenant_id=test_user.tenant_id,
        engagement_id=engagement.id,
        intangibles_input=[
            {
                "name": "Tech",
                "category": "technology",
                "valuation_method": "relief_from_royalty",
                "useful_life_years": "5",
                "assumptions": {},
                "tax_basis": "0",
                "applicable_tax_rate": "0.20",
            }
        ],
    )
    report = await get_ppa_report(async_session, test_user.tenant_id, engagement.id)
    amort_total = sum(report["amortisation_schedule"].values(), start=Decimal("0"))
    assert abs(amort_total - Decimal("300.00")) <= Decimal("0.01")


# Report (3)
@pytest.mark.asyncio
async def test_ppa_report_structure(
    async_session: AsyncSession,
    test_user: IamUser,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _fund(async_session, test_user.tenant_id)
    engagement = await _create_engagement(async_session, test_user)

    async def _fixed_fair_value(*args, **kwargs):  # noqa: ANN001, ANN002
        del args, kwargs
        return Decimal("300.00")

    from financeops.modules import ppa as ppa_module

    monkeypatch.setattr(ppa_module.service, "compute_intangible_fair_value", _fixed_fair_value)
    await run_ppa(
        async_session,
        tenant_id=test_user.tenant_id,
        engagement_id=engagement.id,
        intangibles_input=[
            {
                "name": "Tech",
                "category": "technology",
                "valuation_method": "relief_from_royalty",
                "useful_life_years": "5",
                "assumptions": {},
                "tax_basis": "0",
                "applicable_tax_rate": "0.20",
            }
        ],
    )
    report = await get_ppa_report(async_session, test_user.tenant_id, engagement.id)
    assert {"engagement", "allocation", "intangibles", "purchase_price_bridge", "amortisation_schedule", "goodwill_pct_of_purchase_price"}.issubset(report.keys())


@pytest.mark.asyncio
async def test_goodwill_pct_is_decimal(
    async_session: AsyncSession,
    test_user: IamUser,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _fund(async_session, test_user.tenant_id)
    engagement = await _create_engagement(async_session, test_user)

    async def _fixed_fair_value(*args, **kwargs):  # noqa: ANN001, ANN002
        del args, kwargs
        return Decimal("300.00")

    from financeops.modules import ppa as ppa_module

    monkeypatch.setattr(ppa_module.service, "compute_intangible_fair_value", _fixed_fair_value)
    await run_ppa(
        async_session,
        tenant_id=test_user.tenant_id,
        engagement_id=engagement.id,
        intangibles_input=[
            {
                "name": "Tech",
                "category": "technology",
                "valuation_method": "relief_from_royalty",
                "useful_life_years": "5",
                "assumptions": {},
                "tax_basis": "0",
                "applicable_tax_rate": "0.20",
            }
        ],
    )
    report = await get_ppa_report(async_session, test_user.tenant_id, engagement.id)
    assert isinstance(report["goodwill_pct_of_purchase_price"], Decimal)


@pytest.mark.asyncio
async def test_purchase_price_bridge_reconciles(
    async_session: AsyncSession,
    test_user: IamUser,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _fund(async_session, test_user.tenant_id)
    engagement = await _create_engagement(async_session, test_user)

    async def _fixed_fair_value(*args, **kwargs):  # noqa: ANN001, ANN002
        del args, kwargs
        return Decimal("300.00")

    from financeops.modules import ppa as ppa_module

    monkeypatch.setattr(ppa_module.service, "compute_intangible_fair_value", _fixed_fair_value)
    await run_ppa(
        async_session,
        tenant_id=test_user.tenant_id,
        engagement_id=engagement.id,
        intangibles_input=[
            {
                "name": "Tech",
                "category": "technology",
                "valuation_method": "relief_from_royalty",
                "useful_life_years": "5",
                "assumptions": {},
                "tax_basis": "0",
                "applicable_tax_rate": "0.20",
            }
        ],
    )
    report = await get_ppa_report(async_session, test_user.tenant_id, engagement.id)
    assert report["purchase_price_bridge"]["total"] == Decimal("1000.00")


# API (3)
@pytest.mark.asyncio
async def test_create_ppa_via_api(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_user: IamUser,
    test_access_token: str,
) -> None:
    await _fund(async_session, test_user.tenant_id)
    response = await async_client.post(
        "/api/v1/advisory/ppa/engagements",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "engagement_name": "Acquisition PPA",
            "target_company_name": "Target",
            "acquisition_date": "2025-01-15",
            "purchase_price": "1000.00",
            "purchase_price_currency": "INR",
            "accounting_standard": "IFRS3",
        },
    )
    assert response.status_code == 201
    assert response.json()["data"]["status"] == "draft"


@pytest.mark.asyncio
async def test_identify_intangibles_endpoint(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_user: IamUser,
    test_access_token: str,
) -> None:
    await _fund(async_session, test_user.tenant_id)
    engagement = await _create_engagement(async_session, test_user)
    response = await async_client.post(
        f"/api/v1/advisory/ppa/engagements/{engagement.id}/identify-intangibles",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 200
    assert len(response.json()["data"]["intangibles"]) > 0


@pytest.mark.asyncio
async def test_run_ppa_via_api(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_user: IamUser,
    test_access_token: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _fund(async_session, test_user.tenant_id)
    engagement = await _create_engagement(async_session, test_user)

    async def _fixed_fair_value(*args, **kwargs):  # noqa: ANN001, ANN002
        del args, kwargs
        return Decimal("300.00")

    from financeops.modules import ppa as ppa_module

    monkeypatch.setattr(ppa_module.service, "compute_intangible_fair_value", _fixed_fair_value)
    response = await async_client.post(
        f"/api/v1/advisory/ppa/engagements/{engagement.id}/run",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "intangibles": [
                {
                    "name": "Tech",
                    "category": "technology",
                    "valuation_method": "relief_from_royalty",
                    "useful_life_years": "5",
                    "assumptions": {},
                    "tax_basis": "0",
                    "applicable_tax_rate": "0.20",
                }
            ]
        },
    )
    assert response.status_code == 200
    assert response.json()["data"]["goodwill"] == "160.00"
