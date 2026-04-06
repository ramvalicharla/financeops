from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import ValidationError
from financeops.core.security import create_access_token
from financeops.db.models.audit import AuditTrail
from financeops.db.models.tenants import IamTenant, TenantStatus, TenantType
from financeops.db.models.users import IamUser, UserRole
from financeops.modules.coa.models import CoaIndustryTemplate, ErpAccountMapping, TenantCoaAccount
from financeops.modules.coa.application.tenant_coa_service import TenantCoaService
from financeops.modules.coa.seeds.runner import run_coa_seeds
from financeops.modules.org_setup.application.consolidation_method_service import (
    ConsolidationMethodService,
)
from financeops.modules.org_setup.application.org_setup_service import OrgSetupService
from financeops.modules.org_setup.models import OrgEntity, OrgEntityErpConfig, OrgGroup, OrgOwnership, OrgSetupProgress
from financeops.platform.db.models.entities import CpEntity
from financeops.utils.chain_hash import GENESIS_HASH, compute_chain_hash


def _auth_headers(user: IamUser) -> dict[str, str]:
    token = create_access_token(user.id, user.tenant_id, user.role.value)
    return {"Authorization": f"Bearer {token}"}


async def _seed_coa(async_session: AsyncSession) -> None:
    await run_coa_seeds(async_session)
    await async_session.flush()


async def _software_template(async_session: AsyncSession) -> CoaIndustryTemplate:
    row = (
        await async_session.execute(
            select(CoaIndustryTemplate).where(CoaIndustryTemplate.code == "SOFTWARE_SAAS")
        )
    ).scalar_one()
    return row


async def _seed_tenant_coa(async_session: AsyncSession, tenant_id: uuid.UUID) -> CoaIndustryTemplate:
    template = await _software_template(async_session)
    await TenantCoaService(async_session).initialise_tenant_coa(tenant_id, template.id)
    await async_session.flush()
    return template


async def _setup_group_and_entity(
    async_session: AsyncSession,
    tenant_id: uuid.UUID,
) -> tuple[OrgGroup, OrgEntity]:
    service = OrgSetupService(async_session)
    group = await service.submit_step1(
        tenant_id,
        {
            "group_name": "Acme Group",
            "country_of_incorp": "India",
            "country_code": "IN",
            "functional_currency": "INR",
            "reporting_currency": "INR",
            "logo_url": None,
            "website": "https://acme.example",
        },
    )
    entities = await service.submit_step2(
        tenant_id,
        group.id,
        [
            {
                "legal_name": "Acme India Pvt Ltd",
                "display_name": "Acme India",
                "entity_type": "WHOLLY_OWNED_SUBSIDIARY",
                "country_code": "IN",
                "state_code": "KA",
                "functional_currency": "INR",
                "reporting_currency": "INR",
                "fiscal_year_start": 4,
                "applicable_gaap": "INDAS",
                "incorporation_number": "INC-001",
                "pan": "ABCDE1234F",
                "tan": "BLRA12345A",
                "cin": "L12345KA2020PTC123456",
                "gstin": "29ABCDE1234F1Z5",
                "lei": None,
                "tax_jurisdiction": "India",
                "tax_rate": Decimal("0.2500"),
            }
        ],
    )
    return group, entities[0]


async def _create_second_tenant(async_session: AsyncSession) -> tuple[IamTenant, IamUser]:
    tenant_id = uuid.uuid4()
    tenant = IamTenant(
        id=tenant_id,
        tenant_id=tenant_id,
        chain_hash=compute_chain_hash({"display_name": "Tenant B"}, GENESIS_HASH),
        previous_hash=GENESIS_HASH,
        display_name="Tenant B",
        slug=f"tenant-b-{tenant_id.hex[:8]}",
        tenant_type=TenantType.direct,
        country="IN",
        timezone="UTC",
        status=TenantStatus.active,
        is_platform_tenant=False,
    )
    async_session.add(tenant)
    await async_session.flush()

    user = IamUser(
        tenant_id=tenant.id,
        email=f"tenantb-{tenant_id.hex[:8]}@example.com",
        hashed_password="x",
        full_name="Tenant B User",
        role=UserRole.finance_leader,
        is_active=True,
        mfa_enabled=False,
    )
    async_session.add(user)
    await async_session.flush()
    return tenant, user


