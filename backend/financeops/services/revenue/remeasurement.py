from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.revenue import RevenueAdjustment, RevenueContract, RevenueSchedule
from financeops.schemas.revenue import RevenueContractInput, RevenueContractModificationInput
from financeops.services.accounting_common.accounting_errors import AccountingValidationError
from financeops.services.accounting_common.error_codes import (
    DUPLICATE_IDEMPOTENT_REQUEST,
    VERSION_CHAIN_BROKEN,
)
from financeops.services.accounting_common.quantization_policy import quantize_persisted_amount
from financeops.services.accounting_common.supersession_validator import (
    SupersessionNode,
    ensure_append_targets_terminal,
    validate_linear_chain,
)
from financeops.services.audit_writer import AuditEvent, AuditWriter
from financeops.services.revenue.contract_registry import RegisteredContract
from financeops.utils.determinism import canonical_json_dumps, sha256_hex_text


@dataclass(frozen=True)
class PersistedRevenueAdjustment:
    adjustment_id: UUID
    contract_id: UUID
    effective_date: date
    adjustment_type: str
    idempotency_key: str
    prior_schedule_version_token: str
    new_schedule_version_token: str
    catch_up_amount_reporting_currency: Decimal


@dataclass(frozen=True)
class RemeasurementResult:
    adjustment_count: int
    adjustments_by_contract: dict[UUID, list[PersistedRevenueAdjustment]]


def _expected_cumulative_ratio(*, contract_start_date: date, contract_end_date: date, effective_date: date) -> Decimal:
    total_days = max((contract_end_date - contract_start_date).days + 1, 1)
    elapsed_days = min(max((effective_date - contract_start_date).days + 1, 0), total_days)
    return Decimal(str(elapsed_days)) / Decimal(str(total_days))


