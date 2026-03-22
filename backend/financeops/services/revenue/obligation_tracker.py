from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import ValidationError
from financeops.db.models.revenue import RevenueContractLineItem, RevenuePerformanceObligation
from financeops.schemas.revenue import RevenueContractInput, RevenueRecognitionMethod
from financeops.services.accounting_common.quantization_policy import quantize_persisted_amount
from financeops.services.audit_writer import AuditEvent, AuditWriter
from financeops.services.fx.normalization import normalize_currency_code
from financeops.services.revenue.contract_registry import RegisteredContract


@dataclass(frozen=True)
class RegisteredObligation:
    obligation_id: UUID
    contract_id: UUID
    contract_number: str
    obligation_code: str
    recognition_method: RevenueRecognitionMethod
    standalone_selling_price: Decimal


@dataclass(frozen=True)
class RegisteredLineItem:
    line_item_id: UUID
    contract_id: UUID
    contract_number: str
    obligation_id: UUID
    line_code: str
    line_amount: Decimal
    line_currency: str
    milestone_reference: str | None
    usage_reference: str | None
    source_contract_reference: str
    recognition_method: RevenueRecognitionMethod
    completion_percentage: Decimal | None
    completed_flag: bool | None
    milestone_achieved: bool | None
    usage_quantity: Decimal | None
    recognition_date: date | None
    recognition_start_date: date | None
    recognition_end_date: date | None


@dataclass(frozen=True)
class RegisteredObligationSet:
    obligations: list[RegisteredObligation]
    line_items: list[RegisteredLineItem]


