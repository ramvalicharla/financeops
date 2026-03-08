from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from financeops.modules.ownership_consolidation.application.mapping_service import MappingService
from financeops.modules.ownership_consolidation.application.rule_service import RuleService
from financeops.modules.ownership_consolidation.application.validation_service import (
    ValidationService,
)
from financeops.modules.ownership_consolidation.domain.enums import RunStatus
from financeops.modules.ownership_consolidation.domain.invariants import q6
from financeops.modules.ownership_consolidation.domain.value_objects import (
    DefinitionVersionTokenInput,
    OwnershipRunTokenInput,
)
from financeops.modules.ownership_consolidation.infrastructure.repository import (
    OwnershipConsolidationRepository,
)
from financeops.modules.ownership_consolidation.infrastructure.token_builder import (
    build_definition_version_token,
    build_ownership_run_token,
)


class RunService:
    def __init__(
        self,
        *,
        repository: OwnershipConsolidationRepository,
        validation_service: ValidationService,
        mapping_service: MappingService,
        rule_service: RuleService,
    ) -> None:
        self._repository = repository
        self._validation = validation_service
        self._mapping = mapping_service
        self._rules = rule_service

    async def create_run(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        reporting_period: date,
        source_consolidation_run_refs: list[dict[str, Any]],
        fx_translation_run_ref_nullable: uuid.UUID | None,
        created_by: uuid.UUID,
    ) -> dict[str, Any]:
        self._validation.validate_source_run_refs(
            source_consolidation_run_refs=source_consolidation_run_refs
        )
        structures = await self._repository.active_structure_definitions(
            tenant_id=tenant_id,
            organisation_id=organisation_id,
            reporting_period=reporting_period,
        )
        ownership_rules = await self._repository.active_ownership_rules(
            tenant_id=tenant_id,
            organisation_id=organisation_id,
            reporting_period=reporting_period,
        )
        minority_rules = await self._repository.active_minority_interest_rules(
            tenant_id=tenant_id,
            organisation_id=organisation_id,
            reporting_period=reporting_period,
        )
        self._validation.validate_definition_sets(
            structure_rows=structures,
            ownership_rule_rows=ownership_rules,
            minority_rule_rows=minority_rules,
        )

        selected_structure = self._rules.select_primary_structure(rows=structures)
        selected_ownership_rule = self._rules.select_primary_ownership_rule(rows=ownership_rules)
        selected_minority_rule = self._rules.select_primary_minority_rule(rows=minority_rules)
        relationships = await self._repository.active_relationships(
            tenant_id=tenant_id,
            ownership_structure_id=selected_structure.id,
            reporting_period=reporting_period,
        )
        self._validation.validate_relationships(rows=relationships)

        source_refs_sorted = sorted(
            [
                {
                    "source_type": str(row.get("source_type", "")),
                    "run_id": str(row.get("run_id", "")),
                }
                for row in source_consolidation_run_refs
            ],
            key=lambda row: (row["source_type"], row["run_id"]),
        )
        source_run_ids = [uuid.UUID(row["run_id"]) for row in source_refs_sorted]
        source_runs = await self._repository.list_source_runs(
            tenant_id=tenant_id,
            run_ids=source_run_ids,
        )
        if len(source_runs) != len(set(source_run_ids)):
            raise ValueError("One or more source consolidation runs do not exist for tenant")

        if fx_translation_run_ref_nullable is not None:
            fx_run = await self._repository.get_fx_translation_run(
                tenant_id=tenant_id,
                run_id=fx_translation_run_ref_nullable,
            )
            if fx_run is None:
                raise ValueError("Referenced FX translation run does not exist for tenant")

        hierarchy_version_token = self._token_from_rows(
            rows=source_runs,
            code_attr="hierarchy_version_token",
        )
        scope_version_token = self._token_from_rows(rows=source_runs, code_attr="scope_version_token")
        ownership_structure_version_token = self._token_from_rows(
            rows=structures, code_attr="ownership_structure_code"
        )
        ownership_rule_version_token = self._token_from_rows(
            rows=ownership_rules, code_attr="rule_code"
        )
        minority_interest_rule_version_token = self._token_from_rows(
            rows=minority_rules, code_attr="rule_code"
        )

        run_token = build_ownership_run_token(
            OwnershipRunTokenInput(
                tenant_id=tenant_id,
                organisation_id=organisation_id,
                reporting_period=reporting_period,
                hierarchy_version_token=hierarchy_version_token,
                scope_version_token=scope_version_token,
                ownership_structure_version_token=ownership_structure_version_token,
                ownership_rule_version_token=ownership_rule_version_token,
                minority_interest_rule_version_token=minority_interest_rule_version_token,
                fx_translation_run_ref_nullable=str(fx_translation_run_ref_nullable)
                if fx_translation_run_ref_nullable
                else None,
                source_consolidation_run_refs=source_refs_sorted,
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

        run = await self._repository.create_run(
            tenant_id=tenant_id,
            organisation_id=organisation_id,
            reporting_period=reporting_period,
            hierarchy_version_token=hierarchy_version_token,
            scope_version_token=scope_version_token,
            ownership_structure_version_token=ownership_structure_version_token,
            ownership_rule_version_token=ownership_rule_version_token,
            minority_interest_rule_version_token=minority_interest_rule_version_token,
            fx_translation_run_ref_nullable=fx_translation_run_ref_nullable,
            source_consolidation_run_refs_json=source_refs_sorted,
            run_token=run_token,
            run_status=RunStatus.CREATED.value,
            validation_summary_json={
                "selected_structure_id": str(selected_structure.id),
                "selected_ownership_rule_id": str(selected_ownership_rule.id),
                "selected_minority_rule_id": str(selected_minority_rule.id),
                "relationship_count": len(relationships),
            },
            created_by=created_by,
        )
        return {
            "run_id": str(run.id),
            "run_token": run.run_token,
            "status": run.run_status,
            "idempotent": False,
        }

    async def execute_run(
        self, *, tenant_id: uuid.UUID, run_id: uuid.UUID, created_by: uuid.UUID
    ) -> dict[str, Any]:
        run = await self._repository.get_run(tenant_id=tenant_id, run_id=run_id)
        if run is None:
            raise ValueError("Ownership consolidation run not found")

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

        source_refs = sorted(
            list(run.source_consolidation_run_refs_json),
            key=lambda row: (str(row.get("source_type", "")), str(row.get("run_id", ""))),
        )
        source_run_ids = [uuid.UUID(str(row["run_id"])) for row in source_refs]
        source_metric_rows = await self._repository.list_source_metric_results_for_runs(
            tenant_id=tenant_id,
            run_ids=source_run_ids,
        )
        source_variance_rows = await self._repository.list_source_variance_results_for_runs(
            tenant_id=tenant_id,
            run_ids=source_run_ids,
        )
        if not source_metric_rows and not source_variance_rows:
            raise ValueError("No source consolidation rows found for run references")

        selected_structure_id = str(run.validation_summary_json.get("selected_structure_id", "")).strip()
        if not selected_structure_id:
            raise ValueError("Run validation summary does not contain selected ownership structure")
        relationships = await self._repository.active_relationships(
            tenant_id=tenant_id,
            ownership_structure_id=uuid.UUID(selected_structure_id),
            reporting_period=run.reporting_period,
        )
        relationship_by_child: dict[uuid.UUID, Any] = {}
        for rel in relationships:
            relationship_by_child.setdefault(rel.child_entity_id, rel)

        metric_payloads: list[dict[str, Any]] = []
        variance_payloads: list[dict[str, Any]] = []
        evidence_payloads: list[dict[str, Any]] = []

        for idx, row in enumerate(source_metric_rows, start=1):
            scope_json = dict(row.scope_json or {})
            entity_id = self._mapping.extract_entity_id_from_scope(scope_json)
            relationship = relationship_by_child.get(entity_id) if entity_id is not None else None
            weight = self._mapping.derive_weight(relationship=relationship)
            source_value = Decimal(str(row.aggregated_value))
            attributed_value = q6(source_value * weight)
            minority_value = self._mapping.derive_minority_value(
                source_value=source_value, relationship=relationship
            )
            metric_payloads.append(
                {
                    "line_no": idx,
                    "scope_code": self._mapping.derive_scope_code(scope_json),
                    "metric_code": row.metric_code,
                    "source_consolidated_value": q6(source_value),
                    "ownership_weight_applied": q6(weight),
                    "attributed_value": attributed_value,
                    "minority_interest_value_nullable": minority_value,
                    "reporting_currency_code_nullable": scope_json.get("reporting_currency_code"),
                    "lineage_summary_json": {
                        "source_metric_result_id": str(row.id),
                        "source_run_id": str(row.run_id),
                        "ownership_relationship_id": str(relationship.id) if relationship else None,
                    },
                }
            )

        for idx, row in enumerate(source_variance_rows, start=1):
            source_scope = {"scope_code": "default_scope"}
            source_current = Decimal(str(row.current_value))
            source_comparison = Decimal(str(row.base_value))
            relationship = None
            weight = self._mapping.derive_weight(relationship=relationship)
            attributed_current = q6(source_current * weight)
            attributed_comparison = q6(source_comparison * weight)
            attributed_abs = q6(attributed_current - attributed_comparison)
            attributed_pct = None
            attributed_bps = None
            if attributed_comparison != Decimal("0"):
                attributed_pct = q6((attributed_abs / attributed_comparison) * Decimal("100"))
                attributed_bps = q6(attributed_pct * Decimal("100"))
            variance_payloads.append(
                {
                    "line_no": idx,
                    "scope_code": self._mapping.derive_scope_code(source_scope),
                    "metric_code": row.metric_code,
                    "variance_code": row.comparison_type,
                    "source_current_value": q6(source_current),
                    "source_comparison_value": q6(source_comparison),
                    "ownership_weight_applied": q6(weight),
                    "attributed_current_value": attributed_current,
                    "attributed_comparison_value": attributed_comparison,
                    "attributed_variance_abs": attributed_abs,
                    "attributed_variance_pct": attributed_pct,
                    "attributed_variance_bps": attributed_bps,
                    "minority_interest_value_nullable": None,
                    "lineage_summary_json": {
                        "source_variance_result_id": str(row.id),
                        "source_run_id": str(row.run_id),
                    },
                }
            )

        created_metrics = await self._repository.create_metric_results(
            tenant_id=tenant_id,
            run_id=run_id,
            rows=metric_payloads,
            created_by=created_by,
        )
        created_variances = await self._repository.create_variance_results(
            tenant_id=tenant_id,
            run_id=run_id,
            rows=variance_payloads,
            created_by=created_by,
        )

        for row in created_metrics:
            evidence_payloads.append(
                {
                    "metric_result_id": row.id,
                    "variance_result_id": None,
                    "evidence_type": "source_metric_result",
                    "evidence_ref": str(row.lineage_summary_json.get("source_metric_result_id", "")),
                    "evidence_label": f"Source metric for {row.metric_code}",
                    "evidence_payload_json": dict(row.lineage_summary_json),
                }
            )
        for row in created_variances:
            evidence_payloads.append(
                {
                    "metric_result_id": None,
                    "variance_result_id": row.id,
                    "evidence_type": "source_variance_result",
                    "evidence_ref": str(row.lineage_summary_json.get("source_variance_result_id", "")),
                    "evidence_label": f"Source variance for {row.metric_code}",
                    "evidence_payload_json": dict(row.lineage_summary_json),
                }
            )
        evidence_payloads.append(
            {
                "metric_result_id": None,
                "variance_result_id": None,
                "evidence_type": "ownership_rule_version",
                "evidence_ref": run.ownership_rule_version_token,
                "evidence_label": "Ownership rule version token",
                "evidence_payload_json": {"ownership_rule_version_token": run.ownership_rule_version_token},
            }
        )
        evidence_payloads.append(
            {
                "metric_result_id": None,
                "variance_result_id": None,
                "evidence_type": "minority_interest_rule_version",
                "evidence_ref": run.minority_interest_rule_version_token,
                "evidence_label": "Minority interest rule version token",
                "evidence_payload_json": {
                    "minority_interest_rule_version_token": run.minority_interest_rule_version_token
                },
            }
        )
        if run.fx_translation_run_ref_nullable is not None:
            evidence_payloads.append(
                {
                    "metric_result_id": None,
                    "variance_result_id": None,
                    "evidence_type": "fx_translation_run_ref",
                    "evidence_ref": str(run.fx_translation_run_ref_nullable),
                    "evidence_label": "FX translation run reference",
                    "evidence_payload_json": {"fx_translation_run_ref": str(run.fx_translation_run_ref_nullable)},
                }
            )

        await self._repository.create_evidence_links(
            tenant_id=tenant_id,
            run_id=run_id,
            rows=evidence_payloads,
            created_by=created_by,
        )
        summary = await self._repository.summarize_run(tenant_id=tenant_id, run_id=run_id)
        return {
            "run_id": str(run.id),
            "run_token": run.run_token,
            "status": run.run_status,
            "idempotent": False,
            **summary,
        }

    async def get_run(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> dict[str, Any] | None:
        row = await self._repository.get_run(tenant_id=tenant_id, run_id=run_id)
        if row is None:
            return None
        return {
            "id": str(row.id),
            "organisation_id": str(row.organisation_id),
            "reporting_period": row.reporting_period.isoformat(),
            "hierarchy_version_token": row.hierarchy_version_token,
            "scope_version_token": row.scope_version_token,
            "ownership_structure_version_token": row.ownership_structure_version_token,
            "ownership_rule_version_token": row.ownership_rule_version_token,
            "minority_interest_rule_version_token": row.minority_interest_rule_version_token,
            "fx_translation_run_ref_nullable": str(row.fx_translation_run_ref_nullable)
            if row.fx_translation_run_ref_nullable
            else None,
            "source_consolidation_run_refs": list(row.source_consolidation_run_refs_json),
            "run_token": row.run_token,
            "run_status": row.run_status,
            "validation_summary_json": dict(row.validation_summary_json),
            "created_at": row.created_at.isoformat(),
        }

    async def summary(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> dict[str, Any]:
        row = await self._repository.get_run(tenant_id=tenant_id, run_id=run_id)
        if row is None:
            raise ValueError("Ownership consolidation run not found")
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
                "scope_code": row.scope_code,
                "metric_code": row.metric_code,
                "source_consolidated_value": str(row.source_consolidated_value),
                "ownership_weight_applied": str(row.ownership_weight_applied),
                "attributed_value": str(row.attributed_value),
                "minority_interest_value_nullable": str(row.minority_interest_value_nullable)
                if row.minority_interest_value_nullable is not None
                else None,
                "reporting_currency_code_nullable": row.reporting_currency_code_nullable,
                "lineage_summary_json": dict(row.lineage_summary_json),
            }
            for row in rows
        ]

    async def list_variances(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> list[dict[str, Any]]:
        rows = await self._repository.list_variance_results(tenant_id=tenant_id, run_id=run_id)
        return [
            {
                "id": str(row.id),
                "line_no": row.line_no,
                "scope_code": row.scope_code,
                "metric_code": row.metric_code,
                "variance_code": row.variance_code,
                "source_current_value": str(row.source_current_value),
                "source_comparison_value": str(row.source_comparison_value),
                "ownership_weight_applied": str(row.ownership_weight_applied),
                "attributed_current_value": str(row.attributed_current_value),
                "attributed_comparison_value": str(row.attributed_comparison_value),
                "attributed_variance_abs": str(row.attributed_variance_abs),
                "attributed_variance_pct": str(row.attributed_variance_pct)
                if row.attributed_variance_pct is not None
                else None,
                "attributed_variance_bps": str(row.attributed_variance_bps)
                if row.attributed_variance_bps is not None
                else None,
                "minority_interest_value_nullable": str(row.minority_interest_value_nullable)
                if row.minority_interest_value_nullable is not None
                else None,
                "lineage_summary_json": dict(row.lineage_summary_json),
            }
            for row in rows
        ]

    async def list_evidence(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> list[dict[str, Any]]:
        rows = await self._repository.list_evidence_links(tenant_id=tenant_id, run_id=run_id)
        return [
            {
                "id": str(row.id),
                "metric_result_id": str(row.metric_result_id) if row.metric_result_id else None,
                "variance_result_id": str(row.variance_result_id) if row.variance_result_id else None,
                "evidence_type": row.evidence_type,
                "evidence_ref": row.evidence_ref,
                "evidence_label": row.evidence_label,
                "evidence_payload_json": dict(row.evidence_payload_json),
            }
            for row in rows
        ]

    def _token_from_rows(self, *, rows: list[Any], code_attr: str) -> str:
        payload = []
        for row in rows:
            payload.append(
                {
                    "code": str(getattr(row, code_attr, "")),
                    "version_token": str(getattr(row, "version_token", "")),
                    "id": str(getattr(row, "id")),
                }
            )
        return build_definition_version_token(DefinitionVersionTokenInput(rows=payload))
