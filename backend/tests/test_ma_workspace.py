from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql
from financeops.db.models.credits import CreditTransaction
from financeops.db.models.users import IamUser
from financeops.modules.ma_workspace.models import MADDItem, MADocument, MAValuation, MAWorkspace, MAWorkspaceMember
from financeops.modules.ma_workspace.service import (
    compute_comparable_companies_valuation,
    compute_dcf_valuation,
    create_dd_item,
    create_workspace,
    get_dd_tracker,
    list_workspace_documents,
    register_document,
    update_dd_item,
)
from financeops.services.credit_service import add_credits


async def _fund(async_session: AsyncSession, tenant_id: uuid.UUID, amount: str = "10000.00") -> None:
    await add_credits(async_session, tenant_id, Decimal(amount), "test_ma_fund")
    await async_session.flush()


async def _create_workspace(async_session: AsyncSession, user: IamUser) -> MAWorkspace:
    return await create_workspace(
        async_session,
        tenant_id=user.tenant_id,
        workspace_name="Deal Room",
        deal_codename="Project Falcon",
        deal_type="acquisition",
        target_company_name="Target Co",
        created_by=user.id,
        indicative_deal_value=Decimal("500000000.00"),
    )


def _dcf_assumptions(**overrides: str) -> dict[str, str]:
    values = {
        "ebitda_base": "1000000.00",
        "revenue_base": "4000000.00",
        "revenue_growth_year_1": "0.05",
        "revenue_growth_year_2": "0.05",
        "revenue_growth_year_3": "0.05",
        "revenue_growth_year_4": "0.05",
        "revenue_growth_year_5": "0.05",
        "ebitda_margin_year_1": "0.20",
        "ebitda_margin_year_2": "0.20",
        "ebitda_margin_year_3": "0.20",
        "ebitda_margin_year_4": "0.20",
        "ebitda_margin_year_5": "0.20",
        "terminal_growth_rate": "0.03",
        "discount_rate": "0.12",
        "tax_rate": "0.25",
        "capex_pct_revenue": "0.04",
        "nwc_change_pct_revenue": "0.02",
        "net_debt": "200.00",
    }
    values.update(overrides)
    return values


# Workspace lifecycle (4)
@pytest.mark.asyncio
async def test_create_workspace_charges_credits(async_session: AsyncSession, test_user: IamUser) -> None:
    await _fund(async_session, test_user.tenant_id)
    workspace = await _create_workspace(async_session, test_user)
    tx = (
        await async_session.execute(
            select(CreditTransaction).where(
                CreditTransaction.tenant_id == test_user.tenant_id,
                CreditTransaction.task_type == f"ma:{workspace.id}:monthly",
            )
        )
    ).scalar_one_or_none()
    assert workspace.credit_cost_monthly == 1000
    assert workspace.credit_charged_at is not None
    assert tx is not None


@pytest.mark.asyncio
async def test_creator_added_as_lead_advisor(async_session: AsyncSession, test_user: IamUser) -> None:
    await _fund(async_session, test_user.tenant_id)
    workspace = await _create_workspace(async_session, test_user)
    member = (
        await async_session.execute(
            select(MAWorkspaceMember).where(
                MAWorkspaceMember.workspace_id == workspace.id,
                MAWorkspaceMember.user_id == test_user.id,
                MAWorkspaceMember.tenant_id == test_user.tenant_id,
            )
        )
    ).scalar_one()
    assert member.member_role == "lead_advisor"


@pytest.mark.asyncio
async def test_dd_checklist_seeded_on_creation(async_session: AsyncSession, test_user: IamUser) -> None:
    await _fund(async_session, test_user.tenant_id)
    workspace = await _create_workspace(async_session, test_user)
    items = (
        await async_session.execute(
            select(MADDItem).where(
                MADDItem.workspace_id == workspace.id,
                MADDItem.tenant_id == test_user.tenant_id,
            )
        )
    ).scalars().all()
    categories = {row.category for row in items}
    assert len(items) >= 12
    assert {"financial", "legal", "tax"}.issubset(categories)


