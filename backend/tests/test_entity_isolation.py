from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.security import create_access_token, hash_password
from financeops.db.models.tenants import IamTenant, TenantStatus, TenantType
from financeops.db.models.users import IamUser, UserRole
from financeops.platform.services.tenancy.entity_access import assert_entity_access
from financeops.utils.chain_hash import GENESIS_HASH, compute_chain_hash
from tests.integration.entitlement_helpers import grant_boolean_entitlement


def _auth_headers(user: IamUser) -> dict[str, str]:
    token = create_access_token(user.id, user.tenant_id, user.role.value)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
async def _grant_entity_isolation_entitlements(async_session: AsyncSession, test_user: IamUser) -> None:
    for feature_name in ("bank_reconciliation", "gst"):
        await grant_boolean_entitlement(
            async_session,
            tenant_id=test_user.tenant_id,
            feature_name=feature_name,
            actor_user_id=test_user.id,
        )


async def _create_entity(async_client, user: IamUser, *, code: str, name: str) -> str:
    org_resp = await async_client.post(
        "/api/v1/platform/org/organisations",
        headers=_auth_headers(user),
        json={
            "organisation_code": f"ORG-{code}",
            "organisation_name": f"Org {name}",
            "parent_organisation_id": None,
        },
    )
    assert org_resp.status_code == 200
    organisation_id = org_resp.json()["data"]["id"]
    entity_resp = await async_client.post(
        "/api/v1/platform/org/entities",
        headers=_auth_headers(user),
        json={
            "entity_code": code,
            "entity_name": name,
            "organisation_id": organisation_id,
            "group_id": None,
            "base_currency": "INR",
            "country_code": "IN",
        },
    )
    assert entity_resp.status_code == 200
    return str(entity_resp.json()["data"]["id"])


async def _create_scoped_finance_team_user(
    async_client,
    async_session: AsyncSession,
    owner_user: IamUser,
    *,
    entity_id: str,
) -> IamUser:
    scoped_user = IamUser(
        tenant_id=owner_user.tenant_id,
        email=f"scoped-{uuid.uuid4()}@example.com",
        hashed_password=hash_password("TestPass123!"),
        full_name="Scoped Finance Team",
        role=UserRole.finance_team,
        is_active=True,
    )
    async_session.add(scoped_user)
    await async_session.flush()

    assign_resp = await async_client.post(
        "/api/v1/platform/org/assignments/entity",
        headers=_auth_headers(owner_user),
        json={
            "user_id": str(scoped_user.id),
            "entity_id": entity_id,
            "effective_from": datetime.now(UTC).isoformat(),
            "effective_to": None,
        },
    )
    assert assign_resp.status_code == 200
    return scoped_user


async def _create_other_tenant_user(async_session: AsyncSession) -> IamUser:
    other_tenant_id = uuid.uuid4()
    other_tenant = IamTenant(
        id=other_tenant_id,
        tenant_id=other_tenant_id,
        display_name="Other Tenant",
        tenant_type=TenantType.direct,
        country="IN",
        timezone="UTC",
        status=TenantStatus.active,
        org_setup_complete=True,
        org_setup_step=7,
        chain_hash=compute_chain_hash(
            {
                "display_name": "Other Tenant",
                "tenant_type": TenantType.direct.value,
                "country": "IN",
                "timezone": "UTC",
            },
            GENESIS_HASH,
        ),
        previous_hash=GENESIS_HASH,
    )
    async_session.add(other_tenant)

    other_user = IamUser(
        tenant_id=other_tenant_id,
        email=f"other-leader-{uuid.uuid4()}@example.com",
        hashed_password=hash_password("TestPass123!"),
        full_name="Other Leader",
        role=UserRole.finance_leader,
        is_active=True,
    )
    async_session.add(other_user)
    await async_session.flush()
    return other_user


@pytest.mark.asyncio
async def test_entity_isolation_finance_leader_sees_all(async_client, test_user: IamUser) -> None:
    await _create_entity(async_client, test_user, code="E001", name="Entity A")
    await _create_entity(async_client, test_user, code="E002", name="Entity B")

    response = await async_client.get("/api/v1/platform/entities", headers=_auth_headers(test_user))
    assert response.status_code == 200
    payload = response.json()["data"]
    assert len(payload) >= 2


