from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from financeops.db.models.payroll_gl_normalization import GlNormalizedLine, PayrollNormalizedLine
from financeops.db.models.payroll_gl_reconciliation import (
    PayrollGlReconciliationMapping,
)
from financeops.modules.payroll_gl_reconciliation.domain.entities import (
    PayrollGlComparisonLine,
)
from financeops.modules.payroll_gl_reconciliation.domain.enums import (
    CoreDifferenceType,
    PayrollGlDifferenceType,
)
from financeops.utils.determinism import canonical_json_dumps, sha256_hex_text

_SIX_DP = Decimal("0.000001")
_HUNDRED = Decimal("100")


def _q6(value: Decimal | int | float | str) -> Decimal:
    return Decimal(str(value)).quantize(_SIX_DP, rounding=ROUND_HALF_UP)


def _token_key(payload: dict[str, Any]) -> str:
    return sha256_hex_text(canonical_json_dumps(payload))


def _safe_text(value: str | None) -> str:
    return str(value or "").strip()


def _selector_accounts(mapping: PayrollGlReconciliationMapping) -> set[str]:
    selector = mapping.gl_account_selector_json or {}
    values: list[str] = []
    raw = selector.get("account_codes")
    if isinstance(raw, list):
        values.extend(str(item).strip() for item in raw)
    raw_accounts = selector.get("accounts")
    if isinstance(raw_accounts, list):
        values.extend(str(item).strip() for item in raw_accounts)
    return {item for item in values if item}


def _selector_prefixes(mapping: PayrollGlReconciliationMapping) -> tuple[str, ...]:
    selector = mapping.gl_account_selector_json or {}
    prefixes = selector.get("account_prefixes")
    if not isinstance(prefixes, list):
        return ()
    return tuple(sorted({_safe_text(item) for item in prefixes if _safe_text(item)}))


def _account_matches(
    account_code: str,
    *,
    accounts: set[str],
    prefixes: tuple[str, ...],
) -> bool:
    if account_code in accounts:
        return True
    return any(account_code.startswith(prefix) for prefix in prefixes)


def _sum_gl(
    gl_rows: list[dict[str, Any]],
) -> Decimal:
    total = Decimal("0")
    for row in gl_rows:
        total = _q6(total + _q6(row["signed_amount"]))
    return total


def _variance_pct(payroll_value: Decimal, gl_value: Decimal, variance_abs: Decimal) -> Decimal:
    if gl_value == Decimal("0"):
        return Decimal("0") if variance_abs == Decimal("0") else Decimal("100")
    return _q6((variance_abs / gl_value.copy_abs()) * _HUNDRED)


def _materiality(
    *,
    payroll_metric_code: str,
    entity: str,
    variance_abs: Decimal,
    base_amount: Decimal,
    materiality_config_json: dict[str, Any],
) -> bool:
    absolute_threshold = _q6(materiality_config_json.get("absolute_threshold", "0"))
    percentage_threshold = _q6(materiality_config_json.get("percentage_threshold", "0"))
    metric_overrides = materiality_config_json.get("metric_overrides") or {}
    entity_overrides = materiality_config_json.get("entity_overrides") or {}
    statutory_metrics = {
        str(item)
        for item in (materiality_config_json.get("statutory_metrics") or [])
    }

    metric_override = metric_overrides.get(payroll_metric_code)
    if isinstance(metric_override, dict):
        if "absolute_threshold" in metric_override:
            absolute_threshold = _q6(metric_override["absolute_threshold"])
        if "percentage_threshold" in metric_override:
            percentage_threshold = _q6(metric_override["percentage_threshold"])

    entity_override = entity_overrides.get(entity)
    if isinstance(entity_override, dict):
        if "absolute_threshold" in entity_override:
            absolute_threshold = _q6(entity_override["absolute_threshold"])
        if "percentage_threshold" in entity_override:
            percentage_threshold = _q6(entity_override["percentage_threshold"])

    if payroll_metric_code in statutory_metrics and variance_abs > Decimal("0"):
        return True

    percentage_limit = Decimal("0")
    if base_amount != Decimal("0"):
        percentage_limit = _q6((base_amount.copy_abs() * percentage_threshold) / _HUNDRED)
    effective_threshold = max(absolute_threshold, percentage_limit)
    return variance_abs > effective_threshold