@pytest.mark.asyncio
async def test_workspace_rls_isolation(async_session: AsyncSession, test_user: IamUser) -> None:
    await _fund(async_session, test_user.tenant_id)
    workspace_a = await _create_workspace(async_session, test_user)
    tenant_b = uuid.uuid4()
    await _fund(async_session, tenant_b)
    workspace_b = await create_workspace(
        async_session,
        tenant_id=tenant_b,
        workspace_name="B",
        deal_codename="B",
        deal_type="acquisition",
        target_company_name="B",
        created_by=test_user.id,
    )
    rows = (
        await async_session.execute(
            select(MAWorkspace).where(MAWorkspace.tenant_id == test_user.tenant_id)
        )
    ).scalars().all()
    ids = {row.id for row in rows}
    assert workspace_a.id in ids
    assert workspace_b.id not in ids


# DCF valuation (7)
@pytest.mark.asyncio
async def test_dcf_enterprise_value_is_decimal(async_session: AsyncSession, test_user: IamUser) -> None:
    await _fund(async_session, test_user.tenant_id)
    workspace = await _create_workspace(async_session, test_user)
    valuation = await compute_dcf_valuation(
        async_session,
        workspace_id=workspace.id,
        tenant_id=test_user.tenant_id,
        computed_by=test_user.id,
        valuation_name="Base DCF",
        assumptions=_dcf_assumptions(),
    )
    assert isinstance(valuation.enterprise_value, Decimal)


@pytest.mark.asyncio
async def test_dcf_equity_value_correct(async_session: AsyncSession, test_user: IamUser) -> None:
    await _fund(async_session, test_user.tenant_id)
    workspace = await _create_workspace(async_session, test_user)
    valuation = await compute_dcf_valuation(
        async_session,
        workspace_id=workspace.id,
        tenant_id=test_user.tenant_id,
        computed_by=test_user.id,
        valuation_name="DCF EV-EQ bridge",
        assumptions=_dcf_assumptions(net_debt="200.00"),
    )
    assert valuation.equity_value == valuation.enterprise_value - Decimal("200.00")


@pytest.mark.asyncio
async def test_dcf_terminal_value_computed(async_session: AsyncSession, test_user: IamUser) -> None:
    await _fund(async_session, test_user.tenant_id)
    workspace = await _create_workspace(async_session, test_user)
    valuation = await compute_dcf_valuation(
        async_session,
        workspace_id=workspace.id,
        tenant_id=test_user.tenant_id,
        computed_by=test_user.id,
        valuation_name="DCF Terminal",
        assumptions=_dcf_assumptions(terminal_growth_rate="0.03", discount_rate="0.12"),
    )
    assert valuation.enterprise_value > Decimal("0")


@pytest.mark.asyncio
async def test_dcf_zero_terminal_growth(async_session: AsyncSession, test_user: IamUser) -> None:
    await _fund(async_session, test_user.tenant_id)
    workspace = await _create_workspace(async_session, test_user)
    valuation = await compute_dcf_valuation(
        async_session,
        workspace_id=workspace.id,
        tenant_id=test_user.tenant_id,
        computed_by=test_user.id,
        valuation_name="DCF Zero TG",
        assumptions=_dcf_assumptions(terminal_growth_rate="0.00"),
    )
    assert valuation.enterprise_value > Decimal("0")


@pytest.mark.asyncio
async def test_dcf_valuation_range_is_10pct_band(async_session: AsyncSession, test_user: IamUser) -> None:
    await _fund(async_session, test_user.tenant_id)
    workspace = await _create_workspace(async_session, test_user)
    valuation = await compute_dcf_valuation(
        async_session,
        workspace_id=workspace.id,
        tenant_id=test_user.tenant_id,
        computed_by=test_user.id,
        valuation_name="DCF Range",
        assumptions=_dcf_assumptions(),
    )
    assert valuation.valuation_range_high == (valuation.enterprise_value * Decimal("1.10")).quantize(Decimal("0.01"))
    assert valuation.valuation_range_low == (valuation.enterprise_value * Decimal("0.90")).quantize(Decimal("0.01"))


