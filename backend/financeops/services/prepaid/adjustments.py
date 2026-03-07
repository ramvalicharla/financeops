from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.prepaid import PrepaidAdjustment
from financeops.services.accounting_common.accounting_errors import AccountingValidationError
from financeops.services.accounting_common.error_codes import VERSION_CHAIN_BROKEN
from financeops.schemas.prepaid import PrepaidAdjustmentInput
from financeops.services.accounting_common.quantization_policy import quantize_persisted_amount
from financeops.services.accounting_common.supersession_validator import (
    SupersessionNode,
    ensure_append_targets_terminal,
    validate_linear_chain,
)
from financeops.services.audit_writer import AuditEvent, AuditWriter
from financeops.utils.determinism import canonical_json_dumps, sha256_hex_text


@dataclass(frozen=True)
class PersistedAdjustment:
    adjustment_id: UUID
    effective_date: date
    adjustment_type: str
    idempotency_key: str
    prior_schedule_version_token: str
    new_schedule_version_token: str
    catch_up_amount_reporting_currency: Decimal


def build_schedule_version_token(
    *,
    prepaid_id: UUID,
    pattern_normalized_json: dict,
    reporting_currency: str,
    rate_mode: str,
    adjustment_effective_date: date,
    prior_schedule_version_token_or_root: str,
) -> str:
    token_source = "|".join(
        [
            str(prepaid_id),
            canonical_json_dumps(pattern_normalized_json),
            str(reporting_currency),
            str(rate_mode),
            adjustment_effective_date.isoformat(),
            str(prior_schedule_version_token_or_root),
        ]
    )
    return sha256_hex_text(token_source)


