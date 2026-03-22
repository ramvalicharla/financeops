from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.lease import Lease, LeaseLiabilitySchedule, LeaseModification
from financeops.schemas.lease import LeaseInput, LeaseModificationInput
from financeops.services.accounting_common.accounting_errors import AccountingValidationError
from financeops.services.accounting_common.error_codes import (
    DUPLICATE_IDEMPOTENT_REQUEST,
    VERSION_CHAIN_BROKEN,
)
from financeops.services.accounting_common.quantization_policy import quantize_persisted_amount, quantize_rate
from financeops.services.accounting_common.supersession_validator import (
    SupersessionNode,
    ensure_append_targets_terminal,
    validate_linear_chain,
)
from financeops.services.audit_writer import AuditEvent, AuditWriter
from financeops.services.lease.lease_registry import RegisteredLease
from financeops.utils.determinism import canonical_json_dumps, sha256_hex_text


@dataclass(frozen=True)
class PersistedLeaseModification:
    modification_id: UUID
    lease_id: UUID
    effective_date: object
    modification_type: str
    idempotency_key: str
    prior_schedule_version_token: str
    new_schedule_version_token: str
    remeasurement_delta_reporting_currency: Decimal


@dataclass(frozen=True)
class LeaseRemeasurementResult:
    modification_count: int
    modifications_by_lease: dict[UUID, list[PersistedLeaseModification]]


def build_schedule_version_token(
    *,
    lease_id: UUID,
    modification_payload_normalized: dict[str, str | bool | None],
    reporting_currency: str,
    rate_mode: str,
    prior_version_token_or_root: str,
) -> str:
    payload = {
        "lease_id": str(lease_id),
        "modification_payload_normalized": modification_payload_normalized,
        "reporting_currency": reporting_currency,
        "rate_mode": rate_mode,
        "prior_version_token_or_root": prior_version_token_or_root,
    }
    return sha256_hex_text(canonical_json_dumps(payload))


def _normalized_modification_payload(modification: LeaseModificationInput) -> dict[str, str | bool | None]:
    return {
        "effective_date": modification.effective_date.isoformat(),
        "modification_type": modification.modification_type,
        "modification_reason": modification.modification_reason,
        "new_discount_rate": (
            f"{quantize_rate(modification.new_discount_rate):.6f}"
            if modification.new_discount_rate is not None
            else None
        ),
        "new_end_date": modification.new_end_date.isoformat() if modification.new_end_date is not None else None,
        "remeasurement_delta_reporting_currency": (
            f"{quantize_persisted_amount(modification.remeasurement_delta_reporting_currency):.6f}"
            if modification.remeasurement_delta_reporting_currency is not None
            else None
        ),
    }


def _idempotency_key(*, lease_id: UUID, modification: LeaseModificationInput) -> str:
    payload = {
        "lease_id": str(lease_id),
        "modification": _normalized_modification_payload(modification),
    }
    return sha256_hex_text(canonical_json_dumps(payload))


async def _load_lease_chain(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    lease_number: str,
    source_lease_reference: str,
) -> list[SupersessionNode]:
    rows = (
        await session.execute(
            select(Lease)
            .where(
                Lease.tenant_id == tenant_id,
                Lease.lease_number == lease_number,
                Lease.source_lease_reference == source_lease_reference,
            )
            .order_by(Lease.created_at, Lease.id)
        )
    ).scalars().all()
    return [
        SupersessionNode(
            id=row.id,
            tenant_id=row.tenant_id,
            created_at=row.created_at,
            supersedes_id=row.supersedes_id,
        )
        for row in rows
    ]


