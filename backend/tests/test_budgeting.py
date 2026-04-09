from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.intent.context import MutationContext, governed_mutation_context
from financeops.core.security import create_access_token, hash_password
from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql
from financeops.db.models.users import IamUser, UserRole
from financeops.modules.budgeting.models import BudgetLineItem, BudgetVersion
from financeops.modules.budgeting.service import (
    approve_budget as _approve_budget,
    create_budget_version as _create_budget_version,
    get_budget_vs_actual,
    upsert_budget_line as _upsert_budget_line,
)


def _months(value: str) -> list[Decimal]:
    return [Decimal(value) for _ in range(12)]


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


async def _create_budget_with_lines(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    fiscal_year: int = 2025,
    version_name: str = "Annual Budget",
) -> BudgetVersion:
    version = await create_budget_version(
        session,
        tenant_id=tenant_id,
        fiscal_year=fiscal_year,
        version_name=version_name,
        created_by=user_id,
    )
    await upsert_budget_line(
        session,
        tenant_id=tenant_id,
        budget_version_id=version.id,
        mis_line_item="Revenue",
        mis_category="Revenue",
        monthly_values=_months("1000000.00"),
    )
    await upsert_budget_line(
        session,
        tenant_id=tenant_id,
        budget_version_id=version.id,
        mis_line_item="EBITDA",
        mis_category="EBITDA",
        monthly_values=_months("250000.00"),
    )
    return version


# Version management (5)
@pytest.mark.asyncio
async def test_create_budget_version(async_session: AsyncSession, test_user: IamUser) -> None:
    version = await create_budget_version(
        async_session,
        tenant_id=test_user.tenant_id,
        fiscal_year=2025,
        version_name="Annual Budget v1",
        created_by=test_user.id,
    )
    assert version.version_number == 1
    assert version.status == "draft"


@pytest.mark.asyncio
async def test_version_number_auto_increments(async_session: AsyncSession, test_user: IamUser) -> None:
    await create_budget_version(async_session, test_user.tenant_id, 2025, "v1", test_user.id)
    second = await create_budget_version(async_session, test_user.tenant_id, 2025, "v2", test_user.id)
    assert second.version_number == 2


@pytest.mark.asyncio
async def test_copy_from_version(async_session: AsyncSession, test_user: IamUser) -> None:
    source = await create_budget_version(async_session, test_user.tenant_id, 2025, "v1", test_user.id)
    for idx in range(5):
        await upsert_budget_line(
            async_session,
            tenant_id=test_user.tenant_id,
            budget_version_id=source.id,
            mis_line_item=f"Line {idx}",
            mis_category="Revenue",
            monthly_values=_months("100.00"),
        )
    copied = await create_budget_version(
        async_session,
        tenant_id=test_user.tenant_id,
        fiscal_year=2025,
        version_name="v2",
        created_by=test_user.id,
        copy_from_version_id=source.id,
    )
    source_rows = (
        await async_session.execute(select(BudgetLineItem).where(BudgetLineItem.budget_version_id == source.id))
    ).scalars().all()
    copied_rows = (
        await async_session.execute(select(BudgetLineItem).where(BudgetLineItem.budget_version_id == copied.id))
    ).scalars().all()
    assert len(source_rows) == 5
    assert len(copied_rows) == 5
    assert {row.id for row in source_rows}.isdisjoint({row.id for row in copied_rows})


@pytest.mark.asyncio
async def test_approve_supersedes_previous(async_session: AsyncSession, test_user: IamUser) -> None:
    version_1 = await create_budget_version(async_session, test_user.tenant_id, 2025, "v1", test_user.id)
    version_2 = await create_budget_version(async_session, test_user.tenant_id, 2025, "v2", test_user.id)
    await approve_budget(async_session, test_user.tenant_id, version_1.id, test_user.id)
    await approve_budget(async_session, test_user.tenant_id, version_2.id, test_user.id)

    first = await async_session.get(BudgetVersion, version_1.id)
    second = await async_session.get(BudgetVersion, version_2.id)
    assert first.status == "superseded"
    assert second.status == "approved"
    approved_count = (
        await async_session.execute(
            select(func.count()).select_from(BudgetVersion).where(
                BudgetVersion.tenant_id == test_user.tenant_id,
                BudgetVersion.fiscal_year == 2025,
                BudgetVersion.status == "approved",
            )
        )
    ).scalar_one()
    assert approved_count == 1


