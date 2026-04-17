from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import ValidationError
from financeops.core.intent.context import MutationContext, governed_mutation_context
from financeops.db.models.users import UserRole
from financeops.services.bank_recon_service import (
    add_bank_transaction,
    create_bank_statement,
    list_bank_statements,
    run_bank_reconciliation,
)


def _governed_context(intent_type: str) -> MutationContext:
    return MutationContext(
        intent_id=uuid.uuid4(),
        job_id=uuid.uuid4(),
        actor_user_id=None,
        actor_role=UserRole.finance_leader.value,
        intent_type=intent_type,
    )


@pytest.mark.asyncio
async def test_create_bank_statement(async_session: AsyncSession, test_tenant):
    with governed_mutation_context(_governed_context("CREATE_BANK_STATEMENT")):
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
    with governed_mutation_context(_governed_context("CREATE_BANK_STATEMENT")):
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
    with governed_mutation_context(_governed_context("ADD_BANK_TRANSACTION")):
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
async def test_bank_recon_service_blocks_direct_mutation(async_session: AsyncSession, test_tenant):
    with pytest.raises(ValidationError):
        await create_bank_statement(
            async_session,
            tenant_id=test_tenant.id,
            bank_name="Blocked Bank",
            account_number_masked="XXXX0000",
            currency="INR",
            period_year=2025,
            period_month=1,
            entity_name="Blocked Entity",
            opening_balance=Decimal("0"),
            closing_balance=Decimal("0"),
            file_name="blocked.pdf",
            file_hash="z" * 64,
            uploaded_by=test_tenant.id,
        )


@pytest.mark.asyncio
async def test_run_bank_reconciliation_creates_items(
    async_session: AsyncSession, test_tenant
):
    """Unmatched transactions become bank_only open recon items."""
    with governed_mutation_context(_governed_context("CREATE_BANK_STATEMENT")):
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
    with governed_mutation_context(_governed_context("ADD_BANK_TRANSACTION")):
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
    with governed_mutation_context(_governed_context("ADD_BANK_TRANSACTION")):
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
    with governed_mutation_context(_governed_context("RUN_BANK_RECONCILIATION")):
        result = await run_bank_reconciliation(
            async_session,
            tenant_id=test_tenant.id,
            statement_id=stmt.id,
            run_by=test_tenant.id,
        )
    assert len(result.items) == 2
    assert result.summary.bank_only == 2
    assert all(i.item_type == "bank_only" for i in result.items)
    assert all(i.status == "open" for i in result.items)
    assert all(len(i.chain_hash) == 64 for i in result.items)


@pytest.mark.asyncio
async def test_run_bank_reconciliation_no_transactions(
    async_session: AsyncSession, test_tenant
):
    """Statement with no transactions yields no recon items."""
    with governed_mutation_context(_governed_context("CREATE_BANK_STATEMENT")):
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
    with governed_mutation_context(_governed_context("RUN_BANK_RECONCILIATION")):
        result = await run_bank_reconciliation(
            async_session,
            tenant_id=test_tenant.id,
            statement_id=stmt.id,
            run_by=test_tenant.id,
        )
    assert result.items == []
    assert result.summary.bank_only == 0
    assert result.summary.gl_only == 0


@pytest.mark.asyncio
async def test_list_bank_statements_filter(async_session: AsyncSession, test_tenant):
    entity = "Filter_Bank"
    with governed_mutation_context(_governed_context("CREATE_BANK_STATEMENT")):
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
