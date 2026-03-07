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
from financeops.services.audit_writer import AuditEvent, AuditWriter
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
        balance = await AuditWriter.insert_record(
            session,
            record=CreditBalance(
                tenant_id=tenant_id,
                balance=Decimal("0"),
                reserved=Decimal("0"),
            ),
            audit=AuditEvent(
                tenant_id=tenant_id,
                action="credits.balance.created",
                resource_type="credit_balance",
                new_value={"balance": "0", "reserved": "0"},
            ),
        )
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
        balance = await AuditWriter.insert_record(
            session,
            record=CreditBalance(
                tenant_id=tenant_id,
                balance=Decimal("0"),
                reserved=Decimal("0"),
            ),
            audit=AuditEvent(
                tenant_id=tenant_id,
                action="credits.balance.created",
                resource_type="credit_balance",
                new_value={"balance": "0", "reserved": "0"},
            ),
        )
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

    old_balance_state = {
        "balance": str(balance.balance),
        "reserved": str(balance.reserved),
        "available": str(balance.available),
    }
    balance.reserved = balance.reserved + amount
    balance.updated_at = datetime.now(timezone.utc)

    reservation = await AuditWriter.insert_record(
        session,
        record=CreditReservation(
            tenant_id=tenant_id,
            amount=amount,
            task_type=task_type,
            status=ReservationStatus.pending,
            expires_at=datetime.now(timezone.utc)
            + timedelta(minutes=_RESERVATION_TTL_MINUTES),
        ),
        audit=AuditEvent(
            tenant_id=tenant_id,
            action="credits.reservation.created",
            resource_type="credit_reservation",
            new_value={"task_type": task_type, "amount": str(amount)},
        ),
    )
    await AuditWriter.flush_with_audit(
        session,
        audit=AuditEvent(
            tenant_id=tenant_id,
            action="credits.balance.reserved",
            resource_type="credit_balance",
            resource_id=str(balance.id),
            old_value=old_balance_state,
            new_value={
                "balance": str(balance.balance),
                "reserved": str(balance.reserved),
                "available": str(balance.available),
            },
        ),
    )
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

    old_reservation_status = reservation.status.value
    old_balance_state = {
        "balance": str(balance.balance),
        "reserved": str(balance.reserved),
        "available": str(balance.available),
    }
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
    tx = await AuditWriter.insert_record(
        session,
        record=tx,
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=user_id,
            action="credits.transaction.confirmed",
            resource_type="credit_transaction",
            new_value={
                "task_type": reservation.task_type,
                "amount": str(reservation.amount),
                "direction": CreditDirection.debit.value,
            },
        ),
    )
    await AuditWriter.flush_with_audit(
        session,
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=user_id,
            action="credits.reservation.confirmed",
            resource_type="credit_reservation",
            resource_id=str(reservation.id),
            old_value={
                "status": old_reservation_status,
                **old_balance_state,
            },
            new_value={
                "status": reservation.status.value,
                "balance": str(balance.balance),
                "reserved": str(balance.reserved),
                "available": str(balance.available),
            },
        ),
    )
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

    old_reservation_status = reservation.status.value
    old_balance_state = {
        "balance": str(balance.balance),
        "reserved": str(balance.reserved),
        "available": str(balance.available),
    }
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
    tx = await AuditWriter.insert_record(
        session,
        record=tx,
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=user_id,
            action="credits.transaction.released",
            resource_type="credit_transaction",
            new_value={
                "task_type": reservation.task_type,
                "amount": str(reservation.amount),
                "direction": CreditDirection.credit.value,
            },
        ),
    )
    await AuditWriter.flush_with_audit(
        session,
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=user_id,
            action="credits.reservation.released",
            resource_type="credit_reservation",
            resource_id=str(reservation.id),
            old_value={
                "status": old_reservation_status,
                **old_balance_state,
            },
            new_value={
                "status": reservation.status.value,
                "balance": str(balance.balance),
                "reserved": str(balance.reserved),
                "available": str(balance.available),
            },
        ),
    )
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
        balance = await AuditWriter.insert_record(
            session,
            record=CreditBalance(
                tenant_id=tenant_id,
                balance=Decimal("0"),
                reserved=Decimal("0"),
            ),
            audit=AuditEvent(
                tenant_id=tenant_id,
                action="credits.balance.created",
                resource_type="credit_balance",
                new_value={"balance": "0", "reserved": "0"},
            ),
        )
        balance_result = await session.execute(
            select(CreditBalance)
            .where(CreditBalance.tenant_id == tenant_id)
            .with_for_update()
        )
        balance = balance_result.scalar_one()

    old_balance_state = {
        "balance": str(balance.balance),
        "reserved": str(balance.reserved),
        "available": str(balance.available),
    }
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
    tx = await AuditWriter.insert_record(
        session,
        record=tx,
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=user_id,
            action="credits.transaction.created",
            resource_type="credit_transaction",
            new_value={
                "task_type": reason,
                "amount": str(amount),
                "direction": CreditDirection.credit.value,
            },
        ),
    )
    await AuditWriter.flush_with_audit(
        session,
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=user_id,
            action="credits.balance.added",
            resource_type="credit_balance",
            resource_id=str(balance.id),
            old_value=old_balance_state,
            new_value={
                "balance": str(balance.balance),
                "reserved": str(balance.reserved),
                "available": str(balance.available),
            },
        ),
    )
    log.info(
        "Credits added: tenant=%s amount=%s reason=%s",
        str(tenant_id)[:8],
        amount,
        reason,
    )
    return tx
