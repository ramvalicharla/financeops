from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import ValidationError
from financeops.db.models.tenants import IamTenant, TenantStatus, TenantType
from financeops.db.models.users import IamUser, UserRole
from financeops.modules.coa.application.erp_mapping_service import ErpMappingService
from financeops.modules.coa.application.global_tb_service import GlobalTrialBalanceService
from financeops.modules.coa.application.template_service import CoaTemplateService
from financeops.modules.coa.application.tenant_coa_service import TenantCoaService
from financeops.modules.coa.models import (
    CoaFsClassification,
    CoaGaapMapping,
    CoaIndustryTemplate,
    CoaLedgerAccount,
    ErpAccountMapping,
    TenantCoaAccount,
)
from financeops.modules.coa.seeds.runner import run_coa_seeds
from financeops.platform.db.models.entities import CpEntity
from financeops.platform.db.models.organisations import CpOrganisation
from financeops.utils.chain_hash import GENESIS_HASH, compute_chain_hash


async def _seed_coa(async_session: AsyncSession) -> None:
    await run_coa_seeds(async_session)
    await async_session.flush()


async def _software_template_id(async_session: AsyncSession) -> uuid.UUID:
    return (
        await async_session.execute(
            select(CoaIndustryTemplate.id).where(CoaIndustryTemplate.code == "SOFTWARE_SAAS")
        )
    ).scalar_one()


async def _create_org_entity(
    async_session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    suffix: str,
) -> CpEntity:
    org_data = {"organisation_code": f"ORG_{suffix}", "organisation_name": f"Organisation {suffix}"}
    org = CpOrganisation(
        tenant_id=tenant_id,
        chain_hash=compute_chain_hash(org_data, GENESIS_HASH),
        previous_hash=GENESIS_HASH,
        organisation_code=f"ORG_{suffix}",
        organisation_name=f"Organisation {suffix}",
        parent_organisation_id=None,
        supersedes_id=None,
        is_active=True,
    )
    async_session.add(org)
    await async_session.flush()

    entity_data = {"entity_code": f"ENT_{suffix}", "entity_name": f"Entity {suffix}"}
    entity = CpEntity(
        tenant_id=tenant_id,
        chain_hash=compute_chain_hash(entity_data, GENESIS_HASH),
        previous_hash=GENESIS_HASH,
        entity_code=f"ENT_{suffix}",
        entity_name=f"Entity {suffix}",
        organisation_id=org.id,
        group_id=None,
        base_currency="INR",
        country_code="IN",
        status="active",
    )
    async_session.add(entity)
    await async_session.flush()
    return entity


async def _init_tenant_coa(async_session: AsyncSession, tenant_id: uuid.UUID) -> list[TenantCoaAccount]:
    service = TenantCoaService(async_session)
    await service.initialise_tenant_coa(tenant_id, await _software_template_id(async_session))
    await async_session.flush()
    return await service.get_tenant_accounts(tenant_id)


async def _create_second_tenant(async_session: AsyncSession) -> IamTenant:
    tenant_id = uuid.uuid4()
    tenant_data = {"display_name": "Tenant B", "tenant_type": TenantType.direct.value}
    tenant = IamTenant(
        id=tenant_id,
        tenant_id=tenant_id,
        chain_hash=compute_chain_hash(tenant_data, GENESIS_HASH),
        previous_hash=GENESIS_HASH,
        display_name="Tenant B",
        slug=f"tenant-b-{tenant_id.hex[:8]}",
        tenant_type=TenantType.direct,
        parent_tenant_id=None,
        country="IN",
        timezone="UTC",
        status=TenantStatus.active,
        is_platform_tenant=False,
    )
    async_session.add(tenant)
    await async_session.flush()
    return tenant


@pytest.mark.asyncio
async def test_industry_templates_seeded(async_session: AsyncSession) -> None:
    await _seed_coa(async_session)
    count = int((await async_session.execute(select(func.count()).select_from(CoaIndustryTemplate))).scalar_one())
    assert count == 11


@pytest.mark.asyncio
async def test_fs_classifications_seeded(async_session: AsyncSession) -> None:
    await _seed_coa(async_session)
    count = int((await async_session.execute(select(func.count()).select_from(CoaFsClassification))).scalar_one())
    assert count == 4