@pytest.mark.asyncio
async def test_budget_unique_constraint(async_session: AsyncSession, test_user: IamUser) -> None:
    await create_budget_version(async_session, test_user.tenant_id, 2025, "v1", test_user.id)
    duplicate = BudgetVersion(
        tenant_id=test_user.tenant_id,
        fiscal_year=2025,
        version_name="dup",
        version_number=1,
        created_by=test_user.id,
    )
    async_session.add(duplicate)
    with pytest.raises(IntegrityError):
        await async_session.flush()


# Line items (6)
@pytest.mark.asyncio
async def test_upsert_budget_line_creates_record(async_session: AsyncSession, test_user: IamUser) -> None:
    version = await create_budget_version(async_session, test_user.tenant_id, 2025, "v1", test_user.id)
    line = await upsert_budget_line(
        async_session,
        tenant_id=test_user.tenant_id,
        budget_version_id=version.id,
        mis_line_item="Revenue",
        mis_category="Revenue",
        monthly_values=_months("100.00"),
    )
    assert line.id is not None


@pytest.mark.asyncio
async def test_monthly_values_must_be_12(async_session: AsyncSession, test_user: IamUser) -> None:
    version = await create_budget_version(async_session, test_user.tenant_id, 2025, "v1", test_user.id)
    with pytest.raises(ValueError):
        await upsert_budget_line(
            async_session,
            tenant_id=test_user.tenant_id,
            budget_version_id=version.id,
            mis_line_item="Revenue",
            mis_category="Revenue",
            monthly_values=[Decimal("100.00")] * 11,
        )


@pytest.mark.asyncio
async def test_annual_total_correct(async_session: AsyncSession, test_user: IamUser) -> None:
    version = await create_budget_version(async_session, test_user.tenant_id, 2025, "v1", test_user.id)
    line = await upsert_budget_line(
        async_session,
        tenant_id=test_user.tenant_id,
        budget_version_id=version.id,
        mis_line_item="Revenue",
        mis_category="Revenue",
        monthly_values=[Decimal("100.00")] * 12,
    )
    await async_session.refresh(line)
    assert line.annual_total == Decimal("1200.00")


@pytest.mark.asyncio
async def test_budget_line_is_append_only(async_session: AsyncSession, test_user: IamUser) -> None:
    version = await create_budget_version(async_session, test_user.tenant_id, 2025, "v1", test_user.id)
    line = await upsert_budget_line(
        async_session,
        tenant_id=test_user.tenant_id,
        budget_version_id=version.id,
        mis_line_item="Revenue",
        mis_category="Revenue",
        monthly_values=_months("100.00"),
    )
    await async_session.execute(text(append_only_function_sql()))
    await async_session.execute(text(drop_trigger_sql("budget_line_items")))
    await async_session.execute(text(create_trigger_sql("budget_line_items")))
    await async_session.flush()
    with pytest.raises(Exception):
        await async_session.execute(
            text("UPDATE budget_line_items SET month_01 = :month WHERE id = :id"),
            {"month": Decimal("999.00"), "id": line.id},
        )


@pytest.mark.asyncio
async def test_all_monthly_values_are_decimal(async_session: AsyncSession, test_user: IamUser) -> None:
    version = await create_budget_version(async_session, test_user.tenant_id, 2025, "v1", test_user.id)
    line = await upsert_budget_line(
        async_session,
        tenant_id=test_user.tenant_id,
        budget_version_id=version.id,
        mis_line_item="Revenue",
        mis_category="Revenue",
        monthly_values=[Decimal("100.00")] * 12,
    )
    for i in range(1, 13):
        assert isinstance(getattr(line, f"month_{i:02d}"), Decimal)