@pytest_asyncio.fixture(autouse=True)
async def _ensure_org_setup_incomplete(async_session: AsyncSession, test_user: IamUser) -> None:
    tenant = await async_session.get(IamTenant, test_user.tenant_id)
    assert tenant is not None
    tenant.org_setup_complete = False
    tenant.org_setup_step = 0
    await async_session.flush()


@pytest.mark.asyncio
async def test_financial_route_blocked_before_setup(async_client: AsyncClient, test_user: IamUser) -> None:
    response = await async_client.get(
        "/api/v1/coa/tenant/accounts",
        headers=_auth_headers(test_user),
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ORG_SETUP_REQUIRED"


@pytest.mark.asyncio
async def test_org_setup_routes_accessible_before_setup(async_client: AsyncClient, test_user: IamUser) -> None:
    response = await async_client.get(
        "/api/v1/org-setup/progress",
        headers=_auth_headers(test_user),
    )
    assert response.status_code == 200
    assert response.json()["data"]["current_step"] == 1


@pytest.mark.asyncio
async def test_auth_routes_accessible_before_setup(async_client: AsyncClient, test_user: IamUser) -> None:
    response = await async_client.get(
        "/api/v1/auth/me",
        headers=_auth_headers(test_user),
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_gate_passes_after_setup_complete(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_user: IamUser,
) -> None:
    tenant = await async_session.get(IamTenant, test_user.tenant_id)
    assert tenant is not None
    tenant.org_setup_complete = True
    tenant.org_setup_step = 7
    await async_session.flush()

    response = await async_client.get(
        "/api/v1/coa/tenant/accounts",
        headers=_auth_headers(test_user),
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_progress_creates_if_not_exists(async_session: AsyncSession, test_user: IamUser) -> None:
    service = OrgSetupService(async_session)
    row = await service.get_or_create_progress(test_user.tenant_id)
    assert row.current_step == 1


@pytest.mark.asyncio
async def test_save_step_advances_current_step(async_session: AsyncSession, test_user: IamUser) -> None:
    service = OrgSetupService(async_session)
    await service.save_step(test_user.tenant_id, 1, {"ok": True})
    row = await service.save_step(test_user.tenant_id, 3, {"ok": True})
    tenant = await async_session.get(IamTenant, test_user.tenant_id)
    assert row.current_step == 3
    assert tenant is not None and tenant.org_setup_step == 3


@pytest.mark.asyncio
async def test_save_step_idempotent(async_session: AsyncSession, test_user: IamUser) -> None:
    service = OrgSetupService(async_session)
    first = await service.save_step(test_user.tenant_id, 2, {"v": 1})
    second = await service.save_step(test_user.tenant_id, 2, {"v": 2})
    total = int(
        (
            await async_session.execute(
                select(func.count()).select_from(OrgSetupProgress).where(OrgSetupProgress.tenant_id == test_user.tenant_id)
            )
        ).scalar_one()
    )
    assert first.id == second.id
    assert total == 1


@pytest.mark.asyncio
async def test_step1_creates_org_group(async_session: AsyncSession, test_user: IamUser) -> None:
    service = OrgSetupService(async_session)
    row = await service.submit_step1(
        test_user.tenant_id,
        {
            "group_name": "Acme",
            "country_of_incorp": "India",
            "country_code": "IN",
            "functional_currency": "INR",
            "reporting_currency": "INR",
        },
    )
    assert row.group_name == "Acme"


@pytest.mark.asyncio
async def test_step1_returns_group_id(async_client: AsyncClient, test_user: IamUser) -> None:
    response = await async_client.post(
        "/api/v1/org-setup/step1",
        headers=_auth_headers(test_user),
        json={
            "group_name": "Acme",
            "country_of_incorp": "India",
            "country_code": "IN",
            "functional_currency": "INR",
            "reporting_currency": "INR",
        },
    )
    assert response.status_code == 200
    assert response.json()["data"]["group"]["id"]


@pytest.mark.asyncio
async def test_step1_second_submit_returns_updated_group(async_client: AsyncClient, test_user: IamUser) -> None:
    first = await async_client.post(
        "/api/v1/org-setup/step1",
        headers=_auth_headers(test_user),
        json={
            "group_name": "Acme",
            "country_of_incorp": "India",
            "country_code": "IN",
            "functional_currency": "INR",
            "reporting_currency": "INR",
        },
    )
    assert first.status_code == 200

    second = await async_client.post(
        "/api/v1/org-setup/step1",
        headers=_auth_headers(test_user),
        json={
            "group_name": "Acme Updated",
            "country_of_incorp": "India",
            "country_code": "IN",
            "functional_currency": "INR",
            "reporting_currency": "INR",
        },
    )
    assert second.status_code == 200
    assert second.json()["data"]["group"]["group_name"] == "Acme Updated"


@pytest.mark.asyncio
async def test_step2_creates_entities(async_session: AsyncSession, test_user: IamUser) -> None:
    group, entity = await _setup_group_and_entity(async_session, test_user.tenant_id)
    assert group.id
    assert entity.id


@pytest.mark.asyncio
async def test_step2_creates_cp_entities(async_session: AsyncSession, test_user: IamUser) -> None:
    _, entity = await _setup_group_and_entity(async_session, test_user.tenant_id)
    assert entity.cp_entity_id is not None
    cp_row = await async_session.get(CpEntity, entity.cp_entity_id)
    assert cp_row is not None


@pytest.mark.asyncio
async def test_step2_requires_minimum_one_entity(async_session: AsyncSession, test_user: IamUser) -> None:
    service = OrgSetupService(async_session)
    group = await service.submit_step1(
        test_user.tenant_id,
        {
            "group_name": "Acme",
            "country_of_incorp": "India",
            "country_code": "IN",
            "functional_currency": "INR",
            "reporting_currency": "INR",
        },
    )
    with pytest.raises(ValidationError):
        await service.submit_step2(test_user.tenant_id, group.id, [])


@pytest.mark.asyncio
async def test_step3_creates_ownership_records(async_session: AsyncSession, test_user: IamUser) -> None:
    service = OrgSetupService(async_session)
    group = await service.submit_step1(
        test_user.tenant_id,
        {
            "group_name": "Acme",
            "country_of_incorp": "India",
            "country_code": "IN",
            "functional_currency": "INR",
            "reporting_currency": "INR",
        },
    )
    entities = await service.submit_step2(
        test_user.tenant_id,
        group.id,
        [
            {
                "legal_name": "Parent Co",
                "display_name": "Parent",
                "entity_type": "HOLDING_COMPANY",
                "country_code": "IN",
                "state_code": None,
                "functional_currency": "INR",
                "reporting_currency": "INR",
                "fiscal_year_start": 4,
                "applicable_gaap": "INDAS",
            },
            {
                "legal_name": "Child Co",
                "display_name": "Child",
                "entity_type": "WHOLLY_OWNED_SUBSIDIARY",
                "country_code": "IN",
                "state_code": None,
                "functional_currency": "INR",
                "reporting_currency": "INR",
                "fiscal_year_start": 4,
                "applicable_gaap": "INDAS",
            },
        ],
    )
    rows = await service.submit_step3(
        test_user.tenant_id,
        [
            {
                "parent_entity_id": entities[0].id,
                "child_entity_id": entities[1].id,
                "ownership_pct": Decimal("75.0000"),
                "manual_consolidation_method": None,
                "effective_from": date.today(),
            }
        ],
    )
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_step3_derives_full_consolidation(async_session: AsyncSession, test_user: IamUser) -> None:
    service = OrgSetupService(async_session)
    group = await service.submit_step1(
        test_user.tenant_id,
        {
            "group_name": "Acme",
            "country_of_incorp": "India",
            "country_code": "IN",
            "functional_currency": "INR",
            "reporting_currency": "INR",
        },
    )
    entities = await service.submit_step2(
        test_user.tenant_id,
        group.id,
        [
            {
                "legal_name": "Parent",
                "display_name": "Parent",
                "entity_type": "HOLDING_COMPANY",
                "country_code": "IN",
                "state_code": None,
                "functional_currency": "INR",
                "reporting_currency": "INR",
                "fiscal_year_start": 4,
                "applicable_gaap": "INDAS",
            },
            {
                "legal_name": "Sub",
                "display_name": "Sub",
                "entity_type": "WHOLLY_OWNED_SUBSIDIARY",
                "country_code": "IN",
                "state_code": None,
                "functional_currency": "INR",
                "reporting_currency": "INR",
                "fiscal_year_start": 4,
                "applicable_gaap": "INDAS",
            },
        ],
    )
    rows = await service.submit_step3(
        test_user.tenant_id,
        [
            {
                "parent_entity_id": entities[0].id,
                "child_entity_id": entities[1].id,
                "ownership_pct": Decimal("51.0000"),
                "manual_consolidation_method": None,
                "effective_from": date.today(),
            }
        ],
    )
    assert rows[0].consolidation_method == "FULL_CONSOLIDATION"
    assert isinstance(rows[0].ownership_pct, Decimal)


@pytest.mark.asyncio
async def test_step3_derives_equity_method(async_session: AsyncSession, test_user: IamUser) -> None:
    service = OrgSetupService(async_session)
    group = await service.submit_step1(
        test_user.tenant_id,
        {
            "group_name": "Acme",
            "country_of_incorp": "India",
            "country_code": "IN",
            "functional_currency": "INR",
            "reporting_currency": "INR",
        },
    )
    entities = await service.submit_step2(
        test_user.tenant_id,
        group.id,
        [
            {
                "legal_name": "Parent",
                "display_name": "Parent",
                "entity_type": "HOLDING_COMPANY",
                "country_code": "IN",
                "state_code": None,
                "functional_currency": "INR",
                "reporting_currency": "INR",
                "fiscal_year_start": 4,
                "applicable_gaap": "INDAS",
            },
            {
                "legal_name": "Associate",
                "display_name": "Associate",
                "entity_type": "ASSOCIATE",
                "country_code": "IN",
                "state_code": None,
                "functional_currency": "INR",
                "reporting_currency": "INR",
                "fiscal_year_start": 4,
                "applicable_gaap": "INDAS",
            },
        ],
    )
    rows = await service.submit_step3(
        test_user.tenant_id,
        [
            {
                "parent_entity_id": entities[0].id,
                "child_entity_id": entities[1].id,
                "ownership_pct": Decimal("30.0000"),
                "manual_consolidation_method": None,
                "effective_from": date.today(),
            }
        ],
    )
    assert rows[0].consolidation_method == "EQUITY_METHOD"


@pytest.mark.asyncio
async def test_step3_manual_override_respected(async_session: AsyncSession, test_user: IamUser) -> None:
    service = OrgSetupService(async_session)
    group, entity = await _setup_group_and_entity(async_session, test_user.tenant_id)
    parent = await service.submit_step2(
        test_user.tenant_id,
        group.id,
        [
            {
                "legal_name": "Parent",
                "display_name": "Parent",
                "entity_type": "HOLDING_COMPANY",
                "country_code": "IN",
                "state_code": None,
                "functional_currency": "INR",
                "reporting_currency": "INR",
                "fiscal_year_start": 4,
                "applicable_gaap": "INDAS",
            }
        ],
    )
    rows = await service.submit_step3(
        test_user.tenant_id,
        [
            {
                "parent_entity_id": parent[0].id,
                "child_entity_id": entity.id,
                "ownership_pct": Decimal("10.0000"),
                "manual_consolidation_method": "FULL_CONSOLIDATION",
                "effective_from": date.today(),
            }
        ],
    )
    assert rows[0].consolidation_method == "FULL_CONSOLIDATION"


@pytest.mark.asyncio
async def test_step4_creates_erp_configs(async_session: AsyncSession, test_user: IamUser) -> None:
    service = OrgSetupService(async_session)
    _, entity = await _setup_group_and_entity(async_session, test_user.tenant_id)
    rows = await service.submit_step4(
        test_user.tenant_id,
        [
            {
                "org_entity_id": entity.id,
                "erp_type": "TALLY_PRIME",
                "erp_version": "3.0",
                "is_primary": True,
            }
        ],
    )
    assert len(rows) == 1
    assert rows[0].erp_type == "TALLY_PRIME"


@pytest.mark.asyncio
async def test_step5_initialises_tenant_coa(async_session: AsyncSession, test_user: IamUser) -> None:
    await _seed_coa(async_session)
    service = OrgSetupService(async_session)
    _, entity = await _setup_group_and_entity(async_session, test_user.tenant_id)
    template = await _seed_tenant_coa(async_session, test_user.tenant_id)
    await service.submit_step5(
        test_user.tenant_id,
        [{"entity_id": entity.id, "template_id": template.id}],
    )
    count = int(
        (
            await async_session.execute(
                select(func.count())
                .select_from(TenantCoaAccount)
                .where(TenantCoaAccount.tenant_id == test_user.tenant_id)
            )
        ).scalar_one()
    )
    assert count > 80


@pytest.mark.asyncio
async def test_step5_sets_industry_template_on_entity(async_session: AsyncSession, test_user: IamUser) -> None:
    await _seed_coa(async_session)
    service = OrgSetupService(async_session)
    _, entity = await _setup_group_and_entity(async_session, test_user.tenant_id)
    template = await _seed_tenant_coa(async_session, test_user.tenant_id)
    await service.submit_step5(
        test_user.tenant_id,
        [{"entity_id": entity.id, "template_id": template.id}],
    )
    await async_session.refresh(entity)
    assert entity.industry_template_id == template.id


@pytest.mark.asyncio
async def test_step5_allows_pending_coa_without_upload(async_session: AsyncSession, test_user: IamUser) -> None:
    await _seed_coa(async_session)
    service = OrgSetupService(async_session)
    _, entity = await _setup_group_and_entity(async_session, test_user.tenant_id)
    template = await _software_template(async_session)

    summary = await service.submit_step5(
        test_user.tenant_id,
        [{"entity_id": entity.id, "template_id": template.id}],
    )
    progress = await service.get_or_create_progress(test_user.tenant_id)

    assert summary[0]["account_count"] == 0
    assert (progress.step5_data or {}).get("coa_status") == "pending"


@pytest.mark.asyncio
async def test_mark_coa_skipped_sets_progress_status(async_session: AsyncSession, test_user: IamUser) -> None:
    service = OrgSetupService(async_session)
    progress = await service.mark_coa_skipped(test_user.tenant_id)

    assert progress.current_step >= 5
    assert (progress.step5_data or {}).get("coa_status") == "skipped"


@pytest.mark.asyncio
async def test_step6_confirms_mappings(async_session: AsyncSession, test_user: IamUser) -> None:
    await _seed_coa(async_session)
    service = OrgSetupService(async_session)
    _, entity = await _setup_group_and_entity(async_session, test_user.tenant_id)
    template = await _seed_tenant_coa(async_session, test_user.tenant_id)
    await service.submit_step5(
        test_user.tenant_id,
        [{"entity_id": entity.id, "template_id": template.id}],
    )
    tenant_account = (
        await async_session.execute(
            select(TenantCoaAccount)
            .where(TenantCoaAccount.tenant_id == test_user.tenant_id)
            .order_by(TenantCoaAccount.account_code)
        )
    ).scalars().first()
    assert tenant_account is not None and entity.cp_entity_id is not None

    mapping = ErpAccountMapping(
        tenant_id=test_user.tenant_id,
        entity_id=entity.cp_entity_id,
        erp_connector_type="TALLY",
        erp_account_code="1001",
        erp_account_name="Sales",
        erp_account_type="revenue",
        tenant_coa_account_id=tenant_account.id,
        mapping_confidence=Decimal("0.9500"),
        is_auto_mapped=True,
        is_confirmed=False,
        is_active=True,
    )
    async_session.add(mapping)
    await async_session.flush()

    confirmed = await service.submit_step6(
        test_user.tenant_id,
        [mapping.id],
        confirmed_by=test_user.id,
    )
    await async_session.refresh(mapping)
    assert confirmed == 1
    assert mapping.is_confirmed is True


@pytest.mark.asyncio
async def test_step6_allows_unmapped_completion_when_coa_skipped(async_session: AsyncSession, test_user: IamUser) -> None:
    service = OrgSetupService(async_session)
    await service.mark_coa_skipped(test_user.tenant_id)
    await service.submit_step6(test_user.tenant_id, [], confirmed_by=test_user.id)
    tenant = await async_session.get(IamTenant, test_user.tenant_id)
    assert tenant is not None and tenant.org_setup_complete is True


@pytest.mark.asyncio
async def test_complete_setup_sets_flag(async_session: AsyncSession, test_user: IamUser) -> None:
    service = OrgSetupService(async_session)
    await service.mark_coa_skipped(test_user.tenant_id)
    await service.complete_setup(test_user.tenant_id)
    tenant = await async_session.get(IamTenant, test_user.tenant_id)
    assert tenant is not None
    assert tenant.org_setup_complete is True
    assert tenant.org_setup_step == 7


@pytest.mark.asyncio
async def test_complete_setup_rejects_pending_coa_without_erp(async_session: AsyncSession, test_user: IamUser) -> None:
    service = OrgSetupService(async_session)
    with pytest.raises(ValidationError):
        await service.complete_setup(test_user.tenant_id)


@pytest.mark.asyncio
async def test_complete_setup_allows_erp_connected_without_coa(async_session: AsyncSession, test_user: IamUser) -> None:
    service = OrgSetupService(async_session)
    _, entity = await _setup_group_and_entity(async_session, test_user.tenant_id)
    await service.submit_step4(
        test_user.tenant_id,
        [{"org_entity_id": entity.id, "erp_type": "MANUAL", "erp_version": None, "is_primary": True}],
    )
    assert entity.cp_entity_id is not None
    async_session.add(
        ErpAccountMapping(
            tenant_id=test_user.tenant_id,
            entity_id=entity.cp_entity_id,
            erp_connector_type="MANUAL",
            erp_account_code="ERP-1001",
            erp_account_name="ERP Cash",
            erp_account_type="asset",
            tenant_coa_account_id=None,
            mapping_confidence=Decimal("0.9000"),
            is_auto_mapped=False,
            is_confirmed=False,
            is_active=True,
        )
    )
    await async_session.flush()
    await service.complete_setup(test_user.tenant_id)
    tenant = await async_session.get(IamTenant, test_user.tenant_id)
    assert tenant is not None and tenant.org_setup_complete is True


@pytest.mark.asyncio
async def test_active_erp_config_without_usable_data_keeps_coa_status_pending(
    async_session: AsyncSession,
    test_user: IamUser,
) -> None:
    service = OrgSetupService(async_session)
    _, entity = await _setup_group_and_entity(async_session, test_user.tenant_id)
    await service.submit_step4(
        test_user.tenant_id,
        [{"org_entity_id": entity.id, "erp_type": "MANUAL", "erp_version": None, "is_primary": True}],
    )

    assert await service.get_coa_status(test_user.tenant_id) == "pending"


@pytest.mark.asyncio
async def test_complete_setup_unlocks_financial_routes(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_user: IamUser,
) -> None:
    service = OrgSetupService(async_session)
    await service.mark_coa_skipped(test_user.tenant_id)
    await service.complete_setup(test_user.tenant_id)
    response = await async_client.get(
        "/api/v1/coa/tenant/accounts",
        headers=_auth_headers(test_user),
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_derive_full_consolidation_above_50() -> None:
    service = ConsolidationMethodService()
    assert service.derive_method(Decimal("50.0001"), "WHOLLY_OWNED_SUBSIDIARY", None) == "FULL_CONSOLIDATION"


@pytest.mark.asyncio
async def test_derive_equity_method_20_to_50() -> None:
    service = ConsolidationMethodService()
    assert service.derive_method(Decimal("20.0000"), "ASSOCIATE", None) == "EQUITY_METHOD"
    assert service.derive_method(Decimal("50.0000"), "ASSOCIATE", None) == "EQUITY_METHOD"


@pytest.mark.asyncio
async def test_derive_excluded_below_20() -> None:
    service = ConsolidationMethodService()
    assert service.derive_method(Decimal("19.9999"), "ASSOCIATE", None) == "EXCLUDED"


@pytest.mark.asyncio
async def test_derive_proportionate_for_jv() -> None:
    service = ConsolidationMethodService()
    assert service.derive_method(Decimal("40.0000"), "JOINT_VENTURE", None) == "PROPORTIONATE"


@pytest.mark.asyncio
async def test_all_pct_values_are_decimal_not_float() -> None:
    service = ConsolidationMethodService()
    value = Decimal("51.0000")
    result = service.derive_method(value, "WHOLLY_OWNED_SUBSIDIARY", None)
    assert isinstance(value, Decimal)
    assert result == "FULL_CONSOLIDATION"


@pytest.mark.asyncio
async def test_get_ownership_tree_returns_hierarchy(async_session: AsyncSession, test_user: IamUser) -> None:
    service = OrgSetupService(async_session)
    group = await service.submit_step1(
        test_user.tenant_id,
        {
            "group_name": "Tree Group",
            "country_of_incorp": "India",
            "country_code": "IN",
            "functional_currency": "INR",
            "reporting_currency": "INR",
        },
    )
    entities = await service.submit_step2(
        test_user.tenant_id,
        group.id,
        [
            {
                "legal_name": "Parent",
                "display_name": "Parent",
                "entity_type": "HOLDING_COMPANY",
                "country_code": "IN",
                "state_code": None,
                "functional_currency": "INR",
                "reporting_currency": "INR",
                "fiscal_year_start": 4,
                "applicable_gaap": "INDAS",
            },
            {
                "legal_name": "Child",
                "display_name": "Child",
                "entity_type": "WHOLLY_OWNED_SUBSIDIARY",
                "country_code": "IN",
                "state_code": None,
                "functional_currency": "INR",
                "reporting_currency": "INR",
                "fiscal_year_start": 4,
                "applicable_gaap": "INDAS",
            },
        ],
    )
    await service.submit_step3(
        test_user.tenant_id,
        [
            {
                "parent_entity_id": entities[0].id,
                "child_entity_id": entities[1].id,
                "ownership_pct": Decimal("60.0000"),
                "manual_consolidation_method": None,
                "effective_from": date.today(),
            }
        ],
    )
    tree = await service.get_ownership_tree(test_user.tenant_id)
    assert tree["entities"]
    assert tree["entities"][0]["children"]


@pytest.mark.asyncio
async def test_single_entity_tree(async_session: AsyncSession, test_user: IamUser) -> None:
    service = OrgSetupService(async_session)
    _, entity = await _setup_group_and_entity(async_session, test_user.tenant_id)
    tree = await service.get_ownership_tree(test_user.tenant_id)
    assert len(tree["entities"]) >= 1
    assert any(node["entity_id"] == str(entity.id) for node in tree["entities"])


@pytest.mark.asyncio
async def test_tenant_a_cannot_read_tenant_b_entities(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_user: IamUser,
) -> None:
    service = OrgSetupService(async_session)
    await service.mark_coa_skipped(test_user.tenant_id)
    await service.complete_setup(test_user.tenant_id)

    tenant_b, user_b = await _create_second_tenant(async_session)
    service_b = OrgSetupService(async_session)
    await service_b.mark_coa_skipped(tenant_b.id)
    await service_b.complete_setup(tenant_b.id)
    _, entity_b = await _setup_group_and_entity(async_session, tenant_b.id)

    response = await async_client.get(
        f"/api/v1/org-setup/entities/{entity_b.id}",
        headers=_auth_headers(test_user),
    )
    assert response.status_code == 404
    assert user_b.id


@pytest.mark.asyncio
async def test_tenant_a_cannot_modify_tenant_b_group(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_user: IamUser,
) -> None:
    service = OrgSetupService(async_session)
    await service.mark_coa_skipped(test_user.tenant_id)
    await service.complete_setup(test_user.tenant_id)

    tenant_b, _ = await _create_second_tenant(async_session)
    service_b = OrgSetupService(async_session)
    await service_b.mark_coa_skipped(tenant_b.id)
    await service_b.complete_setup(tenant_b.id)
    _, entity_b = await _setup_group_and_entity(async_session, tenant_b.id)

    response = await async_client.patch(
        f"/api/v1/org-setup/entities/{entity_b.id}",
        headers=_auth_headers(test_user),
        json={"display_name": "Hacked"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_step4_records_persist(async_session: AsyncSession, test_user: IamUser) -> None:
    service = OrgSetupService(async_session)
    _, entity = await _setup_group_and_entity(async_session, test_user.tenant_id)
    await service.submit_step4(
        test_user.tenant_id,
        [{"org_entity_id": entity.id, "erp_type": "MANUAL", "erp_version": None, "is_primary": True}],
    )
    count = int(
        (
            await async_session.execute(
                select(func.count())
                .select_from(OrgEntityErpConfig)
                .where(OrgEntityErpConfig.tenant_id == test_user.tenant_id)
            )
        ).scalar_one()
    )
    assert count == 1


@pytest.mark.asyncio
async def test_step3_records_persist(async_session: AsyncSession, test_user: IamUser) -> None:
    service = OrgSetupService(async_session)
    group = await service.submit_step1(
        test_user.tenant_id,
        {
            "group_name": "Acme",
            "country_of_incorp": "India",
            "country_code": "IN",
            "functional_currency": "INR",
            "reporting_currency": "INR",
        },
    )
    entities = await service.submit_step2(
        test_user.tenant_id,
        group.id,
        [
            {
                "legal_name": "Parent",
                "display_name": "Parent",
                "entity_type": "HOLDING_COMPANY",
                "country_code": "IN",
                "state_code": None,
                "functional_currency": "INR",
                "reporting_currency": "INR",
                "fiscal_year_start": 4,
                "applicable_gaap": "INDAS",
            },
            {
                "legal_name": "Child",
                "display_name": "Child",
                "entity_type": "ASSOCIATE",
                "country_code": "IN",
                "state_code": None,
                "functional_currency": "INR",
                "reporting_currency": "INR",
                "fiscal_year_start": 4,
                "applicable_gaap": "INDAS",
            },
        ],
    )
    await service.submit_step3(
        test_user.tenant_id,
        [
            {
                "parent_entity_id": entities[0].id,
                "child_entity_id": entities[1].id,
                "ownership_pct": Decimal("25.0000"),
                "manual_consolidation_method": None,
                "effective_from": date.today(),
            }
        ],
    )
    count = int(
        (
            await async_session.execute(
                select(func.count())
                .select_from(OrgOwnership)
                .where(OrgOwnership.tenant_id == test_user.tenant_id)
            )
        ).scalar_one()
    )
    assert count == 1


@pytest.mark.asyncio
async def test_get_setup_summary(async_session: AsyncSession, test_user: IamUser) -> None:
    await _seed_coa(async_session)
    service = OrgSetupService(async_session)
    _, entity = await _setup_group_and_entity(async_session, test_user.tenant_id)
    template = await _seed_tenant_coa(async_session, test_user.tenant_id)
    await service.submit_step5(
        test_user.tenant_id,
        [{"entity_id": entity.id, "template_id": template.id}],
    )
    summary = await service.get_setup_summary(test_user.tenant_id)
    assert summary["group"] is not None
    assert summary["entities"]
    assert summary["coa_status"] == "uploaded"
    assert 45 <= summary["onboarding_score"] <= 100
    assert isinstance(summary["mapping_summary"]["confidence_avg"], Decimal)


@pytest.mark.asyncio
async def test_skip_coa_endpoint_marks_status(async_client: AsyncClient, test_user: IamUser) -> None:
    response = await async_client.post(
        "/api/v1/coa/skip",
        headers=_auth_headers(test_user),
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["coa_status"] == "skipped"
    assert payload["next_step"] >= 5
    assert payload["onboarding_score"] >= 0


@pytest.mark.asyncio
async def test_skip_coa_endpoint_writes_audit_log(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_user: IamUser,
) -> None:
    response = await async_client.post(
        "/api/v1/coa/skip",
        headers=_auth_headers(test_user),
    )
    assert response.status_code == 200

    row = (
        await async_session.execute(
            select(AuditTrail)
            .where(
                AuditTrail.tenant_id == test_user.tenant_id,
                AuditTrail.user_id == test_user.id,
                AuditTrail.action == "tenant.coa.skip",
                AuditTrail.resource_type == "org_setup",
            )
            .order_by(AuditTrail.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    assert row is not None
