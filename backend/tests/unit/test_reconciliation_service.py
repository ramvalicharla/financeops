from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.services.reconciliation_service import (
    create_gl_entry,
    create_tb_row,
    list_gl_entries,
    list_recon_items,
    list_tb_rows,
    run_gl_tb_reconciliation,
)


@pytest.mark.asyncio
async def test_create_gl_entry(async_session: AsyncSession, test_tenant):
    entry = await create_gl_entry(
        async_session,
        tenant_id=test_tenant.id,
        period_year=2025,
        period_month=3,
        entity_name="Entity A",
        account_code="1000",
        account_name="Cash",
        debit_amount=Decimal("1000.00"),
        credit_amount=Decimal("0.00"),
        uploaded_by=test_tenant.id,
    )
    assert entry.account_code == "1000"
    assert entry.debit_amount == Decimal("1000.00")
    assert len(entry.chain_hash) == 64


@pytest.mark.asyncio
async def test_create_tb_row(async_session: AsyncSession, test_tenant):
    row = await create_tb_row(
        async_session,
        tenant_id=test_tenant.id,
        period_year=2025,
        period_month=3,
        entity_name="Entity A",
        account_code="1000",
        account_name="Cash",
        opening_balance=Decimal("0"),
        period_debit=Decimal("1000"),
        period_credit=Decimal("0"),
        closing_balance=Decimal("1000"),
        uploaded_by=test_tenant.id,
    )
    assert row.closing_balance == Decimal("1000")
    assert len(row.chain_hash) == 64


@pytest.mark.asyncio
async def test_reconciliation_no_break(async_session: AsyncSession, test_tenant):
    """GL total matches TB closing balance — no recon items created."""
    entity = "Recon_NB"
    period_year, period_month = 2025, 4
    await create_gl_entry(
        async_session,
        tenant_id=test_tenant.id,
        period_year=period_year,
        period_month=period_month,
        entity_name=entity,
        account_code="2000",
        account_name="AR",
        debit_amount=Decimal("500"),
        credit_amount=Decimal("0"),
        uploaded_by=test_tenant.id,
    )
    await create_tb_row(
        async_session,
        tenant_id=test_tenant.id,
        period_year=period_year,
        period_month=period_month,
        entity_name=entity,
        account_code="2000",
        account_name="AR",
        opening_balance=Decimal("0"),
        period_debit=Decimal("500"),
        period_credit=Decimal("0"),
        closing_balance=Decimal("500"),  # GL net = 500, TB = 500 → no break
        uploaded_by=test_tenant.id,
    )
    items = await run_gl_tb_reconciliation(
        async_session,
        tenant_id=test_tenant.id,
        period_year=period_year,
        period_month=period_month,
        entity_name=entity,
        run_by=test_tenant.id,
    )
    assert items == []


@pytest.mark.asyncio
async def test_reconciliation_finds_break(async_session: AsyncSession, test_tenant):
    """GL total differs from TB closing balance — one recon item created."""
    entity = "Recon_Break"
    period_year, period_month = 2025, 5
    await create_gl_entry(
        async_session,
        tenant_id=test_tenant.id,
        period_year=period_year,
        period_month=period_month,
        entity_name=entity,
        account_code="3000",
        account_name="Revenue",
        debit_amount=Decimal("0"),
        credit_amount=Decimal("1000"),
        uploaded_by=test_tenant.id,
    )
    await create_tb_row(
        async_session,
        tenant_id=test_tenant.id,
        period_year=period_year,
        period_month=period_month,
        entity_name=entity,
        account_code="3000",
        account_name="Revenue",
        opening_balance=Decimal("0"),
        period_debit=Decimal("0"),
        period_credit=Decimal("1200"),
        closing_balance=Decimal("1200"),  # TB has extra 200 → break
        uploaded_by=test_tenant.id,
    )
    items = await run_gl_tb_reconciliation(
        async_session,
        tenant_id=test_tenant.id,
        period_year=period_year,
        period_month=period_month,
        entity_name=entity,
        run_by=test_tenant.id,
    )
    assert len(items) == 1
    assert items[0].account_code == "3000"
    # GL net = 0 - 1000 = -1000; TB = 1200; diff = 1200 - (-1000) = 2200
    assert items[0].difference == Decimal("2200")
    assert items[0].status == "open"
    assert len(items[0].chain_hash) == 64


@pytest.mark.asyncio
async def test_gl_entry_chain_hash_sequence(async_session: AsyncSession, test_tenant):
    """GL entries form a valid hash chain."""
    e1 = await create_gl_entry(
        async_session,
        tenant_id=test_tenant.id,
        period_year=2025, period_month=6,
        entity_name="Chain", account_code="4000", account_name="Expenses",
        debit_amount=Decimal("100"), credit_amount=Decimal("0"),
        uploaded_by=test_tenant.id,
    )
    e2 = await create_gl_entry(
        async_session,
        tenant_id=test_tenant.id,
        period_year=2025, period_month=6,
        entity_name="Chain", account_code="4001", account_name="Rent",
        debit_amount=Decimal("200"), credit_amount=Decimal("0"),
        uploaded_by=test_tenant.id,
    )
    assert e2.previous_hash == e1.chain_hash


@pytest.mark.asyncio
async def test_list_gl_entries_filter(async_session: AsyncSession, test_tenant):
    entity = "Filter_GL"
    await create_gl_entry(
        async_session, tenant_id=test_tenant.id,
        period_year=2025, period_month=1, entity_name=entity,
        account_code="5000", account_name="COGS",
        debit_amount=Decimal("300"), credit_amount=Decimal("0"),
        uploaded_by=test_tenant.id,
    )
    result = await list_gl_entries(
        async_session, test_tenant.id, period_year=2025, period_month=1, entity_name=entity
    )
    assert len(result) >= 1
    assert all(e.entity_name == entity for e in result)
