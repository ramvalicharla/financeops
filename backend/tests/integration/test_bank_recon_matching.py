from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.intent.context import MutationContext, governed_mutation_context
from financeops.db.models.accounting_jv import AccountingJVAggregate, AccountingJVLine, EntryType, JVStatus
from financeops.db.models.bank_recon import BankReconItem
from financeops.db.models.users import UserRole
from financeops.platform.db.models.entities import CpEntity
from financeops.services.bank_recon_service import (
    add_bank_transaction,
    create_bank_statement,
    list_bank_recon_items,
    run_bank_reconciliation,
)
from financeops.modules.bank_reconciliation.domain.exceptions import StatementAlreadyProcessedError


def _governed_context(intent_type: str) -> MutationContext:
    return MutationContext(
        intent_id=uuid.uuid4(),
        job_id=uuid.uuid4(),
        actor_user_id=None,
        actor_role=UserRole.finance_leader.value,
        intent_type=intent_type,
    )


async def _default_entity_id(session: AsyncSession, tenant_id: uuid.UUID) -> uuid.UUID:
    return (
        await session.execute(
            select(CpEntity.id)
            .where(CpEntity.tenant_id == tenant_id)
            .order_by(CpEntity.created_at.asc())
            .limit(1)
        )
    ).scalar_one()


async def _seed_statement(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    uploaded_by: uuid.UUID,
    period_year: int = 2025,
    period_month: int = 5,
) -> tuple[uuid.UUID, uuid.UUID]:
    with governed_mutation_context(_governed_context("CREATE_BANK_STATEMENT")):
        statement = await create_bank_statement(
            session,
            tenant_id=tenant_id,
            bank_name="HDFC Bank",
            account_number_masked="XXXX1234",
            currency="INR",
            period_year=period_year,
            period_month=period_month,
            entity_name="Recon Entity",
            opening_balance=Decimal("0"),
            closing_balance=Decimal("0"),
            file_name="stmt.pdf",
            file_hash="a" * 64,
            uploaded_by=uploaded_by,
        )
    return statement.id, statement.entity_id


async def _add_bank_txn(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    statement_id: uuid.UUID,
    txn_date: date,
    description: str,
    signed_amount: Decimal,
) -> uuid.UUID:
    debit_amount = abs(signed_amount) if signed_amount < 0 else Decimal("0")
    credit_amount = signed_amount if signed_amount > 0 else Decimal("0")
    with governed_mutation_context(_governed_context("ADD_BANK_TRANSACTION")):
        txn = await add_bank_transaction(
            session,
            tenant_id=tenant_id,
            statement_id=statement_id,
            transaction_date=txn_date,
            description=description,
            debit_amount=debit_amount,
            credit_amount=credit_amount,
            balance=Decimal("0"),
        )
    return txn.id


