from __future__ import annotations

from decimal import Decimal

from financeops.modules.mis_manager.application.mapping_service import MappingService
from financeops.modules.mis_manager.domain.entities import (
    NormalizedLine,
    SnapshotBuildResult,
    ValidationException,
)
from financeops.modules.mis_manager.domain.enums import ValidationStatus
from financeops.modules.mis_manager.domain.value_objects import SnapshotTokenInput
from financeops.modules.mis_manager.infrastructure.token_builder import (
    build_snapshot_token,
)


class SnapshotService:
    def __init__(self, mapping_service: MappingService) -> None:
        self._mapping_service = mapping_service

    def build_snapshot_token(self, payload: SnapshotTokenInput) -> str:
        return build_snapshot_token(payload)

    def normalize_sheet(
        self,
        *,
        sheet_name: str,
        headers: list[str],
        rows: list[list[str]],
        currency_code: str,
    ) -> SnapshotBuildResult:
        row_labels = [
            str(row[0]).strip() for row in rows if row and str(row[0]).strip()
        ]
        mappings = self._mapping_service.map_rows_to_canonical_metrics(row_labels)
        mapping_index = {item.source_label: item for item in mappings}

        normalized_lines: list[NormalizedLine] = []
        exceptions: list[ValidationException] = []
        line_no = 0

        for row_idx, row in enumerate(rows, start=1):
            if not row:
                continue
            row_label = str(row[0]).strip() if row else ""
            if not row_label:
                continue
            if _is_subtotal_row(row_label):
                continue

            mapping = mapping_index.get(row_label)
            if mapping is None or mapping.canonical_metric_code is None:
                exceptions.append(
                    ValidationException(
                        exception_code="MISSING_REQUIRED_ROW",
                        severity="warning",
                        source_ref=f"{sheet_name}:r{row_idx}",
                        message=f"Unmapped row label '{row_label}'",
                    )
                )
                continue

            for col_idx, cell in enumerate(row[1:], start=2):
                value = _parse_numeric(cell)
                if value is None:
                    if str(cell).strip():
                        exceptions.append(
                            ValidationException(
                                exception_code="NON_NUMERIC_VALUE",
                                severity="warning",
                                source_ref=f"{sheet_name}:r{row_idx}c{col_idx}",
                                message=f"Ignored non-numeric value '{cell}'",
                            )
                        )
                    continue
                line_no += 1
                source_col = (
                    headers[col_idx - 1]
                    if len(headers) >= col_idx
                    else f"col_{col_idx}"
                )
                normalized_lines.append(
                    NormalizedLine(
                        line_no=line_no,
                        canonical_metric_code=mapping.canonical_metric_code,
                        canonical_dimension_json={},
                        source_row_ref=f"{sheet_name}:r{row_idx}",
                        source_column_ref=f"{sheet_name}:{source_col}",
                        period_value=value,
                        currency_code=currency_code,
                        sign_applied="as_is",
                        validation_status=ValidationStatus.VALID,
                    )
                )

        return SnapshotBuildResult(
            snapshot_token="",
            normalized_lines=normalized_lines,
            exceptions=exceptions,
            validation_summary_json={
                "normalization_rule_set": "mis_normalization_v1",
                "line_count": len(normalized_lines),
                "exception_count": len(exceptions),
            },
        )


def _parse_numeric(value: str) -> Decimal | None:
    raw = str(value).strip()
    if not raw:
        return None
    try:
        return Decimal(raw.replace(",", ""))
    except Exception:
        return None


def _is_subtotal_row(label: str) -> bool:
    lowered = label.strip().lower()
    return lowered.startswith("total") or "subtotal" in lowered