async def _resolve_latest_token_for_lease(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    lease_id: UUID,
    root_schedule_version_token: str,
) -> str:
    latest = (
        await session.execute(
            select(LeaseModification)
            .where(
                LeaseModification.tenant_id == tenant_id,
                LeaseModification.run_id == run_id,
                LeaseModification.lease_id == lease_id,
            )
            .order_by(
                desc(LeaseModification.effective_date),
                desc(LeaseModification.created_at),
                desc(LeaseModification.id),
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if latest is None:
        return root_schedule_version_token
    return latest.new_schedule_version_token


async def apply_lease_modifications(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID,
    run_id: UUID,
    correlation_id: str,
    leases: Iterable[LeaseInput],
    registered_leases: list[RegisteredLease],
    root_schedule_version_tokens: dict[UUID, str],
    reporting_currency: str,
    rate_mode: str,
) -> LeaseRemeasurementResult:
    lease_state: dict[str, Lease] = {}
    for lease in registered_leases:
        model_result = await session.execute(
            select(Lease).where(
                Lease.tenant_id == tenant_id,
                Lease.id == lease.lease_id,
            )
        )
        model = model_result.scalar_one()
        lease_state[lease.lease_number] = model

    created_modifications = 0
    modifications_by_lease: dict[UUID, list[PersistedLeaseModification]] = {}

    for lease_input in sorted(leases, key=lambda item: item.lease_number):
        current_lease = lease_state[lease_input.lease_number]
        schedule_lease_id = current_lease.id
        root_token = root_schedule_version_tokens.get(schedule_lease_id)
        if root_token is None:
            raise AccountingValidationError(
                error_code=VERSION_CHAIN_BROKEN,
                message="Missing root lease schedule version token",
            )
        prior_token = root_token
        existing_chain_rows = (
            await session.execute(
                select(LeaseModification)
                .where(
                    LeaseModification.tenant_id == tenant_id,
                    LeaseModification.run_id == run_id,
                    LeaseModification.lease_id == schedule_lease_id,
                )
                .order_by(LeaseModification.created_at, LeaseModification.id)
            )
        ).scalars().all()
        modification_chain_nodes = [
            SupersessionNode(
                id=row.id,
                tenant_id=row.tenant_id,
                created_at=row.created_at,
                supersedes_id=row.supersedes_id,
            )
            for row in existing_chain_rows
        ]
        validate_linear_chain(nodes=modification_chain_nodes, tenant_id=tenant_id)
        chain_modifications: list[LeaseModification] = list(existing_chain_rows)
        persisted_for_lease: list[PersistedLeaseModification] = []

        ordered_modifications = sorted(
            lease_input.modifications,
            key=lambda item: (
                item.effective_date,
                item.modification_type,
                item.modification_reason,
                str(item.new_end_date) if item.new_end_date is not None else "",
            ),
        )
        for modification in ordered_modifications:
            ensure_append_targets_terminal(
                nodes=modification_chain_nodes,
                tenant_id=tenant_id,
                supersedes_id=chain_modifications[-1].id if chain_modifications else None,
            )
            idempotency_key = _idempotency_key(lease_id=schedule_lease_id, modification=modification)
            payload = _normalized_modification_payload(modification)

            existing_modification = (
                await session.execute(
                    select(LeaseModification).where(
                        LeaseModification.tenant_id == tenant_id,
                        LeaseModification.run_id == run_id,
                        LeaseModification.lease_id == schedule_lease_id,
                        LeaseModification.effective_date == modification.effective_date,
                        LeaseModification.modification_type == modification.modification_type,
                        LeaseModification.idempotency_key == idempotency_key,
                    )
                )
            ).scalar_one_or_none()
            if existing_modification is not None:
                expected_existing_token = build_schedule_version_token(
                    lease_id=schedule_lease_id,
                    modification_payload_normalized=payload,
                    reporting_currency=reporting_currency,
                    rate_mode=rate_mode,
                    prior_version_token_or_root=existing_modification.prior_schedule_version_token,
                )
                if existing_modification.new_schedule_version_token != expected_existing_token:
                    raise AccountingValidationError(
                        error_code=DUPLICATE_IDEMPOTENT_REQUEST,
                        message="Lease modification idempotency conflict",
                    )

                persisted = PersistedLeaseModification(
                    modification_id=existing_modification.id,
                    lease_id=schedule_lease_id,
                    effective_date=existing_modification.effective_date,
                    modification_type=existing_modification.modification_type,
                    idempotency_key=existing_modification.idempotency_key,
                    prior_schedule_version_token=existing_modification.prior_schedule_version_token,
                    new_schedule_version_token=existing_modification.new_schedule_version_token,
                    remeasurement_delta_reporting_currency=existing_modification.remeasurement_delta_reporting_currency,
                )
                persisted_for_lease.append(persisted)
                prior_token = existing_modification.new_schedule_version_token
                continue

            if prior_token == root_token and chain_modifications:
                prior_token = chain_modifications[-1].new_schedule_version_token

            new_token = build_schedule_version_token(
                lease_id=schedule_lease_id,
                modification_payload_normalized=payload,
                reporting_currency=reporting_currency,
                rate_mode=rate_mode,
                prior_version_token_or_root=prior_token,
            )

            updated_lease = current_lease
            target_discount_rate = (
                quantize_rate(modification.new_discount_rate)
                if modification.new_discount_rate is not None
                else current_lease.initial_discount_rate
            )
            target_end_date = modification.new_end_date or current_lease.end_date
            if (
                target_discount_rate != current_lease.initial_discount_rate
                or target_end_date != current_lease.end_date
            ):
                chain_nodes = await _load_lease_chain(
                    session,
                    tenant_id=tenant_id,
                    lease_number=current_lease.lease_number,
                    source_lease_reference=current_lease.source_lease_reference,
                )
                ensure_append_targets_terminal(
                    nodes=chain_nodes,
                    tenant_id=tenant_id,
                    supersedes_id=current_lease.id,
                )
                existing_superseding = (
                    await session.execute(
                        select(Lease)
                        .where(
                            Lease.tenant_id == tenant_id,
                            Lease.supersedes_id == current_lease.id,
                            Lease.initial_discount_rate == target_discount_rate,
                            Lease.end_date == target_end_date,
                            Lease.correlation_id == correlation_id,
                        )
                        .order_by(desc(Lease.created_at))
                        .limit(1)
                    )
                ).scalar_one_or_none()
                updated_lease = existing_superseding
                if updated_lease is None:
                    updated_lease = await AuditWriter.insert_financial_record(
                        session,
                        model_class=Lease,
                        tenant_id=tenant_id,
                        record_data={
                            "lease_number": current_lease.lease_number,
                            "source_lease_reference": current_lease.source_lease_reference,
                            "initial_discount_rate": str(target_discount_rate),
                        },
                        values={
                            "lease_number": current_lease.lease_number,
                            "counterparty_id": current_lease.counterparty_id,
                            "lease_currency": current_lease.lease_currency,
                            "commencement_date": current_lease.commencement_date,
                            "end_date": target_end_date,
                            "payment_frequency": current_lease.payment_frequency,
                            "initial_discount_rate": target_discount_rate,
                            "discount_rate_source": current_lease.discount_rate_source,
                            "discount_rate_reference_date": current_lease.discount_rate_reference_date,
                            "discount_rate_policy_code": current_lease.discount_rate_policy_code,
                            "initial_measurement_basis": current_lease.initial_measurement_basis,
                            "source_lease_reference": current_lease.source_lease_reference,
                            "policy_code": current_lease.policy_code,
                            "policy_version": current_lease.policy_version,
                            "parent_reference_id": current_lease.parent_reference_id,
                            "source_reference_id": current_lease.source_reference_id,
                            "correlation_id": correlation_id,
                            "supersedes_id": current_lease.id,
                        },
                        audit=AuditEvent(
                            tenant_id=tenant_id,
                            user_id=user_id,
                            action="lease.contract.superseded",
                            resource_type="lease",
                            new_value={
                                "lease_number": current_lease.lease_number,
                                "supersedes_id": str(current_lease.id),
                                "correlation_id": correlation_id,
                            },
                        ),
                    )
                lease_state[lease_input.lease_number] = updated_lease
                current_lease = updated_lease

            prior_liability_row = (
                await session.execute(
                    select(LeaseLiabilitySchedule)
                    .where(
                        LeaseLiabilitySchedule.tenant_id == tenant_id,
                        LeaseLiabilitySchedule.run_id == run_id,
                        LeaseLiabilitySchedule.lease_id == schedule_lease_id,
                        LeaseLiabilitySchedule.schedule_version_token == prior_token,
                        LeaseLiabilitySchedule.schedule_date <= modification.effective_date,
                    )
                    .order_by(desc(LeaseLiabilitySchedule.schedule_date), desc(LeaseLiabilitySchedule.created_at))
                    .limit(1)
                )
            ).scalar_one_or_none()

            delta = quantize_persisted_amount(modification.remeasurement_delta_reporting_currency or Decimal("0"))
            created_modification = await AuditWriter.insert_financial_record(
                session,
                model_class=LeaseModification,
                tenant_id=tenant_id,
                record_data={
                    "run_id": str(run_id),
                    "lease_id": str(schedule_lease_id),
                    "effective_date": modification.effective_date.isoformat(),
                    "modification_type": modification.modification_type,
                    "idempotency_key": idempotency_key,
                },
                values={
                    "run_id": run_id,
                    "lease_id": schedule_lease_id,
                    "effective_date": modification.effective_date,
                    "modification_type": modification.modification_type,
                    "modification_reason": modification.modification_reason,
                    "idempotency_key": idempotency_key,
                    "prior_schedule_version_token": prior_token,
                    "new_schedule_version_token": new_token,
                    "prior_schedule_reference": str(prior_liability_row.id) if prior_liability_row else None,
                    "new_schedule_reference": (
                        f"forward_regenerated:{schedule_lease_id}:{modification.effective_date.isoformat()}"
                    ),
                    "remeasurement_delta_reporting_currency": delta,
                    "source_lease_reference": current_lease.source_lease_reference,
                    "parent_reference_id": schedule_lease_id,
                    "source_reference_id": prior_liability_row.id if prior_liability_row else schedule_lease_id,
                    "correlation_id": correlation_id,
                    "supersedes_id": chain_modifications[-1].id if chain_modifications else None,
                },
                audit=AuditEvent(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    action="lease.modification.created",
                    resource_type="lease_modification",
                    new_value={
                        "lease_id": str(schedule_lease_id),
                        "effective_date": modification.effective_date.isoformat(),
                        "modification_type": modification.modification_type,
                        "idempotency_key": idempotency_key,
                        "correlation_id": correlation_id,
                    },
                ),
            )
            created_modifications += 1
            chain_modifications.append(created_modification)
            modification_chain_nodes.append(
                SupersessionNode(
                    id=created_modification.id,
                    tenant_id=created_modification.tenant_id,
                    created_at=created_modification.created_at,
                    supersedes_id=created_modification.supersedes_id,
                )
            )

            persisted = PersistedLeaseModification(
                modification_id=created_modification.id,
                lease_id=schedule_lease_id,
                effective_date=created_modification.effective_date,
                modification_type=created_modification.modification_type,
                idempotency_key=created_modification.idempotency_key,
                prior_schedule_version_token=created_modification.prior_schedule_version_token,
                new_schedule_version_token=created_modification.new_schedule_version_token,
                remeasurement_delta_reporting_currency=created_modification.remeasurement_delta_reporting_currency,
            )
            persisted_for_lease.append(persisted)
            prior_token = persisted.new_schedule_version_token

        if persisted_for_lease:
            modifications_by_lease[schedule_lease_id] = persisted_for_lease

    return LeaseRemeasurementResult(
        modification_count=created_modifications,
        modifications_by_lease=modifications_by_lease,
    )

