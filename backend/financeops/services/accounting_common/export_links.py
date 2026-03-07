from __future__ import annotations

from financeops.core.exceptions import ValidationError


def _escape_excel_text(value: str) -> str:
    return value.replace("'", "''").replace('"', '""')


def build_sheet_anchor(*, sheet_name: str, row_index: int, column: str = "A") -> str:
    if row_index < 1:
        raise ValidationError("row_index must be >= 1")
    normalized_column = column.strip().upper()
    if not normalized_column.isalpha():
        raise ValidationError("column must contain only letters")
    escaped_sheet = _escape_excel_text(sheet_name.strip())
    return f"'{escaped_sheet}'!{normalized_column}{row_index}"


def build_hyperlink_formula(
    *,
    target_sheet: str,
    target_row: int,
    label: str,
    target_column: str = "A",
) -> str:
    anchor = build_sheet_anchor(
        sheet_name=target_sheet,
        row_index=target_row,
        column=target_column,
    )
    escaped_label = _escape_excel_text(label)
    return f'=HYPERLINK("#{anchor}","{escaped_label}")'
