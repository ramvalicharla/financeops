from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

from financeops.modules.payroll_gl_normalization.domain.entities import (
    NormalizationExceptionEntry,
    PayrollNormalizedEntry,
)
from financeops.modules.payroll_gl_normalization.domain.enums import (
    ExceptionSeverity,
    LineStatus,
)

_SCALE = Decimal("0.000001")


class PayrollNormalizationService:
    def normalize(
        self,
        *,
        headers: list[str],
        rows: list[list[str]],
        mappings: list[dict[str, Any]],
        reporting_period: date,
    ) -> tuple[list[PayrollNormalizedEntry], list[NormalizationExceptionEntry]]:
        lower_headers = [str(header).strip() for header in headers]
        index_by_header = {header: idx for idx, header in enumerate(lower_headers)}
        mapped_headers = {item["source_field_name"] for item in mappings}

        dimensions = {
            item["canonical_field_name"]: item["source_field_name"]
            for item in mappings
            if item["mapping_type"] == "payroll_dimension"
        }
        metric_mappings = [
            item for item in mappings if item["mapping_type"] == "payroll_metric"
        ]

        lines: list[PayrollNormalizedEntry] = []
        exceptions: list[NormalizationExceptionEntry] = []
        line_no = 0
        for row_idx, row in enumerate(rows, start=1):
            employee_code = self._get_value(row, dimensions.get("employee_code"), index_by_header)
            employee_name = self._get_value(row, dimensions.get("employee_name"), index_by_header)
            if not employee_code and not employee_name:
                continue
            currency_code = (
                self._get_value(row, dimensions.get("currency_code"), index_by_header) or "USD"
            ).upper()

            for mapping in metric_mappings:
                source_field = mapping["source_field_name"]
                canonical_metric = mapping["canonical_field_name"]
                raw = self._get_value(row, source_field, index_by_header)
                if raw is None or raw == "":
                    continue
                amount = self._parse_numeric(raw)
                if amount is None:
                    exceptions.append(
                        NormalizationExceptionEntry(
                            exception_code="NON_NUMERIC_AMOUNT",
                            severity=ExceptionSeverity.ERROR,
                            source_ref=f"row:{row_idx},col:{source_field}",
                            message=f"Non-numeric payroll metric value for {canonical_metric}",
                        )
                    )
                    continue
                line_no += 1
                lines.append(
                    PayrollNormalizedEntry(
                        row_no=line_no,
                        employee_code=employee_code,
                        employee_name=employee_name,
                        payroll_period=reporting_period,
                        legal_entity=self._get_value(row, dimensions.get("legal_entity"), index_by_header),
                        department=self._get_value(row, dimensions.get("department"), index_by_header),
                        cost_center=self._get_value(row, dimensions.get("cost_center"), index_by_header),
                        business_unit=self._get_value(row, dimensions.get("business_unit"), index_by_header),
                        location=self._get_value(row, dimensions.get("location"), index_by_header),
                        grade=self._get_value(row, dimensions.get("grade"), index_by_header),
                        designation=self._get_value(row, dimensions.get("designation"), index_by_header),
                        currency_code=currency_code,
                        canonical_metric_code=canonical_metric,
                        amount_value=amount,
                        source_row_ref=f"row:{row_idx}",
                        source_column_ref=source_field,
                        normalization_status=LineStatus.VALID,
                    )
                )

            for col_idx, header in enumerate(lower_headers):
                if header in mapped_headers:
                    continue
                value = row[col_idx] if col_idx < len(row) else ""
                if not value:
                    continue
                parsed = self._parse_numeric(value)
                if parsed is not None:
                    exceptions.append(
                        NormalizationExceptionEntry(
                            exception_code="UNMAPPED_PAY_COMPONENT",
                            severity=ExceptionSeverity.WARNING,
                            source_ref=f"row:{row_idx},col:{header}",
                            message="Numeric payroll component was not mapped",
                        )
                    )

            if not employee_code and not employee_name:
                exceptions.append(
                    NormalizationExceptionEntry(
                        exception_code="REQUIRED_FIELD_MISSING",
                        severity=ExceptionSeverity.ERROR,
                        source_ref=f"row:{row_idx}",
                        message="Employee code or employee name is required",
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

    def _parse_numeric(self, value: str) -> Decimal | None:
        text = str(value).strip().replace(",", "")
        if not text:
            return None
        try:
            return Decimal(text).quantize(_SCALE, rounding=ROUND_HALF_UP)
        except (InvalidOperation, ValueError):
            return None