async def persist_adjustments(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    prepaid_id: UUID,
    source_expense_reference: str,
    parent_reference_id: UUID | None,
    source_reference_id: UUID | None,
    correlation_id: str,
    user_id: UUID,
    adjustments: Iterable[PrepaidAdjustmentInput],
    root_schedule_version_token: str,
    pattern_normalized_json: dict,
    reporting_currency: str,
    rate_mode: str,
) -> list[PersistedAdjustment]:
    ordered = sorted(
        adjustments,
        key=lambda row: (row.effective_date, row.adjustment_type, row.idempotency_key),
    )
    existing_chain_rows = (
        await session.execute(
            select(PrepaidAdjustment)
            .where(
                PrepaidAdjustment.tenant_id == tenant_id,
                PrepaidAdjustment.run_id == run_id,
                PrepaidAdjustment.prepaid_id == prepaid_id,
            )
            .order_by(PrepaidAdjustment.created_at, PrepaidAdjustment.id)
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

    persisted: list[PersistedAdjustment] = []
    prior_token = root_schedule_version_token
    prior_adjustment_id: UUID | None = existing_chain_rows[-1].id if existing_chain_rows else None

    for adjustment in ordered:
        ensure_append_targets_terminal(
            nodes=chain_nodes,
            tenant_id=tenant_id,
            supersedes_id=prior_adjustment_id,
        )

        existing_result = await session.execute(
            select(PrepaidAdjustment).where(
                PrepaidAdjustment.tenant_id == tenant_id,
                PrepaidAdjustment.run_id == run_id,
                PrepaidAdjustment.prepaid_id == prepaid_id,
                PrepaidAdjustment.effective_date == adjustment.effective_date,
                PrepaidAdjustment.adjustment_type == adjustment.adjustment_type,
                PrepaidAdjustment.idempotency_key == adjustment.idempotency_key,
            )
        )
        existing = existing_result.scalar_one_or_none()
        if existing is not None:
            expected_existing_token = build_schedule_version_token(
                prepaid_id=prepaid_id,
                pattern_normalized_json=pattern_normalized_json,
                reporting_currency=reporting_currency,
                rate_mode=rate_mode,
                adjustment_effective_date=existing.effective_date,
                prior_schedule_version_token_or_root=existing.prior_schedule_version_token,
            )
            if existing.new_schedule_version_token != expected_existing_token:
                raise AccountingValidationError(
                    error_code=VERSION_CHAIN_BROKEN,
                    message="Prepaid adjustment version token mismatch",
                )
            if prior_adjustment_id is None and existing.supersedes_id is not None:
                raise AccountingValidationError(
                    error_code=VERSION_CHAIN_BROKEN,
                    message="Prepaid adjustment supersession chain is not linear",
                )
            if (
                prior_adjustment_id is not None
                and existing.id != prior_adjustment_id
                and existing.supersedes_id != prior_adjustment_id
            ):
                raise AccountingValidationError(
                    error_code=VERSION_CHAIN_BROKEN,
                    message="Prepaid adjustment supersession chain is not linear",
                )
            persisted.append(
                PersistedAdjustment(
                    adjustment_id=existing.id,
                    effective_date=existing.effective_date,
                    adjustment_type=existing.adjustment_type,
                    idempotency_key=existing.idempotency_key,
                    prior_schedule_version_token=existing.prior_schedule_version_token,
                    new_schedule_version_token=existing.new_schedule_version_token,
                    catch_up_amount_reporting_currency=existing.catch_up_amount_reporting_currency,
                )
            )
            prior_token = existing.new_schedule_version_token
            prior_adjustment_id = existing.id
            continue

        if prior_token == root_schedule_version_token and existing_chain_rows:
            prior_token = existing_chain_rows[-1].new_schedule_version_token

        new_token = build_schedule_version_token(
            prepaid_id=prepaid_id,
            pattern_normalized_json=pattern_normalized_json,
            reporting_currency=reporting_currency,
            rate_mode=rate_mode,
            adjustment_effective_date=adjustment.effective_date,
            prior_schedule_version_token_or_root=prior_token,
        )

        if existing is None:
            existing = await AuditWriter.insert_financial_record(
                session,
                model_class=PrepaidAdjustment,
                tenant_id=tenant_id,
                record_data={
                    "run_id": str(run_id),
                    "prepaid_id": str(prepaid_id),
                    "effective_date": adjustment.effective_date.isoformat(),
                    "adjustment_type": adjustment.adjustment_type,
                    "idempotency_key": adjustment.idempotency_key,
                },
                values={
                    "run_id": run_id,
                    "prepaid_id": prepaid_id,
                    "effective_date": adjustment.effective_date,
                    "adjustment_type": adjustment.adjustment_type,
                    "adjustment_reason": adjustment.adjustment_reason,
                    "idempotency_key": adjustment.idempotency_key,
                    "prior_schedule_version_token": prior_token,
                    "new_schedule_version_token": new_token,
                    "catch_up_amount_reporting_currency": quantize_persisted_amount(
                        adjustment.catch_up_amount_reporting_currency
                    ),
                    "source_expense_reference": source_expense_reference,
                    "parent_reference_id": parent_reference_id,
                    "source_reference_id": source_reference_id,
                    "correlation_id": correlation_id,
                    "supersedes_id": prior_adjustment_id,
                },
                audit=AuditEvent(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    action="prepaid.adjustment.created",
                    resource_type="prepaid_adjustment",
                    new_value={
                        "run_id": str(run_id),
                        "prepaid_id": str(prepaid_id),
                        "effective_date": adjustment.effective_date.isoformat(),
                        "idempotency_key": adjustment.idempotency_key,
                        "correlation_id": correlation_id,
                    },
                ),
            )
            chain_nodes.append(
                SupersessionNode(
                    id=existing.id,
                    tenant_id=existing.tenant_id,
                    created_at=existing.created_at,
                    supersedes_id=existing.supersedes_id,
                )
            )

        persisted.append(
            PersistedAdjustment(
                adjustment_id=existing.id,
                effective_date=existing.effective_date,
                adjustment_type=existing.adjustment_type,
                idempotency_key=existing.idempotency_key,
                prior_schedule_version_token=existing.prior_schedule_version_token,
                new_schedule_version_token=existing.new_schedule_version_token,
                catch_up_amount_reporting_currency=existing.catch_up_amount_reporting_currency,
            )
        )
        prior_token = existing.new_schedule_version_token
        prior_adjustment_id = existing.id

    return persisted


async def resolve_effective_version_token(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    prepaid_id: UUID,
    root_schedule_version_token: str,
) -> str:
    result = await session.execute(
        select(PrepaidAdjustment)
        .where(
            PrepaidAdjustment.tenant_id == tenant_id,
            PrepaidAdjustment.run_id == run_id,
            PrepaidAdjustment.prepaid_id == prepaid_id,
        )
        .order_by(
            desc(PrepaidAdjustment.effective_date),
            desc(PrepaidAdjustment.created_at),
            desc(PrepaidAdjustment.id),
        )
        .limit(1)
    )
    latest = result.scalar_one_or_none()
    if latest is None:
        return root_schedule_version_token
    return latest.new_schedule_version_token