@pytest.mark.asyncio
async def test_entity_isolation_finance_team_sees_assigned_only(
    async_client,
    async_session: AsyncSession,
    test_user: IamUser,
) -> None:
    entity_a = await _create_entity(async_client, test_user, code="E101", name="Entity A")
    entity_b = await _create_entity(async_client, test_user, code="E102", name="Entity B")

    team_user = IamUser(
        tenant_id=test_user.tenant_id,
        email=f"fin-team-{uuid.uuid4()}@example.com",
        hashed_password=hash_password("TestPass123!"),
        full_name="Finance Team",
        role=UserRole.finance_team,
        is_active=True,
    )
    async_session.add(team_user)
    await async_session.flush()

    assign_resp = await async_client.post(
        "/api/v1/platform/org/assignments/entity",
        headers=_auth_headers(test_user),
        json={
            "user_id": str(team_user.id),
            "entity_id": entity_a,
            "effective_from": datetime.now(UTC).isoformat(),
            "effective_to": None,
        },
    )
    assert assign_resp.status_code == 200

    list_resp = await async_client.get("/api/v1/platform/entities", headers=_auth_headers(team_user))
    assert list_resp.status_code == 200
    entity_ids = {row["id"] for row in list_resp.json()["data"]}
    assert entity_a in entity_ids
    assert entity_b not in entity_ids


@pytest.mark.asyncio
async def test_entity_isolation_detail_access_denied(
    async_client,
    async_session: AsyncSession,
    test_user: IamUser,
) -> None:
    entity_a = await _create_entity(async_client, test_user, code="E201", name="Entity A")
    entity_b = await _create_entity(async_client, test_user, code="E202", name="Entity B")

    team_user = IamUser(
        tenant_id=test_user.tenant_id,
        email=f"fin-team-{uuid.uuid4()}@example.com",
        hashed_password=hash_password("TestPass123!"),
        full_name="Finance Team",
        role=UserRole.finance_team,
        is_active=True,
    )
    async_session.add(team_user)
    await async_session.flush()

    await async_client.post(
        "/api/v1/platform/org/assignments/entity",
        headers=_auth_headers(test_user),
        json={
            "user_id": str(team_user.id),
            "entity_id": entity_a,
            "effective_from": datetime.now(UTC).isoformat(),
            "effective_to": None,
        },
    )

    denied = await async_client.get(f"/api/v1/platform/entities/{entity_b}", headers=_auth_headers(team_user))
    assert denied.status_code == 403


@pytest.mark.asyncio
async def test_entity_isolation_detail_access_granted(
    async_client,
    async_session: AsyncSession,
    test_user: IamUser,
) -> None:
    entity_a = await _create_entity(async_client, test_user, code="E301", name="Entity A")

    team_user = IamUser(
        tenant_id=test_user.tenant_id,
        email=f"fin-team-{uuid.uuid4()}@example.com",
        hashed_password=hash_password("TestPass123!"),
        full_name="Finance Team",
        role=UserRole.finance_team,
        is_active=True,
    )
    async_session.add(team_user)
    await async_session.flush()

    await async_client.post(
        "/api/v1/platform/org/assignments/entity",
        headers=_auth_headers(test_user),
        json={
            "user_id": str(team_user.id),
            "entity_id": entity_a,
            "effective_from": datetime.now(UTC).isoformat(),
            "effective_to": None,
        },
    )

    granted = await async_client.get(f"/api/v1/platform/entities/{entity_a}", headers=_auth_headers(team_user))
    assert granted.status_code == 200
    assert granted.json()["data"]["id"] == entity_a


