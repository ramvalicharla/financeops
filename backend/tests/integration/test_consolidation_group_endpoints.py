from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.reconciliation import GlEntry
from financeops.modules.org_setup.models import OrgEntity, OrgGroup, OrgOwnership
from financeops.platform.db.models.entities import CpEntity
from financeops.services.audit_writer import AuditWriter


async def _insert_gl_entry(
    session: AsyncSession,
    *,
    tenant_id,
    entity_id,
    entity_name: str,
    account_code: str,
    account_name: str,
    debit: str,
    credit: str,
    uploaded_by,
) -> None:
    await AuditWriter.insert_financial_record(
        session,
        model_class=GlEntry,
        tenant_id=tenant_id,
        record_data={
            "entity_id": str(entity_id),
            "account_code": account_code,
            "debit": debit,
            "credit": credit,
        },
        values={
            "entity_id": entity_id,
            "period_year": 2026,
            "period_month": 3,
            "entity_name": entity_name,
            "account_code": account_code,
            "account_name": account_name,
            "debit_amount": Decimal(debit),
            "credit_amount": Decimal(credit),
            "description": "consolidation test",
            "source_ref": "test-consolidation",
            "currency": "INR",
            "uploaded_by": uploaded_by,
        },
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_group_consolidation_endpoints(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_tenant,
    test_user,
    test_access_token: str,
) -> None:
    org_result = await async_session.execute(
        select(CpEntity.organisation_id).where(CpEntity.tenant_id == test_tenant.id).limit(1)
    )
    organisation_id = org_result.scalar_one()

    parent_cp = (
        await async_session.execute(
            select(CpEntity).where(CpEntity.tenant_id == test_tenant.id).limit(1)
        )
    ).scalar_one()
    child_cp = await AuditWriter.insert_financial_record(
        async_session,
        model_class=CpEntity,
        tenant_id=test_tenant.id,
        record_data={
            "entity_code": "ENT_CHILD",
            "entity_name": "Child Entity",
            "organisation_id": str(organisation_id),
        },
        values={
            "entity_code": "ENT_CHILD",
            "entity_name": "Child Entity",
            "organisation_id": organisation_id,
            "group_id": None,
            "base_currency": "INR",
            "country_code": "IN",
            "status": "active",
            "deactivated_at": None,
            "correlation_id": "test-child-entity",
        },
    )

    group = OrgGroup(
        tenant_id=test_tenant.id,
        group_name="Test Group",
        country_of_incorp="India",
        country_code="IN",
        functional_currency="INR",
        reporting_currency="INR",
        logo_url=None,
        website=None,
    )
    async_session.add(group)
    await async_session.flush()

    parent_org_entity = OrgEntity(
        tenant_id=test_tenant.id,
        org_group_id=group.id,
        cp_entity_id=parent_cp.id,
        legal_name="Parent Legal",
        display_name="Parent",
        entity_type="HOLDING_COMPANY",
        country_code="IN",
        state_code=None,
        functional_currency="INR",
        reporting_currency="INR",
        fiscal_year_start=4,
        applicable_gaap="INDAS",
        industry_template_id=None,
        incorporation_number=None,
        pan=None,
        tan=None,
        cin=None,
        gstin=None,
        lei=None,
        tax_jurisdiction=None,
        tax_rate=None,
        is_active=True,
    )
    child_org_entity = OrgEntity(
        tenant_id=test_tenant.id,
        org_group_id=group.id,
        cp_entity_id=child_cp.id,
        legal_name="Child Legal",
        display_name="Child",
        entity_type="WHOLLY_OWNED_SUBSIDIARY",
        country_code="IN",
        state_code=None,
        functional_currency="INR",
        reporting_currency="INR",
        fiscal_year_start=4,
        applicable_gaap="INDAS",
        industry_template_id=None,
        incorporation_number=None,
        pan=None,
        tan=None,
        cin=None,
        gstin=None,
        lei=None,
        tax_jurisdiction=None,
        tax_rate=None,
        is_active=True,
    )
    async_session.add(parent_org_entity)
    async_session.add(child_org_entity)
    await async_session.flush()

    ownership = OrgOwnership(
        tenant_id=test_tenant.id,
        parent_entity_id=parent_org_entity.id,
        child_entity_id=child_org_entity.id,
        ownership_pct=Decimal("80.0000"),
        consolidation_method="FULL_CONSOLIDATION",
        effective_from=date(2020, 1, 1),
        effective_to=None,
        notes=None,
    )
    async_session.add(ownership)
    await async_session.flush()

    await _insert_gl_entry(
        async_session,
        tenant_id=test_tenant.id,
        entity_id=parent_cp.id,
        entity_name="Parent Entity",
        account_code="A100",
        account_name="Current Asset - Cash",
        debit="1000",
        credit="0",
        uploaded_by=test_user.id,
    )
    await _insert_gl_entry(
        async_session,
        tenant_id=test_tenant.id,
        entity_id=parent_cp.id,
        entity_name="Parent Entity",
        account_code="A200",
        account_name="Asset - Investment in Subsidiary",
        debit="500",
        credit="0",
        uploaded_by=test_user.id,
    )
    await _insert_gl_entry(
        async_session,
        tenant_id=test_tenant.id,
        entity_id=parent_cp.id,
        entity_name="Parent Entity",
        account_code="A300",
        account_name="Current Asset - Intercompany Receivable",
        debit="200",
        credit="0",
        uploaded_by=test_user.id,
    )
    await _insert_gl_entry(
        async_session,
        tenant_id=test_tenant.id,
        entity_id=parent_cp.id,
        entity_name="Parent Entity",
        account_code="R100",
        account_name="Intercompany Revenue",
        debit="0",
        credit="300",
        uploaded_by=test_user.id,
    )
    await _insert_gl_entry(
        async_session,
        tenant_id=test_tenant.id,
        entity_id=parent_cp.id,
        entity_name="Parent Entity",
        account_code="L100",
        account_name="Current Liability - Intercompany Payable",
        debit="0",
        credit="1400",
        uploaded_by=test_user.id,
    )

    await _insert_gl_entry(
        async_session,
        tenant_id=test_tenant.id,
        entity_id=child_cp.id,
        entity_name="Child Entity",
        account_code="A100",
        account_name="Current Asset - Cash",
        debit="1000",
        credit="0",
        uploaded_by=test_user.id,
    )
    await _insert_gl_entry(
        async_session,
        tenant_id=test_tenant.id,
        entity_id=child_cp.id,
        entity_name="Child Entity",
        account_code="X100",
        account_name="Intercompany Expense",
        debit="300",
        credit="0",
        uploaded_by=test_user.id,
    )
    await _insert_gl_entry(
        async_session,
        tenant_id=test_tenant.id,
        entity_id=child_cp.id,
        entity_name="Child Entity",
        account_code="E100",
        account_name="Equity - Share Capital",
        debit="0",
        credit="400",
        uploaded_by=test_user.id,
    )
    await _insert_gl_entry(
        async_session,
        tenant_id=test_tenant.id,
        entity_id=child_cp.id,
        entity_name="Child Entity",
        account_code="L100",
        account_name="Current Liability - Intercompany Payable",
        debit="0",
        credit="900",
        uploaded_by=test_user.id,
    )

    summary_response = await async_client.get(
        f"/api/v1/consolidation/summary?org_group_id={group.id}&as_of_date=2026-03-31",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert summary_response.status_code == 200
    summary_data = summary_response.json()["data"]
    assert summary_data["summary"]["entity_count"] == 2
    assert summary_data["statements"]["trial_balance"]["is_balanced"] is True

    run_response = await async_client.post(
        "/api/v1/consolidation/run",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "org_group_id": str(group.id),
            "as_of_date": "2026-03-31",
        },
    )
    assert run_response.status_code == 202
    run_payload = run_response.json()["data"]
    run_id = run_payload["run_id"]

    details_response = await async_client.get(
        f"/api/v1/consolidation/runs/{run_id}",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert details_response.status_code == 200
    assert details_response.json()["data"]["status"] == "completed"

    statements_response = await async_client.get(
        f"/api/v1/consolidation/runs/{run_id}/statements",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert statements_response.status_code == 200
    statements_data = statements_response.json()["data"]
    assert statements_data["statements"]["trial_balance"]["is_balanced"] is True
    assert len(statements_data["elimination_summary"]) >= 1
