from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from difflib import SequenceMatcher

from financeops.db.models.gst import GstReconItem, GstReturn, GstReturnLineItem
from financeops.modules.gst_reconciliation.application.gst_service import validate_gst_rate
from financeops.modules.gst_reconciliation.application.itc_eligibility_service import evaluate_itc_eligibility

_AMOUNT_TOLERANCE = Decimal("0.0001")


@dataclass(slots=True)
class GstMatchContext:
    rate_master: frozenset[Decimal]
    today: date


def build_recon_items(
    *,
    return_a: GstReturn,
    return_b: GstReturn,
    lines_a: list[GstReturnLineItem],
    lines_b: list[GstReturnLineItem],
    run_by,
    context: GstMatchContext,
) -> list[GstReconItem]:
    pass_one_index: dict[tuple[str, str, Decimal], list[GstReturnLineItem]] = {}
    for row in lines_b:
        key = (_normalize_gstin(row.supplier_gstin), _normalize_invoice(row.invoice_number), row.taxable_value)
        pass_one_index.setdefault(key, []).append(row)

    remaining_b: dict[str, GstReturnLineItem] = {_line_key(row): row for row in lines_b}
    items: list[GstReconItem] = []

    for line_a in lines_a:
        exact_key = (
            _normalize_gstin(line_a.supplier_gstin),
            _normalize_invoice(line_a.invoice_number),
            line_a.taxable_value,
        )
        candidates = pass_one_index.get(exact_key, [])
        matched = _take_match(candidates, remaining_b)
        if matched is not None:
            items.append(_build_item(return_a, return_b, line_a, matched, run_by, "matched", context))
            continue

        matched = _find_near_match(line_a, remaining_b.values())
        if matched is not None:
            remaining_b.pop(_line_key(matched), None)
            items.append(_build_item(return_a, return_b, line_a, matched, run_by, "near_match", context))
            continue

        matched = _find_fuzzy_match(line_a, remaining_b.values())
        if matched is not None:
            remaining_b.pop(_line_key(matched), None)
            items.append(_build_item(return_a, return_b, line_a, matched, run_by, "fuzzy_match", context))
            continue

        items.append(_build_item(return_a, return_b, line_a, None, run_by, "return_only", context))

    for line_b in remaining_b.values():
        items.append(_build_item(return_a, return_b, None, line_b, run_by, "portal_only", context))
    return items


def _build_item(
    return_a: GstReturn,
    return_b: GstReturn,
    line_a: GstReturnLineItem | None,
    line_b: GstReturnLineItem | None,
    run_by,
    match_type: str,
    context: GstMatchContext,
) -> GstReconItem:
    source_line = line_a or line_b
    assert source_line is not None
    appears_in_gstr2b = line_b is not None
    itc_result = evaluate_itc_eligibility(
        line_item=source_line,
        appears_in_gstr2b=appears_in_gstr2b,
        today=context.today,
    )
    value_a = line_a.taxable_value if line_a is not None else Decimal("0")
    value_b = line_b.taxable_value if line_b is not None else Decimal("0")
    difference = value_b - value_a
    gst_rate = source_line.gst_rate
    return GstReconItem(
        tenant_id=return_a.tenant_id,
        chain_hash="",
        previous_hash="",
        period_year=return_a.period_year,
        period_month=return_a.period_month,
        entity_id=return_a.entity_id,
        entity_name=return_a.entity_name,
        return_type_a=return_a.return_type,
        return_type_b=return_b.return_type,
        return_a_id=return_a.id,
        return_b_id=return_b.id,
        field_name="invoice_match",
        value_a=value_a,
        value_b=value_b,
        difference=difference,
        status="open",
        notes=None,
        resolved_by=None,
        run_by=run_by,
        line_item_a_id=line_a.id if line_a is not None else None,
        line_item_b_id=line_b.id if line_b is not None else None,
        supplier_gstin=source_line.supplier_gstin,
        invoice_number=source_line.invoice_number,
        invoice_date=source_line.invoice_date,
        gst_rate=gst_rate,
        rate_mismatch=not validate_gst_rate(gst_rate, context.rate_master),
        match_type=match_type,
        itc_eligible=itc_result.itc_eligible,
        itc_blocked_reason=itc_result.itc_blocked_reason,
        reverse_itc=itc_result.reverse_itc,
    )


def _take_match(candidates: list[GstReturnLineItem], remaining_b: dict[str, GstReturnLineItem]) -> GstReturnLineItem | None:
    while candidates:
        candidate = candidates.pop(0)
        removed = remaining_b.pop(_line_key(candidate), None)
        if removed is not None:
            return removed
    return None


def _find_near_match(
    line_a: GstReturnLineItem,
    candidates,
) -> GstReturnLineItem | None:
    for line_b in candidates:
        if _normalize_gstin(line_a.supplier_gstin) != _normalize_gstin(line_b.supplier_gstin):
            continue
        if line_a.taxable_value != line_b.taxable_value:
            continue
        if line_a.invoice_date is None or line_b.invoice_date is None:
            continue
        if abs((line_a.invoice_date - line_b.invoice_date).days) <= 3:
            return line_b
    return None


def _find_fuzzy_match(
    line_a: GstReturnLineItem,
    candidates,
) -> GstReturnLineItem | None:
    normalized_invoice_a = _normalize_invoice(line_a.invoice_number)
    for line_b in candidates:
        if _normalize_gstin(line_a.supplier_gstin) != _normalize_gstin(line_b.supplier_gstin):
            continue
        if line_b.taxable_value == Decimal("0"):
            continue
        if abs(line_a.taxable_value - line_b.taxable_value) / abs(line_b.taxable_value) >= _AMOUNT_TOLERANCE:
            continue
        ratio = SequenceMatcher(None, normalized_invoice_a, _normalize_invoice(line_b.invoice_number)).ratio()
        if ratio > 0.8:
            return line_b
    return None


def _normalize_invoice(invoice_number: str | None) -> str:
    return "".join(ch for ch in str(invoice_number or "").strip().upper() if ch.isalnum())


def _normalize_gstin(gstin: str | None) -> str:
    return str(gstin or "").strip().upper()


def _line_key(row: GstReturnLineItem) -> str:
    return f"{row.id}"