@pytest.mark.asyncio
async def test_entity_isolation_finance_module_respects_assignment(
    async_client,
    async_session: AsyncSession,
    test_user: IamUser,
) -> None:
    entity_a = await _create_entity(async_client, test_user, code="E401", name="Entity A")
    entity_b = await _create_entity(async_client, test_user, code="E402", name="Entity B")

    team_user = IamUser(
        tenant_id=test_user.tenant_id,
        email=f"fin-team-{uuid.uuid4()}@example.com",
        hashed_password=hash_password("TestPass123!"),
        full_name="Finance Team",
        role=UserRole.finance_team,
        is_active=True,
    )
    async_session.add(team_user)
    await async_session.flush()

    await async_client.post(
        "/api/v1/platform/org/assignments/entity",
        headers=_auth_headers(test_user),
        json={
            "user_id": str(team_user.id),
            "entity_id": entity_a,
            "effective_from": datetime.now(UTC).isoformat(),
            "effective_to": None,
        },
    )

    denied = await async_client.post(
        "/api/v1/tax/provision/compute",
        headers=_auth_headers(team_user),
        json={
            "period": "2026-03",
            "entity_id": entity_b,
            "applicable_tax_rate": "0.2517",
        },
    )
    assert denied.status_code == 403


@pytest.mark.asyncio
async def test_entity_isolation_rls_not_bypassed(
    async_client,
    async_session: AsyncSession,
    test_user: IamUser,
) -> None:
    entity_a = await _create_entity(async_client, test_user, code="E501", name="Entity A")

    other_tenant_id = uuid.uuid4()
    other_tenant = IamTenant(
        id=other_tenant_id,
        tenant_id=other_tenant_id,
        display_name="Other Tenant",
        tenant_type=TenantType.direct,
        country="IN",
        timezone="UTC",
        status=TenantStatus.active,
        org_setup_complete=True,
        org_setup_step=7,
        chain_hash=compute_chain_hash(
            {
                "display_name": "Other Tenant",
                "tenant_type": TenantType.direct.value,
                "country": "IN",
                "timezone": "UTC",
            },
            GENESIS_HASH,
        ),
        previous_hash=GENESIS_HASH,
    )
    async_session.add(other_tenant)

    other_user = IamUser(
        tenant_id=other_tenant_id,
        email=f"other-leader-{uuid.uuid4()}@example.com",
        hashed_password=hash_password("TestPass123!"),
        full_name="Other Leader",
        role=UserRole.finance_leader,
        is_active=True,
    )
    async_session.add(other_user)
    await async_session.flush()

    denied = await async_client.get(f"/api/v1/platform/entities/{entity_a}", headers=_auth_headers(other_user))
    assert denied.status_code == 404


@pytest.mark.asyncio
async def test_assert_entity_access_helper(
    async_client,
    async_session: AsyncSession,
    test_user: IamUser,
) -> None:
    entity_id = await _create_entity(async_client, test_user, code="E601", name="Entity A")

    team_user = IamUser(
        tenant_id=test_user.tenant_id,
        email=f"fin-team-{uuid.uuid4()}@example.com",
        hashed_password=hash_password("TestPass123!"),
        full_name="Finance Team",
        role=UserRole.finance_team,
        is_active=True,
    )
    async_session.add(team_user)
    await async_session.flush()

    with pytest.raises(HTTPException):
        await assert_entity_access(
            session=async_session,
            tenant_id=test_user.tenant_id,
            entity_id=uuid.UUID(entity_id),
            user_id=team_user.id,
            user_role=team_user.role,
        )

    await async_client.post(
        "/api/v1/platform/org/assignments/entity",
        headers=_auth_headers(test_user),
        json={
            "user_id": str(team_user.id),
            "entity_id": entity_id,
            "effective_from": datetime.now(UTC).isoformat(),
            "effective_to": None,
        },
    )

    await assert_entity_access(
        session=async_session,
        tenant_id=test_user.tenant_id,
        entity_id=uuid.UUID(entity_id),
        user_id=team_user.id,
        user_role=team_user.role,
    )


@pytest.mark.asyncio
async def test_entity_isolation_digital_signoff_non_signatory_denied(
    async_client,
    async_session: AsyncSession,
    test_user: IamUser,
) -> None:
    entity_a = await _create_entity(async_client, test_user, code="E701", name="Entity A")
    entity_b = await _create_entity(async_client, test_user, code="E702", name="Entity B")
    team_user = await _create_scoped_finance_team_user(
        async_client,
        async_session,
        test_user,
        entity_id=entity_b,
    )

    created = await async_client.post(
        "/api/v1/signoff/initiate",
        headers=_auth_headers(test_user),
        json={
            "document_type": "board_pack",
            "document_id": entity_a,
            "document_reference": "ENTITY-A-DOC",
            "period": "2026-03",
            "signatory_user_id": str(test_user.id),
            "signatory_role": "Director",
            "document_content": "signed content",
            "declaration_text": "I approve",
        },
    )
    assert created.status_code == 200
    signoff_id = created.json()["data"]["id"]

    denied = await async_client.post(
        f"/api/v1/signoff/{signoff_id}/sign",
        headers=_auth_headers(team_user),
        json={"totp_code": "000000"},
    )
    assert denied.status_code in {401, 403}


