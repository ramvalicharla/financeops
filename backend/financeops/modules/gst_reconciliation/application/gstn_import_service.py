from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from financeops.modules.gst_reconciliation.domain.exceptions import InvalidGstinError
from financeops.utils.gstin import validate_gstin


@dataclass(slots=True)
class ParsedGstReturnLineItem:
    supplier_gstin: str
    invoice_number: str
    invoice_date: date | None
    taxable_value: Decimal
    igst_amount: Decimal
    cgst_amount: Decimal
    sgst_amount: Decimal
    cess_amount: Decimal
    total_tax: Decimal
    gst_rate: Decimal | None
    payment_status: str | None
    expense_category: str | None


def parse_gstr1_json(json_data: dict[str, Any]) -> list[ParsedGstReturnLineItem]:
    return _parse_return_lines(json_data)


def parse_gstr2b_json(json_data: dict[str, Any]) -> list[ParsedGstReturnLineItem]:
    return _parse_return_lines(json_data)


def _parse_return_lines(json_data: dict[str, Any]) -> list[ParsedGstReturnLineItem]:
    raw_items = list(_collect_line_item_dicts(json_data))
    parsed: list[ParsedGstReturnLineItem] = []
    for raw in raw_items:
        supplier_gstin = str(
            raw.get("supplier_gstin")
            or raw.get("gstin")
            or raw.get("counterparty_gstin")
            or ""
        ).strip().upper()
        if not validate_gstin(supplier_gstin):
            raise InvalidGstinError(supplier_gstin)
        invoice_number = str(raw.get("invoice_number") or raw.get("invoice_no") or "").strip()
        parsed.append(
            ParsedGstReturnLineItem(
                supplier_gstin=supplier_gstin,
                invoice_number=invoice_number,
                invoice_date=_parse_date(raw.get("invoice_date") or raw.get("date")),
                taxable_value=_to_decimal(raw.get("taxable_value")),
                igst_amount=_to_decimal(raw.get("igst") or raw.get("igst_amount")),
                cgst_amount=_to_decimal(raw.get("cgst") or raw.get("cgst_amount")),
                sgst_amount=_to_decimal(raw.get("sgst") or raw.get("sgst_amount")),
                cess_amount=_to_decimal(raw.get("cess") or raw.get("cess_amount")),
                total_tax=(
                    _to_decimal(raw.get("igst") or raw.get("igst_amount"))
                    + _to_decimal(raw.get("cgst") or raw.get("cgst_amount"))
                    + _to_decimal(raw.get("sgst") or raw.get("sgst_amount"))
                    + _to_decimal(raw.get("cess") or raw.get("cess_amount"))
                ),
                gst_rate=_optional_decimal(raw.get("gst_rate") or raw.get("rate")),
                payment_status=_optional_text(raw.get("payment_status")),
                expense_category=_optional_text(raw.get("expense_category")),
            )
        )
    return parsed


def _collect_line_item_dicts(payload: Any):
    if isinstance(payload, list):
        for item in payload:
            yield from _collect_line_item_dicts(item)
        return
    if not isinstance(payload, dict):
        return
    if "supplier_gstin" in payload or "gstin" in payload:
        yield payload
    for value in payload.values():
        if isinstance(value, (list, dict)):
            yield from _collect_line_item_dicts(value)


def _parse_date(value: Any) -> date | None:
    if value in {None, ""}:
        return None
    return date.fromisoformat(str(value))


def _to_decimal(value: Any) -> Decimal:
    if value in {None, ""}:
        return Decimal("0")
    return Decimal(str(value))


def _optional_decimal(value: Any) -> Decimal | None:
    if value in {None, ""}:
        return None
    return Decimal(str(value))


def _optional_text(value: Any) -> str | None:
    if value in {None, ""}:
        return None
    return str(value)
