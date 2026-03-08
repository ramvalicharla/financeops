from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from financeops.modules.multi_entity_consolidation.application.adjustment_service import (
    AdjustmentService,
)
from financeops.modules.multi_entity_consolidation.application.aggregation_service import (
    AggregationService,
)
from financeops.modules.multi_entity_consolidation.application.hierarchy_service import (
    HierarchyService,
)
from financeops.modules.multi_entity_consolidation.application.intercompany_service import (
    IntercompanyService,
)
from financeops.modules.multi_entity_consolidation.application.validation_service import (
    ValidationService,
)
from financeops.modules.multi_entity_consolidation.domain.enums import RunStatus
from financeops.modules.multi_entity_consolidation.domain.value_objects import (
    ConsolidationRunTokenInput,
    DefinitionVersionTokenInput,
)
from financeops.modules.multi_entity_consolidation.infrastructure.repository import (
    MultiEntityConsolidationRepository,
)
from financeops.modules.multi_entity_consolidation.infrastructure.token_builder import (
    build_consolidation_run_token,
    build_definition_version_token,
)


class RunService:
    def __init__(
        self,
        *,
        repository: MultiEntityConsolidationRepository,
        validation_service: ValidationService,
        hierarchy_service: HierarchyService,
        aggregation_service: AggregationService,
        intercompany_service: IntercompanyService,
        adjustment_service: AdjustmentService,
    ) -> None:
        self._repository = repository
        self._validation = validation_service
        self._hierarchy = hierarchy_service
        self._aggregation = aggregation_service
        self._intercompany = intercompany_service
        self._adjustment = adjustment_service

    async def create_run(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        reporting_period: date,
        source_run_refs: list[dict[str, Any]],
        created_by: uuid.UUID,
    ) -> dict[str, Any]:
        self._validation.validate_source_run_refs(source_run_refs=source_run_refs)
        hierarchies = await self._repository.active_entity_hierarchies(
            tenant_id=tenant_id,
            organisation_id=organisation_id,
            reporting_period=reporting_period,
        )
        scopes = await self._repository.active_scopes(
            tenant_id=tenant_id,
            organisation_id=organisation_id,
            reporting_period=reporting_period,
        )
        rules = await self._repository.active_rule_definitions(
            tenant_id=tenant_id,
            organisation_id=organisation_id,
            reporting_period=reporting_period,
        )
        intercompany = await self._repository.active_intercompany_rules(
            tenant_id=tenant_id,
            organisation_id=organisation_id,
            reporting_period=reporting_period,
        )
        adjustments = await self._repository.active_adjustment_definitions(
            tenant_id=tenant_id,
            organisation_id=organisation_id,
            reporting_period=reporting_period,
        )
        self._validation.validate_definition_sets(
            hierarchy_rows=hierarchies,
            scope_rows=scopes,
            rule_rows=rules,
            intercompany_rows=intercompany,
            adjustment_rows=adjustments,
        )
        hierarchy = sorted(hierarchies, key=lambda value: (value.hierarchy_code, value.id))[0]
        scope = sorted(scopes, key=lambda value: (value.scope_code, value.id))[0]

        run_token = build_consolidation_run_token(
            ConsolidationRunTokenInput(
                tenant_id=tenant_id,
                organisation_id=organisation_id,
                reporting_period=reporting_period,
                hierarchy_version_token=self._version_token(hierarchies, "hierarchy_code"),
                scope_version_token=self._version_token(scopes, "scope_code"),
                rule_version_token=self._version_token(rules, "rule_code"),
                intercompany_version_token=self._version_token(intercompany, "rule_code"),
                adjustment_version_token=self._version_token(adjustments, "adjustment_code"),
                source_run_refs=sorted(
                    source_run_refs,
                    key=lambda row: (str(row.get("source_type", "")), str(row.get("run_id", ""))),
                ),
                run_status=RunStatus.CREATED.value,
            )
        )
        existing = await self._repository.get_run_by_token(tenant_id=tenant_id, run_token=run_token)
        if existing is not None:
            return {
                "run_id": str(existing.id),
                "run_token": existing.run_token,
                "status": existing.run_status,
                "idempotent": True,
            }

        created = await self._repository.create_run(
            tenant_id=tenant_id,
            organisation_id=organisation_id,
            reporting_period=reporting_period,
            hierarchy_id=hierarchy.id,
            scope_id=scope.id,
            hierarchy_version_token=self._version_token(hierarchies, "hierarchy_code"),
            scope_version_token=self._version_token(scopes, "scope_code"),
            rule_version_token=self._version_token(rules, "rule_code"),
            intercompany_version_token=self._version_token(intercompany, "rule_code"),
            adjustment_version_token=self._version_token(adjustments, "adjustment_code"),
            source_run_refs_json=sorted(
                source_run_refs,
                key=lambda row: (str(row.get("source_type", "")), str(row.get("run_id", ""))),
            ),
            run_token=run_token,
            run_status=RunStatus.CREATED.value,
            validation_summary_json={
                "hierarchy_versions": len(hierarchies),
                "scope_versions": len(scopes),
                "rule_versions": len(rules),
                "intercompany_versions": len(intercompany),
                "adjustment_versions": len(adjustments),
            },
            created_by=created_by,
        )
        return {
            "run_id": str(created.id),
            "run_token": created.run_token,
            "status": created.run_status,
            "idempotent": False,
        }

    async def execute_run(
        self,
        *,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
        created_by: uuid.UUID,
    ) -> dict[str, Any]:
        run = await self._repository.get_run(tenant_id=tenant_id, run_id=run_id)
        if run is None:
            raise ValueError("Consolidation run not found")

        existing_metrics = await self._repository.list_metric_results(tenant_id=tenant_id, run_id=run_id)
        if existing_metrics:
            summary = await self._repository.summarize_run(tenant_id=tenant_id, run_id=run_id)
            return {
                "run_id": str(run.id),
                "run_token": run.run_token,
                "status": run.run_status,
                "idempotent": True,
                **summary,
            }

        nodes = await self._repository.active_hierarchy_nodes(
            tenant_id=tenant_id,
            hierarchy_id=run.hierarchy_id,
        )
        entity_ids = self._hierarchy.deterministic_entity_order(nodes=nodes)
        allowed_entity_ids = {str(value) for value in entity_ids}

        source_refs = sorted(
            list(run.source_run_refs_json),
            key=lambda row: (str(row.get("source_type", "")), str(row.get("run_id", ""))),
        )
        metric_run_ids = [
            uuid.UUID(str(row["run_id"]))
            for row in source_refs
            if str(row.get("source_type")) in {"metric_run", "ratio_metric_run"}
        ]
        variance_run_ids = [
            uuid.UUID(str(row["run_id"]))
            for row in source_refs
            if str(row.get("source_type")) in {"variance_run", "ratio_variance_run"}
        ]

        metric_runs = await self._repository.list_metric_runs(
            tenant_id=tenant_id,
            run_ids=sorted(set(metric_run_ids + variance_run_ids), key=lambda value: str(value)),
        )
        runs_by_id = {row.id: row for row in metric_runs}
        for run_ref in metric_run_ids + variance_run_ids:
            if runs_by_id.get(run_ref) is None:
                raise ValueError(f"Referenced source run not found: {run_ref}")

        metric_rows = await self._repository.list_metric_results_for_runs(
            tenant_id=tenant_id,
            run_ids=metric_run_ids,
        )
        variance_rows = await self._repository.list_variance_results_for_runs(
            tenant_id=tenant_id,
            run_ids=variance_run_ids,
        )

        consolidated_metrics = self._aggregation.aggregate_metrics(
            metric_rows=metric_rows,
            allowed_entity_ids=allowed_entity_ids,
        )
        consolidated_variances = self._aggregation.aggregate_variances(
            variance_rows=variance_rows,
            allowed_entity_ids=allowed_entity_ids,
        )
        intercompany_summary = self._intercompany.classify_source_refs(source_run_refs=source_refs)
        adjustment_summary = self._adjustment.summarize_adjustments()

        metric_db_rows = [
            {
                "line_no": index,
                "metric_code": row.metric_code,
                "scope_json": {"entity_ids": sorted(allowed_entity_ids)},
                "currency_code": row.currency_code,
                "aggregated_value": row.aggregated_value,
                "entity_count": row.entity_count,
                "materiality_flag": False,
            }
            for index, row in enumerate(consolidated_metrics, start=1)
        ]
        variance_db_rows = [
            {
                "line_no": index,
                "metric_code": row.metric_code,
                "comparison_type": row.comparison_type,
                "base_value": row.base_value,
                "current_value": row.current_value,
                "variance_value": row.variance_value,
                "variance_pct": row.variance_pct,
                "materiality_flag": False,
            }
            for index, row in enumerate(consolidated_variances, start=1)
        ]
        created_metrics = await self._repository.create_metric_results(
            tenant_id=tenant_id,
            run_id=run_id,
            rows=metric_db_rows,
            created_by=created_by,
        )
        created_variances = await self._repository.create_variance_results(
            tenant_id=tenant_id,
            run_id=run_id,
            rows=variance_db_rows,
            created_by=created_by,
        )

        evidence_rows: list[dict[str, Any]] = []
        for row in created_metrics:
            evidence_rows.append(
                {
                    "metric_result_id": row.id,
                    "variance_result_id": None,
                    "evidence_type": "entity_metric_result",
                    "evidence_ref": f"metric_code:{row.metric_code}",
                    "evidence_label": f"Consolidated metric {row.metric_code}",
                    "evidence_payload_json": {"aggregated_value": str(row.aggregated_value)},
                }
            )
        for row in created_variances:
            evidence_rows.append(
                {
                    "metric_result_id": None,
                    "variance_result_id": row.id,
                    "evidence_type": "entity_variance_result",
                    "evidence_ref": f"metric_code:{row.metric_code}:{row.comparison_type}",
                    "evidence_label": f"Consolidated variance {row.metric_code}",
                    "evidence_payload_json": {"variance_value": str(row.variance_value)},
                }
            )
        evidence_rows.append(
            {
                "metric_result_id": None,
                "variance_result_id": None,
                "evidence_type": "intercompany_decision",
                "evidence_ref": "intercompany:summary",
                "evidence_label": "Intercompany hook evaluation",
                "evidence_payload_json": intercompany_summary,
            }
        )
        evidence_rows.append(
            {
                "metric_result_id": None,
                "variance_result_id": None,
                "evidence_type": "adjustment_reference",
                "evidence_ref": "adjustment:summary",
                "evidence_label": "Adjustment hook evaluation",
                "evidence_payload_json": adjustment_summary,
            }
        )
        created_evidence = await self._repository.create_evidence_links(
            tenant_id=tenant_id,
            run_id=run_id,
            rows=evidence_rows,
            created_by=created_by,
        )
        summary = await self._repository.summarize_run(tenant_id=tenant_id, run_id=run_id)
        return {
            "run_id": str(run.id),
            "run_token": run.run_token,
            "status": run.run_status,
            "idempotent": False,
            **summary,
            "intercompany_unmatched_count": int(intercompany_summary["unmatched_count"]),
            "adjustment_count": int(adjustment_summary["adjustment_count"]),
            "evidence_count": len(created_evidence),
        }

    async def get_run(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> dict[str, Any] | None:
        row = await self._repository.get_run(tenant_id=tenant_id, run_id=run_id)
        if row is None:
            return None
        return {
            "id": str(row.id),
            "organisation_id": str(row.organisation_id),
            "reporting_period": row.reporting_period.isoformat(),
            "hierarchy_id": str(row.hierarchy_id),
            "scope_id": str(row.scope_id),
            "hierarchy_version_token": row.hierarchy_version_token,
            "scope_version_token": row.scope_version_token,
            "rule_version_token": row.rule_version_token,
            "intercompany_version_token": row.intercompany_version_token,
            "adjustment_version_token": row.adjustment_version_token,
            "source_run_refs": list(row.source_run_refs_json),
            "run_token": row.run_token,
            "run_status": row.run_status,
            "validation_summary_json": dict(row.validation_summary_json),
            "created_at": row.created_at.isoformat(),
        }

    async def summary(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> dict[str, Any]:
        row = await self._repository.get_run(tenant_id=tenant_id, run_id=run_id)
        if row is None:
            raise ValueError("Consolidation run not found")
        summary = await self._repository.summarize_run(tenant_id=tenant_id, run_id=run_id)
        return {
            "run_id": str(row.id),
            "run_token": row.run_token,
            "run_status": row.run_status,
            **summary,
        }

    async def list_metrics(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> list[dict[str, Any]]:
        rows = await self._repository.list_metric_results(tenant_id=tenant_id, run_id=run_id)
        return [
            {
                "id": str(row.id),
                "line_no": row.line_no,
                "metric_code": row.metric_code,
                "scope_json": row.scope_json,
                "currency_code": row.currency_code,
                "aggregated_value": str(row.aggregated_value),
                "entity_count": row.entity_count,
                "materiality_flag": bool(row.materiality_flag),
            }
            for row in rows
        ]

    async def list_variances(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> list[dict[str, Any]]:
        rows = await self._repository.list_variance_results(tenant_id=tenant_id, run_id=run_id)
        return [
            {
                "id": str(row.id),
                "line_no": row.line_no,
                "metric_code": row.metric_code,
                "comparison_type": row.comparison_type,
                "base_value": str(row.base_value),
                "current_value": str(row.current_value),
                "variance_value": str(row.variance_value),
                "variance_pct": None if row.variance_pct is None else str(row.variance_pct),
                "materiality_flag": bool(row.materiality_flag),
            }
            for row in rows
        ]

    async def list_evidence(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> list[dict[str, Any]]:
        rows = await self._repository.list_evidence_links(tenant_id=tenant_id, run_id=run_id)
        return [
            {
                "id": str(row.id),
                "metric_result_id": None if row.metric_result_id is None else str(row.metric_result_id),
                "variance_result_id": None if row.variance_result_id is None else str(row.variance_result_id),
                "evidence_type": row.evidence_type,
                "evidence_ref": row.evidence_ref,
                "evidence_label": row.evidence_label,
                "evidence_payload_json": row.evidence_payload_json,
            }
            for row in rows
        ]

    def _version_token(self, rows: list[object], code_field: str) -> str:
        payload_rows = [
            {
                "id": str(row.id),
                "code": str(getattr(row, code_field)),
                "version_token": str(row.version_token),
                "effective_from": row.effective_from.isoformat(),
            }
            for row in sorted(rows, key=lambda value: (str(getattr(value, code_field)), str(value.id)))
        ]
        return build_definition_version_token(DefinitionVersionTokenInput(rows=payload_rows))