async def register_obligations_and_line_items(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID,
    correlation_id: str,
    contracts: Iterable[RevenueContractInput],
    registered_contracts: list[RegisteredContract],
) -> RegisteredObligationSet:
    contract_by_number = {item.contract_number: item for item in registered_contracts}
    obligations: list[RegisteredObligation] = []
    line_items: list[RegisteredLineItem] = []

    for contract in sorted(contracts, key=lambda item: item.contract_number):
        registered_contract = contract_by_number.get(contract.contract_number)
        if registered_contract is None:
            raise ValidationError("Contract was not registered before obligation tracking")

        obligation_method_by_code: dict[str, RevenueRecognitionMethod] = {}
        obligation_id_by_code: dict[str, UUID] = {}

        for obligation in sorted(contract.performance_obligations, key=lambda item: item.obligation_code):
            existing_result = await session.execute(
                select(RevenuePerformanceObligation)
                .where(
                    RevenuePerformanceObligation.tenant_id == tenant_id,
                    RevenuePerformanceObligation.contract_id == registered_contract.contract_id,
                    RevenuePerformanceObligation.obligation_code == obligation.obligation_code,
                    RevenuePerformanceObligation.correlation_id == correlation_id,
                )
                .order_by(RevenuePerformanceObligation.created_at)
                .limit(1)
            )
            existing = existing_result.scalar_one_or_none()
            if existing is None:
                existing = await AuditWriter.insert_financial_record(
                    session,
                    model_class=RevenuePerformanceObligation,
                    tenant_id=tenant_id,
                    record_data={
                        "contract_id": str(registered_contract.contract_id),
                        "obligation_code": obligation.obligation_code,
                        "recognition_method": obligation.recognition_method.value,
                    },
                    values={
                        "contract_id": registered_contract.contract_id,
                        "obligation_code": obligation.obligation_code,
                        "description": obligation.description,
                        "standalone_selling_price": quantize_persisted_amount(obligation.standalone_selling_price),
                        "allocation_basis": obligation.allocation_basis,
                        "recognition_method": obligation.recognition_method.value,
                        "source_contract_reference": registered_contract.source_contract_reference,
                        "parent_reference_id": registered_contract.contract_id,
                        "source_reference_id": registered_contract.contract_id,
                        "correlation_id": correlation_id,
                        "supersedes_id": None,
                    },
                    audit=AuditEvent(
                        tenant_id=tenant_id,
                        user_id=user_id,
                        action="revenue.obligation.created",
                        resource_type="revenue_performance_obligation",
                        new_value={
                            "contract_id": str(registered_contract.contract_id),
                            "obligation_code": obligation.obligation_code,
                            "correlation_id": correlation_id,
                        },
                    ),
                )

            obligation_method = RevenueRecognitionMethod(existing.recognition_method)
            obligation_method_by_code[existing.obligation_code] = obligation_method
            obligation_id_by_code[existing.obligation_code] = existing.id
            obligations.append(
                RegisteredObligation(
                    obligation_id=existing.id,
                    contract_id=existing.contract_id,
                    contract_number=registered_contract.contract_number,
                    obligation_code=existing.obligation_code,
                    recognition_method=obligation_method,
                    standalone_selling_price=existing.standalone_selling_price,
                )
            )

        sorted_obligation_codes = sorted(obligation_id_by_code)
        default_obligation_id = obligation_id_by_code[sorted_obligation_codes[0]] if sorted_obligation_codes else None

        for line_item in sorted(contract.contract_line_items, key=lambda item: item.line_code):
            resolved_obligation_code = line_item.obligation_code
            if resolved_obligation_code is None:
                if len(sorted_obligation_codes) == 1:
                    resolved_obligation_code = sorted_obligation_codes[0]
                else:
                    raise ValidationError(
                        "line item obligation_code is required when a contract has multiple obligations"
                    )

            obligation_id = obligation_id_by_code.get(resolved_obligation_code)
            if obligation_id is None:
                if default_obligation_id is None:
                    raise ValidationError("Contract line item has no resolvable obligation")
                obligation_id = default_obligation_id

            resolved_method = line_item.recognition_method or obligation_method_by_code[resolved_obligation_code]

            existing_line_result = await session.execute(
                select(RevenueContractLineItem)
                .where(
                    RevenueContractLineItem.tenant_id == tenant_id,
                    RevenueContractLineItem.contract_id == registered_contract.contract_id,
                    RevenueContractLineItem.line_code == line_item.line_code,
                    RevenueContractLineItem.correlation_id == correlation_id,
                )
                .order_by(RevenueContractLineItem.created_at)
                .limit(1)
            )
            existing_line = existing_line_result.scalar_one_or_none()
            if existing_line is None:
                existing_line = await AuditWriter.insert_financial_record(
                    session,
                    model_class=RevenueContractLineItem,
                    tenant_id=tenant_id,
                    record_data={
                        "contract_id": str(registered_contract.contract_id),
                        "line_code": line_item.line_code,
                        "line_amount": str(line_item.line_amount),
                    },
                    values={
                        "contract_id": registered_contract.contract_id,
                        "obligation_id": obligation_id,
                        "line_code": line_item.line_code,
                        "line_amount": quantize_persisted_amount(line_item.line_amount),
                        "line_currency": normalize_currency_code(line_item.line_currency),
                        "milestone_reference": line_item.milestone_reference,
                        "usage_reference": line_item.usage_reference,
                        "source_contract_reference": registered_contract.source_contract_reference,
                        "parent_reference_id": obligation_id,
                        "source_reference_id": registered_contract.contract_id,
                        "correlation_id": correlation_id,
                        "supersedes_id": None,
                    },
                    audit=AuditEvent(
                        tenant_id=tenant_id,
                        user_id=user_id,
                        action="revenue.line_item.created",
                        resource_type="revenue_contract_line_item",
                        new_value={
                            "contract_id": str(registered_contract.contract_id),
                            "line_code": line_item.line_code,
                            "correlation_id": correlation_id,
                        },
                    ),
                )

            line_items.append(
                RegisteredLineItem(
                    line_item_id=existing_line.id,
                    contract_id=registered_contract.contract_id,
                    contract_number=registered_contract.contract_number,
                    obligation_id=obligation_id,
                    line_code=existing_line.line_code,
                    line_amount=existing_line.line_amount,
                    line_currency=existing_line.line_currency,
                    milestone_reference=existing_line.milestone_reference,
                    usage_reference=existing_line.usage_reference,
                    source_contract_reference=existing_line.source_contract_reference,
                    recognition_method=resolved_method,
                    completion_percentage=line_item.completion_percentage,
                    completed_flag=line_item.completed_flag,
                    milestone_achieved=line_item.milestone_achieved,
                    usage_quantity=line_item.usage_quantity,
                    recognition_date=line_item.recognition_date,
                    recognition_start_date=line_item.recognition_start_date,
                    recognition_end_date=line_item.recognition_end_date,
                )
            )

    obligations.sort(key=lambda item: (item.contract_number, item.obligation_code))
    line_items.sort(key=lambda item: (item.contract_number, item.line_code))
    return RegisteredObligationSet(obligations=obligations, line_items=line_items)

