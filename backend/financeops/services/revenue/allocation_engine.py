from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable
from uuid import UUID

from financeops.core.exceptions import ValidationError
from financeops.services.accounting_common.quantization_policy import quantize_persisted_amount
from financeops.services.revenue.contract_registry import RegisteredContract
from financeops.services.revenue.obligation_tracker import RegisteredObligation


@dataclass(frozen=True)
class ObligationAllocation:
    contract_id: UUID
    obligation_id: UUID
    obligation_code: str
    allocated_amount_contract_currency: Decimal


def allocate_contract_values(
    *,
    contracts: Iterable[RegisteredContract],
    obligations: Iterable[RegisteredObligation],
) -> list[ObligationAllocation]:
    obligations_by_contract: dict[UUID, list[RegisteredObligation]] = {}
    for obligation in obligations:
        obligations_by_contract.setdefault(obligation.contract_id, []).append(obligation)

    allocations: list[ObligationAllocation] = []

    for contract in sorted(contracts, key=lambda item: item.contract_number):
        contract_obligations = sorted(
            obligations_by_contract.get(contract.contract_id, []),
            key=lambda item: item.obligation_code,
        )
        if not contract_obligations:
            raise ValidationError("Contract has no registered performance obligations")

        ssp_total = quantize_persisted_amount(
            sum((item.standalone_selling_price for item in contract_obligations), start=Decimal("0"))
        )
        if ssp_total <= Decimal("0"):
            raise ValidationError("Standalone selling price total must be positive")

        provisional: list[ObligationAllocation] = []
        for obligation in contract_obligations:
            ratio = obligation.standalone_selling_price / ssp_total
            allocated = quantize_persisted_amount(contract.total_contract_value * ratio)
            provisional.append(
                ObligationAllocation(
                    contract_id=contract.contract_id,
                    obligation_id=obligation.obligation_id,
                    obligation_code=obligation.obligation_code,
                    allocated_amount_contract_currency=allocated,
                )
            )

        provisional_sum = quantize_persisted_amount(
            sum((item.allocated_amount_contract_currency for item in provisional), start=Decimal("0"))
        )
        residual = quantize_persisted_amount(contract.total_contract_value - provisional_sum)

        if residual != Decimal("0.000000"):
            anchor = provisional[0]
            adjusted_anchor = ObligationAllocation(
                contract_id=anchor.contract_id,
                obligation_id=anchor.obligation_id,
                obligation_code=anchor.obligation_code,
                allocated_amount_contract_currency=quantize_persisted_amount(
                    anchor.allocated_amount_contract_currency + residual
                ),
            )
            provisional[0] = adjusted_anchor

        reconciled = quantize_persisted_amount(
            sum((item.allocated_amount_contract_currency for item in provisional), start=Decimal("0"))
        )
        if reconciled != quantize_persisted_amount(contract.total_contract_value):
            raise ValidationError("Allocation failed to reconcile exactly to contract total")

        allocations.extend(provisional)

    allocations.sort(key=lambda item: (str(item.contract_id), item.obligation_code))
    return allocations
