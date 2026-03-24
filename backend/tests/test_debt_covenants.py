from __future__ import annotations

from decimal import Decimal
import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.security import create_access_token
from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql
from financeops.db.models.users import IamUser
from financeops.modules.debt_covenants.models import CovenantBreachEvent, CovenantDefinition
from financeops.modules.debt_covenants import service as covenant_service
from financeops.modules.debt_covenants.service import check_all_covenants, compute_covenant_value, get_covenant_dashboard


def _auth_headers(user: IamUser) -> dict[str, str]:
    token = create_access_token(user.id, user.tenant_id, user.role.value)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_debt_to_ebitda_computed_correctly(async_session: AsyncSession, test_user: IamUser, monkeypatch: pytest.MonkeyPatch) -> None:
    async def _snapshot(*args, **kwargs):  # type: ignore[no-untyped-def]
        return {
            "total_debt": Decimal("5000000"),
            "ltm_ebitda": Decimal("1000000"),
            "ebit": Decimal("0"),
            "interest_expense": Decimal("1"),
            "current_assets": Decimal("1"),
            "current_liabilities": Decimal("1"),
            "total_equity": Decimal("1"),
            "cash": Decimal("0"),
            "taxes": Decimal("0"),
            "capex": Decimal("0"),
            "debt_service": Decimal("1"),
            "net_debt": Decimal("0"),
        }

    monkeypatch.setattr(covenant_service, "_financial_snapshot", _snapshot)
    ratio = await compute_covenant_value(async_session, test_user.tenant_id, "debt_to_ebitda", "2026-03")
    assert ratio == Decimal("5.000000")


@pytest.mark.asyncio
async def test_interest_coverage_computed(async_session: AsyncSession, test_user: IamUser, monkeypatch: pytest.MonkeyPatch) -> None:
    async def _snapshot(*args, **kwargs):  # type: ignore[no-untyped-def]
        return {
            "total_debt": Decimal("0"),
            "ltm_ebitda": Decimal("1"),
            "ebit": Decimal("500000"),
            "interest_expense": Decimal("100000"),
            "current_assets": Decimal("1"),
            "current_liabilities": Decimal("1"),
            "total_equity": Decimal("1"),
            "cash": Decimal("0"),
            "taxes": Decimal("0"),
            "capex": Decimal("0"),
            "debt_service": Decimal("1"),
            "net_debt": Decimal("0"),
        }

    monkeypatch.setattr(covenant_service, "_financial_snapshot", _snapshot)
    ratio = await compute_covenant_value(async_session, test_user.tenant_id, "interest_coverage", "2026-03")
    assert ratio == Decimal("5.000000")


@pytest.mark.asyncio
async def test_covenant_pass(async_session: AsyncSession, test_user: IamUser, monkeypatch: pytest.MonkeyPatch) -> None:
    covenant = CovenantDefinition(
        tenant_id=test_user.tenant_id,
        facility_name="TL",
        lender_name="Bank",
        covenant_type="debt_to_ebitda",
        covenant_label="D/E",
        threshold_value=Decimal("5.0"),
        threshold_direction="below",
        measurement_frequency="monthly",
        notification_threshold_pct=Decimal("90.00"),
    )
    async_session.add(covenant)
    await async_session.flush()

    async def _value(*args, **kwargs):  # type: ignore[no-untyped-def]
        return Decimal("4.4")

    monkeypatch.setattr(covenant_service, "compute_covenant_value", _value)
    events = await check_all_covenants(async_session, test_user.tenant_id, "2026-03")
    assert events[0].breach_type == "pass"


@pytest.mark.asyncio
async def test_covenant_breach_above(async_session: AsyncSession, test_user: IamUser, monkeypatch: pytest.MonkeyPatch) -> None:
    covenant = CovenantDefinition(
        tenant_id=test_user.tenant_id,
        facility_name="TL",
        lender_name="Bank",
        covenant_type="debt_to_ebitda",
        covenant_label="D/E",
        threshold_value=Decimal("5.0"),
        threshold_direction="below",
        measurement_frequency="monthly",
        notification_threshold_pct=Decimal("90.00"),
    )
    async_session.add(covenant)
    await async_session.flush()

    async def _value(*args, **kwargs):  # type: ignore[no-untyped-def]
        return Decimal("5.5")

    monkeypatch.setattr(covenant_service, "compute_covenant_value", _value)
    events = await check_all_covenants(async_session, test_user.tenant_id, "2026-03")
    assert events[0].breach_type == "breach"