@pytest.mark.asyncio
async def test_software_saas_accounts_seeded(async_session: AsyncSession) -> None:
    await _seed_coa(async_session)
    template_id = await _software_template_id(async_session)
    count = int(
        (
            await async_session.execute(
                select(func.count())
                .select_from(CoaLedgerAccount)
                .where(CoaLedgerAccount.industry_template_id == template_id)
            )
        ).scalar_one()
    )
    assert count > 80


@pytest.mark.asyncio
async def test_gaap_mappings_seeded(async_session: AsyncSession) -> None:
    await _seed_coa(async_session)
    template_id = await _software_template_id(async_session)
    total_accounts = int(
        (
            await async_session.execute(
                select(func.count())
                .select_from(CoaLedgerAccount)
                .where(CoaLedgerAccount.industry_template_id == template_id)
            )
        ).scalar_one()
    )
    mapped_accounts = int(
        (
            await async_session.execute(
                select(func.count())
                .select_from(CoaGaapMapping)
                .where(CoaGaapMapping.gaap == "INDAS")
            )
        ).scalar_one()
    )
    assert mapped_accounts == total_accounts


@pytest.mark.asyncio
async def test_no_balance_columns_on_ledger_accounts() -> None:
    column_names = [column.name.lower() for column in CoaLedgerAccount.__table__.columns]
    assert "balance" not in column_names
    assert all("amount" not in column_name for column_name in column_names)


@pytest.mark.asyncio
async def test_get_all_templates_returns_11(async_session: AsyncSession) -> None:
    await _seed_coa(async_session)
    service = CoaTemplateService(async_session)
    templates = await service.get_all_templates()
    assert len(templates) == 11


@pytest.mark.asyncio
async def test_get_hierarchy_returns_full_tree(async_session: AsyncSession) -> None:
    await _seed_coa(async_session)
    service = CoaTemplateService(async_session)
    hierarchy = await service.get_full_hierarchy(await _software_template_id(async_session))
    assert hierarchy["classifications"]


@pytest.mark.asyncio
async def test_hierarchy_has_seven_levels(async_session: AsyncSession) -> None:
    await _seed_coa(async_session)
    service = CoaTemplateService(async_session)
    hierarchy = await service.get_full_hierarchy(await _software_template_id(async_session))
    classifications = hierarchy["classifications"]
    path_found = False
    for classification in classifications:
        for schedule in classification["schedules"]:
            for line_item in schedule["line_items"]:
                for subline in line_item["sublines"]:
                    for group in subline["account_groups"]:
                        for subgroup in group["account_subgroups"]:
                            if subgroup["ledger_accounts"]:
                                path_found = True
                                break
    assert path_found


@pytest.mark.asyncio
async def test_initialise_tenant_coa_creates_accounts(async_session: AsyncSession, test_user: IamUser) -> None:
    await _seed_coa(async_session)
    rows = await _init_tenant_coa(async_session, test_user.tenant_id)
    assert len(rows) > 80


@pytest.mark.asyncio
async def test_initialise_is_idempotent(async_session: AsyncSession, test_user: IamUser) -> None:
    await _seed_coa(async_session)
    service = TenantCoaService(async_session)
    template_id = await _software_template_id(async_session)
    await service.initialise_tenant_coa(test_user.tenant_id, template_id)
    await service.initialise_tenant_coa(test_user.tenant_id, template_id)
    await async_session.flush()
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
async def test_add_custom_account(async_session: AsyncSession, test_user: IamUser) -> None:
    await _seed_coa(async_session)
    accounts = await _init_tenant_coa(async_session, test_user.tenant_id)
    parent_subgroup_id = accounts[0].parent_subgroup_id
    assert parent_subgroup_id is not None
    service = TenantCoaService(async_session)
    custom = await service.add_custom_account(
        test_user.tenant_id,
        parent_subgroup_id=parent_subgroup_id,
        account_code="CUS_CUSTOM_001",
        display_name="Custom SaaS Account",
    )
    assert custom.is_custom is True