async def _seed_gl_bank_line(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    created_by: uuid.UUID,
    posting_date: date,
    signed_amount: Decimal,
    narration: str,
) -> str:
    absolute_amount = abs(signed_amount)
    jv = AccountingJVAggregate(
        tenant_id=tenant_id,
        chain_hash="b" * 64,
        previous_hash="0" * 64,
        entity_id=entity_id,
        location_id=None,
        cost_centre_id=None,
        jv_number=f"JV-{uuid.uuid4().hex[:8].upper()}",
        status=JVStatus.APPROVED,
        version=1,
        period_date=posting_date,
        fiscal_year=posting_date.year,
        fiscal_period=posting_date.month,
        description=narration,
        reference=f"REF-{uuid.uuid4().hex[:8].upper()}",
        source="MANUAL",
        external_reference_id=None,
        total_debit=absolute_amount,
        total_credit=absolute_amount,
        currency="INR",
        workflow_instance_id=None,
        created_by=created_by,
        created_by_intent_id=None,
        recorded_by_job_id=None,
        resubmission_count=0,
        voided_by=None,
        void_reason=None,
        voided_at=None,
        submitted_at=None,
        first_reviewed_at=None,
        decided_at=None,
        updated_at=datetime.now(UTC),
    )
    session.add(jv)
    await session.flush()

    bank_entry_type = EntryType.DEBIT if signed_amount >= 0 else EntryType.CREDIT
    offset_entry_type = EntryType.CREDIT if bank_entry_type == EntryType.DEBIT else EntryType.DEBIT
    session.add(
        AccountingJVLine(
            tenant_id=tenant_id,
            chain_hash="c" * 64,
            previous_hash="0" * 64,
            jv_id=jv.id,
            jv_version=1,
            line_number=1,
            account_code="1000",
            account_name="Current Account - Bank 1",
            entry_type=bank_entry_type,
            amount=absolute_amount,
            currency="INR",
            transaction_currency=None,
            functional_currency=None,
            fx_rate=None,
            amount_inr=None,
            base_amount=None,
            entity_id=entity_id,
            location_id=None,
            cost_centre_id=None,
            narration=narration,
            tax_code=None,
            is_tax_line=False,
            created_by_intent_id=None,
            recorded_by_job_id=None,
        )
    )
    session.add(
        AccountingJVLine(
            tenant_id=tenant_id,
            chain_hash="d" * 64,
            previous_hash="0" * 64,
            jv_id=jv.id,
            jv_version=1,
            line_number=2,
            account_code="4000",
            account_name="Counterparty",
            entry_type=offset_entry_type,
            amount=absolute_amount,
            currency="INR",
            transaction_currency=None,
            functional_currency=None,
            fx_rate=None,
            amount_inr=None,
            base_amount=None,
            entity_id=entity_id,
            location_id=None,
            cost_centre_id=None,
            narration="Offset",
            tax_code=None,
            is_tax_line=False,
            created_by_intent_id=None,
            recorded_by_job_id=None,
        )
    )
    await session.flush()
    return f"{jv.id}:1"


async def _run_recon(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    statement_id: uuid.UUID,
    run_by: uuid.UUID,
    force_rerun: bool = False,
):
    with governed_mutation_context(_governed_context("RUN_BANK_RECONCILIATION")):
        return await run_bank_reconciliation(
            session,
            tenant_id=tenant_id,
            statement_id=statement_id,
            run_by=run_by,
            force_rerun=force_rerun,
        )


@pytest.mark.asyncio
async def test_exact_match_same_day_same_amount(
    async_session: AsyncSession,
    test_tenant,
    test_user,
):
    statement_id, entity_id = await _seed_statement(
        async_session,
        tenant_id=test_tenant.id,
        uploaded_by=test_user.id,
    )
    await _add_bank_txn(
        async_session,
        tenant_id=test_tenant.id,
        statement_id=statement_id,
        txn_date=date(2025, 5, 10),
        description="Customer receipt",
        signed_amount=Decimal("1500.00"),
    )
    gl_reference = await _seed_gl_bank_line(
        async_session,
        tenant_id=test_tenant.id,
        entity_id=entity_id,
        created_by=test_user.id,
        posting_date=date(2025, 5, 10),
        signed_amount=Decimal("1500.00"),
        narration="Customer receipt",
    )

    result = await _run_recon(
        async_session,
        tenant_id=test_tenant.id,
        statement_id=statement_id,
        run_by=test_user.id,
    )

    assert result.summary.matched == 1
    assert result.summary.bank_only == 0
    assert result.summary.gl_only == 0
    assert result.items[0].item_type == "matched"
    assert result.items[0].gl_reference == gl_reference


