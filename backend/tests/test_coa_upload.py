from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import ValidationError
from financeops.db.models.users import IamUser
from financeops.modules.coa.application.coa_upload_service import CoaUploadService
from financeops.modules.coa.application.tenant_coa_resolver import TenantCoaResolver
from financeops.modules.coa.application.tenant_coa_service import TenantCoaService
from financeops.modules.coa.models import (
    CoaIndustryTemplate,
    CoaLedgerAccount,
    CoaSourceType,
    CoaUploadMode,
)
from financeops.modules.coa.seeds.runner import run_coa_seeds


async def _software_template(async_session: AsyncSession) -> CoaIndustryTemplate:
    return (
        await async_session.execute(
            select(CoaIndustryTemplate).where(CoaIndustryTemplate.code == "SOFTWARE_SAAS")
        )
    ).scalar_one()


@pytest.mark.asyncio
async def test_validate_only_detects_duplicate_ledger_code(async_session: AsyncSession) -> None:
    service = CoaUploadService(async_session)
    csv_content = (
        "group_code,group_name,subgroup_code,subgroup_name,ledger_code,ledger_name,ledger_type,is_control_account\n"
        "REV,Revenue,REV_SG,Revenue SG,LED001,Subscription Revenue,INCOME,true\n"
        "REV,Revenue,REV_SG,Revenue SG,LED001,Duplicate Revenue,INCOME,false\n"
    ).encode("utf-8")

    result = await service.validate_only(file_name="coa.csv", file_bytes=csv_content)

    assert result["total_rows"] == 2
    assert result["invalid_rows"] == 1
    assert "duplicate ledger_code in upload" in result["errors"][0]["errors"]


@pytest.mark.asyncio
async def test_upload_and_apply_creates_tenant_custom_ledger(async_session: AsyncSession, test_user: IamUser) -> None:
    await run_coa_seeds(async_session)
    template = await _software_template(async_session)

    service = CoaUploadService(async_session)
    csv_content = (
        "group_code,group_name,subgroup_code,subgroup_name,ledger_code,ledger_name,ledger_type,is_control_account\n"
        "CUS_GRP,Custom Group,CUS_SUB,Custom Subgroup,CUS_LEDGER_001,Custom Ledger,EXPENSE,true\n"
    ).encode("utf-8")

    upload = await service.upload(
        actor_id=test_user.id,
        tenant_id=test_user.tenant_id,
        template_id=template.id,
        source_type=CoaSourceType.TENANT_CUSTOM,
        upload_mode=CoaUploadMode.APPEND,
        file_name="coa.csv",
        file_bytes=csv_content,
    )

    assert upload["upload_status"] == "SUCCESS"
    apply_result = await service.apply_batch(
        batch_id=uuid.UUID(str(upload["batch_id"])),
        actor_tenant_id=test_user.tenant_id,
        is_platform_admin=False,
    )
    assert apply_result["applied_rows"] == 1

    resolver = TenantCoaResolver(async_session)
    rows = await resolver.resolve_accounts(tenant_id=test_user.tenant_id, template_id=template.id)
    assert any(row.code == "CUS_LEDGER_001" for row in rows)


@pytest.mark.asyncio
async def test_initialise_tenant_coa_fails_when_template_has_no_ledgers(
    async_session: AsyncSession,
    test_user: IamUser,
) -> None:
    empty_template = CoaIndustryTemplate(
        code="EMPTY_TEMPLATE",
        name="Empty Template",
        description="No ledgers",
        is_active=True,
    )
    async_session.add(empty_template)
    await async_session.flush()

    service = TenantCoaService(async_session)
    with pytest.raises(ValidationError, match="CoA template has no ledger accounts"):
        await service.initialise_tenant_coa(test_user.tenant_id, empty_template.id)


@pytest.mark.asyncio
async def test_apply_replace_disables_previous_scope_ledgers(async_session: AsyncSession, test_user: IamUser) -> None:
    await run_coa_seeds(async_session)
    template = await _software_template(async_session)
    service = CoaUploadService(async_session)

    first_csv = (
        "group_code,group_name,subgroup_code,subgroup_name,ledger_code,ledger_name,ledger_type,is_control_account\n"
        "CUS_GRP,Custom Group,CUS_SUB,Custom Subgroup,CUS_LEDGER_100,Custom Ledger 100,INCOME,false\n"
    ).encode("utf-8")
    first_upload = await service.upload(
        actor_id=test_user.id,
        tenant_id=test_user.tenant_id,
        template_id=template.id,
        source_type=CoaSourceType.TENANT_CUSTOM,
        upload_mode=CoaUploadMode.APPEND,
        file_name="coa_first.csv",
        file_bytes=first_csv,
    )
    await service.apply_batch(
        batch_id=uuid.UUID(str(first_upload["batch_id"])),
        actor_tenant_id=test_user.tenant_id,
        is_platform_admin=False,
    )

    replace_csv = (
        "group_code,group_name,subgroup_code,subgroup_name,ledger_code,ledger_name,ledger_type,is_control_account\n"
        "CUS_GRP,Custom Group,CUS_SUB,Custom Subgroup,CUS_LEDGER_200,Custom Ledger 200,INCOME,false\n"
    ).encode("utf-8")
    replace_upload = await service.upload(
        actor_id=test_user.id,
        tenant_id=test_user.tenant_id,
        template_id=template.id,
        source_type=CoaSourceType.TENANT_CUSTOM,
        upload_mode=CoaUploadMode.REPLACE,
        file_name="coa_replace.csv",
        file_bytes=replace_csv,
    )
    await service.apply_batch(
        batch_id=uuid.UUID(str(replace_upload["batch_id"])),
        actor_tenant_id=test_user.tenant_id,
        is_platform_admin=False,
    )

    custom_ledgers = (
        await async_session.execute(
            select(CoaLedgerAccount)
            .where(CoaLedgerAccount.industry_template_id == template.id)
            .where(CoaLedgerAccount.tenant_id == test_user.tenant_id)
            .where(CoaLedgerAccount.source_type == CoaSourceType.TENANT_CUSTOM)
            .order_by(CoaLedgerAccount.version.asc(), CoaLedgerAccount.code.asc())
        )
    ).scalars().all()

    assert any(item.code == "CUS_LEDGER_100" and item.is_active is False for item in custom_ledgers)
    assert any(item.code == "CUS_LEDGER_200" and item.is_active is True for item in custom_ledgers)
