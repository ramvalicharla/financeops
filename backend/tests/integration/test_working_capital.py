from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.entitlement_helpers import grant_boolean_entitlement
from tests.working_capital_helpers import compute_wc_snapshot, seed_working_capital_gl_data


@pytest_asyncio.fixture(autouse=True)
async def _grant_working_capital_entitlement(async_session: AsyncSession, test_user) -> None:
    await grant_boolean_entitlement(
        async_session,
        tenant_id=test_user.tenant_id,
        feature_name="working_capital",
        actor_user_id=test_user.id,
    )


@pytest.mark.asyncio
async def test_wc_snapshot_reads_from_gl_not_hardcoded_values(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_user,
    test_access_token: str,
) -> None:
    await seed_working_capital_gl_data(
        async_session,
        tenant_id=test_user.tenant_id,
        period="2026-10",
        uploaded_by=test_user.id,
        ar="123456.78",
        ap="65432.10",
        inventory="7654.32",
        cash="1111.11",
        accrued_liabilities="2222.22",
        revenue="987654.32",
        cogs="456789.12",
    )

    response = await async_client.get(
        "/api/v1/working-capital/dashboard?period=2026-10",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )

    assert response.status_code == 200
    snapshot = response.json()["data"]["current_snapshot"]
    assert Decimal(str(snapshot["ar_total"])) == Decimal("123456.78")
    assert Decimal(str(snapshot["ap_total"])) == Decimal("65432.10")
    assert Decimal(str(snapshot["net_working_capital"])) == Decimal("64567.89")


@pytest.mark.asyncio
async def test_wc_raises_insufficient_data_error_for_new_tenant_no_gl(
    async_client: AsyncClient,
    test_access_token: str,
) -> None:
    response = await async_client.get(
        "/api/v1/working-capital/dashboard?period=2026-11",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )

    assert response.status_code == 422
    assert "No GL data for tenant" in response.text


@pytest.mark.asyncio
async def test_wc_current_ratio_calculation_with_decimal_precision(
    async_session: AsyncSession,
    test_user,
) -> None:
    await seed_working_capital_gl_data(
        async_session,
        tenant_id=test_user.tenant_id,
        period="2026-12",
        uploaded_by=test_user.id,
        ar="500.10",
        ap="600.00",
        inventory="200.20",
        cash="633.03",
        accrued_liabilities="200.00",
        revenue="9000.00",
        cogs="3000.00",
    )

    snapshot = await compute_wc_snapshot(async_session, test_user.tenant_id, "2026-12")
    assert snapshot.current_ratio == Decimal("1.6667")
    assert snapshot.quick_ratio == Decimal("1.4164")


@pytest.mark.asyncio
async def test_wc_dso_uses_indian_financial_year_april_march(
    async_session: AsyncSession,
    test_user,
) -> None:
    await seed_working_capital_gl_data(
        async_session,
        tenant_id=test_user.tenant_id,
        period="2026-06",
        uploaded_by=test_user.id,
        ar="365.00",
        ap="120.00",
        inventory="90.00",
        cash="210.00",
        accrued_liabilities="30.00",
        revenue="1650.00",
        cogs="730.00",
        prior_revenue={
            "2026-04": "1000.00",
            "2026-05": "1000.00",
        },
    )

    snapshot = await compute_wc_snapshot(async_session, test_user.tenant_id, "2026-06")
    assert snapshot.dso_days == Decimal("36.50")


@pytest.mark.asyncio
async def test_wc_rls_tenant_a_cannot_see_tenant_b_snapshot(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_user,
    test_access_token: str,
) -> None:
    await seed_working_capital_gl_data(
        async_session,
        tenant_id=test_user.tenant_id,
        period="2027-01",
        uploaded_by=test_user.id,
        ar="111.11",
        ap="80.00",
        inventory="70.00",
        cash="50.00",
        accrued_liabilities="20.00",
        revenue="1111.10",
        cogs="444.44",
    )
    await compute_wc_snapshot(async_session, test_user.tenant_id, "2027-01")

    tenant_b = uuid.uuid4()
    await seed_working_capital_gl_data(
        async_session,
        tenant_id=tenant_b,
        period="2027-01",
        uploaded_by=tenant_b,
        ar="999.99",
        ap="88.00",
        inventory="77.00",
        cash="66.00",
        accrued_liabilities="11.00",
        revenue="9999.99",
        cogs="3333.33",
    )
    await compute_wc_snapshot(async_session, tenant_b, "2027-01")

    response = await async_client.get(
        "/api/v1/working-capital/dashboard?period=2027-01",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )

    assert response.status_code == 200
    snapshot = response.json()["data"]["current_snapshot"]
    assert Decimal(str(snapshot["ar_total"])) == Decimal("111.11")
    assert Decimal(str(snapshot["ar_total"])) != Decimal("999.99")
