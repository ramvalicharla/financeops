from __future__ import annotations

import csv
from decimal import Decimal
from io import StringIO
from typing import Any


def parse_csv_bytes(content: bytes, *, sheet_name: str = "csv") -> dict[str, Any]:
    decoded = content.decode("utf-8-sig")
    rows = list(csv.reader(StringIO(decoded)))
    non_empty_rows = [row for row in rows if any(str(cell).strip() for cell in row)]
    headers = [str(item).strip() for item in (non_empty_rows[0] if non_empty_rows else [])]
    data_rows = non_empty_rows[1:] if len(non_empty_rows) > 1 else []

    values = [str(cell).strip() for row in data_rows for cell in row if str(cell).strip()]
    numeric_count = sum(1 for value in values if _is_number(value))
    text_count = sum(1 for value in values if not _is_number(value))
    formula_count = sum(1 for value in values if value.startswith("="))
    total_cells = max(len(values), 1)
    row_labels = [str(row[0]).strip() for row in data_rows if row and str(row[0]).strip()]

    return {
        "sheet_name": sheet_name,
        "headers": headers,
        "rows": data_rows,
        "row_labels": row_labels,
        "header_row_index": 0,
        "data_start_row_index": 1 if headers else 0,
        "blank_row_density": Decimal(len(rows) - len(non_empty_rows)) / Decimal(max(len(rows), 1)),
        "formula_density": Decimal(formula_count) / Decimal(total_cells),
        "text_to_numeric_ratio": Decimal(text_count) / Decimal(max(numeric_count, 1)),
        "merged_cell_count": 0,
    }


def _is_number(value: str) -> bool:
    try:
        float(value.replace(",", ""))
        return True
    except (TypeError, ValueError):
        return False