def _decimal_text(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return f"{quantize_persisted_amount(value):.6f}"


def _normalized_modification_payload(modification: RevenueContractModificationInput) -> dict[str, str | bool | None]:
    return {
        "effective_date": modification.effective_date.isoformat(),
        "adjustment_type": modification.adjustment_type,
        "adjustment_reason": modification.adjustment_reason,
        "new_total_contract_value": _decimal_text(modification.new_total_contract_value),
        "requires_catch_up": bool(modification.requires_catch_up),
    }


def build_schedule_version_token(
    *,
    contract_id: UUID,
    modification_payload_normalized: dict[str, str | bool | None],
    reporting_currency: str,
    rate_mode: str,
    prior_version_token_or_root: str,
) -> str:
    payload = {
        "contract_id": str(contract_id),
        "modification_payload_normalized": modification_payload_normalized,
        "reporting_currency": reporting_currency,
        "rate_mode": rate_mode,
        "prior_version_token_or_root": prior_version_token_or_root,
    }
    return sha256_hex_text(canonical_json_dumps(payload))


def _modification_idempotency_key(
    *,
    contract_id: UUID,
    modification: RevenueContractModificationInput,
) -> str:
    payload = {
        "contract_id": str(contract_id),
        "modification": _normalized_modification_payload(modification),
    }
    return sha256_hex_text(canonical_json_dumps(payload))


async def _load_contract_chain(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    contract_number: str,
    source_contract_reference: str,
) -> list[SupersessionNode]:
    rows = (
        await session.execute(
            select(RevenueContract)
            .where(
                RevenueContract.tenant_id == tenant_id,
                RevenueContract.contract_number == contract_number,
                RevenueContract.source_contract_reference == source_contract_reference,
            )
            .order_by(RevenueContract.created_at, RevenueContract.id)
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


async def _resolve_latest_token_for_contract(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    contract_id: UUID,
    root_schedule_version_token: str,
) -> str:
    latest = (
        await session.execute(
            select(RevenueAdjustment)
            .where(
                RevenueAdjustment.tenant_id == tenant_id,
                RevenueAdjustment.run_id == run_id,
                RevenueAdjustment.contract_id == contract_id,
            )
            .order_by(
                desc(RevenueAdjustment.effective_date),
                desc(RevenueAdjustment.created_at),
                desc(RevenueAdjustment.id),
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if latest is None:
        return root_schedule_version_token
    return latest.new_schedule_version_token


async def apply_contract_modifications(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID,
    run_id: UUID,
    correlation_id: str,
    contracts: Iterable[RevenueContractInput],
    registered_contracts: list[RegisteredContract],
    root_schedule_version_tokens: dict[UUID, str],
    reporting_currency: str,
    rate_mode: str,
) -> RemeasurementResult:
    contract_state: dict[str, RevenueContract] = {}
    for contract in registered_contracts:
        model_result = await session.execute(
            select(RevenueContract).where(
                RevenueContract.tenant_id == tenant_id,
                RevenueContract.id == contract.contract_id,
            )
        )
        model = model_result.scalar_one()
        contract_state[contract.contract_number] = model

    created_adjustments = 0
    adjustments_by_contract: dict[UUID, list[PersistedRevenueAdjustment]] = {}

    for contract_input in sorted(contracts, key=lambda item: item.contract_number):
        current_contract = contract_state[contract_input.contract_number]
        schedule_contract_id = current_contract.id
        root_token = root_schedule_version_tokens.get(schedule_contract_id)
        if root_token is None:
            raise AccountingValidationError(
                error_code=VERSION_CHAIN_BROKEN,
                message="Missing root revenue schedule version token",
            )
        prior_token = root_token
        existing_chain_rows = (
            await session.execute(
                select(RevenueAdjustment)
                .where(
                    RevenueAdjustment.tenant_id == tenant_id,
                    RevenueAdjustment.run_id == run_id,
                    RevenueAdjustment.contract_id == schedule_contract_id,
                )
                .order_by(RevenueAdjustment.created_at, RevenueAdjustment.id)
            )
        ).scalars().all()
        chain_nodes = [
            SupersessionNode(
                id=row.id,
                tenant_id=row.tenant_id,
                created_at=row.created_at,
                supersedes_id=row.supersedes_id,
            )
            for row in existing_chain_rows
        ]
        validate_linear_chain(nodes=chain_nodes, tenant_id=tenant_id)
        chain_adjustments: list[RevenueAdjustment] = list(existing_chain_rows)
        persisted_for_contract: list[PersistedRevenueAdjustment] = []

        ordered_modifications = sorted(
            contract_input.modifications,
            key=lambda item: (
                item.effective_date,
                item.adjustment_type,
                item.adjustment_reason,
                _decimal_text(item.new_total_contract_value),
                item.requires_catch_up,
            ),
        )
        for modification in ordered_modifications:
            ensure_append_targets_terminal(
                nodes=chain_nodes,
                tenant_id=tenant_id,
                supersedes_id=chain_adjustments[-1].id if chain_adjustments else None,
            )
            idempotency_key = _modification_idempotency_key(
                contract_id=schedule_contract_id,
                modification=modification,
            )
            modification_payload = _normalized_modification_payload(modification)

            existing_adjustment = (
                await session.execute(
                    select(RevenueAdjustment).where(
                        RevenueAdjustment.tenant_id == tenant_id,
                        RevenueAdjustment.run_id == run_id,
                        RevenueAdjustment.contract_id == schedule_contract_id,
                        RevenueAdjustment.effective_date == modification.effective_date,
                        RevenueAdjustment.adjustment_type == modification.adjustment_type,
                        RevenueAdjustment.idempotency_key == idempotency_key,
                    )
                )
            ).scalar_one_or_none()

            if existing_adjustment is not None:
                expected_existing_token = build_schedule_version_token(
                    contract_id=schedule_contract_id,
                    modification_payload_normalized=modification_payload,
                    reporting_currency=reporting_currency,
                    rate_mode=rate_mode,
                    prior_version_token_or_root=existing_adjustment.prior_schedule_version_token,
                )
                if existing_adjustment.new_schedule_version_token != expected_existing_token:
                    raise AccountingValidationError(
                        error_code=DUPLICATE_IDEMPOTENT_REQUEST,
                        message="Revenue modification idempotency conflict",
                    )

                persisted = PersistedRevenueAdjustment(
                    adjustment_id=existing_adjustment.id,
                    contract_id=schedule_contract_id,
                    effective_date=existing_adjustment.effective_date,
                    adjustment_type=existing_adjustment.adjustment_type,
                    idempotency_key=existing_adjustment.idempotency_key,
                    prior_schedule_version_token=existing_adjustment.prior_schedule_version_token,
                    new_schedule_version_token=existing_adjustment.new_schedule_version_token,
                    catch_up_amount_reporting_currency=existing_adjustment.catch_up_amount_reporting_currency,
                )
                persisted_for_contract.append(persisted)
                prior_token = existing_adjustment.new_schedule_version_token
                continue

            if prior_token == root_token and chain_adjustments:
                prior_token = chain_adjustments[-1].new_schedule_version_token

            new_token = build_schedule_version_token(
                contract_id=schedule_contract_id,
                modification_payload_normalized=modification_payload,
                reporting_currency=reporting_currency,
                rate_mode=rate_mode,
                prior_version_token_or_root=prior_token,
            )

            new_contract = current_contract
            if modification.new_total_contract_value is not None:
                proposed_total = quantize_persisted_amount(modification.new_total_contract_value)
                if proposed_total != current_contract.total_contract_value:
                    chain_nodes = await _load_contract_chain(
                        session,
                        tenant_id=tenant_id,
                        contract_number=current_contract.contract_number,
                        source_contract_reference=current_contract.source_contract_reference,
                    )
                    ensure_append_targets_terminal(
                        nodes=chain_nodes,
                        tenant_id=tenant_id,
                        supersedes_id=current_contract.id,
                    )
                    existing_superseding = (
                        await session.execute(
                            select(RevenueContract)
                            .where(
                                RevenueContract.tenant_id == tenant_id,
                                RevenueContract.supersedes_id == current_contract.id,
                                RevenueContract.total_contract_value == proposed_total,
                                RevenueContract.correlation_id == correlation_id,
                            )
                            .order_by(desc(RevenueContract.created_at))
                            .limit(1)
                        )
                    ).scalar_one_or_none()
                    new_contract = existing_superseding
                    if new_contract is None:
                        new_contract = await AuditWriter.insert_financial_record(
                            session,
                            model_class=RevenueContract,
                            tenant_id=tenant_id,
                            record_data={
                                "contract_number": current_contract.contract_number,
                                "source_contract_reference": current_contract.source_contract_reference,
                                "total_contract_value": str(proposed_total),
                            },
                            values={
                                "contract_number": current_contract.contract_number,
                                "customer_id": current_contract.customer_id,
                                "contract_currency": current_contract.contract_currency,
                                "contract_start_date": current_contract.contract_start_date,
                                "contract_end_date": current_contract.contract_end_date,
                                "total_contract_value": proposed_total,
                                "source_contract_reference": current_contract.source_contract_reference,
                                "policy_code": current_contract.policy_code,
                                "policy_version": current_contract.policy_version,
                                "correlation_id": correlation_id,
                                "supersedes_id": current_contract.id,
                            },
                            audit=AuditEvent(
                                tenant_id=tenant_id,
                                user_id=user_id,
                                action="revenue.contract.superseded",
                                resource_type="revenue_contract",
                                new_value={
                                    "contract_number": current_contract.contract_number,
                                    "supersedes_id": str(current_contract.id),
                                    "correlation_id": correlation_id,
                                },
                            ),
                        )
                    contract_state[contract_input.contract_number] = new_contract
                    current_contract = new_contract

            historical_schedule_total = (
                await session.execute(
                    select(RevenueSchedule).where(
                        RevenueSchedule.tenant_id == tenant_id,
                        RevenueSchedule.run_id == run_id,
                        RevenueSchedule.contract_id == schedule_contract_id,
                        RevenueSchedule.schedule_version_token == prior_token,
                        RevenueSchedule.recognition_date <= modification.effective_date,
                    )
                )
            ).scalars().all()
            recognized_to_date = quantize_persisted_amount(
                sum(
                    (row.recognized_amount_reporting_currency for row in historical_schedule_total),
                    start=Decimal("0"),
                )
            )

            ratio = _expected_cumulative_ratio(
                contract_start_date=current_contract.contract_start_date,
                contract_end_date=current_contract.contract_end_date,
                effective_date=modification.effective_date,
            )
            expected_cumulative = quantize_persisted_amount(current_contract.total_contract_value * ratio)
            catch_up = (
                quantize_persisted_amount(expected_cumulative - recognized_to_date)
                if modification.requires_catch_up
                else Decimal("0.000000")
            )

            latest_prior_schedule = (
                await session.execute(
                    select(RevenueSchedule)
                    .where(
                        RevenueSchedule.tenant_id == tenant_id,
                        RevenueSchedule.run_id == run_id,
                        RevenueSchedule.contract_id == schedule_contract_id,
                        RevenueSchedule.schedule_version_token == prior_token,
                        RevenueSchedule.recognition_date <= modification.effective_date,
                    )
                    .order_by(desc(RevenueSchedule.recognition_date), desc(RevenueSchedule.created_at))
                    .limit(1)
                )
            ).scalar_one_or_none()

            created_adjustment = await AuditWriter.insert_financial_record(
                session,
                model_class=RevenueAdjustment,
                tenant_id=tenant_id,
                record_data={
                    "run_id": str(run_id),
                    "contract_id": str(schedule_contract_id),
                    "effective_date": modification.effective_date.isoformat(),
                    "adjustment_type": modification.adjustment_type,
                    "idempotency_key": idempotency_key,
                },
                values={
                    "run_id": run_id,
                    "contract_id": schedule_contract_id,
                    "effective_date": modification.effective_date,
                    "adjustment_type": modification.adjustment_type,
                    "adjustment_reason": modification.adjustment_reason,
                    "idempotency_key": idempotency_key,
                    "prior_schedule_version_token": prior_token,
                    "new_schedule_version_token": new_token,
                    "prior_schedule_reference": str(latest_prior_schedule.id) if latest_prior_schedule else None,
                    "new_schedule_reference": (
                        f"forward_regenerated:{schedule_contract_id}:{modification.effective_date.isoformat()}"
                    ),
                    "catch_up_amount_reporting_currency": catch_up,
                    "source_contract_reference": current_contract.source_contract_reference,
                    "parent_reference_id": schedule_contract_id,
                    "source_reference_id": latest_prior_schedule.id if latest_prior_schedule else schedule_contract_id,
                    "correlation_id": correlation_id,
                    "supersedes_id": chain_adjustments[-1].id if chain_adjustments else None,
                },
                audit=AuditEvent(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    action="revenue.adjustment.created",
                    resource_type="revenue_adjustment",
                    new_value={
                        "contract_id": str(schedule_contract_id),
                        "effective_date": modification.effective_date.isoformat(),
                        "adjustment_type": modification.adjustment_type,
                        "idempotency_key": idempotency_key,
                        "correlation_id": correlation_id,
                    },
                ),
            )
            created_adjustments += 1
            chain_adjustments.append(created_adjustment)
            chain_nodes.append(
                SupersessionNode(
                    id=created_adjustment.id,
                    tenant_id=created_adjustment.tenant_id,
                    created_at=created_adjustment.created_at,
                    supersedes_id=created_adjustment.supersedes_id,
                )
            )

            persisted = PersistedRevenueAdjustment(
                adjustment_id=created_adjustment.id,
                contract_id=schedule_contract_id,
                effective_date=created_adjustment.effective_date,
                adjustment_type=created_adjustment.adjustment_type,
                idempotency_key=created_adjustment.idempotency_key,
                prior_schedule_version_token=created_adjustment.prior_schedule_version_token,
                new_schedule_version_token=created_adjustment.new_schedule_version_token,
                catch_up_amount_reporting_currency=created_adjustment.catch_up_amount_reporting_currency,
            )
            persisted_for_contract.append(persisted)
            prior_token = persisted.new_schedule_version_token

        if persisted_for_contract:
            adjustments_by_contract[schedule_contract_id] = persisted_for_contract

    return RemeasurementResult(
        adjustment_count=created_adjustments,
        adjustments_by_contract=adjustments_by_contract,
    )