@pytest.mark.asyncio
async def test_custom_code_unique_per_tenant(async_session: AsyncSession, test_user: IamUser) -> None:
    await _seed_coa(async_session)
    accounts = await _init_tenant_coa(async_session, test_user.tenant_id)
    parent_subgroup_id = accounts[0].parent_subgroup_id
    assert parent_subgroup_id is not None
    service = TenantCoaService(async_session)
    await service.add_custom_account(
        test_user.tenant_id,
        parent_subgroup_id=parent_subgroup_id,
        account_code="CUS_DUP_001",
        display_name="Custom One",
    )
    with pytest.raises(ValidationError):
        await service.add_custom_account(
            test_user.tenant_id,
            parent_subgroup_id=parent_subgroup_id,
            account_code="CUS_DUP_001",
            display_name="Custom Two",
        )


@pytest.mark.asyncio
async def test_update_display_name(async_session: AsyncSession, test_user: IamUser) -> None:
    await _seed_coa(async_session)
    accounts = await _init_tenant_coa(async_session, test_user.tenant_id)
    service = TenantCoaService(async_session)
    updated = await service.update_account(
        test_user.tenant_id,
        account_id=accounts[0].id,
        display_name="Renamed Account",
        is_active=None,
    )
    assert updated.display_name == "Renamed Account"


@pytest.mark.asyncio
async def test_toggle_account_inactive(async_session: AsyncSession, test_user: IamUser) -> None:
    await _seed_coa(async_session)
    accounts = await _init_tenant_coa(async_session, test_user.tenant_id)
    service = TenantCoaService(async_session)
    toggled = await service.toggle_account_active(test_user.tenant_id, accounts[0].id)
    assert toggled.is_active is False


@pytest.mark.asyncio
async def test_auto_suggest_exact_code_match(async_session: AsyncSession, test_user: IamUser) -> None:
    await _seed_coa(async_session)
    accounts = await _init_tenant_coa(async_session, test_user.tenant_id)
    entity = await _create_org_entity(async_session, tenant_id=test_user.tenant_id, suffix="01")
    service = ErpMappingService(async_session)
    rows = await service.auto_suggest_mappings(
        tenant_id=test_user.tenant_id,
        entity_id=entity.id,
        erp_connector_type="TALLY",
        erp_accounts=[{"code": accounts[0].account_code, "name": "Some ERP Name", "type": "asset"}],
    )
    assert rows[0].mapping_confidence == Decimal("1.0000")
    assert isinstance(rows[0].mapping_confidence, Decimal)


@pytest.mark.asyncio
async def test_auto_suggest_name_similarity_is_decimal(async_session: AsyncSession, test_user: IamUser) -> None:
    await _seed_coa(async_session)
    accounts = await _init_tenant_coa(async_session, test_user.tenant_id)
    entity = await _create_org_entity(async_session, tenant_id=test_user.tenant_id, suffix="02")
    service = ErpMappingService(async_session)
    rows = await service.auto_suggest_mappings(
        tenant_id=test_user.tenant_id,
        entity_id=entity.id,
        erp_connector_type="ZOHO",
        erp_accounts=[{"code": "X-100", "name": accounts[0].display_name, "type": "asset"}],
    )
    assert isinstance(rows[0].mapping_confidence, Decimal)
    assert rows[0].mapping_confidence is not None


@pytest.mark.asyncio
async def test_unconfirmed_not_included_in_confirmed_count(async_session: AsyncSession, test_user: IamUser) -> None:
    await _seed_coa(async_session)
    accounts = await _init_tenant_coa(async_session, test_user.tenant_id)
    entity = await _create_org_entity(async_session, tenant_id=test_user.tenant_id, suffix="03")
    service = ErpMappingService(async_session)
    await service.auto_suggest_mappings(
        tenant_id=test_user.tenant_id,
        entity_id=entity.id,
        erp_connector_type="TALLY",
        erp_accounts=[{"code": accounts[0].account_code, "name": accounts[0].display_name, "type": "asset"}],
    )
    summary = await service.get_mapping_summary(test_user.tenant_id, entity.id, "TALLY")
    assert summary["mapped"] >= 1
    assert summary["confirmed"] == 0