@pytest.mark.asyncio
async def test_covenant_near_breach(async_session: AsyncSession, test_user: IamUser, monkeypatch: pytest.MonkeyPatch) -> None:
    covenant = CovenantDefinition(
        tenant_id=test_user.tenant_id,
        facility_name="TL",
        lender_name="Bank",
        covenant_type="debt_to_ebitda",
        covenant_label="D/E",
        threshold_value=Decimal("5.0"),
        threshold_direction="below",
        measurement_frequency="monthly",
        notification_threshold_pct=Decimal("90.00"),
    )
    async_session.add(covenant)
    await async_session.flush()

    async def _value(*args, **kwargs):  # type: ignore[no-untyped-def]
        return Decimal("4.6")

    monkeypatch.setattr(covenant_service, "compute_covenant_value", _value)
    events = await check_all_covenants(async_session, test_user.tenant_id, "2026-03")
    assert events[0].breach_type == "near_breach"


@pytest.mark.asyncio
async def test_breach_event_append_only(async_session: AsyncSession, test_user: IamUser) -> None:
    event = CovenantBreachEvent(
        covenant_id=uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        tenant_id=test_user.tenant_id,
        period="2026-03",
        actual_value=Decimal("5.5"),
        threshold_value=Decimal("5.0"),
        breach_type="breach",
        variance_pct=Decimal("10.0000"),
    )
    async_session.add(event)
    await async_session.flush()

    await async_session.execute(text(append_only_function_sql()))
    await async_session.execute(text(drop_trigger_sql("covenant_breach_events")))
    await async_session.execute(text(create_trigger_sql("covenant_breach_events")))
    await async_session.flush()

    with pytest.raises(Exception):
        await async_session.execute(
            text("UPDATE covenant_breach_events SET breach_type='pass' WHERE id=:id"),
            {"id": event.id},
        )


@pytest.mark.asyncio
async def test_headroom_pct_computed(async_session: AsyncSession, test_user: IamUser, monkeypatch: pytest.MonkeyPatch) -> None:
    covenant = CovenantDefinition(
        tenant_id=test_user.tenant_id,
        facility_name="TL",
        lender_name="Bank",
        covenant_type="debt_to_ebitda",
        covenant_label="D/E",
        threshold_value=Decimal("5.0"),
        threshold_direction="below",
        measurement_frequency="monthly",
        notification_threshold_pct=Decimal("90.00"),
    )
    async_session.add(covenant)
    await async_session.flush()

    async def _value(*args, **kwargs):  # type: ignore[no-untyped-def]
        return Decimal("4.0")

    monkeypatch.setattr(covenant_service, "compute_covenant_value", _value)
    await check_all_covenants(async_session, test_user.tenant_id, "2026-03")
    dashboard = await get_covenant_dashboard(async_session, test_user.tenant_id)
    assert Decimal(str(dashboard["covenants"][0]["headroom_pct"])) > Decimal("0")


@pytest.mark.asyncio
async def test_all_covenant_values_decimal(async_session: AsyncSession, test_user: IamUser) -> None:
    value = await compute_covenant_value(async_session, test_user.tenant_id, "minimum_cash_balance", "2026-03")
    assert isinstance(value, Decimal)


@pytest.mark.asyncio
async def test_zero_ebitda_no_division_error(async_session: AsyncSession, test_user: IamUser, monkeypatch: pytest.MonkeyPatch) -> None:
    async def _snapshot(*args, **kwargs):  # type: ignore[no-untyped-def]
        return {
            "total_debt": Decimal("100"),
            "ltm_ebitda": Decimal("0"),
            "ebit": Decimal("0"),
            "interest_expense": Decimal("1"),
            "current_assets": Decimal("1"),
            "current_liabilities": Decimal("1"),
            "total_equity": Decimal("1"),
            "cash": Decimal("0"),
            "taxes": Decimal("0"),
            "capex": Decimal("0"),
            "debt_service": Decimal("1"),
            "net_debt": Decimal("0"),
        }

    monkeypatch.setattr(covenant_service, "_financial_snapshot", _snapshot)
    value = await compute_covenant_value(async_session, test_user.tenant_id, "debt_to_ebitda", "2026-03")
    assert value == Decimal("0.000000")