@pytest.mark.asyncio
async def test_entity_isolation_debt_covenants_cross_tenant_denied(
    async_client,
    async_session: AsyncSession,
    test_user: IamUser,
) -> None:
    created = await async_client.post(
        "/api/v1/covenants",
        headers=_auth_headers(test_user),
        json={
            "facility_name": "TL-A",
            "lender_name": "Bank A",
            "covenant_type": "debt_to_ebitda",
            "covenant_label": "Debt/EBITDA",
            "threshold_value": "5.0",
            "threshold_direction": "below",
            "measurement_frequency": "monthly",
        },
    )
    assert created.status_code == 200
    covenant_id = created.json()["data"]["id"]

    other_user = await _create_other_tenant_user(async_session)
    denied = await async_client.get(
        f"/api/v1/covenants/{covenant_id}/history",
        headers=_auth_headers(other_user),
    )
    assert denied.status_code in {403, 404}


@pytest.mark.asyncio
async def test_entity_isolation_treasury_cross_tenant_denied(
    async_client,
    async_session: AsyncSession,
    test_user: IamUser,
) -> None:
    created = await async_client.post(
        "/api/v1/treasury/forecasts",
        headers=_auth_headers(test_user),
        json={
            "run_name": "Entity A Forecast",
            "base_date": "2026-03-30",
            "opening_cash_balance": "100000.00",
            "currency": "INR",
            "weeks": 13,
            "seed_historical": False,
        },
    )
    assert created.status_code == 200
    forecast_id = created.json()["data"]["run"]["id"]

    other_user = await _create_other_tenant_user(async_session)
    denied = await async_client.get(
        f"/api/v1/treasury/forecasts/{forecast_id}",
        headers=_auth_headers(other_user),
    )
    assert denied.status_code in {403, 404}


@pytest.mark.asyncio
async def test_entity_isolation_multi_gaap_cross_tenant_denied(
    async_client,
    async_session: AsyncSession,
    test_user: IamUser,
) -> None:
    computed = await async_client.post(
        "/api/v1/gaap/compute",
        headers=_auth_headers(test_user),
        json={"period": "2026-03", "gaap_framework": "INDAS"},
    )
    assert computed.status_code == 200

    other_user = await _create_other_tenant_user(async_session)
    denied = await async_client.get(
        "/api/v1/gaap/INDAS/2026-03",
        headers=_auth_headers(other_user),
    )
    assert denied.status_code in {403, 404}


@pytest.mark.asyncio
async def test_entity_isolation_transfer_pricing_cross_tenant_denied(
    async_client,
    async_session: AsyncSession,
    test_user: IamUser,
) -> None:
    generated = await async_client.post(
        "/api/v1/transfer-pricing/generate-3ceb",
        headers=_auth_headers(test_user),
        json={"fiscal_year": 2026},
    )
    assert generated.status_code == 200
    document_id = generated.json()["data"]["id"]

    other_user = await _create_other_tenant_user(async_session)
    denied = await async_client.get(
        f"/api/v1/transfer-pricing/documents/{document_id}",
        headers=_auth_headers(other_user),
    )
    assert denied.status_code in {403, 404}


