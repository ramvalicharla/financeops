from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.services.bank_recon_service import (
    add_bank_transaction,
    create_bank_statement,
    list_bank_statements,
    list_bank_transactions,
    run_bank_reconciliation,
)


@pytest.mark.asyncio
async def test_create_bank_statement(async_session: AsyncSession, test_tenant):
    stmt = await create_bank_statement(
        async_session,
        tenant_id=test_tenant.id,
        bank_name="HDFC Bank",
        account_number_masked="XXXX1234",
        currency="INR",
        period_year=2025,
        period_month=3,
        entity_name="Entity A",
        opening_balance=Decimal("10000"),
        closing_balance=Decimal("12000"),
        file_name="march_stmt.pdf",
        file_hash="a" * 64,
        uploaded_by=test_tenant.id,
    )
    assert stmt.bank_name == "HDFC Bank"
    assert stmt.status == "pending"
    assert len(stmt.chain_hash) == 64


@pytest.mark.asyncio
async def test_add_bank_transaction(async_session: AsyncSession, test_tenant):
    stmt = await create_bank_statement(
        async_session,
        tenant_id=test_tenant.id,
        bank_name="SBI",
        account_number_masked="XXXX5678",
        currency="INR",
        period_year=2025,
        period_month=4,
        entity_name="Entity B",
        opening_balance=Decimal("5000"),
        closing_balance=Decimal("6500"),
        file_name="april_stmt.pdf",
        file_hash="b" * 64,
        uploaded_by=test_tenant.id,
    )
    txn = await add_bank_transaction(
        async_session,
        tenant_id=test_tenant.id,
        statement_id=stmt.id,
        transaction_date=date(2025, 4, 15),
        description="Customer payment",
        debit_amount=Decimal("0"),
        credit_amount=Decimal("1500"),
        balance=Decimal("6500"),
    )
    assert txn.match_status == "unmatched"
    assert txn.credit_amount == Decimal("1500")
    assert len(txn.chain_hash) == 64


@pytest.mark.asyncio
async def test_run_bank_reconciliation_creates_items(
    async_session: AsyncSession, test_tenant
):
    """Unmatched transactions become bank_only open recon items."""
    stmt = await create_bank_statement(
        async_session,
        tenant_id=test_tenant.id,
        bank_name="Axis Bank",
        account_number_masked="XXXX9999",
        currency="INR",
        period_year=2025,
        period_month=5,
        entity_name="Recon_Entity",
        opening_balance=Decimal("0"),
        closing_balance=Decimal("3000"),
        file_name="may_stmt.pdf",
        file_hash="c" * 64,
        uploaded_by=test_tenant.id,
    )
    await add_bank_transaction(
        async_session,
        tenant_id=test_tenant.id,
        statement_id=stmt.id,
        transaction_date=date(2025, 5, 10),
        description="Vendor payment",
        debit_amount=Decimal("1000"),
        credit_amount=Decimal("0"),
        balance=Decimal("2000"),
    )
    await add_bank_transaction(
        async_session,
        tenant_id=test_tenant.id,
        statement_id=stmt.id,
        transaction_date=date(2025, 5, 20),
        description="Receipt",
        debit_amount=Decimal("0"),
        credit_amount=Decimal("3000"),
        balance=Decimal("3000"),
    )
    items = await run_bank_reconciliation(
        async_session,
        tenant_id=test_tenant.id,
        statement_id=stmt.id,
        run_by=test_tenant.id,
    )
    assert len(items) == 2
    assert all(i.item_type == "bank_only" for i in items)
    assert all(i.status == "open" for i in items)
    assert all(len(i.chain_hash) == 64 for i in items)


@pytest.mark.asyncio
async def test_run_bank_reconciliation_no_transactions(
    async_session: AsyncSession, test_tenant
):
    """Statement with no transactions → no recon items."""
    stmt = await create_bank_statement(
        async_session,
        tenant_id=test_tenant.id,
        bank_name="ICICI",
        account_number_masked="XXXX0001",
        currency="USD",
        period_year=2025,
        period_month=6,
        entity_name="Empty_Entity",
        opening_balance=Decimal("0"),
        closing_balance=Decimal("0"),
        file_name="empty_stmt.pdf",
        file_hash="d" * 64,
        uploaded_by=test_tenant.id,
    )
    items = await run_bank_reconciliation(
        async_session,
        tenant_id=test_tenant.id,
        statement_id=stmt.id,
        run_by=test_tenant.id,
    )
    assert items == []


@pytest.mark.asyncio
async def test_list_bank_statements_filter(async_session: AsyncSession, test_tenant):
    entity = "Filter_Bank"
    await create_bank_statement(
        async_session,
        tenant_id=test_tenant.id,
        bank_name="Kotak",
        account_number_masked="XXXX2222",
        currency="INR",
        period_year=2025,
        period_month=7,
        entity_name=entity,
        opening_balance=Decimal("100"),
        closing_balance=Decimal("200"),
        file_name="july_stmt.pdf",
        file_hash="e" * 64,
        uploaded_by=test_tenant.id,
    )
    result = await list_bank_statements(
        async_session,
        test_tenant.id,
        entity_name=entity,
    )
    assert len(result) >= 1
    assert all(s.entity_name == entity for s in result)