class MatchingService:
    def match(
        self,
        *,
        payroll_lines: Iterable[PayrollNormalizedLine],
        gl_lines: Iterable[GlNormalizedLine],
        mappings: list[PayrollGlReconciliationMapping],
        reporting_period: date,
        materiality_config_json: dict[str, Any],
        tolerance_json: dict[str, Decimal],
        max_timing_lag_days: int,
    ) -> list[PayrollGlComparisonLine]:
        payroll_rows = sorted(
            payroll_lines,
            key=lambda row: (
                row.row_no,
                _safe_text(row.employee_code),
                _safe_text(row.canonical_metric_code),
                str(row.id),
            ),
        )
        gl_rows = sorted(
            gl_lines,
            key=lambda row: (
                row.row_no,
                _safe_text(row.account_code),
                _safe_text(row.legal_entity),
                str(row.id),
            ),
        )

        payroll_agg: dict[tuple[str, str, str, str, str], Decimal] = defaultdict(Decimal)
        for row in payroll_rows:
            key = (
                _safe_text(row.canonical_metric_code),
                _safe_text(row.legal_entity),
                _safe_text(row.department),
                _safe_text(row.cost_center),
                _safe_text(row.currency_code) or "USD",
            )
            payroll_agg[key] = _q6(payroll_agg[key] + _q6(row.amount_value))

        gl_entries: list[dict[str, Any]] = []
        for row in gl_rows:
            gl_entries.append(
                {
                    "id": str(row.id),
                    "account_code": _safe_text(row.account_code),
                    "legal_entity": _safe_text(row.legal_entity),
                    "department": _safe_text(row.department),
                    "cost_center": _safe_text(row.cost_center),
                    "currency_code": _safe_text(row.currency_code) or "USD",
                    "signed_amount": _q6(row.signed_amount),
                    "posting_date": row.posting_date,
                }
            )

        mapping_by_metric = {row.payroll_metric_code: row for row in mappings}
        tolerance_abs = _q6(tolerance_json.get("absolute_threshold", Decimal("0")))
        rounding_threshold = _q6(
            materiality_config_json.get("rounding_threshold", tolerance_abs)
        )

        used_gl_ids: set[str] = set()
        lines: list[PayrollGlComparisonLine] = []

        for key in sorted(payroll_agg.keys()):
            metric, entity, department, cost_center, currency = key
            payroll_value = _q6(payroll_agg[key])
            mapping = mapping_by_metric.get(metric)
            if mapping is None:
                lines.append(
                    self._build_line(
                        metric=metric,
                        entity=entity,
                        department=department,
                        cost_center=cost_center,
                        currency=currency,
                        payroll_value=payroll_value,
                        gl_value=Decimal("0"),
                        payroll_difference_type=PayrollGlDifferenceType.MAPPING_GAP,
                        core_difference_type=CoreDifferenceType.MAPPING_GAP,
                        materiality_config_json=materiality_config_json,
                    )
                )
                continue

            accounts = _selector_accounts(mapping)
            prefixes = _selector_prefixes(mapping)
            if not accounts and not prefixes:
                lines.append(
                    self._build_line(
                        metric=metric,
                        entity=entity,
                        department=department,
                        cost_center=cost_center,
                        currency=currency,
                        payroll_value=payroll_value,
                        gl_value=Decimal("0"),
                        payroll_difference_type=PayrollGlDifferenceType.MAPPING_GAP,
                        core_difference_type=CoreDifferenceType.MAPPING_GAP,
                        materiality_config_json=materiality_config_json,
                    )
                )
                continue

            account_candidates = [
                row
                for row in gl_entries
                if row["currency_code"] == currency
                and _account_matches(
                    row["account_code"],
                    accounts=accounts,
                    prefixes=prefixes,
                )
            ]
            entity_candidates = [
                row
                for row in account_candidates
                if not entity or not row["legal_entity"] or row["legal_entity"] == entity
            ]
            dept_candidates = [
                row
                for row in entity_candidates
                if not department or not row["department"] or row["department"] == department
            ]
            cc_candidates = [
                row
                for row in dept_candidates
                if not cost_center or not row["cost_center"] or row["cost_center"] == cost_center
            ]

            gl_value = _sum_gl(cc_candidates)
            for row in cc_candidates:
                used_gl_ids.add(row["id"])

            payroll_difference_type = PayrollGlDifferenceType.ROUNDING_DIFFERENCE
            core_difference_type = CoreDifferenceType.NONE
            variance_abs = _q6((payroll_value - gl_value).copy_abs())
            if variance_abs == Decimal("0"):
                payroll_difference_type = PayrollGlDifferenceType.ROUNDING_DIFFERENCE
                core_difference_type = CoreDifferenceType.NONE
            elif variance_abs <= rounding_threshold:
                payroll_difference_type = PayrollGlDifferenceType.ROUNDING_DIFFERENCE
                core_difference_type = CoreDifferenceType.VALUE_MISMATCH
            elif not account_candidates:
                payroll_difference_type = PayrollGlDifferenceType.MISSING_GL_POSTING
                core_difference_type = CoreDifferenceType.MISSING_IN_B
            elif account_candidates and not entity_candidates:
                payroll_difference_type = PayrollGlDifferenceType.ENTITY_MISMATCH
                core_difference_type = CoreDifferenceType.CLASSIFICATION_DIFFERENCE
            elif entity_candidates and not dept_candidates:
                payroll_difference_type = PayrollGlDifferenceType.COST_CENTER_MISMATCH
                core_difference_type = CoreDifferenceType.CLASSIFICATION_DIFFERENCE
            elif dept_candidates and not cc_candidates:
                payroll_difference_type = PayrollGlDifferenceType.COST_CENTER_MISMATCH
                core_difference_type = CoreDifferenceType.CLASSIFICATION_DIFFERENCE
            elif self._is_timing_difference(
                candidates=account_candidates,
                reporting_period=reporting_period,
                max_lag_days=max_timing_lag_days,
            ):
                payroll_difference_type = PayrollGlDifferenceType.TIMING_DIFFERENCE
                core_difference_type = CoreDifferenceType.TIMING_DIFFERENCE
            elif metric == "net_pay":
                payroll_difference_type = PayrollGlDifferenceType.PAYABLE_MISMATCH
                core_difference_type = CoreDifferenceType.VALUE_MISMATCH
            elif metric in {"employer_pf", "employer_esi", "payroll_tax"}:
                payroll_difference_type = PayrollGlDifferenceType.ACCRUAL_GAP
                core_difference_type = CoreDifferenceType.VALUE_MISMATCH
            else:
                payroll_difference_type = PayrollGlDifferenceType.CLASSIFICATION_DIFFERENCE
                core_difference_type = CoreDifferenceType.VALUE_MISMATCH

            lines.append(
                self._build_line(
                    metric=metric,
                    entity=entity,
                    department=department,
                    cost_center=cost_center,
                    currency=currency,
                    payroll_value=payroll_value,
                    gl_value=gl_value,
                    payroll_difference_type=payroll_difference_type,
                    core_difference_type=core_difference_type,
                    materiality_config_json=materiality_config_json,
                )
            )

        # Unmatched GL rows in mapped account buckets are explicit gaps.
        mapped_accounts: set[str] = set()
        mapped_prefixes: set[str] = set()
        for mapping in mappings:
            mapped_accounts |= _selector_accounts(mapping)
            mapped_prefixes |= set(_selector_prefixes(mapping))
        extra_gl = [
            row
            for row in gl_entries
            if row["id"] not in used_gl_ids
            and (
                row["account_code"] in mapped_accounts
                or any(row["account_code"].startswith(prefix) for prefix in mapped_prefixes)
            )
        ]
        extra_by_key: dict[tuple[str, str, str, str, str], Decimal] = defaultdict(Decimal)
        for row in extra_gl:
            key = (
                row["account_code"],
                row["legal_entity"],
                row["department"],
                row["cost_center"],
                row["currency_code"],
            )
            extra_by_key[key] = _q6(extra_by_key[key] + row["signed_amount"])
        for key in sorted(extra_by_key.keys()):
            account_code, entity, department, cost_center, currency = key
            lines.append(
                self._build_line(
                    metric=f"gl_only:{account_code}",
                    entity=entity,
                    department=department,
                    cost_center=cost_center,
                    currency=currency,
                    payroll_value=Decimal("0"),
                    gl_value=_q6(extra_by_key[key]),
                    payroll_difference_type=PayrollGlDifferenceType.MISSING_PAYROLL_COMPONENT,
                    core_difference_type=CoreDifferenceType.MISSING_IN_A,
                    materiality_config_json=materiality_config_json,
                )
            )

        lines.sort(key=lambda item: item.line_key)
        return lines

    def _build_line(
        self,
        *,
        metric: str,
        entity: str,
        department: str,
        cost_center: str,
        currency: str,
        payroll_value: Decimal,
        gl_value: Decimal,
        payroll_difference_type: PayrollGlDifferenceType,
        core_difference_type: CoreDifferenceType,
        materiality_config_json: dict[str, Any],
    ) -> PayrollGlComparisonLine:
        payroll_q = _q6(payroll_value)
        gl_q = _q6(gl_value)
        variance_value = _q6(payroll_q - gl_q)
        variance_abs = _q6(variance_value.copy_abs())
        base_amount = gl_q if gl_q != Decimal("0") else payroll_q
        variance_pct = _variance_pct(payroll_q, gl_q, variance_abs)
        materiality_flag = _materiality(
            payroll_metric_code=metric,
            entity=entity,
            variance_abs=variance_abs,
            base_amount=base_amount,
            materiality_config_json=materiality_config_json,
        )
        comparison_dimension_json = {
            "payroll_metric_code": metric,
            "legal_entity": entity,
            "department": department,
            "cost_center": cost_center,
            "currency_code": currency,
        }
        return PayrollGlComparisonLine(
            line_key=_token_key(comparison_dimension_json),
            comparison_dimension_json=comparison_dimension_json,
            payroll_value=payroll_q,
            gl_value=gl_q,
            variance_value=variance_value,
            variance_abs=variance_abs,
            variance_pct=variance_pct,
            currency_code=currency,
            core_difference_type=core_difference_type,
            payroll_difference_type=payroll_difference_type,
            materiality_flag=materiality_flag,
            explanation_hint=(
                None if core_difference_type == CoreDifferenceType.NONE else "review_required"
            ),
        )

    def _is_timing_difference(
        self,
        *,
        candidates: list[dict[str, Any]],
        reporting_period: date,
        max_lag_days: int,
    ) -> bool:
        if max_lag_days <= 0:
            return False
        for row in candidates:
            posting_date = row.get("posting_date")
            if posting_date is None:
                continue
            lag_days = abs((posting_date - reporting_period).days)
            if lag_days <= max_lag_days and posting_date.month != reporting_period.month:
                return True
        return False

