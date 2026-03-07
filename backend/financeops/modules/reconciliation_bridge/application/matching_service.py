from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from financeops.modules.reconciliation_bridge.domain.entities import (
    ReconciliationComputedLine,
)
from financeops.modules.reconciliation_bridge.domain.enums import (
    DifferenceType,
    ReconciliationStatus,
)
from financeops.utils.determinism import canonical_json_dumps, sha256_hex_text

_SCALE = Decimal("0.000001")
_HUNDRED = Decimal("100")


def _q(value: Decimal | int | float | str) -> Decimal:
    return Decimal(str(value)).quantize(_SCALE, rounding=ROUND_HALF_UP)


def _line_key(seed: dict[str, Any]) -> str:
    return sha256_hex_text(canonical_json_dumps(seed))


def _to_decimal(value: Any) -> Decimal:
    return _q(value if isinstance(value, Decimal) else Decimal(str(value)))


def _read_thresholds(
    *,
    materiality_config_json: dict[str, Any],
    account: str,
) -> tuple[Decimal, Decimal]:
    absolute_threshold = _to_decimal(materiality_config_json.get("absolute_threshold", "0"))
    percentage_threshold = _to_decimal(
        materiality_config_json.get("percentage_threshold", "0")
    )
    account_overrides = materiality_config_json.get("account_overrides") or {}
    override = account_overrides.get(account) if isinstance(account_overrides, dict) else None
    if isinstance(override, dict):
        if "absolute_threshold" in override:
            absolute_threshold = _to_decimal(override["absolute_threshold"])
        if "percentage_threshold" in override:
            percentage_threshold = _to_decimal(override["percentage_threshold"])
    return absolute_threshold, percentage_threshold


def _evaluate_materiality(
    *,
    variance_abs: Decimal,
    base_amount: Decimal,
    absolute_threshold: Decimal,
    percentage_threshold: Decimal,
) -> tuple[bool, Decimal]:
    percentage_limit = Decimal("0")
    if base_amount != Decimal("0"):
        percentage_limit = (base_amount.copy_abs() * percentage_threshold / _HUNDRED).quantize(
            _SCALE, rounding=ROUND_HALF_UP
        )
    effective_threshold = max(absolute_threshold, percentage_limit)
    return variance_abs > effective_threshold, effective_threshold


def _build_line(
    *,
    dimensions: dict[str, Any],
    source_a_value: Decimal,
    source_b_value: Decimal,
    difference_type: DifferenceType,
    materiality_config_json: dict[str, Any],
) -> ReconciliationComputedLine:
    source_a_q = _q(source_a_value)
    source_b_q = _q(source_b_value)
    variance_value = _q(source_a_q - source_b_q)
    variance_abs = _q(variance_value.copy_abs())

    if source_b_q == Decimal("0"):
        variance_pct = Decimal("0") if variance_abs == Decimal("0") else Decimal("100")
    else:
        variance_pct = _q((variance_abs / source_b_q.copy_abs()) * _HUNDRED)

    account = str(dimensions.get("account") or dimensions.get("metric") or "unknown")
    abs_threshold, pct_threshold = _read_thresholds(
        materiality_config_json=materiality_config_json,
        account=account,
    )
    materiality_flag, effective_threshold = _evaluate_materiality(
        variance_abs=variance_abs,
        base_amount=source_b_q,
        absolute_threshold=abs_threshold,
        percentage_threshold=pct_threshold,
    )

    status = ReconciliationStatus.MATCHED
    if difference_type != DifferenceType.NONE:
        status = ReconciliationStatus.EXCEPTION
    elif variance_abs > effective_threshold:
        status = ReconciliationStatus.EXCEPTION

    return ReconciliationComputedLine(
        line_key=_line_key(dimensions),
        comparison_dimension_json=dimensions,
        source_a_value=source_a_q,
        source_b_value=source_b_q,
        variance_value=variance_value,
        variance_abs=variance_abs,
        variance_pct=variance_pct,
        currency_code=str(dimensions.get("currency_code") or "USD"),
        reconciliation_status=status,
        difference_type=difference_type,
        materiality_flag=materiality_flag,
        explanation_hint=None if status == ReconciliationStatus.MATCHED else "review_required",
    )