@pytest.mark.asyncio
async def test_budget_line_rls_enforced(async_session: AsyncSession, test_user: IamUser) -> None:
    version_a = await create_budget_version(async_session, test_user.tenant_id, 2025, "v1", test_user.id)
    await upsert_budget_line(
        async_session,
        tenant_id=test_user.tenant_id,
        budget_version_id=version_a.id,
        mis_line_item="Revenue",
        mis_category="Revenue",
        monthly_values=_months("100.00"),
    )
    tenant_b = uuid.uuid4()
    version_b = await create_budget_version(async_session, tenant_b, 2025, "v1", test_user.id)
    await upsert_budget_line(
        async_session,
        tenant_id=tenant_b,
        budget_version_id=version_b.id,
        mis_line_item="Revenue",
        mis_category="Revenue",
        monthly_values=_months("200.00"),
    )
    rows_a = (
        await async_session.execute(select(BudgetLineItem).where(BudgetLineItem.tenant_id == test_user.tenant_id))
    ).scalars().all()
    assert rows_a
    assert all(row.tenant_id == test_user.tenant_id for row in rows_a)


# Budget vs actual (8)
@pytest.mark.asyncio
async def test_budget_vs_actual_revenue_line(async_session: AsyncSession, test_user: IamUser, monkeypatch: pytest.MonkeyPatch) -> None:
    version = await _create_budget_with_lines(async_session, tenant_id=test_user.tenant_id, user_id=test_user.id)
    await approve_budget(async_session, test_user.tenant_id, version.id, test_user.id)

    async def _fake_actuals(*args, **kwargs):
        del args, kwargs
        return {("Revenue", 1): Decimal("950000.00")}

    from financeops.modules.budgeting import service as budget_service

    monkeypatch.setattr(budget_service, "_load_actuals_map", _fake_actuals)
    payload = await get_budget_vs_actual(async_session, test_user.tenant_id, 2025, "2025-01")
    revenue_line = next(row for row in payload["lines"] if row["mis_line_item"] == "Revenue")
    assert revenue_line["variance_amount"] == Decimal("-50000.00")
    assert revenue_line["variance_pct"] == Decimal("-5.0000")


@pytest.mark.asyncio
async def test_budget_vs_actual_ytd_aggregation(async_session: AsyncSession, test_user: IamUser, monkeypatch: pytest.MonkeyPatch) -> None:
    version = await _create_budget_with_lines(async_session, tenant_id=test_user.tenant_id, user_id=test_user.id)
    await approve_budget(async_session, test_user.tenant_id, version.id, test_user.id)

    async def _fake_actuals(*args, **kwargs):
        del args, kwargs
        return {
            ("Revenue", 1): Decimal("900000.00"),
            ("Revenue", 2): Decimal("1000000.00"),
            ("Revenue", 3): Decimal("1100000.00"),
        }

    from financeops.modules.budgeting import service as budget_service

    monkeypatch.setattr(budget_service, "_load_actuals_map", _fake_actuals)
    payload = await get_budget_vs_actual(async_session, test_user.tenant_id, 2025, "2025-03")
    revenue_line = next(row for row in payload["lines"] if row["mis_line_item"] == "Revenue")
    assert revenue_line["budget_ytd"] == Decimal("3000000.00")
    assert revenue_line["actual_ytd"] == Decimal("3000000.00")


@pytest.mark.asyncio
async def test_variance_pct_zero_when_budget_zero(async_session: AsyncSession, test_user: IamUser, monkeypatch: pytest.MonkeyPatch) -> None:
    version = await create_budget_version(async_session, test_user.tenant_id, 2025, "v1", test_user.id)
    await upsert_budget_line(
        async_session,
        tenant_id=test_user.tenant_id,
        budget_version_id=version.id,
        mis_line_item="Other Income",
        mis_category="Revenue",
        monthly_values=_months("0.00"),
    )
    await approve_budget(async_session, test_user.tenant_id, version.id, test_user.id)

    async def _fake_actuals(*args, **kwargs):
        del args, kwargs
        return {("Other Income", 1): Decimal("100.00")}

    from financeops.modules.budgeting import service as budget_service

    monkeypatch.setattr(budget_service, "_load_actuals_map", _fake_actuals)
    payload = await get_budget_vs_actual(async_session, test_user.tenant_id, 2025, "2025-01")
    row = payload["lines"][0]
    assert row["variance_pct"] == Decimal("0")