@pytest.mark.asyncio
async def test_ma_valuations_append_only(async_session: AsyncSession, test_user: IamUser) -> None:
    await _fund(async_session, test_user.tenant_id)
    workspace = await _create_workspace(async_session, test_user)
    valuation = await compute_dcf_valuation(
        async_session,
        workspace_id=workspace.id,
        tenant_id=test_user.tenant_id,
        computed_by=test_user.id,
        valuation_name="Append Only",
        assumptions=_dcf_assumptions(),
    )
    await async_session.execute(text(append_only_function_sql()))
    await async_session.execute(text(drop_trigger_sql("ma_valuations")))
    await async_session.execute(text(create_trigger_sql("ma_valuations")))
    await async_session.flush()
    with pytest.raises(Exception):
        await async_session.execute(
            text("UPDATE ma_valuations SET enterprise_value = :value WHERE id = :id"),
            {"value": Decimal("1.00"), "id": valuation.id},
        )


@pytest.mark.asyncio
async def test_all_dcf_outputs_decimal(async_session: AsyncSession, test_user: IamUser) -> None:
    await _fund(async_session, test_user.tenant_id)
    workspace = await _create_workspace(async_session, test_user)
    valuation = await compute_dcf_valuation(
        async_session,
        workspace_id=workspace.id,
        tenant_id=test_user.tenant_id,
        computed_by=test_user.id,
        valuation_name="DCF Decimal",
        assumptions=_dcf_assumptions(),
    )
    assert isinstance(valuation.enterprise_value, Decimal)
    assert isinstance(valuation.equity_value, Decimal)
    assert isinstance(valuation.ev_ebitda_multiple, Decimal)
    assert isinstance(valuation.ev_revenue_multiple, Decimal)


# Comparable companies (3)
@pytest.mark.asyncio
async def test_comparable_companies_blended_ev(async_session: AsyncSession, test_user: IamUser) -> None:
    await _fund(async_session, test_user.tenant_id)
    workspace = await _create_workspace(async_session, test_user)
    valuation = await compute_comparable_companies_valuation(
        async_session,
        workspace_id=workspace.id,
        tenant_id=test_user.tenant_id,
        computed_by=test_user.id,
        valuation_name="Comps",
        assumptions={
            "ltm_ebitda": "100",
            "ltm_revenue": "500",
            "peer_ev_ebitda_median": "10",
            "peer_ev_revenue_median": "2",
            "control_premium_pct": "0.25",
            "net_debt": "0",
        },
    )
    assert valuation.enterprise_value == Decimal("1250.00")


@pytest.mark.asyncio
async def test_control_premium_applied(async_session: AsyncSession, test_user: IamUser) -> None:
    await _fund(async_session, test_user.tenant_id)
    workspace = await _create_workspace(async_session, test_user)
    valuation = await compute_comparable_companies_valuation(
        async_session,
        workspace_id=workspace.id,
        tenant_id=test_user.tenant_id,
        computed_by=test_user.id,
        valuation_name="Comps Premium",
        assumptions={
            "ltm_ebitda": "100",
            "ltm_revenue": "500",
            "peer_ev_ebitda_median": "10",
            "peer_ev_revenue_median": "2",
            "control_premium_pct": "0.25",
            "net_debt": "0",
        },
    )
    blended_ev = Decimal("1000.00")
    assert valuation.enterprise_value > blended_ev


@pytest.mark.asyncio
async def test_comparable_ev_ebitda_multiple_stored(async_session: AsyncSession, test_user: IamUser) -> None:
    await _fund(async_session, test_user.tenant_id)
    workspace = await _create_workspace(async_session, test_user)
    valuation = await compute_comparable_companies_valuation(
        async_session,
        workspace_id=workspace.id,
        tenant_id=test_user.tenant_id,
        computed_by=test_user.id,
        valuation_name="Comps Multiple",
        assumptions={
            "ltm_ebitda": "100",
            "ltm_revenue": "500",
            "peer_ev_ebitda_median": "11.25",
            "peer_ev_revenue_median": "2",
            "control_premium_pct": "0.10",
            "net_debt": "0",
        },
    )
    assert valuation.ev_ebitda_multiple == Decimal("11.2500")


