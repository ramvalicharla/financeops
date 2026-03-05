from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import InsufficientCreditsError
from financeops.db.models.credits import (
    CreditBalance,
    CreditDirection,
    CreditReservation,
    CreditTransaction,
    CreditTransactionStatus,
    ReservationStatus,
)
from financeops.utils.chain_hash import GENESIS_HASH, compute_chain_hash, get_previous_hash

log = logging.getLogger(__name__)

_RESERVATION_TTL_MINUTES = 30


async def get_balance(session: AsyncSession, tenant_id: uuid.UUID) -> CreditBalance:
    """Return the current credit balance row for a tenant."""
    result = await session.execute(
        select(CreditBalance).where(CreditBalance.tenant_id == tenant_id)
    )
    balance = result.scalar_one_or_none()
    if balance is None:
        balance = CreditBalance(tenant_id=tenant_id, balance=Decimal("0"), reserved=Decimal("0"))
        session.add(balance)
        await session.flush()
    return balance


async def check_balance(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    required_credits: Decimal,
) -> bool:
    """Return True if tenant has sufficient available credits."""
    balance = await get_balance(session, tenant_id)
    return balance.available >= required_credits


async def reserve_credits(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    task_type: str,
    amount: Decimal,
) -> uuid.UUID:
    """
    Atomically reserve credits for a pending task.
    Uses SELECT FOR UPDATE to prevent concurrent overdraw.
    Returns: reservation_id UUID.
    Raises: InsufficientCreditsError if balance insufficient.
    """
    # SELECT FOR UPDATE prevents concurrent overdraw
    result = await session.execute(
        select(CreditBalance)
        .where(CreditBalance.tenant_id == tenant_id)
        .with_for_update()
    )
    balance = result.scalar_one_or_none()
    if balance is None:
        balance = CreditBalance(tenant_id=tenant_id, balance=Decimal("0"), reserved=Decimal("0"))
        session.add(balance)
        await session.flush()
        # Re-fetch with lock
        result = await session.execute(
            select(CreditBalance)
            .where(CreditBalance.tenant_id == tenant_id)
            .with_for_update()
        )
        balance = result.scalar_one()

    if balance.available < amount:
        raise InsufficientCreditsError(
            f"Required {amount} credits but only {balance.available} available"
        )

    balance.reserved = balance.reserved + amount
    balance.updated_at = datetime.now(timezone.utc)

    reservation = CreditReservation(
        tenant_id=tenant_id,
        amount=amount,
        task_type=task_type,
        status=ReservationStatus.pending,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=_RESERVATION_TTL_MINUTES),
    )
    session.add(reservation)
    await session.flush()
    log.info(
        "Credits reserved: tenant=%s amount=%s reservation=%s",
        str(tenant_id)[:8],
        amount,
        reservation.id,
    )
    return reservation.id


async def confirm_credits(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    reservation_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
) -> CreditTransaction:
    """
    Confirm a reservation: deduct from balance and create immutable transaction record.
    """
    result = await session.execute(
        select(CreditReservation)
        .where(
            CreditReservation.id == reservation_id,
            CreditReservation.tenant_id == tenant_id,
            CreditReservation.status == ReservationStatus.pending,
        )
        .with_for_update()
    )
    reservation = result.scalar_one_or_none()
    if reservation is None:
        raise ValueError(f"Reservation {reservation_id} not found or already processed")

    balance_result = await session.execute(
        select(CreditBalance)
        .where(CreditBalance.tenant_id == tenant_id)
        .with_for_update()
    )
    balance = balance_result.scalar_one()

    balance_before = balance.balance
    balance.balance = balance.balance - reservation.amount
    balance.reserved = balance.reserved - reservation.amount
    balance.updated_at = datetime.now(timezone.utc)

    reservation.status = ReservationStatus.confirmed

    previous_hash = await get_previous_hash(session, CreditTransaction, tenant_id)
    record_data = {
        "tenant_id": str(tenant_id),
        "task_type": reservation.task_type,
        "amount": str(reservation.amount),
        "direction": CreditDirection.debit.value,
        "balance_before": str(balance_before),
        "balance_after": str(balance.balance),
        "reservation_id": str(reservation_id),
    }
    chain_hash = compute_chain_hash(record_data, previous_hash)

    tx = CreditTransaction(
        tenant_id=tenant_id,
        user_id=user_id,
        task_type=reservation.task_type,
        amount=reservation.amount,
        direction=CreditDirection.debit,
        balance_before=balance_before,
        balance_after=balance.balance,
        reservation_id=reservation_id,
        status=CreditTransactionStatus.confirmed,
        chain_hash=chain_hash,
        previous_hash=previous_hash,
    )
    session.add(tx)
    await session.flush()
    return tx


