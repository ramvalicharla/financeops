from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.prepaid import Prepaid
from financeops.schemas.prepaid import PrepaidAdjustmentInput, PrepaidInput
from financeops.services.accounting_common.quantization_policy import quantize_persisted_amount
from financeops.services.audit_writer import AuditEvent, AuditWriter
from financeops.services.fx.normalization import normalize_currency_code
from financeops.services.prepaid.pattern_resolver import NormalizedPattern, normalize_pattern


@dataclass(frozen=True)
class RegisteredPrepaid:
    prepaid_id: UUID
    prepaid_code: str
    prepaid_currency: str
    reporting_currency: str
    term_start_date: date
    term_end_date: date
    base_amount_contract_currency: Decimal
    period_frequency: str
    pattern_type: str
    normalized_pattern: NormalizedPattern
    rate_mode: str
    source_expense_reference: str
    parent_reference_id: UUID | None
    source_reference_id: UUID | None
    adjustments: list[PrepaidAdjustmentInput]


async def register_prepaids(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID,
    correlation_id: str,
    prepaids: Iterable[PrepaidInput],
) -> list[RegisteredPrepaid]:
    registered: list[RegisteredPrepaid] = []

    for prepaid in prepaids:
        normalized_pattern = normalize_pattern(prepaid)

        existing_result = await session.execute(
            select(Prepaid)
            .where(
                Prepaid.tenant_id == tenant_id,
                Prepaid.prepaid_code == prepaid.prepaid_code,
                Prepaid.source_expense_reference == prepaid.source_expense_reference,
                Prepaid.correlation_id == correlation_id,
            )
            .order_by(Prepaid.created_at)
            .limit(1)
        )
        existing = existing_result.scalar_one_or_none()

        if existing is None:
            existing = await AuditWriter.insert_financial_record(
                session,
                model_class=Prepaid,
                tenant_id=tenant_id,
                record_data={
                    "prepaid_code": prepaid.prepaid_code,
                    "source_expense_reference": prepaid.source_expense_reference,
                    "pattern_type": prepaid.pattern_type.value,
                    "rate_mode": prepaid.rate_mode.value,
                },
                values={
                    "prepaid_code": prepaid.prepaid_code,
                    "description": prepaid.description,
                    "prepaid_currency": normalize_currency_code(prepaid.prepaid_currency),
                    "reporting_currency": normalize_currency_code(prepaid.reporting_currency),
                    "term_start_date": prepaid.term_start_date,
                    "term_end_date": prepaid.term_end_date,
                    "base_amount_contract_currency": quantize_persisted_amount(
                        prepaid.base_amount_contract_currency
                    ),
                    "period_frequency": "monthly",
                    "pattern_type": prepaid.pattern_type.value,
                    "pattern_json_normalized": normalized_pattern.canonical_json,
                    "rate_mode": prepaid.rate_mode.value,
                    "source_expense_reference": prepaid.source_expense_reference,
                    "parent_reference_id": prepaid.parent_reference_id,
                    "source_reference_id": prepaid.source_reference_id,
                    "correlation_id": correlation_id,
                    "supersedes_id": None,
                },
                audit=AuditEvent(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    action="prepaid.registry.created",
                    resource_type="prepaid",
                    new_value={
                        "prepaid_code": prepaid.prepaid_code,
                        "source_expense_reference": prepaid.source_expense_reference,
                        "correlation_id": correlation_id,
                    },
                ),
            )

        registered.append(
            RegisteredPrepaid(
                prepaid_id=existing.id,
                prepaid_code=existing.prepaid_code,
                prepaid_currency=existing.prepaid_currency,
                reporting_currency=existing.reporting_currency,
                term_start_date=existing.term_start_date,
                term_end_date=existing.term_end_date,
                base_amount_contract_currency=existing.base_amount_contract_currency,
                period_frequency=existing.period_frequency,
                pattern_type=existing.pattern_type,
                normalized_pattern=normalized_pattern,
                rate_mode=existing.rate_mode,
                source_expense_reference=existing.source_expense_reference,
                parent_reference_id=existing.parent_reference_id,
                source_reference_id=existing.source_reference_id,
                adjustments=list(prepaid.adjustments),
            )
        )

    registered.sort(key=lambda row: (row.prepaid_code, str(row.prepaid_id)))
    return registered
