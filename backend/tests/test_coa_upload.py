from __future__ import annotations

import io
import uuid

import pytest
from openpyxl import Workbook
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
    CoaUploadBatch,
    CoaUploadMode,
    TenantCoaAccount,
)
from financeops.modules.coa.seeds.runner import run_coa_seeds


async def _software_template(async_session: AsyncSession) -> CoaIndustryTemplate:
    return (
        await async_session.execute(
            select(CoaIndustryTemplate).where(CoaIndustryTemplate.code == "SOFTWARE_SAAS")
        )
    ).scalar_one()


async def _template_ledger(async_session: AsyncSession, template_id: uuid.UUID) -> CoaLedgerAccount:
    return (
        await async_session.execute(
            select(CoaLedgerAccount)
            .where(
                CoaLedgerAccount.industry_template_id == template_id,
                CoaLedgerAccount.tenant_id.is_(None),
                CoaLedgerAccount.is_active.is_(True),
            )
            .order_by(CoaLedgerAccount.sort_order.asc(), CoaLedgerAccount.code.asc())
            .limit(1)
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
async def test_parse_normalized_dataframe_accepts_xlsx_alias_columns(async_session: AsyncSession) -> None:
    service = CoaUploadService(async_session)
    workbook = Workbook()
    sheet = workbook.active
    sheet.append([" Particulars ", " Dr ", " CR "])
    sheet.append([" Cash ", "1,250.50", ""])
    sheet.append(["", "", ""])
    sheet.append([" Revenue ", "", "(250.25)"])
    buffer = io.BytesIO()
    workbook.save(buffer)

    dataframe = service.parse_normalized_dataframe(
        file_name="trial_balance.xlsx",
        file_bytes=buffer.getvalue(),
    )

    assert list(dataframe.columns) == ["account", "debit", "credit"]
    assert dataframe.to_dict(orient="records") == [
        {"account": "Cash", "debit": 1250.5, "credit": 0.0},
        {"account": "Revenue", "debit": 0.0, "credit": -250.25},
    ]


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


@pytest.mark.asyncio
async def test_flexible_upload_returns_activation_summary_and_review_flags(
    async_session: AsyncSession,
    test_user: IamUser,
) -> None:
    await run_coa_seeds(async_session)
    template = await _software_template(async_session)
    seed_ledger = await _template_ledger(async_session, template.id)

    tenant_service = TenantCoaService(async_session)
    await tenant_service.initialise_tenant_coa(test_user.tenant_id, template.id)
    existing = (
        await async_session.execute(
            select(TenantCoaAccount).where(
                TenantCoaAccount.tenant_id == test_user.tenant_id,
                TenantCoaAccount.account_code == seed_ledger.code,
            )
        )
    ).scalar_one()
    await async_session.delete(existing)
    await async_session.flush()

    service = CoaUploadService(async_session)
    csv_content = (
        "ledger,dr,cr\n"
        f"{seed_ledger.name},1000,0\n"
        "Needs Human Review,0,1000\n"
    ).encode("utf-8")

    upload = await service.upload(
        actor_id=test_user.id,
        tenant_id=test_user.tenant_id,
        template_id=template.id,
        source_type=CoaSourceType.TENANT_CUSTOM,
        upload_mode=CoaUploadMode.APPEND,
        file_name="tb.csv",
        file_bytes=csv_content,
    )

    assert upload["upload_status"] == "SUCCESS"
    assert upload["upload_kind"] == "FLEXIBLE_TB"
    assert upload["requires_review"] is True
    assert upload["activation_summary"]["auto_create"] == 1
    assert upload["activation_summary"]["needs_review"] == 1


@pytest.mark.asyncio
async def test_flexible_upload_apply_is_idempotent_and_marks_activation(
    async_session: AsyncSession,
    test_user: IamUser,
) -> None:
    await run_coa_seeds(async_session)
    template = await _software_template(async_session)
    seed_ledger = await _template_ledger(async_session, template.id)

    tenant_service = TenantCoaService(async_session)
    await tenant_service.initialise_tenant_coa(test_user.tenant_id, template.id)
    existing = (
        await async_session.execute(
            select(TenantCoaAccount).where(
                TenantCoaAccount.tenant_id == test_user.tenant_id,
                TenantCoaAccount.account_code == seed_ledger.code,
            )
        )
    ).scalar_one()
    await async_session.delete(existing)
    await async_session.flush()

    service = CoaUploadService(async_session)
    csv_content = f"account,debit,credit\n{seed_ledger.name},500,0\n".encode("utf-8")

    upload = await service.upload(
        actor_id=test_user.id,
        tenant_id=test_user.tenant_id,
        template_id=template.id,
        source_type=CoaSourceType.TENANT_CUSTOM,
        upload_mode=CoaUploadMode.APPEND,
        file_name="tb.csv",
        file_bytes=csv_content,
    )
    apply_result = await service.apply_batch(
        batch_id=uuid.UUID(str(upload["batch_id"])),
        actor_tenant_id=test_user.tenant_id,
        is_platform_admin=False,
    )
    assert apply_result["batch_id"] == upload["batch_id"]

    batch = (
        await async_session.execute(
            select(CoaUploadBatch).where(CoaUploadBatch.id == uuid.UUID(str(upload["batch_id"])))
        )
    ).scalar_one()
    summary = dict((batch.error_log or {}).get("activation_summary") or {})
    assert (batch.error_log or {}).get("activation_applied") is True
    assert int(summary.get("auto_created_applied", 0)) == 1

    replay = await service.upload(
        actor_id=test_user.id,
        tenant_id=test_user.tenant_id,
        template_id=template.id,
        source_type=CoaSourceType.TENANT_CUSTOM,
        upload_mode=CoaUploadMode.APPEND,
        file_name="tb.csv",
        file_bytes=csv_content,
    )
    assert replay["idempotent_replay"] is True
    assert replay["batch_id"] == upload["batch_id"]