async def release_credits(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    reservation_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
) -> CreditTransaction:
    """
    Release a reservation on task failure: restore available balance.
    Creates a CreditTransaction with direction=credit to record the release.
    """
    result = await session.execute(
        select(CreditReservation)
        .where(
            CreditReservation.id == reservation_id,
            CreditReservation.tenant_id == tenant_id,
            CreditReservation.status == ReservationStatus.pending,
        )
        .with_for_update()
    )
    reservation = result.scalar_one_or_none()
    if reservation is None:
        raise ValueError(f"Reservation {reservation_id} not found or already processed")

    balance_result = await session.execute(
        select(CreditBalance)
        .where(CreditBalance.tenant_id == tenant_id)
        .with_for_update()
    )
    balance = balance_result.scalar_one()

    balance_before = balance.balance
    balance.reserved = balance.reserved - reservation.amount
    balance.updated_at = datetime.now(timezone.utc)

    reservation.status = ReservationStatus.released

    previous_hash = await get_previous_hash(session, CreditTransaction, tenant_id)
    record_data = {
        "tenant_id": str(tenant_id),
        "task_type": reservation.task_type,
        "amount": str(reservation.amount),
        "direction": CreditDirection.credit.value,
        "balance_before": str(balance_before),
        "balance_after": str(balance.balance),
        "reservation_id": str(reservation_id),
    }
    chain_hash = compute_chain_hash(record_data, previous_hash)

    tx = CreditTransaction(
        tenant_id=tenant_id,
        user_id=user_id,
        task_type=reservation.task_type,
        amount=reservation.amount,
        direction=CreditDirection.credit,
        balance_before=balance_before,
        balance_after=balance.balance,
        reservation_id=reservation_id,
        status=CreditTransactionStatus.released,
        chain_hash=chain_hash,
        previous_hash=previous_hash,
    )
    session.add(tx)
    await session.flush()
    log.info(
        "Credits released: tenant=%s reservation=%s amount=%s",
        str(tenant_id)[:8],
        reservation_id,
        reservation.amount,
    )
    return tx


async def add_credits(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    amount: Decimal,
    reason: str,
    user_id: uuid.UUID | None = None,
) -> CreditTransaction:
    """
    Add credits to a tenant balance (purchase / manual top-up).
    Creates an immutable CreditTransaction record with chain hash.
    """
    balance_result = await session.execute(
        select(CreditBalance)
        .where(CreditBalance.tenant_id == tenant_id)
        .with_for_update()
    )
    balance = balance_result.scalar_one_or_none()
    if balance is None:
        balance = CreditBalance(tenant_id=tenant_id, balance=Decimal("0"), reserved=Decimal("0"))
        session.add(balance)
        await session.flush()
        balance_result = await session.execute(
            select(CreditBalance)
            .where(CreditBalance.tenant_id == tenant_id)
            .with_for_update()
        )
        balance = balance_result.scalar_one()

    balance_before = balance.balance
    balance.balance = balance.balance + amount
    balance.updated_at = datetime.now(timezone.utc)

    previous_hash = await get_previous_hash(session, CreditTransaction, tenant_id)
    record_data = {
        "tenant_id": str(tenant_id),
        "task_type": reason,
        "amount": str(amount),
        "direction": CreditDirection.credit.value,
        "balance_before": str(balance_before),
        "balance_after": str(balance.balance),
    }
    chain_hash = compute_chain_hash(record_data, previous_hash)

    tx = CreditTransaction(
        tenant_id=tenant_id,
        user_id=user_id,
        task_type=reason,
        amount=amount,
        direction=CreditDirection.credit,
        balance_before=balance_before,
        balance_after=balance.balance,
        reservation_id=None,
        status=CreditTransactionStatus.confirmed,
        chain_hash=chain_hash,
        previous_hash=previous_hash,
    )
    session.add(tx)
    await session.flush()
    log.info(
        "Credits added: tenant=%s amount=%s reason=%s",
        str(tenant_id)[:8],
        amount,
        reason,
    )
    return tx
