from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.services.gst_service import (
    create_gst_return,
    list_gst_recon_items,
    list_gst_returns,
    run_gst_reconciliation,
)


@pytest.mark.asyncio
async def test_create_gst_return_computes_total_tax(
    async_session: AsyncSession, test_tenant
):
    r = await create_gst_return(
        async_session,
        tenant_id=test_tenant.id,
        period_year=2025,
        period_month=3,
        entity_name="GST_Entity",
        gstin="29ABCDE1234F1Z5",
        return_type="GSTR1",
        taxable_value=Decimal("100000"),
        igst_amount=Decimal("18000"),
        cgst_amount=Decimal("0"),
        sgst_amount=Decimal("0"),
        cess_amount=Decimal("0"),
        created_by=test_tenant.id,
    )
    assert r.return_type == "GSTR1"
    assert r.total_tax == Decimal("18000")
    assert r.status == "draft"
    assert len(r.chain_hash) == 64


@pytest.mark.asyncio
async def test_run_gst_reconciliation_no_diff(
    async_session: AsyncSession, test_tenant
):
    """GSTR1 and GSTR3B with identical values → no recon items."""
    entity = "GST_NoDiff"
    period_year, period_month = 2025, 4
    for return_type in ("GSTR1", "GSTR3B"):
        await create_gst_return(
            async_session,
            tenant_id=test_tenant.id,
            period_year=period_year,
            period_month=period_month,
            entity_name=entity,
            gstin="29ABCDE1234F1Z5",
            return_type=return_type,
            taxable_value=Decimal("200000"),
            igst_amount=Decimal("36000"),
            cgst_amount=Decimal("0"),
            sgst_amount=Decimal("0"),
            cess_amount=Decimal("0"),
            created_by=test_tenant.id,
        )
    items = await run_gst_reconciliation(
        async_session,
        tenant_id=test_tenant.id,
        period_year=period_year,
        period_month=period_month,
        entity_name=entity,
        return_type_a="GSTR1",
        return_type_b="GSTR3B",
        run_by=test_tenant.id,
    )
    assert items == []


@pytest.mark.asyncio
async def test_run_gst_reconciliation_finds_diff(
    async_session: AsyncSession, test_tenant
):
    """GSTR1 and GSTR3B with different IGST → one recon item."""
    entity = "GST_Diff"
    period_year, period_month = 2025, 5
    await create_gst_return(
        async_session,
        tenant_id=test_tenant.id,
        period_year=period_year,
        period_month=period_month,
        entity_name=entity,
        gstin="29XYZDE1234F1Z5",
        return_type="GSTR1",
        taxable_value=Decimal("100000"),
        igst_amount=Decimal("18000"),
        cgst_amount=Decimal("0"),
        sgst_amount=Decimal("0"),
        cess_amount=Decimal("0"),
        created_by=test_tenant.id,
    )
    await create_gst_return(
        async_session,
        tenant_id=test_tenant.id,
        period_year=period_year,
        period_month=period_month,
        entity_name=entity,
        gstin="29XYZDE1234F1Z5",
        return_type="GSTR3B",
        taxable_value=Decimal("100000"),
        igst_amount=Decimal("20000"),  # 2000 more than GSTR1
        cgst_amount=Decimal("0"),
        sgst_amount=Decimal("0"),
        cess_amount=Decimal("0"),
        created_by=test_tenant.id,
    )
    items = await run_gst_reconciliation(
        async_session,
        tenant_id=test_tenant.id,
        period_year=period_year,
        period_month=period_month,
        entity_name=entity,
        return_type_a="GSTR1",
        return_type_b="GSTR3B",
        run_by=test_tenant.id,
    )
    # Only igst_amount differs; total_tax also differs (2000 more in GSTR3B)
    assert len(items) == 2
    igst_item = next(i for i in items if i.field_name == "igst_amount")
    assert igst_item.difference == Decimal("2000")
    assert igst_item.status == "open"
    assert len(igst_item.chain_hash) == 64


@pytest.mark.asyncio
async def test_run_gst_reconciliation_missing_return(
    async_session: AsyncSession, test_tenant
):
    """If one return type is missing, reconciliation returns empty list."""
    items = await run_gst_reconciliation(
        async_session,
        tenant_id=test_tenant.id,
        period_year=2099,
        period_month=1,
        entity_name="NoSuchEntity",
        return_type_a="GSTR1",
        return_type_b="GSTR3B",
        run_by=test_tenant.id,
    )
    assert items == []


@pytest.mark.asyncio
async def test_list_gst_returns_filter(async_session: AsyncSession, test_tenant):
    entity = "GST_Filter"
    await create_gst_return(
        async_session,
        tenant_id=test_tenant.id,
        period_year=2025,
        period_month=6,
        entity_name=entity,
        gstin="29FILTER1234F1Z5",
        return_type="GSTR2A",
        taxable_value=Decimal("50000"),
        igst_amount=Decimal("9000"),
        cgst_amount=Decimal("0"),
        sgst_amount=Decimal("0"),
        cess_amount=Decimal("0"),
        created_by=test_tenant.id,
    )
    result = await list_gst_returns(
        async_session,
        test_tenant.id,
        entity_name=entity,
        return_type="GSTR2A",
    )
    assert len(result) >= 1
    assert all(r.entity_name == entity for r in result)
    assert all(r.return_type == "GSTR2A" for r in result)
