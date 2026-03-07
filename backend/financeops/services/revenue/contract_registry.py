from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import ValidationError
from financeops.db.models.revenue import RevenueContract
from financeops.schemas.revenue import RevenueContractInput
from financeops.services.accounting_common.quantization_policy import quantize_persisted_amount
from financeops.services.audit_writer import AuditEvent, AuditWriter
from financeops.services.fx.normalization import normalize_currency_code


@dataclass(frozen=True)
class RegisteredContract:
    contract_id: UUID
    contract_number: str
    contract_currency: str
    contract_start_date: date
    contract_end_date: date
    total_contract_value: Decimal
    source_contract_reference: str


def _contract_fingerprint(contract: RevenueContractInput) -> tuple[str, str, str]:
    return (
        contract.contract_number,
        contract.source_contract_reference,
        contract.policy_version,
    )


async def register_contracts(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID,
    correlation_id: str,
    contracts: Iterable[RevenueContractInput],
) -> list[RegisteredContract]:
    registered: list[RegisteredContract] = []
    seen_fingerprints: set[tuple[str, str, str]] = set()

    for contract in contracts:
        fingerprint = _contract_fingerprint(contract)
        if fingerprint in seen_fingerprints:
            raise ValidationError("Duplicate contract fingerprint in request payload")
        seen_fingerprints.add(fingerprint)

        existing_result = await session.execute(
            select(RevenueContract)
            .where(
                RevenueContract.tenant_id == tenant_id,
                RevenueContract.contract_number == contract.contract_number,
                RevenueContract.source_contract_reference == contract.source_contract_reference,
                RevenueContract.policy_version == contract.policy_version,
                RevenueContract.correlation_id == correlation_id,
            )
            .order_by(RevenueContract.created_at)
            .limit(1)
        )
        existing = existing_result.scalar_one_or_none()
        if existing is not None:
            registered.append(
                RegisteredContract(
                    contract_id=existing.id,
                    contract_number=existing.contract_number,
                    contract_currency=existing.contract_currency,
                    contract_start_date=existing.contract_start_date,
                    contract_end_date=existing.contract_end_date,
                    total_contract_value=existing.total_contract_value,
                    source_contract_reference=existing.source_contract_reference,
                )
            )
            continue

        total_contract_value = quantize_persisted_amount(contract.total_contract_value)
        if total_contract_value <= Decimal("0"):
            raise ValidationError("total_contract_value must be positive")

        created = await AuditWriter.insert_financial_record(
            session,
            model_class=RevenueContract,
            tenant_id=tenant_id,
            record_data={
                "contract_number": contract.contract_number,
                "customer_id": contract.customer_id,
                "contract_currency": contract.contract_currency,
                "source_contract_reference": contract.source_contract_reference,
            },
            values={
                "contract_number": contract.contract_number,
                "customer_id": contract.customer_id,
                "contract_currency": normalize_currency_code(contract.contract_currency),
                "contract_start_date": contract.contract_start_date,
                "contract_end_date": contract.contract_end_date,
                "total_contract_value": total_contract_value,
                "source_contract_reference": contract.source_contract_reference,
                "policy_code": contract.policy_code,
                "policy_version": contract.policy_version,
                "correlation_id": correlation_id,
                "supersedes_id": None,
            },
            audit=AuditEvent(
                tenant_id=tenant_id,
                user_id=user_id,
                action="revenue.contract.created",
                resource_type="revenue_contract",
                new_value={
                    "contract_number": contract.contract_number,
                    "source_contract_reference": contract.source_contract_reference,
                    "correlation_id": correlation_id,
                },
            ),
        )
        registered.append(
                RegisteredContract(
                    contract_id=created.id,
                    contract_number=created.contract_number,
                    contract_currency=created.contract_currency,
                    contract_start_date=created.contract_start_date,
                    contract_end_date=created.contract_end_date,
                    total_contract_value=created.total_contract_value,
                    source_contract_reference=created.source_contract_reference,
                )
        )

    registered.sort(key=lambda item: (item.contract_number, str(item.contract_id)))
    return registered
