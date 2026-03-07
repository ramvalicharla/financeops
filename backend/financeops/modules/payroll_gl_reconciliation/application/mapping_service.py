from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from typing import Any

from financeops.db.models.payroll_gl_reconciliation import PayrollGlReconciliationMapping
from financeops.modules.payroll_gl_reconciliation.domain.value_objects import (
    MappingVersionTokenInput,
)
from financeops.modules.payroll_gl_reconciliation.infrastructure.token_builder import (
    build_mapping_version_token,
)


class MappingService:
    def mapping_version_token(
        self, rows: Iterable[PayrollGlReconciliationMapping]
    ) -> str:
        payload: list[dict[str, Any]] = []
        for row in rows:
            payload.append(
                {
                    "mapping_code": row.mapping_code,
                    "payroll_metric_code": row.payroll_metric_code,
                    "gl_account_selector_json": row.gl_account_selector_json or {},
                    "cost_center_rule_json": row.cost_center_rule_json or {},
                    "department_rule_json": row.department_rule_json or {},
                    "entity_rule_json": row.entity_rule_json or {},
                    "effective_from": row.effective_from.isoformat(),
                    "status": row.status,
                }
            )
        payload.sort(
            key=lambda item: (
                str(item["mapping_code"]),
                str(item["payroll_metric_code"]),
                str(item["effective_from"]),
            )
        )
        return build_mapping_version_token(MappingVersionTokenInput(mapping_rows=payload))

    def validate_active_set(
        self,
        rows: Iterable[PayrollGlReconciliationMapping],
        *,
        reporting_period: date,
    ) -> list[PayrollGlReconciliationMapping]:
        selected = sorted(
            (
                row
                for row in rows
                if row.status == "active" and row.effective_from <= reporting_period
            ),
            key=lambda item: (item.mapping_code, item.effective_from, str(item.id)),
        )
        if not selected:
            raise ValueError("No active payroll-gl reconciliation mappings found")

        by_metric: dict[str, list[PayrollGlReconciliationMapping]] = {}
        for row in selected:
            by_metric.setdefault(row.payroll_metric_code, []).append(row)
        duplicate_metrics = sorted(
            metric for metric, metric_rows in by_metric.items() if len(metric_rows) > 1
        )
        if duplicate_metrics:
            raise ValueError(
                "Duplicate active payroll metric mappings found: "
                + ", ".join(duplicate_metrics)
            )
        return selected

