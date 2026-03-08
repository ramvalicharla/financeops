from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from financeops.modules.cash_flow_engine.application.bridge_service import BridgeService
from financeops.modules.cash_flow_engine.application.mapping_service import MappingService
from financeops.modules.cash_flow_engine.application.validation_service import ValidationService
from financeops.modules.cash_flow_engine.domain.enums import RunStatus
from financeops.modules.cash_flow_engine.domain.invariants import q6
from financeops.modules.cash_flow_engine.domain.value_objects import (
    CashFlowRunTokenInput,
    DefinitionVersionTokenInput,
)
from financeops.modules.cash_flow_engine.infrastructure.repository import CashFlowRepository
from financeops.modules.cash_flow_engine.infrastructure.token_builder import (
    build_cash_flow_run_token,
    build_definition_version_token,
)


class RunService:
    def __init__(
        self,
        *,
        repository: CashFlowRepository,
        validation_service: ValidationService,
        mapping_service: MappingService,
        bridge_service: BridgeService,
    ) -> None:
        self._repository = repository
        self._validation = validation_service
        self._mapping = mapping_service
        self._bridge = bridge_service

    async def create_run(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        reporting_period: date,
        source_consolidation_run_ref: uuid.UUID,
        source_fx_translation_run_ref_nullable: uuid.UUID | None,
        source_ownership_consolidation_run_ref_nullable: uuid.UUID | None,
        created_by: uuid.UUID,
    ) -> dict[str, Any]:
        self._validation.validate_source_refs(
            source_consolidation_run_ref=source_consolidation_run_ref
        )
        source_consolidation_run = await self._repository.get_consolidation_run(
            tenant_id=tenant_id, run_id=source_consolidation_run_ref
        )
        if source_consolidation_run is None:
            raise ValueError("Source consolidation run does not exist for tenant")
        if source_fx_translation_run_ref_nullable is not None:
            fx_run = await self._repository.get_fx_translation_run(
                tenant_id=tenant_id, run_id=source_fx_translation_run_ref_nullable
            )
            if fx_run is None:
                raise ValueError("Source FX translation run does not exist for tenant")
        if source_ownership_consolidation_run_ref_nullable is not None:
            ownership_run = await self._repository.get_ownership_run(
                tenant_id=tenant_id,
                run_id=source_ownership_consolidation_run_ref_nullable,
            )
            if ownership_run is None:
                raise ValueError("Source ownership consolidation run does not exist for tenant")

        statement_rows = await self._repository.active_statement_definitions(
            tenant_id=tenant_id,
            organisation_id=organisation_id,
            reporting_period=reporting_period,
        )
        line_mapping_rows = await self._repository.active_line_mappings(
            tenant_id=tenant_id,
            organisation_id=organisation_id,
            reporting_period=reporting_period,
        )
        bridge_rule_rows = await self._repository.active_bridge_rules(
            tenant_id=tenant_id,
            organisation_id=organisation_id,
            reporting_period=reporting_period,
        )
        self._validation.validate_definition_sets(
            statement_rows=statement_rows,
            line_mapping_rows=line_mapping_rows,
            bridge_rule_rows=bridge_rule_rows,
        )

        selected_statement = statement_rows[0]
        selected_bridge_rule = bridge_rule_rows[0]

        statement_definition_version_token = build_definition_version_token(
            DefinitionVersionTokenInput(
                rows=[
                    {
                        "definition_code": selected_statement.definition_code,
                        "version_token": selected_statement.version_token,
                        "method_type": selected_statement.method_type,
                    }
                ]
            )
        )
        line_mapping_version_token = build_definition_version_token(
            DefinitionVersionTokenInput(
                rows=[
                    {
                        "mapping_code": row.mapping_code,
                        "line_code": row.line_code,
                        "line_order": int(row.line_order),
                        "source_metric_code": row.source_metric_code,
                        "version_token": row.version_token,
                    }
                    for row in sorted(
                        line_mapping_rows,
                        key=lambda row: (row.mapping_code, row.line_order, row.id),
                    )
                ]
            )
        )
        bridge_rule_version_token = build_definition_version_token(
            DefinitionVersionTokenInput(
                rows=[
                    {
                        "rule_code": selected_bridge_rule.rule_code,
                        "version_token": selected_bridge_rule.version_token,
                    }
                ]
            )
        )

        run_token = build_cash_flow_run_token(
            CashFlowRunTokenInput(
                tenant_id=tenant_id,
                organisation_id=organisation_id,
                reporting_period=reporting_period,
                statement_definition_version_token=statement_definition_version_token,
                line_mapping_version_token=line_mapping_version_token,
                bridge_rule_version_token=bridge_rule_version_token,
                source_consolidation_run_ref=str(source_consolidation_run_ref),
                source_fx_translation_run_ref_nullable=str(
                    source_fx_translation_run_ref_nullable
                )
                if source_fx_translation_run_ref_nullable
                else None,
                source_ownership_consolidation_run_ref_nullable=str(
                    source_ownership_consolidation_run_ref_nullable
                )
                if source_ownership_consolidation_run_ref_nullable
                else None,
                run_status=RunStatus.CREATED.value,
            )
        )
        existing = await self._repository.get_run_by_token(
            tenant_id=tenant_id, run_token=run_token
        )
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
            statement_definition_version_token=statement_definition_version_token,
            line_mapping_version_token=line_mapping_version_token,
            bridge_rule_version_token=bridge_rule_version_token,
            source_consolidation_run_ref=source_consolidation_run_ref,
            source_fx_translation_run_ref_nullable=source_fx_translation_run_ref_nullable,
            source_ownership_consolidation_run_ref_nullable=source_ownership_consolidation_run_ref_nullable,
            run_token=run_token,
            run_status=RunStatus.CREATED.value,
            validation_summary_json={
                "selected_statement_definition_id": str(selected_statement.id),
                "selected_bridge_rule_id": str(selected_bridge_rule.id),
                "line_mapping_count": len(line_mapping_rows),
                "selected_line_mapping_ids": [
                    str(row.id)
                    for row in sorted(
                        line_mapping_rows,
                        key=lambda row: (row.mapping_code, row.line_order, row.id),
                    )
                ],
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
            raise ValueError("Cash flow run not found")

        existing_lines = await self._repository.list_line_results(
            tenant_id=tenant_id, run_id=run_id
        )
        if existing_lines:
            summary = await self._repository.summarize_run(tenant_id=tenant_id, run_id=run_id)
            return {
                "run_id": str(run.id),
                "run_token": run.run_token,
                "status": run.run_status,
                "idempotent": True,
                **summary,
            }

        selected_statement_id = str(
            run.validation_summary_json.get("selected_statement_definition_id", "")
        )
        if not selected_statement_id:
            raise ValueError("Run does not contain selected statement definition id")
        selected_statement = await self._repository.get_statement_definition(
            tenant_id=tenant_id, definition_id=uuid.UUID(selected_statement_id)
        )
        if selected_statement is None:
            raise ValueError("Statement definition snapshot for run token not found")

        mapping_ids_raw = list(
            run.validation_summary_json.get("selected_line_mapping_ids", [])
        )
        mapping_ids = [uuid.UUID(str(value)) for value in mapping_ids_raw]
        line_mapping_rows = await self._repository.list_line_mappings_by_ids(
            tenant_id=tenant_id,
            mapping_ids=mapping_ids,
        )
        if not line_mapping_rows:
            raise ValueError("Line mapping snapshot for run token not found")
        line_mapping_rows = [
            row
            for row in line_mapping_rows
            if str(row.method_type) == str(selected_statement.method_type)
        ]
        if not line_mapping_rows:
            raise ValueError("No line mappings match statement method type")

        selected_bridge_id = str(
            run.validation_summary_json.get("selected_bridge_rule_id", "")
        )
        if not selected_bridge_id:
            raise ValueError("Run does not contain selected bridge rule id")
        selected_bridge = await self._repository.get_bridge_rule(
            tenant_id=tenant_id, rule_id=uuid.UUID(selected_bridge_id)
        )
        if selected_bridge is None:
            raise ValueError("Bridge rule snapshot for run token not found")

        has_ownership_source = run.source_ownership_consolidation_run_ref_nullable is not None
        has_fx_source = run.source_fx_translation_run_ref_nullable is not None

        source_rows = await self._load_source_rows(
            tenant_id=tenant_id,
            run=run,
        )
        if not source_rows:
            raise ValueError("No source rows found for cash flow run")

        metric_totals: dict[str, Decimal] = {}
        metric_refs: dict[str, list[str]] = {}
        metric_currency: dict[str, str] = {}
        for row in source_rows:
            metric_code = str(row["metric_code"])
            metric_totals[metric_code] = q6(
                metric_totals.get(metric_code, Decimal("0")) + Decimal(str(row["value"]))
            )
            refs = metric_refs.setdefault(metric_code, [])
            refs.append(str(row["source_row_id"]))
            metric_currency.setdefault(metric_code, str(row["currency_code"]).upper())
        for refs in metric_refs.values():
            refs.sort()

        applicable_mappings = self._mapping.filter_applicable_mappings(
            mappings=sorted(
                line_mapping_rows,
                key=lambda row: (row.mapping_code, row.line_order, row.id),
            ),
            has_ownership_source=has_ownership_source,
            has_fx_source=has_fx_source,
        )
        if not applicable_mappings:
            raise ValueError("No applicable line mappings for selected source basis")

        missing_source_metrics: list[str] = []
        base_line_values: dict[str, Decimal] = {}
        for row in applicable_mappings:
            metric_code = str(row.source_metric_code)
            if metric_code.startswith("derived:"):
                continue
            source_value = metric_totals.get(metric_code)
            if source_value is None:
                missing_source_metrics.append(metric_code)
                continue
            base_line_values[str(row.line_code)] = self._mapping.compute_line_value(
                source_value=source_value,
                sign_multiplier=Decimal(str(row.sign_multiplier)),
            )
        self._validation.validate_line_mappings_have_sources(
            missing_source_metrics=missing_source_metrics
        )

        derived_values = self._bridge.compute_derived_values(
            base_line_values=base_line_values,
            bridge_logic_json=dict(selected_bridge.bridge_logic_json or {}),
        )

        line_payloads: list[dict[str, Any]] = []
        evidence_payloads: list[dict[str, Any]] = []
        source_evidence_type = "source_consolidation_metric"
        if has_ownership_source:
            source_evidence_type = "source_ownership_metric"
        elif has_fx_source:
            source_evidence_type = "source_fx_metric"

        for line_no, row in enumerate(applicable_mappings, start=1):
            source_metric = str(row.source_metric_code)
            if source_metric.startswith("derived:"):
                derived_key = source_metric.split(":", 1)[1].strip() or str(row.line_code)
                source_value = q6(derived_values.get(derived_key, Decimal("0")))
                source_refs = []
                source_currency = "USD"
            else:
                source_value = q6(metric_totals.get(source_metric, Decimal("0")))
                source_refs = metric_refs.get(source_metric, [])
                source_currency = metric_currency.get(source_metric, "USD")
            computed_value = self._mapping.compute_line_value(
                source_value=source_value,
                sign_multiplier=Decimal(str(row.sign_multiplier)),
            )
            line_payloads.append(
                {
                    "line_no": line_no,
                    "line_code": row.line_code,
                    "line_name": row.line_name,
                    "section_code": row.section_code,
                    "line_order": row.line_order,
                    "method_type": row.method_type,
                    "source_metric_code": row.source_metric_code,
                    "source_value": source_value,
                    "sign_multiplier": row.sign_multiplier,
                    "computed_value": computed_value,
                    "currency_code": source_currency,
                    "ownership_basis_applied": has_ownership_source,
                    "fx_basis_applied": has_fx_source,
                    "lineage_summary_json": {
                        "line_mapping_id": str(row.id),
                        "source_metric_refs": source_refs,
                        "bridge_rule_id": str(selected_bridge.id),
                    },
                }
            )

        created_lines = await self._repository.create_line_results(
            tenant_id=tenant_id,
            run_id=run_id,
            rows=line_payloads,
            created_by=created_by,
        )
        for row in created_lines:
            evidence_payloads.append(
                {
                    "line_result_id": row.id,
                    "evidence_type": "line_mapping",
                    "evidence_ref": str(row.lineage_summary_json.get("line_mapping_id", "")),
                    "evidence_label": f"Line mapping for {row.line_code}",
                    "evidence_payload_json": {
                        "source_metric_code": row.source_metric_code,
                    },
                }
            )
            evidence_payloads.append(
                {
                    "line_result_id": row.id,
                    "evidence_type": "bridge_rule",
                    "evidence_ref": str(row.lineage_summary_json.get("bridge_rule_id", "")),
                    "evidence_label": f"Bridge rule for {row.line_code}",
                    "evidence_payload_json": {},
                }
            )
            source_refs = list(row.lineage_summary_json.get("source_metric_refs", []))
            for ref in sorted(str(value) for value in source_refs):
                evidence_payloads.append(
                    {
                        "line_result_id": row.id,
                        "evidence_type": source_evidence_type,
                        "evidence_ref": ref,
                        "evidence_label": f"Source metric for {row.line_code}",
                        "evidence_payload_json": {},
                    }
                )

        if run.source_ownership_consolidation_run_ref_nullable is not None:
            evidence_payloads.append(
                {
                    "line_result_id": None,
                    "evidence_type": "ownership_run_ref",
                    "evidence_ref": str(run.source_ownership_consolidation_run_ref_nullable),
                    "evidence_label": "Ownership source run",
                    "evidence_payload_json": {},
                }
            )
        if run.source_fx_translation_run_ref_nullable is not None:
            evidence_payloads.append(
                {
                    "line_result_id": None,
                    "evidence_type": "fx_run_ref",
                    "evidence_ref": str(run.source_fx_translation_run_ref_nullable),
                    "evidence_label": "FX source run",
                    "evidence_payload_json": {},
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

    async def _load_source_rows(
        self,
        *,
        tenant_id: uuid.UUID,
        run: Any,
    ) -> list[dict[str, Any]]:
        if run.source_ownership_consolidation_run_ref_nullable is not None:
            rows = await self._repository.list_source_ownership_metric_results(
                tenant_id=tenant_id,
                run_id=run.source_ownership_consolidation_run_ref_nullable,
            )
            return [
                {
                    "metric_code": row.metric_code,
                    "value": row.attributed_value,
                    "currency_code": row.reporting_currency_code_nullable or "USD",
                    "source_row_id": row.id,
                }
                for row in rows
            ]
        if run.source_fx_translation_run_ref_nullable is not None:
            rows = await self._repository.list_source_fx_metric_results(
                tenant_id=tenant_id,
                run_id=run.source_fx_translation_run_ref_nullable,
            )
            return [
                {
                    "metric_code": row.metric_code,
                    "value": row.translated_value,
                    "currency_code": row.reporting_currency_code,
                    "source_row_id": row.id,
                }
                for row in rows
            ]
        rows = await self._repository.list_source_consolidation_metric_results(
            tenant_id=tenant_id,
            run_id=run.source_consolidation_run_ref,
        )
        return [
            {
                "metric_code": row.metric_code,
                "value": row.aggregated_value,
                "currency_code": row.currency_code,
                "source_row_id": row.id,
            }
            for row in rows
        ]