@pytest.mark.asyncio
async def test_entity_isolation_auditor_portal_token_cannot_access_other_engagement(
    async_client,
    test_user: IamUser,
) -> None:
    grant_a = await async_client.post(
        "/api/v1/audit/access/grant",
        headers=_auth_headers(test_user),
        json={
            "auditor_email": "aud-a@example.com",
            "auditor_firm": "Firm",
            "engagement_name": "Audit A",
            "valid_from": date.today().isoformat(),
            "valid_until": (date.today() + timedelta(days=30)).isoformat(),
            "modules_accessible": [],
        },
    )
    assert grant_a.status_code == 200
    token_a = grant_a.json()["data"]["token"]

    grant_b = await async_client.post(
        "/api/v1/audit/access/grant",
        headers=_auth_headers(test_user),
        json={
            "auditor_email": "aud-b@example.com",
            "auditor_firm": "Firm",
            "engagement_name": "Audit B",
            "valid_from": date.today().isoformat(),
            "valid_until": (date.today() + timedelta(days=30)).isoformat(),
            "modules_accessible": [],
        },
    )
    assert grant_b.status_code == 200
    token_b = grant_b.json()["data"]["token"]

    created_with_b = await async_client.post(
        "/api/v1/audit/portal/requests",
        headers={"X-Auditor-Token": token_b},
        json={
            "category": "bank",
            "description": "Entity B only request",
            "due_date": date.today().isoformat(),
        },
    )
    assert created_with_b.status_code == 200
    request_id_b = created_with_b.json()["data"]["request"]["id"]

    listed_with_a = await async_client.get(
        "/api/v1/audit/portal/requests",
        headers={"X-Auditor-Token": token_a},
    )
    assert listed_with_a.status_code == 200
    listed_ids = {item["id"] for item in listed_with_a.json()["data"]["requests"]}
    assert request_id_b not in listed_ids


@pytest.mark.asyncio
async def test_entity_isolation_expense_management_non_owner_denied(
    async_client,
    async_session: AsyncSession,
    test_user: IamUser,
) -> None:
    await _create_entity(async_client, test_user, code="E801", name="Entity A")
    entity_b = await _create_entity(async_client, test_user, code="E802", name="Entity B")
    team_user = await _create_scoped_finance_team_user(
        async_client,
        async_session,
        test_user,
        entity_id=entity_b,
    )

    created = await async_client.post(
        "/api/v1/expenses",
        headers=_auth_headers(test_user),
        json={
            "vendor_name": "Vendor A",
            "description": "Stationery purchase",
            "category": "office_supplies",
            "amount": "1250.00",
            "currency": "INR",
            "claim_date": "2025-03-17",
            "has_receipt": True,
            "receipt_url": "https://example.com/receipt.pdf",
        },
    )
    assert created.status_code == 201
    claim_id = created.json()["data"]["id"]

    denied = await async_client.get(
        f"/api/v1/expenses/{claim_id}",
        headers=_auth_headers(team_user),
    )
    assert denied.status_code == 404


@pytest.mark.asyncio
async def test_entity_isolation_closing_checklist_non_leader_update_denied(
    async_client,
    async_session: AsyncSession,
    test_user: IamUser,
) -> None:
    await _create_entity(async_client, test_user, code="E901", name="Entity A")
    entity_b = await _create_entity(async_client, test_user, code="E902", name="Entity B")
    team_user = await _create_scoped_finance_team_user(
        async_client,
        async_session,
        test_user,
        entity_id=entity_b,
    )

    template = await async_client.post(
        "/api/v1/close/templates",
        headers=_auth_headers(test_user),
        json={
            "name": "Entity Isolation Template",
            "description": "test",
            "is_default": True,
            "tasks": [
                {
                    "task_name": "Leader-only task",
                    "description": "Must be completed by leader",
                    "assigned_role": "finance_leader",
                    "days_relative_to_period_end": 0,
                    "depends_on_task_ids": [],
                    "auto_trigger_event": None,
                    "order_index": 0,
                }
            ],
        },
    )
    assert template.status_code == 201

    checklist = await async_client.get(
        "/api/v1/close/2026-03",
        headers=_auth_headers(test_user),
    )
    assert checklist.status_code == 200
    task_id = checklist.json()["data"]["tasks"][0]["id"]

    denied = await async_client.patch(
        f"/api/v1/close/2026-03/tasks/{task_id}",
        headers=_auth_headers(team_user),
        json={"status": "completed", "notes": "try update"},
    )
    assert denied.status_code == 403