@pytest.mark.asyncio
async def test_all_variance_values_are_decimal(async_session: AsyncSession, test_user: IamUser) -> None:
    version = await _create_budget_with_lines(async_session, tenant_id=test_user.tenant_id, user_id=test_user.id)
    await approve_budget(async_session, test_user.tenant_id, version.id, test_user.id)
    payload = await get_budget_vs_actual(async_session, test_user.tenant_id, 2025, "2025-01")
    for row in payload["lines"]:
        assert isinstance(row["variance_amount"], Decimal)
        assert isinstance(row["variance_pct"], Decimal)


@pytest.mark.asyncio
async def test_on_budget_true_when_within_5pct(async_session: AsyncSession, test_user: IamUser, monkeypatch: pytest.MonkeyPatch) -> None:
    version = await _create_budget_with_lines(async_session, tenant_id=test_user.tenant_id, user_id=test_user.id)
    await approve_budget(async_session, test_user.tenant_id, version.id, test_user.id)

    async def _fake_actuals(*args, **kwargs):
        del args, kwargs
        return {("Revenue", 1): Decimal("960000.00")}

    from financeops.modules.budgeting import service as budget_service

    monkeypatch.setattr(budget_service, "_load_actuals_map", _fake_actuals)
    payload = await get_budget_vs_actual(async_session, test_user.tenant_id, 2025, "2025-01")
    assert payload["summary"]["on_budget"] is True


@pytest.mark.asyncio
async def test_on_budget_false_when_over_5pct(async_session: AsyncSession, test_user: IamUser, monkeypatch: pytest.MonkeyPatch) -> None:
    version = await _create_budget_with_lines(async_session, tenant_id=test_user.tenant_id, user_id=test_user.id)
    await approve_budget(async_session, test_user.tenant_id, version.id, test_user.id)

    async def _fake_actuals(*args, **kwargs):
        del args, kwargs
        return {("Revenue", 1): Decimal("800000.00")}

    from financeops.modules.budgeting import service as budget_service

    monkeypatch.setattr(budget_service, "_load_actuals_map", _fake_actuals)
    payload = await get_budget_vs_actual(async_session, test_user.tenant_id, 2025, "2025-01")
    assert payload["summary"]["on_budget"] is False


@pytest.mark.asyncio
async def test_budget_vs_actual_uses_approved_version(async_session: AsyncSession, test_user: IamUser, monkeypatch: pytest.MonkeyPatch) -> None:
    draft = await create_budget_version(async_session, test_user.tenant_id, 2025, "draft", test_user.id)
    approved = await create_budget_version(async_session, test_user.tenant_id, 2025, "approved", test_user.id)
    await upsert_budget_line(async_session, test_user.tenant_id, draft.id, "Revenue", "Revenue", _months("2000000.00"))
    await upsert_budget_line(async_session, test_user.tenant_id, approved.id, "Revenue", "Revenue", _months("1000000.00"))
    await approve_budget(async_session, test_user.tenant_id, approved.id, test_user.id)

    async def _fake_actuals(*args, **kwargs):
        del args, kwargs
        return {("Revenue", 1): Decimal("1000000.00")}

    from financeops.modules.budgeting import service as budget_service

    monkeypatch.setattr(budget_service, "_load_actuals_map", _fake_actuals)
    payload = await get_budget_vs_actual(async_session, test_user.tenant_id, 2025, "2025-01")
    assert payload["version_id"] == str(approved.id)


@pytest.mark.asyncio
async def test_budget_vs_actual_multi_entity(async_session: AsyncSession, test_user: IamUser, monkeypatch: pytest.MonkeyPatch) -> None:
    version = await create_budget_version(async_session, test_user.tenant_id, 2025, "v1", test_user.id)
    entity_a = uuid.uuid4()
    entity_b = uuid.uuid4()
    await upsert_budget_line(
        async_session,
        tenant_id=test_user.tenant_id,
        budget_version_id=version.id,
        mis_line_item="Revenue",
        mis_category="Revenue",
        monthly_values=_months("1000000.00"),
        entity_id=entity_a,
    )
    await upsert_budget_line(
        async_session,
        tenant_id=test_user.tenant_id,
        budget_version_id=version.id,
        mis_line_item="Revenue",
        mis_category="Revenue",
        monthly_values=_months("500000.00"),
        entity_id=entity_b,
    )
    await approve_budget(async_session, test_user.tenant_id, version.id, test_user.id)

    async def _fake_actuals(*args, **kwargs):
        del args, kwargs
        return {("Revenue", 1): Decimal("900000.00")}

    from financeops.modules.budgeting import service as budget_service

    monkeypatch.setattr(budget_service, "_load_actuals_map", _fake_actuals)
    payload = await get_budget_vs_actual(
        async_session,
        test_user.tenant_id,
        2025,
        "2025-01",
        entity_id=entity_a,
    )
    assert len(payload["lines"]) == 1