# DD tracker (5)
@pytest.mark.asyncio
async def test_dd_tracker_completion_pct(async_session: AsyncSession, test_user: IamUser) -> None:
    await _fund(async_session, test_user.tenant_id)
    workspace = await _create_workspace(async_session, test_user)
    items = (
        await async_session.execute(
            select(MADDItem).where(
                MADDItem.workspace_id == workspace.id,
                MADDItem.tenant_id == test_user.tenant_id,
            )
        )
    ).scalars().all()
    completed_target = len(items) // 2
    for row in items[:completed_target]:
        row.status = "completed"
    await async_session.flush()
    tracker = await get_dd_tracker(async_session, workspace.id, test_user.tenant_id)
    assert tracker["completion_pct"] == Decimal("50.00")


@pytest.mark.asyncio
async def test_flagged_items_in_tracker(async_session: AsyncSession, test_user: IamUser) -> None:
    await _fund(async_session, test_user.tenant_id)
    workspace = await _create_workspace(async_session, test_user)
    item = await create_dd_item(
        async_session,
        workspace_id=workspace.id,
        tenant_id=test_user.tenant_id,
        category="financial",
        item_name="Flagged Item",
        priority="high",
    )
    item.status = "flagged"
    await async_session.flush()
    tracker = await get_dd_tracker(async_session, workspace.id, test_user.tenant_id)
    assert any(row.id == item.id for row in tracker["flagged_items"])


@pytest.mark.asyncio
async def test_overdue_items_detected(async_session: AsyncSession, test_user: IamUser) -> None:
    await _fund(async_session, test_user.tenant_id)
    workspace = await _create_workspace(async_session, test_user)
    item = await create_dd_item(
        async_session,
        workspace_id=workspace.id,
        tenant_id=test_user.tenant_id,
        category="legal",
        item_name="Overdue Item",
        due_date=(datetime.now(UTC) - timedelta(days=1)).date(),
        priority="medium",
    )
    await async_session.flush()
    tracker = await get_dd_tracker(async_session, workspace.id, test_user.tenant_id)
    assert any(row.id == item.id for row in tracker["overdue_items"])


@pytest.mark.asyncio
async def test_dd_item_status_update(async_session: AsyncSession, test_user: IamUser) -> None:
    await _fund(async_session, test_user.tenant_id)
    workspace = await _create_workspace(async_session, test_user)
    item = await create_dd_item(
        async_session,
        workspace_id=workspace.id,
        tenant_id=test_user.tenant_id,
        category="tax",
        item_name="Tax Memo",
        priority="low",
    )
    updated = await update_dd_item(
        async_session,
        workspace_id=workspace.id,
        item_id=item.id,
        tenant_id=test_user.tenant_id,
        status="completed",
    )
    assert updated.status == "completed"


@pytest.mark.asyncio
async def test_dd_items_by_category(async_session: AsyncSession, test_user: IamUser) -> None:
    await _fund(async_session, test_user.tenant_id)
    workspace = await _create_workspace(async_session, test_user)
    tracker = await get_dd_tracker(async_session, workspace.id, test_user.tenant_id)
    assert {"financial", "legal", "tax"}.issubset(tracker["by_category"].keys())


# Documents (3)
@pytest.mark.asyncio
async def test_register_document_creates_record(async_session: AsyncSession, test_user: IamUser) -> None:
    await _fund(async_session, test_user.tenant_id)
    workspace = await _create_workspace(async_session, test_user)
    row = await register_document(
        async_session,
        workspace_id=workspace.id,
        tenant_id=test_user.tenant_id,
        document_name="NDA v1",
        document_type="nda",
        file_url="https://example.com/nda.pdf",
        file_size_bytes=12345,
        is_confidential=True,
        uploaded_by=test_user.id,
    )
    assert row.id is not None