class MatchingService:
    def match_gl_vs_tb(
        self,
        *,
        source_a_rows: Iterable[dict[str, Any]],
        source_b_rows: Iterable[dict[str, Any]],
        materiality_config_json: dict[str, Any],
    ) -> list[ReconciliationComputedLine]:
        gl_map: dict[tuple[str, str, str, str], Decimal] = {}
        tb_map: dict[tuple[str, str, str, str], Decimal] = {}

        for row in source_a_rows:
            key = (
                str(row["account"]),
                str(row["entity"]),
                str(row["currency"]),
                str(row["period"]),
            )
            gl_map[key] = _q(gl_map.get(key, Decimal("0")) + _to_decimal(row["value"]))
        for row in source_b_rows:
            key = (
                str(row["account"]),
                str(row["entity"]),
                str(row["currency"]),
                str(row["period"]),
            )
            tb_map[key] = _q(tb_map.get(key, Decimal("0")) + _to_decimal(row["value"]))

        lines: list[ReconciliationComputedLine] = []
        all_keys = sorted(set(gl_map.keys()) | set(tb_map.keys()))
        for account, entity, currency, period in all_keys:
            a_value = gl_map.get((account, entity, currency, period), Decimal("0"))
            b_value = tb_map.get((account, entity, currency, period), Decimal("0"))
            if (account, entity, currency, period) not in gl_map:
                difference_type = DifferenceType.MISSING_IN_A
            elif (account, entity, currency, period) not in tb_map:
                difference_type = DifferenceType.MISSING_IN_B
            elif _q(a_value - b_value) == Decimal("0"):
                difference_type = DifferenceType.NONE
            else:
                difference_type = DifferenceType.VALUE_MISMATCH

            dimensions = {
                "account": account,
                "entity": entity,
                "currency_code": currency,
                "period": period,
            }
            lines.append(
                _build_line(
                    dimensions=dimensions,
                    source_a_value=a_value,
                    source_b_value=b_value,
                    difference_type=difference_type,
                    materiality_config_json=materiality_config_json,
                )
            )
        return lines

    def match_mis_vs_tb(
        self,
        *,
        source_a_rows: Iterable[dict[str, Any]],
        source_b_rows: Iterable[dict[str, Any]],
        materiality_config_json: dict[str, Any],
    ) -> list[ReconciliationComputedLine]:
        mapping = materiality_config_json.get("mapping") or {}
        mapping = mapping if isinstance(mapping, dict) else {}

        tb_map: dict[tuple[str, str, str, str], Decimal] = {}
        for row in source_b_rows:
            key = (
                str(row["account"]),
                str(row["entity"]),
                str(row["currency"]),
                str(row["period"]),
            )
            tb_map[key] = _q(tb_map.get(key, Decimal("0")) + _to_decimal(row["value"]))

        lines: list[ReconciliationComputedLine] = []
        used_tb_keys: set[tuple[str, str, str, str]] = set()

        sorted_mis = sorted(
            source_a_rows,
            key=lambda row: (
                str(row["metric"]),
                str(row["entity"]),
                str(row["currency"]),
                str(row["period"]),
            ),
        )

        for row in sorted_mis:
            metric = str(row["metric"])
            entity = str(row["entity"])
            currency = str(row["currency"])
            period = str(row["period"])
            mis_value = _to_decimal(row["value"])

            raw_accounts = mapping.get(metric)
            mapped_accounts: list[str] = []
            if isinstance(raw_accounts, str):
                mapped_accounts = [raw_accounts]
            elif isinstance(raw_accounts, list):
                mapped_accounts = sorted(str(item) for item in raw_accounts)

            if not mapped_accounts:
                direct_key = (metric, entity, currency, period)
                if direct_key in tb_map:
                    mapped_accounts = [metric]

            if not mapped_accounts:
                dimensions = {
                    "metric": metric,
                    "entity": entity,
                    "currency_code": currency,
                    "period": period,
                }
                lines.append(
                    _build_line(
                        dimensions=dimensions,
                        source_a_value=mis_value,
                        source_b_value=Decimal("0"),
                        difference_type=DifferenceType.MAPPING_GAP,
                        materiality_config_json=materiality_config_json,
                    )
                )
                continue

            tb_value = Decimal("0")
            for account in mapped_accounts:
                key = (account, entity, currency, period)
                tb_value = _q(tb_value + tb_map.get(key, Decimal("0")))
                if key in tb_map:
                    used_tb_keys.add(key)

            difference_type = DifferenceType.NONE
            if tb_value == Decimal("0") and mis_value != Decimal("0"):
                difference_type = DifferenceType.MISSING_IN_B
            elif _q(mis_value - tb_value) != Decimal("0"):
                difference_type = DifferenceType.VALUE_MISMATCH

            dimensions = {
                "metric": metric,
                "mapped_accounts": mapped_accounts,
                "entity": entity,
                "currency_code": currency,
                "period": period,
            }
            lines.append(
                _build_line(
                    dimensions=dimensions,
                    source_a_value=mis_value,
                    source_b_value=tb_value,
                    difference_type=difference_type,
                    materiality_config_json=materiality_config_json,
                )
            )

        for account, entity, currency, period in sorted(tb_map.keys()):
            key = (account, entity, currency, period)
            if key in used_tb_keys:
                continue
            dimensions = {
                "account": account,
                "entity": entity,
                "currency_code": currency,
                "period": period,
            }
            lines.append(
                _build_line(
                    dimensions=dimensions,
                    source_a_value=Decimal("0"),
                    source_b_value=tb_map[key],
                    difference_type=DifferenceType.MISSING_IN_A,
                    materiality_config_json=materiality_config_json,
                )
            )

        lines.sort(key=lambda item: (item.line_key, item.comparison_dimension_json.get("period", "")))
        return lines