# API (6)
@pytest.mark.asyncio
async def test_create_version_via_api(async_client: AsyncClient, test_access_token: str) -> None:
    response = await async_client.post(
        "/api/v1/budget/versions",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={"fiscal_year": 2025, "version_name": "Annual Budget v1"},
    )
    assert response.status_code == 201
    payload = response.json()["data"]
    assert payload["status"] == "draft"


@pytest.mark.asyncio
async def test_add_line_items_via_api(async_client: AsyncClient, test_access_token: str) -> None:
    create_response = await async_client.post(
        "/api/v1/budget/versions",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={"fiscal_year": 2025, "version_name": "Annual Budget v1"},
    )
    version_id = create_response.json()["data"]["id"]
    add_line_response = await async_client.post(
        f"/api/v1/budget/versions/{version_id}/lines",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "mis_line_item": "Revenue",
            "mis_category": "Revenue",
            "monthly_values": ["100.00"] * 12,
        },
    )
    assert add_line_response.status_code == 201
    assert add_line_response.json()["data"]["mis_line_item"] == "Revenue"


@pytest.mark.asyncio
async def test_approve_via_api_requires_finance_leader(async_client: AsyncClient, async_session: AsyncSession, test_user: IamUser) -> None:
    version = await create_budget_version(async_session, test_user.tenant_id, 2025, "v1", test_user.id)
    employee = IamUser(
        tenant_id=test_user.tenant_id,
        email=f"budget-emp-{uuid.uuid4().hex[:6]}@example.com",
        hashed_password=hash_password("TestPass123!"),
        full_name="Budget Emp",
        role=UserRole.employee,
        is_active=True,
        mfa_enabled=False,
    )
    async_session.add(employee)
    await async_session.flush()
    employee_token = create_access_token(employee.id, employee.tenant_id, employee.role.value)

    response = await async_client.post(
        f"/api/v1/budget/versions/{version.id}/approve",
        headers={"Authorization": f"Bearer {employee_token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_vs_actual_endpoint_returns_structure(async_client: AsyncClient, async_session: AsyncSession, test_user: IamUser, test_access_token: str) -> None:
    version = await _create_budget_with_lines(async_session, tenant_id=test_user.tenant_id, user_id=test_user.id)
    await approve_budget(async_session, test_user.tenant_id, version.id, test_user.id)
    response = await async_client.get(
        "/api/v1/budget/vs-actual?fiscal_year=2025&period=2025-03",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert {"fiscal_year", "period_through", "lines", "summary"}.issubset(payload.keys())


@pytest.mark.asyncio
async def test_vs_actual_export_returns_xlsx(async_client: AsyncClient, async_session: AsyncSession, test_user: IamUser, test_access_token: str) -> None:
    version = await _create_budget_with_lines(async_session, tenant_id=test_user.tenant_id, user_id=test_user.id)
    await approve_budget(async_session, test_user.tenant_id, version.id, test_user.id)
    response = await async_client.get(
        "/api/v1/budget/vs-actual/export?fiscal_year=2025&period=2025-03",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@pytest.mark.asyncio
async def test_tenant_isolation_budget_versions(async_client: AsyncClient, async_session: AsyncSession, test_user: IamUser, test_access_token: str) -> None:
    await create_budget_version(async_session, test_user.tenant_id, 2025, "tenant-a", test_user.id)
    tenant_b = uuid.uuid4()
    await create_budget_version(async_session, tenant_b, 2025, "tenant-b", test_user.id)

    response = await async_client.get(
        "/api/v1/budget/versions?fiscal_year=2025",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 200
    rows = response.json()["data"]["data"]
    assert rows
    assert all(row["tenant_id"] == str(test_user.tenant_id) for row in rows)
