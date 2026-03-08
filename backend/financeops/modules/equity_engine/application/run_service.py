from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from financeops.modules.equity_engine.application.mapping_service import MappingService
from financeops.modules.equity_engine.application.rollforward_service import RollforwardService
from financeops.modules.equity_engine.application.validation_service import ValidationService
from financeops.modules.equity_engine.domain.enums import RunStatus
from financeops.modules.equity_engine.domain.invariants import q6
from financeops.modules.equity_engine.domain.value_objects import (
    DefinitionVersionTokenInput,
    EquityRunTokenInput,
)
from financeops.modules.equity_engine.infrastructure.repository import EquityRepository
from financeops.modules.equity_engine.infrastructure.token_builder import (
    build_definition_version_token,
    build_equity_run_token,
)


class RunService:
    def __init__(
        self,
        *,
        repository: EquityRepository,
        validation_service: ValidationService,
        mapping_service: MappingService,
        rollforward_service: RollforwardService,
    ) -> None:
        self._repository = repository
        self._validation = validation_service
        self._mapping = mapping_service
        self._rollforward = rollforward_service

    async def create_run(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        reporting_period: date,
        consolidation_run_ref_nullable: uuid.UUID | None,
        fx_translation_run_ref_nullable: uuid.UUID | None,
        ownership_consolidation_run_ref_nullable: uuid.UUID | None,
        created_by: uuid.UUID,
    ) -> dict[str, Any]:
        statement_rows = await self._repository.active_statement_definitions(
            tenant_id=tenant_id,
            organisation_id=organisation_id,
            reporting_period=reporting_period,
        )
        if not statement_rows:
            raise ValueError("No active equity statement definition found")
        selected_statement = sorted(
            statement_rows,
            key=lambda row: (row.statement_code, row.id),
        )[0]

        line_rows = await self._repository.active_line_definitions(
            tenant_id=tenant_id,
            organisation_id=organisation_id,
            statement_definition_id=selected_statement.id,
            reporting_period=reporting_period,
        )
        rule_rows = await self._repository.active_rollforward_rules(
            tenant_id=tenant_id,
            organisation_id=organisation_id,
            reporting_period=reporting_period,
        )
        mapping_rows = await self._repository.active_source_mappings(
            tenant_id=tenant_id,
            organisation_id=organisation_id,
            reporting_period=reporting_period,
        )
        self._validation.validate_definition_sets(
            statement_rows=statement_rows,
            line_definition_rows=line_rows,
            rollforward_rule_rows=rule_rows,
            source_mapping_rows=mapping_rows,
        )

        if consolidation_run_ref_nullable is not None:
            consolidation_run = await self._repository.get_consolidation_run(
                tenant_id=tenant_id,
                run_id=consolidation_run_ref_nullable,
            )
            if consolidation_run is None:
                raise ValueError("Source consolidation run does not exist for tenant")
        if fx_translation_run_ref_nullable is not None:
            fx_run = await self._repository.get_fx_translation_run(
                tenant_id=tenant_id,
                run_id=fx_translation_run_ref_nullable,
            )
            if fx_run is None:
                raise ValueError("Source FX translation run does not exist for tenant")
        if ownership_consolidation_run_ref_nullable is not None:
            ownership_run = await self._repository.get_ownership_run(
                tenant_id=tenant_id,
                run_id=ownership_consolidation_run_ref_nullable,
            )
            if ownership_run is None:
                raise ValueError("Source ownership consolidation run does not exist for tenant")

        statement_definition_version_token = build_definition_version_token(
            DefinitionVersionTokenInput(
                rows=[
                    {
                        "statement_code": selected_statement.statement_code,
                        "version_token": selected_statement.version_token,
                        "reporting_currency_basis": selected_statement.reporting_currency_basis,
                        "ownership_basis_flag": bool(selected_statement.ownership_basis_flag),
                    }
                ]
            )
        )
        sorted_lines = sorted(line_rows, key=lambda row: (row.presentation_order, row.line_code, row.id))
        line_definition_version_token = build_definition_version_token(
            DefinitionVersionTokenInput(
                rows=[
                    {
                        "line_code": row.line_code,
                        "line_type": row.line_type,
                        "presentation_order": int(row.presentation_order),
                        "rollforward_required_flag": bool(row.rollforward_required_flag),
                        "version_token": row.version_token,
                    }
                    for row in sorted_lines
                ]
            )
        )
        sorted_rules = sorted(rule_rows, key=lambda row: (row.rule_code, row.id))
        rollforward_rule_version_token = build_definition_version_token(
            DefinitionVersionTokenInput(
                rows=[
                    {
                        "rule_code": row.rule_code,
                        "rule_type": row.rule_type,
                        "version_token": row.version_token,
                    }
                    for row in sorted_rules
                ]
            )
        )
        sorted_mappings = sorted(mapping_rows, key=lambda row: (row.mapping_code, row.line_code, row.source_type, row.id))
        source_mapping_version_token = build_definition_version_token(
            DefinitionVersionTokenInput(
                rows=[
                    {
                        "mapping_code": row.mapping_code,
                        "line_code": row.line_code,
                        "source_type": row.source_type,
                        "version_token": row.version_token,
                    }
                    for row in sorted_mappings
                ]
            )
        )

        run_token = build_equity_run_token(
            EquityRunTokenInput(
                tenant_id=tenant_id,
                organisation_id=organisation_id,
                reporting_period=reporting_period,
                statement_definition_version_token=statement_definition_version_token,
                line_definition_version_token=line_definition_version_token,
                rollforward_rule_version_token=rollforward_rule_version_token,
                source_mapping_version_token=source_mapping_version_token,
                consolidation_run_ref_nullable=str(consolidation_run_ref_nullable) if consolidation_run_ref_nullable else None,
                fx_translation_run_ref_nullable=str(fx_translation_run_ref_nullable) if fx_translation_run_ref_nullable else None,
                ownership_consolidation_run_ref_nullable=str(ownership_consolidation_run_ref_nullable) if ownership_consolidation_run_ref_nullable else None,
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
            statement_definition_version_token=statement_definition_version_token,
            line_definition_version_token=line_definition_version_token,
            rollforward_rule_version_token=rollforward_rule_version_token,
            source_mapping_version_token=source_mapping_version_token,
            consolidation_run_ref_nullable=consolidation_run_ref_nullable,
            fx_translation_run_ref_nullable=fx_translation_run_ref_nullable,
            ownership_consolidation_run_ref_nullable=ownership_consolidation_run_ref_nullable,
            run_token=run_token,
            run_status=RunStatus.CREATED.value,
            validation_summary_json={
                "selected_statement_definition_id": str(selected_statement.id),
                "selected_line_definition_ids": [str(row.id) for row in sorted_lines],
                "selected_rule_ids": [str(row.id) for row in sorted_rules],
                "selected_mapping_ids": [str(row.id) for row in sorted_mappings],
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
            raise ValueError("Equity run not found")

        existing_lines = await self._repository.list_line_results(tenant_id=tenant_id, run_id=run_id)
        if existing_lines:
            summary = await self._repository.summarize_run(tenant_id=tenant_id, run_id=run_id)
            return {
                "run_id": str(run.id),
                "run_token": run.run_token,
                "status": run.run_status,
                "idempotent": True,
                **summary,
            }

        line_ids = [uuid.UUID(str(v)) for v in list(run.validation_summary_json.get("selected_line_definition_ids", []))]
        rule_ids = [uuid.UUID(str(v)) for v in list(run.validation_summary_json.get("selected_rule_ids", []))]
        mapping_ids = [uuid.UUID(str(v)) for v in list(run.validation_summary_json.get("selected_mapping_ids", []))]
        line_rows = await self._repository.line_definitions_by_ids(tenant_id=tenant_id, line_definition_ids=line_ids)
        rule_rows = await self._repository.rollforward_rules_by_ids(tenant_id=tenant_id, rule_ids=rule_ids)
        mapping_rows = await self._repository.source_mappings_by_ids(tenant_id=tenant_id, mapping_ids=mapping_ids)
        if not line_rows:
            raise ValueError("Line definition snapshot for run token not found")
        if not rule_rows:
            raise ValueError("Rule snapshot for run token not found")
        if not mapping_rows:
            raise ValueError("Source mapping snapshot for run token not found")

        has_cta_rule = any(str(rule.rule_type) == "cta_derivation_rule" for rule in rule_rows)
        has_ownership_rule = any(
            str(rule.rule_type) in {"ownership_attribution_rule", "minority_interest_equity_rule"}
            for rule in rule_rows
        )
        has_fx_mapping = any(str(mapping.source_type) == "fx_translation_result" for mapping in mapping_rows)
        has_ownership_mapping = any(str(mapping.source_type) == "ownership_result" for mapping in mapping_rows)
        has_consolidation_mapping = any(str(mapping.source_type) in {"consolidation_result", "pnl_result"} for mapping in mapping_rows)

        self._validation.validate_run_sources(
            consolidation_required=has_consolidation_mapping,
            consolidation_present=run.consolidation_run_ref_nullable is not None,
            fx_required=has_cta_rule or has_fx_mapping,
            fx_present=run.fx_translation_run_ref_nullable is not None,
            ownership_required=has_ownership_rule or has_ownership_mapping,
            ownership_present=run.ownership_consolidation_run_ref_nullable is not None,
        )

        consolidation_values: dict[str, Decimal] = {}
        consolidation_refs: dict[str, list[str]] = {}
        if run.consolidation_run_ref_nullable is not None:
            rows = await self._repository.list_source_consolidation_metric_results(
                tenant_id=tenant_id,
                run_id=run.consolidation_run_ref_nullable,
            )
            for row in rows:
                code = str(row.metric_code)
                consolidation_values[code] = q6(consolidation_values.get(code, Decimal("0")) + Decimal(str(row.aggregated_value)))
                consolidation_refs.setdefault(code, []).append(str(row.id))

        fx_values: dict[str, Decimal] = {}
        fx_rows_raw: list[dict[str, Any]] = []
        if run.fx_translation_run_ref_nullable is not None:
            rows = await self._repository.list_source_fx_metric_results(
                tenant_id=tenant_id,
                run_id=run.fx_translation_run_ref_nullable,
            )
            for row in rows:
                code = str(row.metric_code)
                fx_values[code] = q6(fx_values.get(code, Decimal("0")) + Decimal(str(row.translated_value)))
                fx_rows_raw.append(
                    {
                        "metric_code": code,
                        "translated_value": Decimal(str(row.translated_value)),
                        "source_value": Decimal(str(row.source_value)),
                        "source_row_id": str(row.id),
                    }
                )

        ownership_values: dict[str, Decimal] = {}
        minority_values: dict[str, Decimal] = {}
        if run.ownership_consolidation_run_ref_nullable is not None:
            rows = await self._repository.list_source_ownership_metric_results(
                tenant_id=tenant_id,
                run_id=run.ownership_consolidation_run_ref_nullable,
            )
            for row in rows:
                code = str(row.metric_code)
                ownership_values[code] = q6(ownership_values.get(code, Decimal("0")) + Decimal(str(row.attributed_value)))
                minority_values[code] = q6(
                    minority_values.get(code, Decimal("0"))
                    + Decimal(str(row.minority_interest_value_nullable or 0))
                )

        rules_by_type = {
            str(row.rule_type): row
            for row in sorted(rule_rows, key=lambda row: (row.rule_type, row.rule_code, row.id))
        }

        line_payloads: list[dict[str, Any]] = []
        evidence_payloads: list[dict[str, Any]] = []
        total_opening = Decimal("0")
        total_closing = Decimal("0")

        for line_no, line in enumerate(sorted(line_rows, key=lambda row: (row.presentation_order, row.id)), start=1):
            line_mappings = [
                row
                for row in sorted(mapping_rows, key=lambda row: (row.mapping_code, row.source_type, row.id))
                if str(row.line_code) == str(line.line_code)
            ]
            opening = Decimal("0")
            movement = Decimal("0")
            applied_mapping_ids: list[str] = []
            applied_source_refs: list[str] = []
            for mapping in line_mappings:
                value = self._mapping.sum_source_values(
                    mapping=mapping,
                    consolidation_values=consolidation_values,
                    fx_values=fx_values,
                    ownership_values=ownership_values,
                )
                phase = self._mapping.phase_for_mapping(mapping)
                if phase == "opening":
                    opening = q6(opening + value)
                else:
                    movement = q6(movement + value)
                applied_mapping_ids.append(str(mapping.id))
                selector_codes = list(dict(mapping.source_selector_json or {}).get("metric_codes", []))
                for code in sorted({str(v) for v in selector_codes if str(v)}):
                    applied_source_refs.extend(consolidation_refs.get(code, []))

            if str(line.line_type) == "retained_earnings" and "retained_earnings_bridge_rule" in rules_by_type:
                movement = q6(
                    movement
                    + self._rollforward.retained_earnings_movement(
                        consolidation_values=consolidation_values,
                        rule=rules_by_type["retained_earnings_bridge_rule"],
                    )
                )
            if str(line.line_type) == "cta_reserve" and "cta_derivation_rule" in rules_by_type:
                movement = q6(
                    movement
                    + self._rollforward.cta_movement(
                        fx_rows=fx_rows_raw,
                        rule=rules_by_type["cta_derivation_rule"],
                    )
                )
            if str(line.line_type) == "minority_interest" and "minority_interest_equity_rule" in rules_by_type:
                selector_codes = list(
                    dict(rules_by_type["minority_interest_equity_rule"].source_selector_json or {}).get(
                        "metric_codes", []
                    )
                )
                selected_codes = sorted({str(v) for v in selector_codes if str(v)})
                if not selected_codes:
                    selected_codes = sorted(minority_values.keys())
                total_minor = Decimal("0")
                for code in selected_codes:
                    total_minor += minority_values.get(code, Decimal("0"))
                movement = q6(movement + total_minor)

            closing = q6(opening + movement) if bool(line.rollforward_required_flag) else q6(movement)
            source_currency_amount_nullable = q6(opening + movement)
            reporting_currency_amount_nullable = closing if run.fx_translation_run_ref_nullable else None
            ownership_attributed_amount_nullable = (
                closing if run.ownership_consolidation_run_ref_nullable else None
            )

            total_opening = q6(total_opening + opening)
            total_closing = q6(total_closing + closing)

            line_payloads.append(
                {
                    "line_no": line_no,
                    "line_code": line.line_code,
                    "opening_balance": opening,
                    "movement_amount": movement,
                    "closing_balance": closing,
                    "source_currency_amount_nullable": source_currency_amount_nullable,
                    "reporting_currency_amount_nullable": reporting_currency_amount_nullable,
                    "ownership_attributed_amount_nullable": ownership_attributed_amount_nullable,
                    "lineage_summary_json": {
                        "line_definition_id": str(line.id),
                        "line_type": str(line.line_type),
                        "applied_mapping_ids": sorted(applied_mapping_ids),
                        "applied_rule_codes": sorted(rules_by_type.keys()),
                        "source_refs": sorted({str(v) for v in applied_source_refs}),
                    },
                }
            )

        self._validation.validate_line_count(line_count=len(line_payloads))
        created_lines = await self._repository.create_line_results(
            tenant_id=tenant_id,
            run_id=run_id,
            rows=line_payloads,
            created_by=created_by,
        )

        for row in created_lines:
            mapping_ids = list(row.lineage_summary_json.get("applied_mapping_ids", []))
            for mapping_id in sorted({str(v) for v in mapping_ids if str(v)}):
                evidence_payloads.append(
                    {
                        "result_id": row.id,
                        "evidence_type": "line_mapping_ref",
                        "evidence_ref": mapping_id,
                        "evidence_label": f"Line mapping for {row.line_code}",
                        "evidence_payload_json": {},
                    }
                )

        evidence_payloads.append(
            {
                "result_id": None,
                "evidence_type": "rule_version_ref",
                "evidence_ref": run.rollforward_rule_version_token,
                "evidence_label": "Applied rollforward rule version token",
                "evidence_payload_json": {},
            }
        )
        evidence_payloads.append(
            {
                "result_id": None,
                "evidence_type": "mapping_version_ref",
                "evidence_ref": run.source_mapping_version_token,
                "evidence_label": "Applied source mapping version token",
                "evidence_payload_json": {},
            }
        )
        if run.consolidation_run_ref_nullable is not None:
            evidence_payloads.append(
                {
                    "result_id": None,
                    "evidence_type": "consolidation_result_ref",
                    "evidence_ref": str(run.consolidation_run_ref_nullable),
                    "evidence_label": "Consolidation source run",
                    "evidence_payload_json": {},
                }
            )
        if run.fx_translation_run_ref_nullable is not None:
            evidence_payloads.append(
                {
                    "result_id": None,
                    "evidence_type": "fx_translation_run_ref",
                    "evidence_ref": str(run.fx_translation_run_ref_nullable),
                    "evidence_label": "FX translation source run",
                    "evidence_payload_json": {},
                }
            )
        if run.ownership_consolidation_run_ref_nullable is not None:
            evidence_payloads.append(
                {
                    "result_id": None,
                    "evidence_type": "ownership_run_ref",
                    "evidence_ref": str(run.ownership_consolidation_run_ref_nullable),
                    "evidence_label": "Ownership source run",
                    "evidence_payload_json": {},
                }
            )

        await self._repository.create_evidence_links(
            tenant_id=tenant_id,
            run_id=run_id,
            rows=evidence_payloads,
            created_by=created_by,
        )

        statement_payload = {
            "reporting_period": run.reporting_period.isoformat(),
            "line_count": len(created_lines),
            "lines": [
                {
                    "line_no": row.line_no,
                    "line_code": row.line_code,
                    "opening_balance": str(row.opening_balance),
                    "movement_amount": str(row.movement_amount),
                    "closing_balance": str(row.closing_balance),
                }
                for row in sorted(created_lines, key=lambda row: (row.line_no, row.id))
            ],
        }

        await self._repository.create_statement_result(
            tenant_id=tenant_id,
            run_id=run_id,
            total_equity_opening=total_opening,
            total_equity_closing=total_closing,
            statement_payload_json=statement_payload,
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