@pytest.mark.asyncio
async def test_ma_documents_append_only(async_session: AsyncSession, test_user: IamUser) -> None:
    await _fund(async_session, test_user.tenant_id)
    workspace = await _create_workspace(async_session, test_user)
    row = await register_document(
        async_session,
        workspace_id=workspace.id,
        tenant_id=test_user.tenant_id,
        document_name="LOI",
        document_type="loi",
        file_url="https://example.com/loi.pdf",
        file_size_bytes=200,
        is_confidential=True,
        uploaded_by=test_user.id,
    )
    await async_session.execute(text(append_only_function_sql()))
    await async_session.execute(text(drop_trigger_sql("ma_documents")))
    await async_session.execute(text(create_trigger_sql("ma_documents")))
    await async_session.flush()
    with pytest.raises(Exception):
        await async_session.execute(
            text("UPDATE ma_documents SET document_name = :name WHERE id = :id"),
            {"name": "mutated", "id": row.id},
        )


@pytest.mark.asyncio
async def test_document_list_by_type_filter(async_session: AsyncSession, test_user: IamUser) -> None:
    await _fund(async_session, test_user.tenant_id)
    workspace = await _create_workspace(async_session, test_user)
    await register_document(
        async_session,
        workspace_id=workspace.id,
        tenant_id=test_user.tenant_id,
        document_name="NDA",
        document_type="nda",
        file_url=None,
        file_size_bytes=None,
        is_confidential=True,
        uploaded_by=test_user.id,
    )
    await register_document(
        async_session,
        workspace_id=workspace.id,
        tenant_id=test_user.tenant_id,
        document_name="SPA",
        document_type="spa",
        file_url=None,
        file_size_bytes=None,
        is_confidential=True,
        uploaded_by=test_user.id,
    )
    rows, _ = await list_workspace_documents(
        async_session,
        workspace_id=workspace.id,
        tenant_id=test_user.tenant_id,
        document_type="nda",
        limit=20,
        offset=0,
    )
    assert len(rows) == 1
    assert rows[0].document_type == "nda"


# API (3)
@pytest.mark.asyncio
async def test_create_workspace_via_api(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_user: IamUser,
    test_access_token: str,
) -> None:
    await _fund(async_session, test_user.tenant_id)
    response = await async_client.post(
        "/api/v1/advisory/ma/workspaces",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "workspace_name": "API Workspace",
            "deal_codename": "Project Atlas",
            "deal_type": "acquisition",
            "target_company_name": "Atlas Co",
            "indicative_deal_value": "1000000.00",
        },
    )
    assert response.status_code == 201
    assert response.json()["data"]["deal_status"] == "active"


@pytest.mark.asyncio
async def test_compute_dcf_via_api(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_user: IamUser,
    test_access_token: str,
) -> None:
    await _fund(async_session, test_user.tenant_id)
    workspace = await _create_workspace(async_session, test_user)
    response = await async_client.post(
        f"/api/v1/advisory/ma/workspaces/{workspace.id}/valuations",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "valuation_name": "API DCF",
            "valuation_method": "dcf",
            "assumptions": _dcf_assumptions(),
        },
    )
    assert response.status_code == 201
    assert Decimal(response.json()["data"]["enterprise_value"]) > Decimal("0")


@pytest.mark.asyncio
async def test_dd_update_via_api(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_user: IamUser,
    test_access_token: str,
) -> None:
    await _fund(async_session, test_user.tenant_id)
    workspace = await _create_workspace(async_session, test_user)
    item = await create_dd_item(
        async_session,
        workspace_id=workspace.id,
        tenant_id=test_user.tenant_id,
        category="financial",
        item_name="API DD Item",
        priority="medium",
    )
    response = await async_client.patch(
        f"/api/v1/advisory/ma/workspaces/{workspace.id}/dd/{item.id}",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={"status": "completed", "response_notes": "done"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "completed"
