from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.services.audit_writer import AuditWriter
from financeops.services.mis_service import (
    create_template,
    create_upload,
    get_template,
    list_uploads,
)


@pytest.mark.asyncio
async def test_create_template_basic(async_session: AsyncSession, test_tenant):
    template = await create_template(
        async_session,
        tenant_id=test_tenant.id,
        name="Monthly P&L",
        entity_name="Entity A",
        template_data={"sheets": [{"name": "P&L", "columns": [{"header": "Revenue"}]}]},
        created_by=test_tenant.id,
    )
    assert template.name == "Monthly P&L"
    assert template.entity_name == "Entity A"
    assert template.version == 1
    assert template.is_master is False
    assert template.is_active is True
    assert template.sheet_count == 1
    assert len(template.chain_hash) == 64


@pytest.mark.asyncio
async def test_create_template_version_increments(
    async_session: AsyncSession, test_tenant
):
    t1 = await create_template(
        async_session,
        tenant_id=test_tenant.id,
        name="Template v1",
        entity_name="Entity B",
        template_data={"sheets": []},
        created_by=test_tenant.id,
    )
    t2 = await create_template(
        async_session,
        tenant_id=test_tenant.id,
        name="Template v2",
        entity_name="Entity B",
        template_data={"sheets": []},
        created_by=test_tenant.id,
    )
    assert t1.version == 1
    assert t2.version == 2


@pytest.mark.asyncio
async def test_create_master_template(async_session: AsyncSession, test_tenant):
    template = await create_template(
        async_session,
        tenant_id=test_tenant.id,
        name="Master MIS",
        entity_name="Group",
        template_data={"sheets": [{"name": "PL"}, {"name": "BS"}]},
        is_master=True,
        created_by=test_tenant.id,
    )
    assert template.is_master is True
    assert template.sheet_count == 2


@pytest.mark.asyncio
async def test_get_template_returns_correct(async_session: AsyncSession, test_tenant):
    template = await create_template(
        async_session,
        tenant_id=test_tenant.id,
        name="Lookup Test",
        entity_name="Entity C",
        template_data={"sheets": []},
        created_by=test_tenant.id,
    )
    fetched = await get_template(async_session, test_tenant.id, template.id)
    assert fetched is not None
    assert fetched.id == template.id


@pytest.mark.asyncio
async def test_get_template_wrong_tenant_returns_none(
    async_session: AsyncSession, test_tenant
):
    template = await create_template(
        async_session,
        tenant_id=test_tenant.id,
        name="Private",
        entity_name="Entity D",
        template_data={"sheets": []},
        created_by=test_tenant.id,
    )
    other_tenant_id = uuid.uuid4()
    result = await get_template(async_session, other_tenant_id, template.id)
    assert result is None


@pytest.mark.asyncio
async def test_create_upload(async_session: AsyncSession, test_tenant):
    upload = await create_upload(
        async_session,
        tenant_id=test_tenant.id,
        entity_name="Entity A",
        period_year=2025,
        period_month=3,
        file_name="mis_march_2025.xlsx",
        file_hash="a" * 64,
        uploaded_by=test_tenant.id,
        upload_notes="March 2025 MIS",
    )
    assert upload.period_year == 2025
    assert upload.period_month == 3
    assert upload.status == "pending"
    assert len(upload.chain_hash) == 64


@pytest.mark.asyncio
async def test_list_uploads_filtered_by_period(
    async_session: AsyncSession, test_tenant
):
    await create_upload(
        async_session,
        tenant_id=test_tenant.id,
        entity_name="E1",
        period_year=2025,
        period_month=1,
        file_name="jan.xlsx",
        file_hash="b" * 64,
        uploaded_by=test_tenant.id,
    )
    await create_upload(
        async_session,
        tenant_id=test_tenant.id,
        entity_name="E1",
        period_year=2025,
        period_month=2,
        file_name="feb.xlsx",
        file_hash="c" * 64,
        uploaded_by=test_tenant.id,
    )
    jan_uploads = await list_uploads(
        async_session, test_tenant.id, period_year=2025, period_month=1
    )
    assert len(jan_uploads) == 1
    assert jan_uploads[0].period_month == 1


@pytest.mark.asyncio
async def test_template_chain_hash_integrity(async_session: AsyncSession, test_tenant):
    t1 = await create_template(
        async_session,
        tenant_id=test_tenant.id,
        name="First",
        entity_name="Chain Test",
        template_data={"sheets": []},
        created_by=test_tenant.id,
    )
    t2 = await create_template(
        async_session,
        tenant_id=test_tenant.id,
        name="Second",
        entity_name="Chain Test",
        template_data={"sheets": []},
        created_by=test_tenant.id,
    )
    # Each has a valid chain_hash
    assert len(t1.chain_hash) == 64
    assert len(t2.chain_hash) == 64
    # t2's previous_hash equals t1's chain_hash
    assert t2.previous_hash == t1.chain_hash


@pytest.mark.asyncio
async def test_create_template_uses_audit_writer(
    async_session: AsyncSession, test_tenant
):
    with patch(
        "financeops.services.mis_service.AuditWriter.insert_financial_record",
        wraps=AuditWriter.insert_financial_record,
    ) as spy:
        await create_template(
            async_session,
            tenant_id=test_tenant.id,
            name="AuditWriter Template",
            entity_name="Entity Audit",
            template_data={"sheets": []},
            created_by=test_tenant.id,
        )
    assert spy.await_count == 1


@pytest.mark.asyncio
async def test_create_upload_uses_audit_writer(
    async_session: AsyncSession, test_tenant
):
    with patch(
        "financeops.services.mis_service.AuditWriter.insert_financial_record",
        wraps=AuditWriter.insert_financial_record,
    ) as spy:
        await create_upload(
            async_session,
            tenant_id=test_tenant.id,
            entity_name="Entity Audit",
            period_year=2025,
            period_month=9,
            file_name="audit_writer.xlsx",
            file_hash="d" * 64,
            uploaded_by=test_tenant.id,
        )
    assert spy.await_count == 1
