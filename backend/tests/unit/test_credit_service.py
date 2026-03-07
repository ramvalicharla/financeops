from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import InsufficientCreditsError
from financeops.db.models.credits import CreditBalance, CreditDirection
from financeops.services.audit_writer import AuditWriter
from financeops.services.credit_service import (
    add_credits,
    check_balance,
    confirm_credits,
    get_balance,
    release_credits,
    reserve_credits,
)


@pytest.mark.asyncio
async def test_get_balance_creates_zero_balance_if_missing(async_session: AsyncSession):
    tenant_id = uuid.uuid4()
    balance = await get_balance(async_session, tenant_id)
    assert balance.balance == Decimal("0")
    assert balance.reserved == Decimal("0")
    assert balance.available == Decimal("0")


@pytest.mark.asyncio
async def test_add_credits_increases_balance(async_session: AsyncSession):
    tenant_id = uuid.uuid4()
    tx = await add_credits(async_session, tenant_id, Decimal("500"), "test_topup")
    assert tx.amount == Decimal("500")
    assert tx.direction == CreditDirection.credit

    balance = await get_balance(async_session, tenant_id)
    assert balance.balance == Decimal("500")
    assert balance.available == Decimal("500")


@pytest.mark.asyncio
async def test_reserve_credits_reduces_available(async_session: AsyncSession):
    tenant_id = uuid.uuid4()
    await add_credits(async_session, tenant_id, Decimal("100"), "topup")

    reservation_id = await reserve_credits(
        async_session, tenant_id, "classification", Decimal("10")
    )
    balance = await get_balance(async_session, tenant_id)
    assert balance.reserved == Decimal("10")
    assert balance.available == Decimal("90")


@pytest.mark.asyncio
async def test_reserve_credits_raises_when_insufficient(async_session: AsyncSession):
    tenant_id = uuid.uuid4()
    await add_credits(async_session, tenant_id, Decimal("5"), "topup")

    with pytest.raises(InsufficientCreditsError):
        await reserve_credits(
            async_session, tenant_id, "advisory", Decimal("100")
        )


@pytest.mark.asyncio
async def test_confirm_credits_debits_balance(async_session: AsyncSession):
    tenant_id = uuid.uuid4()
    await add_credits(async_session, tenant_id, Decimal("50"), "topup")

    reservation_id = await reserve_credits(
        async_session, tenant_id, "classification", Decimal("10")
    )
    tx = await confirm_credits(async_session, tenant_id, reservation_id)
    assert tx.direction == CreditDirection.debit
    assert tx.amount == Decimal("10")

    balance = await get_balance(async_session, tenant_id)
    assert balance.balance == Decimal("40")
    assert balance.reserved == Decimal("0")
    assert balance.available == Decimal("40")


@pytest.mark.asyncio
async def test_release_credits_restores_available(async_session: AsyncSession):
    tenant_id = uuid.uuid4()
    await add_credits(async_session, tenant_id, Decimal("50"), "topup")

    reservation_id = await reserve_credits(
        async_session, tenant_id, "classification", Decimal("10")
    )
    tx = await release_credits(async_session, tenant_id, reservation_id)
    assert tx.direction == CreditDirection.credit

    balance = await get_balance(async_session, tenant_id)
    assert balance.balance == Decimal("50")
    assert balance.reserved == Decimal("0")
    assert balance.available == Decimal("50")


@pytest.mark.asyncio
async def test_credit_transaction_has_chain_hash(async_session: AsyncSession):
    tenant_id = uuid.uuid4()
    tx = await add_credits(async_session, tenant_id, Decimal("100"), "topup")
    assert len(tx.chain_hash) == 64
    assert tx.previous_hash == "0" * 64  # Genesis hash for first record


@pytest.mark.asyncio
async def test_check_balance_returns_true_when_sufficient(async_session: AsyncSession):
    tenant_id = uuid.uuid4()
    await add_credits(async_session, tenant_id, Decimal("100"), "topup")
    result = await check_balance(async_session, tenant_id, Decimal("50"))
    assert result is True


@pytest.mark.asyncio
async def test_check_balance_returns_false_when_insufficient(async_session: AsyncSession):
    tenant_id = uuid.uuid4()
    await add_credits(async_session, tenant_id, Decimal("10"), "topup")
    result = await check_balance(async_session, tenant_id, Decimal("100"))
    assert result is False


@pytest.mark.asyncio
async def test_add_credits_uses_audit_writer(async_session: AsyncSession):
    tenant_id = uuid.uuid4()
    with patch(
        "financeops.services.credit_service.AuditWriter.insert_record",
        wraps=AuditWriter.insert_record,
    ) as insert_spy:
        with patch(
            "financeops.services.credit_service.AuditWriter.flush_with_audit",
            wraps=AuditWriter.flush_with_audit,
        ) as flush_spy:
            await add_credits(async_session, tenant_id, Decimal("25"), "audit_topup")
    assert insert_spy.await_count >= 1
    assert flush_spy.await_count >= 1


@pytest.mark.asyncio
async def test_reserve_confirm_release_use_audit_writer(async_session: AsyncSession):
    tenant_id = uuid.uuid4()
    await add_credits(async_session, tenant_id, Decimal("100"), "seed")
    reservation_id = await reserve_credits(
        async_session, tenant_id, "classification", Decimal("10")
    )

    with patch(
        "financeops.services.credit_service.AuditWriter.insert_record",
        wraps=AuditWriter.insert_record,
    ) as insert_spy:
        with patch(
            "financeops.services.credit_service.AuditWriter.flush_with_audit",
            wraps=AuditWriter.flush_with_audit,
        ) as flush_spy:
            await confirm_credits(async_session, tenant_id, reservation_id)
    assert insert_spy.await_count >= 1
    assert flush_spy.await_count >= 1

    reservation_id_2 = await reserve_credits(
        async_session, tenant_id, "classification", Decimal("5")
    )
    with patch(
        "financeops.services.credit_service.AuditWriter.insert_record",
        wraps=AuditWriter.insert_record,
    ) as insert_spy:
        with patch(
            "financeops.services.credit_service.AuditWriter.flush_with_audit",
            wraps=AuditWriter.flush_with_audit,
        ) as flush_spy:
            await release_credits(async_session, tenant_id, reservation_id_2)
    assert insert_spy.await_count >= 1
    assert flush_spy.await_count >= 1
