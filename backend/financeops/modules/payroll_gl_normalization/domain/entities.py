from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from financeops.modules.payroll_gl_normalization.domain.enums import (
    ExceptionSeverity,
    LineStatus,
)


@dataclass(frozen=True)
class NormalizationExceptionEntry:
    exception_code: str
    severity: ExceptionSeverity
    source_ref: str
    message: str


@dataclass(frozen=True)
class PayrollNormalizedEntry:
    row_no: int
    employee_code: str | None
    employee_name: str | None
    payroll_period: date
    legal_entity: str | None
    department: str | None
    cost_center: str | None
    business_unit: str | None
    location: str | None
    grade: str | None
    designation: str | None
    currency_code: str
    canonical_metric_code: str
    amount_value: Decimal
    source_row_ref: str
    source_column_ref: str
    normalization_status: LineStatus


@dataclass(frozen=True)
class GlNormalizedEntry:
    row_no: int
    journal_id: str | None
    journal_line_no: str | None
    posting_date: date | None
    document_date: date | None
    posting_period: str
    legal_entity: str | None
    account_code: str | None
    account_name: str | None
    cost_center: str | None
    department: str | None
    business_unit: str | None
    project: str | None
    customer: str | None
    vendor: str | None
    source_module: str | None
    source_document_id: str | None
    currency_code: str
    debit_amount: Decimal
    credit_amount: Decimal
    signed_amount: Decimal
    local_amount: Decimal
    transaction_amount: Decimal
    source_row_ref: str
    source_column_ref: str
    normalization_status: LineStatus


@dataclass(frozen=True)
class StructureSignatureBundle:
    structure_hash: str
    header_hash: str
    row_signature_hash: str
    detection_summary_json: dict[str, Any]
