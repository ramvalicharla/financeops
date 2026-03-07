from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import ValidationError
from financeops.db.models.lease import LeasePayment
from financeops.schemas.lease import LeaseInput
from financeops.services.accounting_common.quantization_policy import quantize_persisted_amount
from financeops.services.audit_writer import AuditEvent, AuditWriter
from financeops.services.lease.lease_registry import RegisteredLease


@dataclass(frozen=True)
class RegisteredLeasePayment:
    payment_id: UUID
    lease_id: UUID
    lease_number: str
    payment_date: date
    payment_amount_lease_currency: Decimal
    payment_type: str
    payment_sequence: int
    source_lease_reference: str


async def register_lease_payments(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID,
    correlation_id: str,
    leases: Iterable[LeaseInput],
    registered_leases: list[RegisteredLease],
) -> list[RegisteredLeasePayment]:
    lease_by_number = {item.lease_number: item for item in registered_leases}
    payments: list[RegisteredLeasePayment] = []

    for lease_input in sorted(leases, key=lambda item: item.lease_number):
        registered_lease = lease_by_number.get(lease_input.lease_number)
        if registered_lease is None:
            raise ValidationError("Lease was not registered before payment tracking")

        ordered_payments = sorted(
            lease_input.payments,
            key=lambda item: (item.payment_sequence, item.payment_date),
        )

        for payment in ordered_payments:
            existing_result = await session.execute(
                select(LeasePayment)
                .where(
                    LeasePayment.tenant_id == tenant_id,
                    LeasePayment.lease_id == registered_lease.lease_id,
                    LeasePayment.payment_sequence == payment.payment_sequence,
                    LeasePayment.correlation_id == correlation_id,
                )
                .order_by(LeasePayment.created_at)
                .limit(1)
            )
            existing = existing_result.scalar_one_or_none()

            if existing is None:
                existing = await AuditWriter.insert_financial_record(
                    session,
                    model_class=LeasePayment,
                    tenant_id=tenant_id,
                    record_data={
                        "lease_id": str(registered_lease.lease_id),
                        "payment_sequence": payment.payment_sequence,
                        "payment_date": payment.payment_date.isoformat(),
                        "payment_amount_lease_currency": str(payment.payment_amount_lease_currency),
                    },
                    values={
                        "lease_id": registered_lease.lease_id,
                        "payment_date": payment.payment_date,
                        "payment_amount_lease_currency": quantize_persisted_amount(
                            payment.payment_amount_lease_currency
                        ),
                        "payment_type": payment.payment_type,
                        "payment_sequence": payment.payment_sequence,
                        "source_lease_reference": lease_input.source_lease_reference,
                        "parent_reference_id": registered_lease.lease_id,
                        "source_reference_id": registered_lease.lease_id,
                        "correlation_id": correlation_id,
                        "supersedes_id": None,
                    },
                    audit=AuditEvent(
                        tenant_id=tenant_id,
                        user_id=user_id,
                        action="lease.payment.created",
                        resource_type="lease_payment",
                        new_value={
                            "lease_id": str(registered_lease.lease_id),
                            "payment_sequence": payment.payment_sequence,
                            "correlation_id": correlation_id,
                        },
                    ),
                )

            payments.append(
                RegisteredLeasePayment(
                    payment_id=existing.id,
                    lease_id=existing.lease_id,
                    lease_number=registered_lease.lease_number,
                    payment_date=existing.payment_date,
                    payment_amount_lease_currency=existing.payment_amount_lease_currency,
                    payment_type=existing.payment_type,
                    payment_sequence=existing.payment_sequence,
                    source_lease_reference=existing.source_lease_reference,
                )
            )

    payments.sort(key=lambda item: (item.lease_number, item.payment_sequence, item.payment_date))
    return payments


def build_payment_timeline(
    *,
    lease_id: UUID,
    payments: list[RegisteredLeasePayment],
) -> list[RegisteredLeasePayment]:
    timeline = sorted(
        [item for item in payments if item.lease_id == lease_id],
        key=lambda item: (item.payment_sequence, item.payment_date, str(item.payment_id)),
    )
    for idx in range(1, len(timeline)):
        previous = timeline[idx - 1]
        current = timeline[idx]
        if current.payment_sequence < previous.payment_sequence:
            raise ValidationError("Lease payment timeline sequence regression detected")
        if current.payment_sequence == previous.payment_sequence and current.payment_date < previous.payment_date:
            raise ValidationError("Lease payment timeline date regression detected")
    return timeline