@pytest.mark.asyncio
async def test_exact_match_removes_from_pool_not_double_matched(
    async_session: AsyncSession,
    test_tenant,
    test_user,
):
    statement_id, entity_id = await _seed_statement(async_session, tenant_id=test_tenant.id, uploaded_by=test_user.id)
    for idx in range(2):
        await _add_bank_txn(
            async_session,
            tenant_id=test_tenant.id,
            statement_id=statement_id,
            txn_date=date(2025, 5, 11),
            description=f"Same amount {idx}",
            signed_amount=Decimal("1000.00"),
        )
    await _seed_gl_bank_line(
        async_session,
        tenant_id=test_tenant.id,
        entity_id=entity_id,
        created_by=test_user.id,
        posting_date=date(2025, 5, 11),
        signed_amount=Decimal("1000.00"),
        narration="Only one GL line",
    )

    result = await _run_recon(async_session, tenant_id=test_tenant.id, statement_id=statement_id, run_by=test_user.id)

    assert result.summary.matched == 1
    assert result.summary.bank_only == 1
    assert {item.item_type for item in result.items} == {"matched", "bank_only"}


@pytest.mark.asyncio
async def test_near_match_3_day_tolerance(
    async_session: AsyncSession,
    test_tenant,
    test_user,
):
    statement_id, entity_id = await _seed_statement(async_session, tenant_id=test_tenant.id, uploaded_by=test_user.id)
    await _add_bank_txn(
        async_session,
        tenant_id=test_tenant.id,
        statement_id=statement_id,
        txn_date=date(2025, 5, 14),
        description="NEFT receipt",
        signed_amount=Decimal("2200.00"),
    )
    await _seed_gl_bank_line(
        async_session,
        tenant_id=test_tenant.id,
        entity_id=entity_id,
        created_by=test_user.id,
        posting_date=date(2025, 5, 12),
        signed_amount=Decimal("2200.00"),
        narration="NEFT receipt",
    )

    result = await _run_recon(async_session, tenant_id=test_tenant.id, statement_id=statement_id, run_by=test_user.id)

    assert result.summary.near_match == 1
    assert result.items[0].item_type == "near_match"


@pytest.mark.asyncio
async def test_near_match_4_day_not_matched(
    async_session: AsyncSession,
    test_tenant,
    test_user,
):
    statement_id, entity_id = await _seed_statement(async_session, tenant_id=test_tenant.id, uploaded_by=test_user.id)
    await _add_bank_txn(
        async_session,
        tenant_id=test_tenant.id,
        statement_id=statement_id,
        txn_date=date(2025, 5, 14),
        description="NEFT receipt",
        signed_amount=Decimal("2200.00"),
    )
    await _seed_gl_bank_line(
        async_session,
        tenant_id=test_tenant.id,
        entity_id=entity_id,
        created_by=test_user.id,
        posting_date=date(2025, 5, 10),
        signed_amount=Decimal("2200.00"),
        narration="Payroll clearing",
    )

    result = await _run_recon(async_session, tenant_id=test_tenant.id, statement_id=statement_id, run_by=test_user.id)

    assert result.summary.near_match == 0
    assert result.summary.bank_only == 1
    assert result.summary.gl_only == 1


@pytest.mark.asyncio
async def test_fuzzy_match_description_similarity_above_threshold(
    async_session: AsyncSession,
    test_tenant,
    test_user,
):
    statement_id, entity_id = await _seed_statement(async_session, tenant_id=test_tenant.id, uploaded_by=test_user.id)
    await _add_bank_txn(
        async_session,
        tenant_id=test_tenant.id,
        statement_id=statement_id,
        txn_date=date(2025, 5, 19),
        description="Stripe payout settlement ref",
        signed_amount=Decimal("5000.00"),
    )
    await _seed_gl_bank_line(
        async_session,
        tenant_id=test_tenant.id,
        entity_id=entity_id,
        created_by=test_user.id,
        posting_date=date(2025, 5, 24),
        signed_amount=Decimal("5000.00"),
        narration="Stripe payout settlement ref",
    )

    result = await _run_recon(async_session, tenant_id=test_tenant.id, statement_id=statement_id, run_by=test_user.id)

    assert result.summary.fuzzy == 1
    assert result.items[0].item_type == "fuzzy_match"


