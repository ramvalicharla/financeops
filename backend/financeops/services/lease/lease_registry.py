from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import ValidationError
from financeops.db.models.lease import Lease
from financeops.schemas.lease import LeaseInput
from financeops.services.accounting_common.quantization_policy import quantize_rate
from financeops.services.audit_writer import AuditEvent, AuditWriter
from financeops.services.fx.normalization import normalize_currency_code


@dataclass(frozen=True)
class RegisteredLease:
    lease_id: UUID
    lease_number: str
    lease_currency: str
    commencement_date: date
    end_date: date
    payment_frequency: str
    initial_discount_rate: Decimal
    source_lease_reference: str


def _lease_fingerprint(lease: LeaseInput) -> tuple[str, str, str]:
    return (
        lease.lease_number,
        lease.source_lease_reference,
        lease.policy_version,
    )


async def register_leases(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID,
    correlation_id: str,
    leases: Iterable[LeaseInput],
) -> list[RegisteredLease]:
    registered: list[RegisteredLease] = []
    seen_fingerprints: set[tuple[str, str, str]] = set()

    for lease in leases:
        fingerprint = _lease_fingerprint(lease)
        if fingerprint in seen_fingerprints:
            raise ValidationError("Duplicate lease fingerprint in request payload")
        seen_fingerprints.add(fingerprint)

        existing_result = await session.execute(
            select(Lease)
            .where(
                Lease.tenant_id == tenant_id,
                Lease.lease_number == lease.lease_number,
                Lease.source_lease_reference == lease.source_lease_reference,
                Lease.policy_version == lease.policy_version,
                Lease.correlation_id == correlation_id,
            )
            .order_by(Lease.created_at)
            .limit(1)
        )
        existing = existing_result.scalar_one_or_none()
        if existing is not None:
            registered.append(
                RegisteredLease(
                    lease_id=existing.id,
                    lease_number=existing.lease_number,
                    lease_currency=existing.lease_currency,
                    commencement_date=existing.commencement_date,
                    end_date=existing.end_date,
                    payment_frequency=existing.payment_frequency,
                    initial_discount_rate=existing.initial_discount_rate,
                    source_lease_reference=existing.source_lease_reference,
                )
            )
            continue

        created = await AuditWriter.insert_financial_record(
            session,
            model_class=Lease,
            tenant_id=tenant_id,
            record_data={
                "lease_number": lease.lease_number,
                "counterparty_id": lease.counterparty_id,
                "lease_currency": lease.lease_currency,
                "source_lease_reference": lease.source_lease_reference,
            },
            values={
                "lease_number": lease.lease_number,
                "counterparty_id": lease.counterparty_id,
                "lease_currency": normalize_currency_code(lease.lease_currency),
                "commencement_date": lease.commencement_date,
                "end_date": lease.end_date,
                "payment_frequency": lease.payment_frequency.value,
                "initial_discount_rate": quantize_rate(lease.initial_discount_rate),
                "discount_rate_source": lease.discount_rate_source,
                "discount_rate_reference_date": lease.discount_rate_reference_date,
                "discount_rate_policy_code": lease.discount_rate_policy_code,
                "initial_measurement_basis": lease.initial_measurement_basis,
                "source_lease_reference": lease.source_lease_reference,
                "policy_code": lease.policy_code,
                "policy_version": lease.policy_version,
                "parent_reference_id": None,
                "source_reference_id": None,
                "correlation_id": correlation_id,
                "supersedes_id": None,
            },
            audit=AuditEvent(
                tenant_id=tenant_id,
                user_id=user_id,
                action="lease.contract.created",
                resource_type="lease",
                new_value={
                    "lease_number": lease.lease_number,
                    "source_lease_reference": lease.source_lease_reference,
                    "correlation_id": correlation_id,
                },
            ),
        )

        registered.append(
            RegisteredLease(
                lease_id=created.id,
                lease_number=created.lease_number,
                lease_currency=created.lease_currency,
                commencement_date=created.commencement_date,
                end_date=created.end_date,
                payment_frequency=created.payment_frequency,
                initial_discount_rate=created.initial_discount_rate,
                source_lease_reference=created.source_lease_reference,
            )
        )

    registered.sort(key=lambda item: (item.lease_number, str(item.lease_id)))
    return registered
