from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from financeops.accounting_policy_engine import AccountingPolicyService
from financeops.config import settings
from financeops.data_quality_engine import (
    DataQualityValidationService,
    consolidation_metric_rules,
    consolidation_variance_rules,
)
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
from financeops.modules.ownership_consolidation.application.mapping_service import (
    MappingService as OwnershipMappingService,
)
from financeops.modules.ownership_consolidation.infrastructure.repository import (
    OwnershipConsolidationRepository,
)


class RunService:
    _RESULT_CHUNK_SIZE = 250

    def __init__(
        self,
        *,
        repository: MultiEntityConsolidationRepository,
        validation_service: ValidationService,
        hierarchy_service: HierarchyService,
        aggregation_service: AggregationService,
        intercompany_service: IntercompanyService,
        adjustment_service: AdjustmentService,
        policy_service: AccountingPolicyService | None = None,
    ) -> None:
        self._repository = repository
        self._validation = validation_service
        self._hierarchy = hierarchy_service
        self._aggregation = aggregation_service
        self._intercompany = intercompany_service
        self._adjustment = adjustment_service
        self._policy = policy_service or AccountingPolicyService()
        self._data_quality = DataQualityValidationService()

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
        intercompany = await self._repository.active_intercompany_rules(
            tenant_id=tenant_id,
            organisation_id=run.organisation_id,
            reporting_period=run.reporting_period,
        )
        adjustments = await self._repository.active_adjustment_definitions(
            tenant_id=tenant_id,
            organisation_id=run.organisation_id,
            reporting_period=run.reporting_period,
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
        metric_validation = self._data_quality.validate_dataset(
            rules=consolidation_metric_rules(),
            rows=[self._metric_validation_row(row) for row in metric_rows],
        )
        self._data_quality.raise_if_fail(report=metric_validation)
        variance_validation = self._data_quality.validate_dataset(
            rules=consolidation_variance_rules(),
            rows=[self._variance_validation_row(row) for row in variance_rows],
        )
        self._data_quality.raise_if_fail(report=variance_validation)

        consolidated_metrics = self._aggregation.aggregate_metrics(
            metric_rows=metric_rows,
            allowed_entity_ids=allowed_entity_ids,
        )
        consolidated_variances = self._aggregation.aggregate_variances(
            variance_rows=variance_rows,
            allowed_entity_ids=allowed_entity_ids,
        )
        intercompany_summary = self._intercompany.classify_source_refs(
            source_run_refs=source_refs,
            metric_rows=metric_rows,
            intercompany_rules=intercompany,
        )
        intercompany_policy = self._policy.apply_intercompany_profit_elimination_policy(
            elimination_entries=list(intercompany_summary["elimination_entries"]),
            current_date=run.reporting_period,
        )
        intercompany_summary = {
            **intercompany_summary,
            "elimination_entries": list(intercompany_policy["policy_applied_entries"]),
            "elimination_count": len(intercompany_policy["policy_applied_entries"]),
            "elimination_applied": any(
                str(row.get("elimination_status", "")) == "applied"
                for row in intercompany_policy["policy_applied_entries"]
            ),
            "policy_application": intercompany_policy,
        }
        adjustment_summary = self._adjustment.summarize_adjustments(
            consolidated_metrics=consolidated_metrics,
            intercompany_summary=intercompany_summary,
            adjustment_rows=adjustments,
        )
        minority_interest_summary = await self._compute_minority_interest_summary(
            tenant_id=tenant_id,
            organisation_id=run.organisation_id,
            reporting_period=run.reporting_period,
            allowed_entity_ids=allowed_entity_ids,
            metric_rows=metric_rows,
        )
        minority_interest_summary = self._policy.apply_minority_interest_policy(
            minority_interest_summary=minority_interest_summary,
            current_date=run.reporting_period,
        )
        revenue_policy = self._policy.apply_revenue_reclassification_policy(
            consolidated_metrics=consolidated_metrics,
            current_date=run.reporting_period,
        )

        has_effect = bool(intercompany_summary["elimination_entries"]) or bool(
            adjustment_summary["adjustment_entries"] or adjustment_summary["reclassification_entries"]
        )
        no_intercompany_data = (
            intercompany_summary["validation_report"]["status"] == "PASS"
            and intercompany_summary["validation_report"]["reason"] == "no intercompany transactions"
        )
        if not has_effect and not no_intercompany_data:
            raise ValueError(
                "validation_report.status=FAIL: consolidation produced no elimination or adjustment evidence"
            )

        metric_db_rows = [
            {
                "line_no": index,
                "metric_code": str(row["metric_code"]),
                "scope_json": {"entity_ids": sorted(allowed_entity_ids)},
                "currency_code": str(row["currency_code"]),
                "aggregated_value": Decimal(str(row["aggregated_value"])),
                "entity_count": int(row["entity_count"]),
                "materiality_flag": False,
            }
            for index, row in enumerate(revenue_policy["policy_applied_entries"], start=1)
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
        created_metrics = await self._create_metric_results(
            tenant_id=tenant_id,
            run_id=run_id,
            rows=metric_db_rows,
            created_by=created_by,
        )
        created_variances = await self._create_variance_results(
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
                "evidence_type": "validation_report",
                "evidence_ref": "data-quality:summary",
                "evidence_label": "Data quality validation reports",
                "evidence_payload_json": {
                    "reports": [
                        metric_validation["validation_report"],
                        variance_validation["validation_report"],
                    ]
                },
            }
        )
        evidence_rows.append(
            {
                "metric_result_id": None,
                "variance_result_id": None,
                "evidence_type": "intercompany_decision",
                "evidence_ref": "intercompany:summary",
                "evidence_label": "Intercompany matching and elimination evidence",
                "evidence_payload_json": intercompany_summary,
            }
        )
        evidence_rows.append(
            {
                "metric_result_id": None,
                "variance_result_id": None,
                "evidence_type": "adjustment_reference",
                "evidence_ref": "adjustment:summary",
                "evidence_label": "Adjustment and reclassification evidence",
                "evidence_payload_json": adjustment_summary,
            }
        )
        evidence_rows.append(
            {
                "metric_result_id": None,
                "variance_result_id": None,
                "evidence_type": "adjustment_reference",
                "evidence_ref": "minority-interest:summary",
                "evidence_label": "Minority interest computation trace",
                "evidence_payload_json": minority_interest_summary,
            }
        )
        evidence_rows.append(
            {
                "metric_result_id": None,
                "variance_result_id": None,
                "evidence_type": "adjustment_reference",
                "evidence_ref": "accounting-policy:summary",
                "evidence_label": "Accounting policy application trace",
                "evidence_payload_json": {
                    "intercompany_profit_elimination": intercompany_policy,
                    "minority_interest_adjustment": minority_interest_summary.get(
                        "policy_application", {}
                    ),
                    "revenue_reclassification": revenue_policy,
                },
            }
        )
        created_evidence = await self._create_evidence_links(
            tenant_id=tenant_id,
            run_id=run_id,
            rows=evidence_rows,
            created_by=created_by,
        )
        from financeops.platform.services.control_plane.phase4_service import Phase4ControlPlaneService

        await Phase4ControlPlaneService(self._repository._session).ensure_snapshot_for_subject(
            tenant_id=tenant_id,
            actor_user_id=created_by,
            actor_role="system",
            subject_type="multi_entity_consolidation_run",
            subject_id=str(run.id),
            trigger_event="consolidation_run_complete",
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
            "elimination_entry_count": int(intercompany_summary["elimination_count"]),
            "adjustment_entry_count": int(len(adjustment_summary["adjustment_entries"])),
            "reclassification_entry_count": int(
                len(adjustment_summary["reclassification_entries"])
            ),
            "minority_interest_total": str(minority_interest_summary["aggregate_amount"]),
            "validation_report": intercompany_summary["validation_report"],
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

    async def _create_metric_results(
        self,
        *,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
        rows: list[dict[str, Any]],
        created_by: uuid.UUID,
    ) -> list[object]:
        if not settings.ENABLE_CHUNKED_TASKS or len(rows) <= self._RESULT_CHUNK_SIZE:
            return await self._repository.create_metric_results(
                tenant_id=tenant_id,
                run_id=run_id,
                rows=rows,
                created_by=created_by,
            )

        created: list[object] = []
        for chunk in self._chunk_rows(rows):
            created.extend(
                await self._repository.create_metric_results(
                    tenant_id=tenant_id,
                    run_id=run_id,
                    rows=chunk,
                    created_by=created_by,
                )
            )
        return created

    async def _create_variance_results(
        self,
        *,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
        rows: list[dict[str, Any]],
        created_by: uuid.UUID,
    ) -> list[object]:
        if not settings.ENABLE_CHUNKED_TASKS or len(rows) <= self._RESULT_CHUNK_SIZE:
            return await self._repository.create_variance_results(
                tenant_id=tenant_id,
                run_id=run_id,
                rows=rows,
                created_by=created_by,
            )

        created: list[object] = []
        for chunk in self._chunk_rows(rows):
            created.extend(
                await self._repository.create_variance_results(
                    tenant_id=tenant_id,
                    run_id=run_id,
                    rows=chunk,
                    created_by=created_by,
                )
            )
        return created

    async def _create_evidence_links(
        self,
        *,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
        rows: list[dict[str, Any]],
        created_by: uuid.UUID,
    ) -> list[object]:
        if not settings.ENABLE_CHUNKED_TASKS or len(rows) <= self._RESULT_CHUNK_SIZE:
            return await self._repository.create_evidence_links(
                tenant_id=tenant_id,
                run_id=run_id,
                rows=rows,
                created_by=created_by,
            )

        created: list[object] = []
        for chunk in self._chunk_rows(rows):
            created.extend(
                await self._repository.create_evidence_links(
                    tenant_id=tenant_id,
                    run_id=run_id,
                    rows=chunk,
                    created_by=created_by,
                )
            )
        return created

    def _chunk_rows(self, rows: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
        return [
            rows[index : index + self._RESULT_CHUNK_SIZE]
            for index in range(0, len(rows), self._RESULT_CHUNK_SIZE)
        ]

    async def _compute_minority_interest_summary(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        reporting_period: date,
        allowed_entity_ids: set[str],
        metric_rows: list[object],
    ) -> dict[str, Any]:
        repository = OwnershipConsolidationRepository(self._repository._session)
        structures = await repository.active_structure_definitions(
            tenant_id=tenant_id,
            organisation_id=organisation_id,
            reporting_period=reporting_period,
        )
        if not structures:
            return {
                "validation_report": {
                    "status": "PASS",
                    "reason": "No active ownership structure available for minority-interest computation",
                },
                "aggregate_amount": "0.000000",
                "entity_traces": [],
                "applied": False,
            }

        selected_structure = sorted(
            structures,
            key=lambda value: (value.ownership_structure_code, value.id),
        )[0]
        relationships = await repository.active_relationships(
            tenant_id=tenant_id,
            ownership_structure_id=selected_structure.id,
            reporting_period=reporting_period,
        )
        relevant_relationships = [
            row
            for row in relationships
            if bool(getattr(row, "minority_interest_indicator", False))
            and str(row.child_entity_id) in allowed_entity_ids
        ]
        if not relevant_relationships:
            return {
                "validation_report": {
                    "status": "PASS",
                    "reason": "No minority-interest relationships active for the consolidation scope",
                },
                "aggregate_amount": "0.000000",
                "entity_traces": [],
                "applied": False,
            }

        mapper = OwnershipMappingService()
        metric_rows_by_entity: dict[str, list[object]] = {}
        for row in metric_rows:
            entity_id = self._extract_entity_id(row)
            if entity_id is None:
                continue
            metric_rows_by_entity.setdefault(str(entity_id), []).append(row)

        traces: list[dict[str, Any]] = []
        aggregate_amount = Decimal("0.000000")
        missing_entities: list[str] = []
        for relationship in sorted(
            relevant_relationships,
            key=lambda value: (str(value.child_entity_id), str(value.id)),
        ):
            entity_rows = metric_rows_by_entity.get(str(relationship.child_entity_id), [])
            if not entity_rows:
                missing_entities.append(str(relationship.child_entity_id))
                continue
            for row in sorted(
                entity_rows,
                key=lambda value: (str(getattr(value, "metric_code", "")), str(value.id)),
            ):
                source_value = self._minority_source_value(row)
                minority_value = mapper.derive_minority_value(
                    source_value=source_value,
                    relationship=relationship,
                )
                if minority_value is None:
                    continue
                aggregate_amount += Decimal(str(minority_value))
                traces.append(
                    {
                        "entity_id": str(relationship.child_entity_id),
                        "source_metric_result_id": str(row.id),
                        "metric_code": str(getattr(row, "metric_code", "")),
                        "source_balance": str(source_value),
                        "ownership_percentage": str(relationship.ownership_percentage),
                        "minority_interest_value": str(minority_value),
                        "reason": "Minority interest computed from source balance and ownership share",
                    }
                )
        if missing_entities:
            raise ValueError(
                "validation_report.status=FAIL: missing minority-interest source rows for entities "
                + ", ".join(missing_entities)
            )
        return {
            "validation_report": {
                "status": "PASS",
                "reason": "Minority interest computed per subsidiary and aggregated",
            },
            "aggregate_amount": str(aggregate_amount.quantize(Decimal("0.000000"))),
            "entity_traces": traces,
            "applied": bool(traces),
        }

    def _extract_entity_id(self, row: object) -> uuid.UUID | None:
        dimension_json = dict(getattr(row, "dimension_json", {}) or {})
        scope_json = dimension_json.get("scope")
        if not isinstance(scope_json, dict):
            scope_json = {}
        for raw in (
            dimension_json.get("entity_id"),
            dimension_json.get("legal_entity"),
            scope_json.get("entity_id"),
            scope_json.get("entity"),
        ):
            if raw is None or raw == "":
                continue
            try:
                return uuid.UUID(str(raw))
            except ValueError:
                continue
        return None

    def _minority_source_value(self, row: object) -> Decimal:
        source_summary_json = dict(getattr(row, "source_summary_json", {}) or {})
        for raw in (
            source_summary_json.get("nci_balance"),
            source_summary_json.get("source_balance"),
            getattr(row, "metric_value", None),
        ):
            if raw is None:
                continue
            return Decimal(str(raw))
        raise ValueError(
            f"validation_report.status=FAIL: missing minority-interest source balance for metric row {getattr(row, 'id', 'unknown')}"
        )

    def _metric_validation_row(self, row: object) -> dict[str, Any]:
        source_summary_json = dict(getattr(row, "source_summary_json", {}) or {})
        dimension_json = dict(getattr(row, "dimension_json", {}) or {})
        scope_json = dimension_json.get("scope")
        if not isinstance(scope_json, dict):
            scope_json = {}
        return {
            "id": getattr(row, "id", None),
            "run_id": getattr(row, "run_id", None),
            "metric_code": getattr(row, "metric_code", None),
            "metric_value": getattr(row, "metric_value", None),
            "entity_id": self._extract_entity_id(row),
            "currency_code": (
                source_summary_json.get("currency_code")
                or dimension_json.get("currency_code")
                or scope_json.get("currency_code")
            ),
        }

    def _variance_validation_row(self, row: object) -> dict[str, Any]:
        return {
            "id": getattr(row, "id", None),
            "run_id": getattr(row, "run_id", None),
            "metric_code": getattr(row, "metric_code", None),
            "comparison_type": getattr(row, "comparison_type", None),
            "base_value": getattr(row, "base_value", None),
            "current_value": getattr(row, "current_value", None),
            "variance_value": getattr(row, "variance_value", None),
            "variance_pct": getattr(row, "variance_pct", None),
            "currency_code": getattr(row, "currency_code", None),
        }
