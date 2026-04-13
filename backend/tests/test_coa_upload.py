from __future__ import annotations

import io
import uuid
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import ValidationError
from financeops.core.security import create_access_token
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


def _auth_headers(user: IamUser) -> dict[str, str]:
    token = create_access_token(user.id, user.tenant_id, user.role.value)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def _mock_airlock_admission(monkeypatch: pytest.MonkeyPatch) -> uuid.UUID:
    admitted_item_id = uuid.uuid4()
    monkeypatch.setattr(
        "financeops.modules.coa.application.coa_upload_service.AirlockAdmissionService.assert_admitted",
        AsyncMock(return_value=SimpleNamespace(id=admitted_item_id, status="ADMITTED")),
    )
    return admitted_item_id


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

    result = await service.validate_only(
        actor_tenant_id=uuid.uuid4(),
        file_name="coa.csv",
        file_bytes=csv_content,
        admitted_airlock_item_id=uuid.uuid4(),
        airlock_source_type="coa_validate_upload",
    )

    assert result["total_rows"] == 2
    assert result["invalid_rows"] == 1
    assert "duplicate ledger_code in upload" in result["errors"][0]["errors"]


@pytest.mark.asyncio
async def test_validate_route_tags_onboarding_upload_metadata(
    async_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    test_user: IamUser,
) -> None:
    captured: dict[str, object] = {}

    async def _submit_external_input(self, db, **kwargs):  # type: ignore[no-untyped-def]
        captured["metadata"] = kwargs.get("metadata")
        return SimpleNamespace(
            item_id=uuid.uuid4(),
            status="QUARANTINED",
            quarantine_ref=None,
            checksum_sha256="abc123",
            admitted=False,
        )

    async def _admit_airlock_item(self, db, **kwargs):  # type: ignore[no-untyped-def]
        return SimpleNamespace(
            item_id=kwargs["item_id"],
            status="ADMITTED",
            quarantine_ref=None,
            checksum_sha256="abc123",
            admitted=True,
        )

    monkeypatch.setattr(
        "financeops.core.governance.airlock.AirlockAdmissionService.submit_external_input",
        _submit_external_input,
    )
    monkeypatch.setattr(
        "financeops.core.governance.airlock.AirlockAdmissionService.admit_airlock_item",
        _admit_airlock_item,
    )

    response = await async_client.post(
        "/api/v1/coa/validate",
        headers=_auth_headers(test_user),
        data={
            "origin_source": "onboarding",
            "onboarding_step": "upload_initial_data",
        },
        files={"file": ("coa.csv", b"ledger,dr,cr\nCash,1,0\n", "text/csv")},
    )

    assert response.status_code == 200
    assert captured["metadata"] == {
        "operation": "validate_only",
        "source": "onboarding",
        "onboarding_step": "upload_initial_data",
    }


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
        actor_tenant_id=test_user.tenant_id,
        tenant_id=test_user.tenant_id,
        template_id=template.id,
        source_type=CoaSourceType.TENANT_CUSTOM,
        upload_mode=CoaUploadMode.APPEND,
        file_name="coa.csv",
        file_bytes=csv_content,
        admitted_airlock_item_id=uuid.uuid4(),
        airlock_source_type="coa_upload",
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
        actor_tenant_id=test_user.tenant_id,
        tenant_id=test_user.tenant_id,
        template_id=template.id,
        source_type=CoaSourceType.TENANT_CUSTOM,
        upload_mode=CoaUploadMode.APPEND,
        file_name="coa_first.csv",
        file_bytes=first_csv,
        admitted_airlock_item_id=uuid.uuid4(),
        airlock_source_type="coa_upload",
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
        actor_tenant_id=test_user.tenant_id,
        tenant_id=test_user.tenant_id,
        template_id=template.id,
        source_type=CoaSourceType.TENANT_CUSTOM,
        upload_mode=CoaUploadMode.REPLACE,
        file_name="coa_replace.csv",
        file_bytes=replace_csv,
        admitted_airlock_item_id=uuid.uuid4(),
        airlock_source_type="coa_upload",
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
        actor_tenant_id=test_user.tenant_id,
        tenant_id=test_user.tenant_id,
        template_id=template.id,
        source_type=CoaSourceType.TENANT_CUSTOM,
        upload_mode=CoaUploadMode.APPEND,
        file_name="tb.csv",
        file_bytes=csv_content,
        admitted_airlock_item_id=uuid.uuid4(),
        airlock_source_type="coa_upload",
    )

    assert upload["upload_status"] == "SUCCESS"
    assert upload["upload_kind"] == "FLEXIBLE_TB"
    assert upload["requires_review"] is True
    assert upload["activation_summary"]["auto_create"] == 1
    assert upload["activation_summary"]["needs_review"] == 1


@pytest.mark.asyncio
async def test_flexible_upload_activation_plan_uses_decimal_amounts(
    async_session: AsyncSession,
) -> None:
    service = CoaUploadService(async_session)
    result = service._build_flexible_plan_item(
        row_number=1,
        row={"account": "Precision Check", "debit": "1234567.89", "credit": "0"},
        status="review",
        account_code="PRECISION_CHECK",
    )

    assert isinstance(result["debit"], Decimal)
    assert result["debit"] == Decimal("1234567.8900")
    assert isinstance(result["credit"], Decimal)
    assert result["credit"] == Decimal("0.0000")


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
        actor_tenant_id=test_user.tenant_id,
        tenant_id=test_user.tenant_id,
        template_id=template.id,
        source_type=CoaSourceType.TENANT_CUSTOM,
        upload_mode=CoaUploadMode.APPEND,
        file_name="tb.csv",
        file_bytes=csv_content,
        admitted_airlock_item_id=uuid.uuid4(),
        airlock_source_type="coa_upload",
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
        actor_tenant_id=test_user.tenant_id,
        tenant_id=test_user.tenant_id,
        template_id=template.id,
        source_type=CoaSourceType.TENANT_CUSTOM,
        upload_mode=CoaUploadMode.APPEND,
        file_name="tb.csv",
        file_bytes=csv_content,
        admitted_airlock_item_id=uuid.uuid4(),
        airlock_source_type="coa_upload",
    )
    assert replay["idempotent_replay"] is True
    assert replay["batch_id"] == upload["batch_id"]