@pytest.mark.asyncio
async def test_entity_isolation_scenario_modelling_cross_tenant_denied(
    async_client,
    async_session: AsyncSession,
    test_user: IamUser,
) -> None:
    created = await async_client.post(
        "/api/v1/scenarios",
        headers=_auth_headers(test_user),
        json={
            "name": "Entity A Scenario Set",
            "base_period": "2026-03",
            "horizon_months": 12,
            "base_forecast_run_id": None,
        },
    )
    assert created.status_code == 201
    set_id = created.json()["data"]["scenario_set"]["id"]

    other_user = await _create_other_tenant_user(async_session)
    denied = await async_client.get(
        f"/api/v1/scenarios/{set_id}",
        headers=_auth_headers(other_user),
    )
    assert denied.status_code in {403, 404}


@pytest.mark.asyncio
async def test_entity_isolation_statutory_cross_tenant_denied(
    async_client,
    async_session: AsyncSession,
    test_user: IamUser,
) -> None:
    calendar = await async_client.get(
        f"/api/v1/statutory/calendar?fiscal_year={date.today().year}",
        headers=_auth_headers(test_user),
    )
    assert calendar.status_code == 200
    filing_id = calendar.json()["data"][0]["id"]

    other_user = await _create_other_tenant_user(async_session)
    denied = await async_client.post(
        f"/api/v1/statutory/filings/{filing_id}/file",
        headers=_auth_headers(other_user),
        json={"filed_date": date.today().isoformat(), "filing_reference": "X-1"},
    )
    assert denied.status_code in {403, 404}


@pytest.mark.asyncio
async def test_entity_isolation_bank_reconciliation_cross_tenant_denied(
    async_client,
    async_session: AsyncSession,
    test_user: IamUser,
) -> None:
    created = await async_client.post(
        "/api/v1/bank-recon/statements",
        headers=_auth_headers(test_user),
        json={
            "bank_name": "HDFC",
            "account_number_masked": "XXXX1234",
            "currency": "INR",
            "period_year": 2026,
            "period_month": 3,
            "entity_name": "Entity A",
            "opening_balance": "1000.00",
            "closing_balance": "1200.00",
            "file_name": "stmt.csv",
            "file_hash": "hash-a",
            "transaction_count": 0,
        },
    )
    assert created.status_code == 201
    statement_id = created.json()["data"]["statement_id"]

    other_user = await _create_other_tenant_user(async_session)
    denied = await async_client.get(
        f"/api/v1/bank-recon/transactions/{statement_id}",
        headers=_auth_headers(other_user),
    )
    assert denied.status_code in {403, 404}


@pytest.mark.asyncio
async def test_entity_isolation_gst_returns_cross_tenant_denied(
    async_client,
    async_session: AsyncSession,
    test_user: IamUser,
) -> None:
    created = await async_client.post(
        "/api/v1/gst/returns",
        headers=_auth_headers(test_user),
        json={
            "period_year": 2026,
            "period_month": 3,
            "entity_name": "Entity A",
            "gstin": "27ABCDE1234F1Z5",
            "return_type": "GSTR3B",
            "taxable_value": "1000.00",
            "igst_amount": "0.00",
            "cgst_amount": "90.00",
            "sgst_amount": "90.00",
            "cess_amount": "0.00",
        },
    )
    assert created.status_code == 201
    return_id = created.json()["data"]["return_id"]

    other_user = await _create_other_tenant_user(async_session)
    denied = await async_client.get(
        f"/api/v1/gst/returns/{return_id}",
        headers=_auth_headers(other_user),
    )
    assert denied.status_code in {403, 404}


@pytest.mark.asyncio
async def test_isolation_locations(
    async_client,
    async_session: AsyncSession,
    test_user: IamUser,
) -> None:
    entity_a = await _create_entity(async_client, test_user, code="E1001", name="Entity A")
    entity_b = await _create_entity(async_client, test_user, code="E1002", name="Entity B")
    scoped_user = await _create_scoped_finance_team_user(
        async_client,
        async_session,
        test_user,
        entity_id=entity_b,
    )

    created = await async_client.post(
        "/api/v1/locations",
        headers=_auth_headers(test_user),
        json={
            "entity_id": entity_a,
            "location_name": "Entity A HQ",
            "location_code": "EA-HQ",
        },
    )
    assert created.status_code == 200
    location_id = created.json()["data"]["id"]

    denied = await async_client.get(
        f"/api/v1/locations/{location_id}",
        headers=_auth_headers(scoped_user),
    )
    assert denied.status_code == 403