@pytest.mark.asyncio
async def test_notification_fires_on_near_breach(async_session: AsyncSession, test_user: IamUser, monkeypatch: pytest.MonkeyPatch) -> None:
    covenant = CovenantDefinition(
        tenant_id=test_user.tenant_id,
        facility_name="TL",
        lender_name="Bank",
        covenant_type="debt_to_ebitda",
        covenant_label="D/E",
        threshold_value=Decimal("5.0"),
        threshold_direction="below",
        measurement_frequency="monthly",
        notification_threshold_pct=Decimal("90.00"),
    )
    async_session.add(covenant)
    await async_session.flush()

    calls: list[str] = []

    async def _value(*args, **kwargs):  # type: ignore[no-untyped-def]
        return Decimal("4.6")

    async def _notify(*args, **kwargs):  # type: ignore[no-untyped-def]
        calls.append("notified")

    monkeypatch.setattr(covenant_service, "compute_covenant_value", _value)
    monkeypatch.setattr(covenant_service, "send_notification", _notify)
    await check_all_covenants(async_session, test_user.tenant_id, "2026-03")
    assert calls


@pytest.mark.asyncio
async def test_notification_fires_on_breach(async_session: AsyncSession, test_user: IamUser, monkeypatch: pytest.MonkeyPatch) -> None:
    covenant = CovenantDefinition(
        tenant_id=test_user.tenant_id,
        facility_name="TL",
        lender_name="Bank",
        covenant_type="debt_to_ebitda",
        covenant_label="D/E",
        threshold_value=Decimal("5.0"),
        threshold_direction="below",
        measurement_frequency="monthly",
        notification_threshold_pct=Decimal("90.00"),
    )
    async_session.add(covenant)
    await async_session.flush()

    calls: list[str] = []

    async def _value(*args, **kwargs):  # type: ignore[no-untyped-def]
        return Decimal("5.6")

    async def _notify(*args, **kwargs):  # type: ignore[no-untyped-def]
        calls.append("notified")

    monkeypatch.setattr(covenant_service, "compute_covenant_value", _value)
    monkeypatch.setattr(covenant_service, "send_notification", _notify)
    await check_all_covenants(async_session, test_user.tenant_id, "2026-03")
    assert calls


@pytest.mark.asyncio
async def test_covenant_dashboard_structure(async_session: AsyncSession, test_user: IamUser) -> None:
    payload = await get_covenant_dashboard(async_session, test_user.tenant_id)
    assert {"total_covenants", "passing", "near_breach", "breached", "covenants"}.issubset(payload)


@pytest.mark.asyncio
async def test_covenant_rls(async_session: AsyncSession, test_user: IamUser) -> None:
    other = CovenantDefinition(
        tenant_id=uuid.UUID("33333333-3333-3333-3333-333333333333"),
        facility_name="Other",
        lender_name="Other",
        covenant_type="debt_to_ebitda",
        covenant_label="Other",
        threshold_value=Decimal("5.0"),
        threshold_direction="below",
        measurement_frequency="monthly",
        notification_threshold_pct=Decimal("90.00"),
    )
    async_session.add(other)
    await async_session.flush()

    payload = await get_covenant_dashboard(async_session, test_user.tenant_id)
    assert all(item["definition"].tenant_id == test_user.tenant_id for item in payload["covenants"])


@pytest.mark.asyncio
async def test_api_create_covenant(async_client, test_user: IamUser) -> None:
    response = await async_client.post(
        "/api/v1/covenants",
        headers=_auth_headers(test_user),
        json={
            "facility_name": "HDFC TL",
            "lender_name": "HDFC",
            "covenant_type": "debt_to_ebitda",
            "covenant_label": "Debt/EBITDA",
            "threshold_value": "5.0",
            "threshold_direction": "below",
            "measurement_frequency": "monthly",
        },
    )
    assert response.status_code == 200
    assert response.json()["data"]["facility_name"] == "HDFC TL"


@pytest.mark.asyncio
async def test_api_check_covenants(async_client, async_session: AsyncSession, test_user: IamUser) -> None:
    row = CovenantDefinition(
        tenant_id=test_user.tenant_id,
        facility_name="Check",
        lender_name="Bank",
        covenant_type="debt_to_ebitda",
        covenant_label="Debt/EBITDA",
        threshold_value=Decimal("5.0"),
        threshold_direction="below",
        measurement_frequency="monthly",
        notification_threshold_pct=Decimal("90.00"),
    )
    async_session.add(row)
    await async_session.flush()

    response = await async_client.post(
        "/api/v1/covenants/check",
        headers=_auth_headers(test_user),
        json={"period": "2026-03"},
    )
    assert response.status_code == 200
    assert "events" in response.json()["data"]