@pytest.mark.asyncio
async def test_fuzzy_match_below_threshold_not_matched(
    async_session: AsyncSession,
    test_tenant,
    test_user,
):
    statement_id, entity_id = await _seed_statement(async_session, tenant_id=test_tenant.id, uploaded_by=test_user.id)
    await _add_bank_txn(
        async_session,
        tenant_id=test_tenant.id,
        statement_id=statement_id,
        txn_date=date(2025, 5, 19),
        description="Stripe payout settlement",
        signed_amount=Decimal("5000.00"),
    )
    await _seed_gl_bank_line(
        async_session,
        tenant_id=test_tenant.id,
        entity_id=entity_id,
        created_by=test_user.id,
        posting_date=date(2025, 5, 24),
        signed_amount=Decimal("5000.00"),
        narration="Payroll accrual",
    )

    result = await _run_recon(async_session, tenant_id=test_tenant.id, statement_id=statement_id, run_by=test_user.id)

    assert result.summary.fuzzy == 0
    assert result.summary.bank_only == 1
    assert result.summary.gl_only == 1


@pytest.mark.asyncio
async def test_bank_only_created_for_unmatched_bank_transaction(
    async_session: AsyncSession,
    test_tenant,
    test_user,
):
    statement_id, _ = await _seed_statement(async_session, tenant_id=test_tenant.id, uploaded_by=test_user.id)
    await _add_bank_txn(
        async_session,
        tenant_id=test_tenant.id,
        statement_id=statement_id,
        txn_date=date(2025, 5, 10),
        description="Unmatched receipt",
        signed_amount=Decimal("900.00"),
    )

    result = await _run_recon(async_session, tenant_id=test_tenant.id, statement_id=statement_id, run_by=test_user.id)

    assert result.summary.bank_only == 1
    assert result.items[0].item_type == "bank_only"


@pytest.mark.asyncio
async def test_gl_only_created_for_unmatched_gl_entry(
    async_session: AsyncSession,
    test_tenant,
    test_user,
):
    statement_id, entity_id = await _seed_statement(async_session, tenant_id=test_tenant.id, uploaded_by=test_user.id)
    await _add_bank_txn(
        async_session,
        tenant_id=test_tenant.id,
        statement_id=statement_id,
        txn_date=date(2025, 5, 10),
        description="Receipt one",
        signed_amount=Decimal("1000.00"),
    )
    await _seed_gl_bank_line(
        async_session,
        tenant_id=test_tenant.id,
        entity_id=entity_id,
        created_by=test_user.id,
        posting_date=date(2025, 5, 10),
        signed_amount=Decimal("1000.00"),
        narration="Receipt one",
    )
    await _seed_gl_bank_line(
        async_session,
        tenant_id=test_tenant.id,
        entity_id=entity_id,
        created_by=test_user.id,
        posting_date=date(2025, 5, 12),
        signed_amount=Decimal("700.00"),
        narration="Extra unmatched line",
    )

    result = await _run_recon(async_session, tenant_id=test_tenant.id, statement_id=statement_id, run_by=test_user.id)

    assert result.summary.matched == 1
    assert result.summary.gl_only == 1
    assert any(item.item_type == "gl_only" for item in result.items)


@pytest.mark.asyncio
async def test_net_difference_is_decimal_not_float(
    async_session: AsyncSession,
    test_tenant,
    test_user,
):
    statement_id, entity_id = await _seed_statement(async_session, tenant_id=test_tenant.id, uploaded_by=test_user.id)
    await _add_bank_txn(
        async_session,
        tenant_id=test_tenant.id,
        statement_id=statement_id,
        txn_date=date(2025, 5, 10),
        description="Unmatched bank",
        signed_amount=Decimal("1000.00"),
    )
    await _seed_gl_bank_line(
        async_session,
        tenant_id=test_tenant.id,
        entity_id=entity_id,
        created_by=test_user.id,
        posting_date=date(2025, 5, 12),
        signed_amount=Decimal("400.00"),
        narration="Far away GL line",
    )

    result = await _run_recon(async_session, tenant_id=test_tenant.id, statement_id=statement_id, run_by=test_user.id)

    assert isinstance(result.summary.net_difference, Decimal)
    assert result.summary.net_difference == Decimal("600.00")