@pytest.mark.asyncio
async def test_confirm_mapping_sets_confirmed_at(async_session: AsyncSession, test_user: IamUser) -> None:
    await _seed_coa(async_session)
    accounts = await _init_tenant_coa(async_session, test_user.tenant_id)
    entity = await _create_org_entity(async_session, tenant_id=test_user.tenant_id, suffix="04")
    service = ErpMappingService(async_session)
    mappings = await service.auto_suggest_mappings(
        tenant_id=test_user.tenant_id,
        entity_id=entity.id,
        erp_connector_type="TALLY",
        erp_accounts=[{"code": accounts[0].account_code, "name": accounts[0].display_name, "type": "asset"}],
    )
    confirmed = await service.confirm_mapping(
        tenant_id=test_user.tenant_id,
        mapping_id=mappings[0].id,
        tenant_coa_account_id=accounts[0].id,
        confirmed_by=test_user.id,
    )
    assert confirmed.is_confirmed is True
    assert confirmed.confirmed_at is not None


@pytest.mark.asyncio
async def test_bulk_confirm_returns_count(async_session: AsyncSession, test_user: IamUser) -> None:
    await _seed_coa(async_session)
    accounts = await _init_tenant_coa(async_session, test_user.tenant_id)
    entity = await _create_org_entity(async_session, tenant_id=test_user.tenant_id, suffix="05")
    service = ErpMappingService(async_session)
    mappings = await service.auto_suggest_mappings(
        tenant_id=test_user.tenant_id,
        entity_id=entity.id,
        erp_connector_type="TALLY",
        erp_accounts=[
            {"code": accounts[0].account_code, "name": accounts[0].display_name, "type": "asset"},
            {"code": accounts[1].account_code, "name": accounts[1].display_name, "type": "asset"},
        ],
    )
    count = await service.bulk_confirm_mappings(
        tenant_id=test_user.tenant_id,
        mapping_ids=[row.id for row in mappings],
        confirmed_by=test_user.id,
    )
    assert count >= 1


@pytest.mark.asyncio
async def test_unmapped_returns_only_unconfirmed(async_session: AsyncSession, test_user: IamUser) -> None:
    await _seed_coa(async_session)
    accounts = await _init_tenant_coa(async_session, test_user.tenant_id)
    entity = await _create_org_entity(async_session, tenant_id=test_user.tenant_id, suffix="06")
    service = ErpMappingService(async_session)
    mappings = await service.auto_suggest_mappings(
        tenant_id=test_user.tenant_id,
        entity_id=entity.id,
        erp_connector_type="TALLY",
        erp_accounts=[
            {"code": accounts[0].account_code, "name": accounts[0].display_name, "type": "asset"},
            {"code": accounts[1].account_code, "name": accounts[1].display_name, "type": "asset"},
        ],
    )
    await service.confirm_mapping(
        tenant_id=test_user.tenant_id,
        mapping_id=mappings[0].id,
        tenant_coa_account_id=accounts[0].id,
        confirmed_by=test_user.id,
    )
    rows = await service.get_unmapped_accounts(test_user.tenant_id, entity.id, "TALLY")
    assert rows
    assert all((row.tenant_coa_account_id is None) or (row.is_confirmed is False) for row in rows)


@pytest.mark.asyncio
async def test_classify_tb_maps_known_accounts(async_session: AsyncSession, test_user: IamUser) -> None:
    await _seed_coa(async_session)
    accounts = await _init_tenant_coa(async_session, test_user.tenant_id)
    entity = await _create_org_entity(async_session, tenant_id=test_user.tenant_id, suffix="07")
    mapping_service = ErpMappingService(async_session)
    mappings = await mapping_service.auto_suggest_mappings(
        tenant_id=test_user.tenant_id,
        entity_id=entity.id,
        erp_connector_type="TALLY",
        erp_accounts=[{"code": "ERP_001", "name": accounts[0].display_name, "type": "asset"}],
    )
    await mapping_service.confirm_mapping(
        tenant_id=test_user.tenant_id,
        mapping_id=mappings[0].id,
        tenant_coa_account_id=accounts[0].id,
        confirmed_by=test_user.id,
    )
    service = GlobalTrialBalanceService(async_session)
    result = await service.classify_tb(
        tenant_id=test_user.tenant_id,
        entity_id=entity.id,
        raw_tb=[
            {
                "erp_account_code": "ERP_001",
                "erp_account_name": "ERP Account",
                "debit_amount": Decimal("100.00"),
                "credit_amount": Decimal("0.00"),
                "currency": "INR",
            }
        ],
        gaap="INDAS",
    )
    line = result.entity_results[entity.id][0]
    assert line.platform_account_code is not None
    assert line.is_unmapped is False


