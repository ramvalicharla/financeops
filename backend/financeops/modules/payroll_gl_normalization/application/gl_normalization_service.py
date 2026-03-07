from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

from financeops.modules.payroll_gl_normalization.domain.entities import (
    GlNormalizedEntry,
    NormalizationExceptionEntry,
)
from financeops.modules.payroll_gl_normalization.domain.enums import (
    ExceptionSeverity,
    LineStatus,
)

_SCALE = Decimal("0.000001")


class GlNormalizationService:
    def normalize(
        self,
        *,
        headers: list[str],
        rows: list[list[str]],
        mappings: list[dict[str, Any]],
        reporting_period: date,
    ) -> tuple[list[GlNormalizedEntry], list[NormalizationExceptionEntry]]:
        ordered_headers = [str(header).strip() for header in headers]
        index_by_header = {header: idx for idx, header in enumerate(ordered_headers)}
        mapped_headers = {item["source_field_name"] for item in mappings}

        dimensions = {
            item["canonical_field_name"]: item["source_field_name"]
            for item in mappings
            if item["mapping_type"] == "gl_dimension"
        }
        metrics = {
            item["canonical_field_name"]: item["source_field_name"]
            for item in mappings
            if item["mapping_type"] == "gl_metric"
        }

        lines: list[GlNormalizedEntry] = []
        exceptions: list[NormalizationExceptionEntry] = []
        out_row_no = 0
        seen_journal_keys: set[tuple[str, str]] = set()

        for row_idx, row in enumerate(rows, start=1):
            account_code = self._get_value(row, dimensions.get("account_code"), index_by_header)
            account_name = self._get_value(row, dimensions.get("account_name"), index_by_header)
            if not account_code and not account_name:
                continue
            if account_name and "total" in account_name.lower():
                continue

            debit = self._parse_numeric(
                self._get_value(row, metrics.get("debit_amount"), index_by_header)
            )
            credit = self._parse_numeric(
                self._get_value(row, metrics.get("credit_amount"), index_by_header)
            )
            signed_raw = self._parse_numeric(
                self._get_value(row, metrics.get("signed_amount"), index_by_header)
            )

            if debit is None and credit is None and signed_raw is None:
                exceptions.append(
                    NormalizationExceptionEntry(
                        exception_code="INVALID_SIGN_LOGIC",
                        severity=ExceptionSeverity.ERROR,
                        source_ref=f"row:{row_idx}",
                        message="Unable to derive signed amount deterministically",
                    )
                )
                continue

            if signed_raw is None:
                debit_amount = debit or Decimal("0")
                credit_amount = credit or Decimal("0")
                signed_amount = self._q(debit_amount - credit_amount)
            else:
                signed_amount = signed_raw
                if debit is None and credit is None:
                    debit_amount = signed_amount if signed_amount >= 0 else Decimal("0")
                    credit_amount = -signed_amount if signed_amount < 0 else Decimal("0")
                else:
                    debit_amount = debit or Decimal("0")
                    credit_amount = credit or Decimal("0")
                    recomputed = self._q(debit_amount - credit_amount)
                    if recomputed != signed_amount:
                        exceptions.append(
                            NormalizationExceptionEntry(
                                exception_code="INVALID_SIGN_LOGIC",
                                severity=ExceptionSeverity.WARNING,
                                source_ref=f"row:{row_idx}",
                                message="Signed amount differs from debit-credit derivation",
                            )
                        )

            currency = (
                self._get_value(row, dimensions.get("currency_code"), index_by_header) or "USD"
            ).upper()
            posting_date = self._parse_date(
                self._get_value(row, dimensions.get("posting_date"), index_by_header)
            )
            document_date = self._parse_date(
                self._get_value(row, dimensions.get("document_date"), index_by_header)
            )
            posting_period = self._get_value(
                row, dimensions.get("posting_period"), index_by_header
            ) or reporting_period.strftime("%Y-%m")
            journal_id = self._get_value(row, dimensions.get("journal_id"), index_by_header)
            journal_line_no = self._get_value(
                row, dimensions.get("journal_line_no"), index_by_header
            )
            if journal_id and journal_line_no:
                key = (journal_id, journal_line_no)
                if key in seen_journal_keys:
                    exceptions.append(
                        NormalizationExceptionEntry(
                            exception_code="DUPLICATE_JOURNAL_LINE",
                            severity=ExceptionSeverity.WARNING,
                            source_ref=f"row:{row_idx}",
                            message="Duplicate journal and line number combination",
                        )
                    )
                seen_journal_keys.add(key)

            out_row_no += 1
            lines.append(
                GlNormalizedEntry(
                    row_no=out_row_no,
                    journal_id=journal_id,
                    journal_line_no=journal_line_no,
                    posting_date=posting_date,
                    document_date=document_date,
                    posting_period=posting_period,
                    legal_entity=self._get_value(row, dimensions.get("legal_entity"), index_by_header),
                    account_code=account_code.upper() if account_code else None,
                    account_name=account_name,
                    cost_center=self._get_value(row, dimensions.get("cost_center"), index_by_header),
                    department=self._get_value(row, dimensions.get("department"), index_by_header),
                    business_unit=self._get_value(row, dimensions.get("business_unit"), index_by_header),
                    project=self._get_value(row, dimensions.get("project"), index_by_header),
                    customer=self._get_value(row, dimensions.get("customer"), index_by_header),
                    vendor=self._get_value(row, dimensions.get("vendor"), index_by_header),
                    source_module=self._get_value(row, dimensions.get("source_module"), index_by_header),
                    source_document_id=self._get_value(
                        row, dimensions.get("source_document_id"), index_by_header
                    ),
                    currency_code=currency,
                    debit_amount=self._q(debit_amount),
                    credit_amount=self._q(credit_amount),
                    signed_amount=self._q(signed_amount),
                    local_amount=self._q(
                        self._parse_numeric(
                            self._get_value(row, metrics.get("local_amount"), index_by_header)
                        )
                        or signed_amount
                    ),
                    transaction_amount=self._q(
                        self._parse_numeric(
                            self._get_value(
                                row, metrics.get("transaction_amount"), index_by_header
                            )
                        )
                        or signed_amount
                    ),
                    source_row_ref=f"row:{row_idx}",
                    source_column_ref=metrics.get("signed_amount")
                    or metrics.get("debit_amount")
                    or metrics.get("credit_amount")
                    or "unknown",
                    normalization_status=LineStatus.VALID,
                )
            )

            if not account_code:
                exceptions.append(
                    NormalizationExceptionEntry(
                        exception_code="UNKNOWN_ACCOUNT_CODE",
                        severity=ExceptionSeverity.ERROR,
                        source_ref=f"row:{row_idx}",
                        message="Account code missing for GL row",
                    )
                )

            for col_idx, header in enumerate(ordered_headers):
                if header in mapped_headers:
                    continue
                value = row[col_idx] if col_idx < len(row) else ""
                if not value:
                    continue
                parsed = self._parse_numeric(value)
                if parsed is not None:
                    exceptions.append(
                        NormalizationExceptionEntry(
                            exception_code="UNMAPPED_GL_DIMENSION",
                            severity=ExceptionSeverity.WARNING,
                            source_ref=f"row:{row_idx},col:{header}",
                            message="Numeric or dimensional source column was not mapped",
                        )
                    )
        return lines, exceptions

    def _get_value(
        self, row: list[str], header: str | None, index_by_header: dict[str, int]
    ) -> str | None:
        if not header:
            return None
        idx = index_by_header.get(header)
        if idx is None or idx >= len(row):
            return None
        value = str(row[idx]).strip()
        return value or None

    def _parse_numeric(self, value: str | None) -> Decimal | None:
        if value is None:
            return None
        text = str(value).strip().replace(",", "")
        if text == "":
            return None
        try:
            return Decimal(text).quantize(_SCALE, rounding=ROUND_HALF_UP)
        except (InvalidOperation, ValueError):
            return None

    def _parse_date(self, value: str | None) -> date | None:
        if value is None:
            return None
        text = value.strip()
        if not text:
            return None
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y", "%Y/%m/%d"):
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue
        return None

    def _q(self, value: Decimal) -> Decimal:
        return value.quantize(_SCALE, rounding=ROUND_HALF_UP)