@pytest.mark.asyncio
async def test_rerun_creates_new_items_original_items_unchanged(
    async_session: AsyncSession,
    test_tenant,
    test_user,
):
    statement_id, entity_id = await _seed_statement(async_session, tenant_id=test_tenant.id, uploaded_by=test_user.id)
    await _add_bank_txn(
        async_session,
        tenant_id=test_tenant.id,
        statement_id=statement_id,
        txn_date=date(2025, 5, 10),
        description="Receipt",
        signed_amount=Decimal("1000.00"),
    )
    await _seed_gl_bank_line(
        async_session,
        tenant_id=test_tenant.id,
        entity_id=entity_id,
        created_by=test_user.id,
        posting_date=date(2025, 5, 10),
        signed_amount=Decimal("1000.00"),
        narration="Receipt",
    )

    first = await _run_recon(async_session, tenant_id=test_tenant.id, statement_id=statement_id, run_by=test_user.id)
    second = await _run_recon(
        async_session,
        tenant_id=test_tenant.id,
        statement_id=statement_id,
        run_by=test_user.id,
        force_rerun=True,
    )

    assert len(first.items) == 1
    assert len(second.items) == 1
    all_items = (
        await async_session.execute(
            select(BankReconItem).where(
                BankReconItem.tenant_id == test_tenant.id,
                BankReconItem.statement_id == statement_id,
            )
        )
    ).scalars().all()
    assert len(all_items) == 2


@pytest.mark.asyncio
async def test_duplicate_statement_raises_not_processes_twice(
    async_session: AsyncSession,
    test_tenant,
    test_user,
):
    statement_id, _ = await _seed_statement(async_session, tenant_id=test_tenant.id, uploaded_by=test_user.id)
    await _add_bank_txn(
        async_session,
        tenant_id=test_tenant.id,
        statement_id=statement_id,
        txn_date=date(2025, 5, 10),
        description="Receipt",
        signed_amount=Decimal("1000.00"),
    )

    await _run_recon(async_session, tenant_id=test_tenant.id, statement_id=statement_id, run_by=test_user.id)

    with pytest.raises(StatementAlreadyProcessedError):
        await _run_recon(async_session, tenant_id=test_tenant.id, statement_id=statement_id, run_by=test_user.id)


@pytest.mark.asyncio
async def test_rls_tenant_a_cannot_see_tenant_b_recon_items(
    async_session: AsyncSession,
    test_tenant,
    test_user,
):
    statement_id, _ = await _seed_statement(async_session, tenant_id=test_tenant.id, uploaded_by=test_user.id)
    await _add_bank_txn(
        async_session,
        tenant_id=test_tenant.id,
        statement_id=statement_id,
        txn_date=date(2025, 5, 10),
        description="Tenant A receipt",
        signed_amount=Decimal("1000.00"),
    )
    await _run_recon(async_session, tenant_id=test_tenant.id, statement_id=statement_id, run_by=test_user.id)

    other_tenant_id = uuid.uuid4()
    items = await list_bank_recon_items(async_session, tenant_id=other_tenant_id)
    assert items == []


@pytest.mark.asyncio
async def test_zero_transactions_returns_empty_summary(
    async_session: AsyncSession,
    test_tenant,
    test_user,
):
    statement_id, _ = await _seed_statement(async_session, tenant_id=test_tenant.id, uploaded_by=test_user.id)

    result = await _run_recon(async_session, tenant_id=test_tenant.id, statement_id=statement_id, run_by=test_user.id)

    assert result.items == []
    assert result.summary == type(result.summary)()