@pytest.mark.asyncio
async def test_classify_tb_flags_unmapped_not_drops(async_session: AsyncSession, test_user: IamUser) -> None:
    await _seed_coa(async_session)
    entity = await _create_org_entity(async_session, tenant_id=test_user.tenant_id, suffix="08")
    service = GlobalTrialBalanceService(async_session)
    result = await service.classify_tb(
        tenant_id=test_user.tenant_id,
        entity_id=entity.id,
        raw_tb=[
            {
                "erp_account_code": "UNKNOWN_001",
                "erp_account_name": "Unknown Account",
                "debit_amount": Decimal("50.00"),
                "credit_amount": Decimal("0.00"),
                "currency": "INR",
            }
        ],
        gaap="INDAS",
    )
    assert len(result.unmapped_lines) == 1
    assert len(result.entity_results[entity.id]) == 1
    assert result.entity_results[entity.id][0].is_unmapped is True


@pytest.mark.asyncio
async def test_classify_tb_is_balanced(async_session: AsyncSession, test_user: IamUser) -> None:
    await _seed_coa(async_session)
    entity = await _create_org_entity(async_session, tenant_id=test_user.tenant_id, suffix="09")
    service = GlobalTrialBalanceService(async_session)
    result = await service.classify_tb(
        tenant_id=test_user.tenant_id,
        entity_id=entity.id,
        raw_tb=[
            {"erp_account_code": "U1", "erp_account_name": "U1", "debit_amount": Decimal("100.00"), "credit_amount": Decimal("0.00"), "currency": "INR"},
            {"erp_account_code": "U2", "erp_account_name": "U2", "debit_amount": Decimal("0.00"), "credit_amount": Decimal("100.00"), "currency": "INR"},
        ],
    )
    assert result.is_balanced is True


@pytest.mark.asyncio
async def test_classify_tb_unconfirmed_flagged_separately(async_session: AsyncSession, test_user: IamUser) -> None:
    await _seed_coa(async_session)
    accounts = await _init_tenant_coa(async_session, test_user.tenant_id)
    entity = await _create_org_entity(async_session, tenant_id=test_user.tenant_id, suffix="10")
    mapping_service = ErpMappingService(async_session)
    await mapping_service.auto_suggest_mappings(
        tenant_id=test_user.tenant_id,
        entity_id=entity.id,
        erp_connector_type="ZOHO",
        erp_accounts=[{"code": "ERP_UNCONF", "name": accounts[0].display_name, "type": "asset"}],
    )
    service = GlobalTrialBalanceService(async_session)
    result = await service.classify_tb(
        tenant_id=test_user.tenant_id,
        entity_id=entity.id,
        raw_tb=[
            {"erp_account_code": "ERP_UNCONF", "erp_account_name": "ERP Unconfirmed", "debit_amount": Decimal("25.00"), "credit_amount": Decimal("0.00"), "currency": "INR"}
        ],
    )
    assert result.unconfirmed_count == 1
    assert result.unconfirmed_lines[0].is_unconfirmed is True


@pytest.mark.asyncio
async def test_consolidated_sums_across_entities(async_session: AsyncSession, test_user: IamUser) -> None:
    await _seed_coa(async_session)
    accounts = await _init_tenant_coa(async_session, test_user.tenant_id)
    entity_a = await _create_org_entity(async_session, tenant_id=test_user.tenant_id, suffix="11A")
    entity_b = await _create_org_entity(async_session, tenant_id=test_user.tenant_id, suffix="11B")
    mapping_service = ErpMappingService(async_session)
    map_a = await mapping_service.auto_suggest_mappings(
        tenant_id=test_user.tenant_id,
        entity_id=entity_a.id,
        erp_connector_type="MANUAL",
        erp_accounts=[{"code": "ERP_C1", "name": accounts[0].display_name, "type": "asset"}],
    )
    map_b = await mapping_service.auto_suggest_mappings(
        tenant_id=test_user.tenant_id,
        entity_id=entity_b.id,
        erp_connector_type="MANUAL",
        erp_accounts=[{"code": "ERP_C1", "name": accounts[0].display_name, "type": "asset"}],
    )
    await mapping_service.confirm_mapping(test_user.tenant_id, map_a[0].id, accounts[0].id, test_user.id)
    await mapping_service.confirm_mapping(test_user.tenant_id, map_b[0].id, accounts[0].id, test_user.id)
    service = GlobalTrialBalanceService(async_session)
    result = await service.classify_multi_entity_tb(
        tenant_id=test_user.tenant_id,
        entity_raw_tbs={
            entity_a.id: [{"erp_account_code": "ERP_C1", "erp_account_name": "ERP", "debit_amount": Decimal("100.00"), "credit_amount": Decimal("0.00"), "currency": "INR"}],
            entity_b.id: [{"erp_account_code": "ERP_C1", "erp_account_name": "ERP", "debit_amount": Decimal("50.00"), "credit_amount": Decimal("0.00"), "currency": "INR"}],
        },
    )
    assert result.consolidated
    assert result.consolidated[0].debit_amount == Decimal("150.00")


@pytest.mark.asyncio
async def test_all_amounts_are_decimal_not_float(async_session: AsyncSession, test_user: IamUser) -> None:
    await _seed_coa(async_session)
    entity = await _create_org_entity(async_session, tenant_id=test_user.tenant_id, suffix="12")
    service = GlobalTrialBalanceService(async_session)
    result = await service.classify_tb(
        tenant_id=test_user.tenant_id,
        entity_id=entity.id,
        raw_tb=[{"erp_account_code": "U3", "erp_account_name": "U3", "debit_amount": Decimal("7.00"), "credit_amount": Decimal("3.00"), "currency": "INR"}],
    )
    assert isinstance(result.total_debits, Decimal)
    assert isinstance(result.total_credits, Decimal)
    for line in result.entity_results[entity.id]:
        assert isinstance(line.debit_amount, Decimal)
        assert isinstance(line.credit_amount, Decimal)
        assert isinstance(line.net_amount, Decimal)


@pytest.mark.asyncio
async def test_tenant_a_cannot_read_tenant_b_coa(async_session: AsyncSession, test_user: IamUser) -> None:
    await _seed_coa(async_session)
    tenant_b = await _create_second_tenant(async_session)
    service = TenantCoaService(async_session)
    template_id = await _software_template_id(async_session)
    await service.initialise_tenant_coa(test_user.tenant_id, template_id)
    await service.initialise_tenant_coa(tenant_b.id, template_id)
    await async_session.flush()

    accounts_b = await service.get_tenant_accounts(tenant_b.id)
    parent_subgroup_id = accounts_b[0].parent_subgroup_id
    assert parent_subgroup_id is not None
    await service.add_custom_account(
        tenant_id=tenant_b.id,
        parent_subgroup_id=parent_subgroup_id,
        account_code="B_ONLY_001",
        display_name="Tenant B Account",
    )
    await async_session.flush()

    missing = await service.get_account_by_code(test_user.tenant_id, "B_ONLY_001")
    assert missing is None


@pytest.mark.asyncio
async def test_entity_isolation_erp_mappings(async_session: AsyncSession, test_user: IamUser) -> None:
    await _seed_coa(async_session)
    accounts = await _init_tenant_coa(async_session, test_user.tenant_id)
    entity_a = await _create_org_entity(async_session, tenant_id=test_user.tenant_id, suffix="13A")
    entity_b = await _create_org_entity(async_session, tenant_id=test_user.tenant_id, suffix="13B")
    service = ErpMappingService(async_session)
    await service.auto_suggest_mappings(
        tenant_id=test_user.tenant_id,
        entity_id=entity_a.id,
        erp_connector_type="TALLY",
        erp_accounts=[{"code": "A_ONLY", "name": accounts[0].display_name, "type": "asset"}],
    )
    await service.auto_suggest_mappings(
        tenant_id=test_user.tenant_id,
        entity_id=entity_b.id,
        erp_connector_type="TALLY",
        erp_accounts=[{"code": "B_ONLY", "name": accounts[1].display_name, "type": "asset"}],
    )
    unmapped_a = await service.get_unmapped_accounts(
        tenant_id=test_user.tenant_id,
        entity_id=entity_a.id,
        erp_connector_type="TALLY",
    )
    assert unmapped_a
    assert all(row.entity_id == entity_a.id for row in unmapped_a)
