from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from financeops.modules.board_pack_narrative_engine.application.inclusion_service import (
    InclusionService,
)
from financeops.modules.board_pack_narrative_engine.application.narrative_service import (
    NarrativeService,
)
from financeops.modules.board_pack_narrative_engine.application.section_service import (
    SectionService,
)
from financeops.modules.board_pack_narrative_engine.application.validation_service import (
    ValidationService,
)
from financeops.modules.board_pack_narrative_engine.domain.entities import (
    ComputedBoardPack,
)
from financeops.modules.board_pack_narrative_engine.domain.enums import (
    HealthClassification,
    RunStatus,
)
from financeops.modules.board_pack_narrative_engine.domain.value_objects import (
    BoardPackRunTokenInput,
    DefinitionVersionTokenInput,
)
from financeops.modules.board_pack_narrative_engine.infrastructure.repository import (
    BoardPackNarrativeRepository,
)
from financeops.modules.board_pack_narrative_engine.infrastructure.token_builder import (
    build_board_pack_run_token,
    build_definition_version_token,
)


class RunService:
    def __init__(
        self,
        *,
        repository: BoardPackNarrativeRepository,
        validation_service: ValidationService,
        inclusion_service: InclusionService,
        section_service: SectionService,
        narrative_service: NarrativeService,
    ) -> None:
        self._repository = repository
        self._validation_service = validation_service
        self._inclusion_service = inclusion_service
        self._section_service = section_service
        self._narrative_service = narrative_service

    async def create_run(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        reporting_period: date,
        source_metric_run_ids: list[uuid.UUID],
        source_risk_run_ids: list[uuid.UUID],
        source_anomaly_run_ids: list[uuid.UUID],
        created_by: uuid.UUID,
    ) -> dict[str, Any]:
        self._validation_service.validate_run_inputs(
            source_metric_run_ids=source_metric_run_ids,
            source_risk_run_ids=source_risk_run_ids,
            source_anomaly_run_ids=source_anomaly_run_ids,
        )
        metric_runs = await self._repository.list_metric_runs(
            tenant_id=tenant_id,
            run_ids=sorted(source_metric_run_ids, key=lambda value: str(value)),
        )
        metric_runs_by_id = {row.id: row for row in metric_runs}
        for run_id in source_metric_run_ids:
            run = metric_runs_by_id.get(run_id)
            if run is None or run.status != "completed":
                raise ValueError(f"Missing or non-completed metric run: {run_id}")

        risk_runs = await self._repository.list_risk_runs(
            tenant_id=tenant_id,
            run_ids=sorted(source_risk_run_ids, key=lambda value: str(value)),
        )
        risk_runs_by_id = {row.id: row for row in risk_runs}
        for run_id in source_risk_run_ids:
            run = risk_runs_by_id.get(run_id)
            if run is None or run.status != "completed":
                raise ValueError(f"Missing or non-completed risk run: {run_id}")

        anomaly_runs = await self._repository.list_anomaly_runs(
            tenant_id=tenant_id,
            run_ids=sorted(source_anomaly_run_ids, key=lambda value: str(value)),
        )
        anomaly_runs_by_id = {row.id: row for row in anomaly_runs}
        for run_id in source_anomaly_run_ids:
            run = anomaly_runs_by_id.get(run_id)
            if run is None or run.status != "completed":
                raise ValueError(f"Missing or non-completed anomaly run: {run_id}")

        definitions = await self._repository.active_board_pack_definitions(
            tenant_id=tenant_id,
            organisation_id=organisation_id,
            reporting_period=reporting_period,
        )
        sections = await self._repository.active_section_definitions(
            tenant_id=tenant_id,
            organisation_id=organisation_id,
            reporting_period=reporting_period,
        )
        templates = await self._repository.active_narrative_templates(
            tenant_id=tenant_id,
            organisation_id=organisation_id,
            reporting_period=reporting_period,
        )
        inclusion_rules = await self._repository.active_inclusion_rules(
            tenant_id=tenant_id,
            organisation_id=organisation_id,
            reporting_period=reporting_period,
        )
        self._validation_service.validate_definition_sets(
            definitions=definitions,
            sections=sections,
            templates=templates,
            inclusion_rules=inclusion_rules,
        )

        run_token = build_board_pack_run_token(
            BoardPackRunTokenInput(
                tenant_id=tenant_id,
                organisation_id=organisation_id,
                reporting_period=reporting_period,
                board_pack_definition_version_token=self._version_token(
                    definitions, code_field="board_pack_code"
                ),
                section_definition_version_token=self._version_token(
                    sections, code_field="section_code"
                ),
                narrative_template_version_token=self._version_token(
                    templates, code_field="template_code"
                ),
                inclusion_rule_version_token=self._version_token(
                    inclusion_rules, code_field="rule_code"
                ),
                source_metric_run_ids=[str(v) for v in source_metric_run_ids],
                source_risk_run_ids=[str(v) for v in source_risk_run_ids],
                source_anomaly_run_ids=[str(v) for v in source_anomaly_run_ids],
                status=RunStatus.CREATED.value,
            )
        )
        existing = await self._repository.get_board_pack_run_by_token(
            tenant_id=tenant_id, run_token=run_token
        )
        if existing is not None:
            return {
                "run_id": str(existing.id),
                "run_token": existing.run_token,
                "status": existing.status,
                "idempotent": True,
            }

        created = await self._repository.create_board_pack_run(
            tenant_id=tenant_id,
            organisation_id=organisation_id,
            reporting_period=reporting_period,
            board_pack_definition_version_token=self._version_token(
                definitions, code_field="board_pack_code"
            ),
            section_definition_version_token=self._version_token(
                sections, code_field="section_code"
            ),
            narrative_template_version_token=self._version_token(
                templates, code_field="template_code"
            ),
            inclusion_rule_version_token=self._version_token(
                inclusion_rules, code_field="rule_code"
            ),
            source_metric_run_ids_json=[str(v) for v in source_metric_run_ids],
            source_risk_run_ids_json=[str(v) for v in source_risk_run_ids],
            source_anomaly_run_ids_json=[str(v) for v in source_anomaly_run_ids],
            run_token=run_token,
            status=RunStatus.CREATED.value,
            validation_summary_json={"definitions": len(definitions)},
            created_by=created_by,
        )
        return {
            "run_id": str(created.id),
            "run_token": created.run_token,
            "status": created.status,
            "idempotent": False,
        }

    async def execute_run(
        self,
        *,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
        actor_user_id: uuid.UUID,
    ) -> dict[str, Any]:
        run = await self._repository.get_board_pack_run(tenant_id=tenant_id, run_id=run_id)
        if run is None:
            raise ValueError("Board pack run not found")
        completed = await self._ensure_status_row(
            tenant_id=tenant_id,
            run=run,
            status=RunStatus.COMPLETED,
            created_by=actor_user_id,
        )
        existing = await self._repository.get_board_pack_result(
            tenant_id=tenant_id, run_id=completed.id
        )
        if existing is not None:
            summary = await self._repository.summarize_run(tenant_id=tenant_id, run_id=completed.id)
            return {
                "run_id": str(completed.id),
                "run_token": completed.run_token,
                "status": completed.status,
                "idempotent": True,
                **summary,
            }

        definitions = await self._repository.active_board_pack_definitions(
            tenant_id=tenant_id,
            organisation_id=completed.organisation_id,
            reporting_period=completed.reporting_period,
        )
        sections = await self._repository.active_section_definitions(
            tenant_id=tenant_id,
            organisation_id=completed.organisation_id,
            reporting_period=completed.reporting_period,
        )
        templates = await self._repository.active_narrative_templates(
            tenant_id=tenant_id,
            organisation_id=completed.organisation_id,
            reporting_period=completed.reporting_period,
        )
        inclusion_rules = await self._repository.active_inclusion_rules(
            tenant_id=tenant_id,
            organisation_id=completed.organisation_id,
            reporting_period=completed.reporting_period,
        )
        self._validation_service.validate_definition_sets(
            definitions=definitions,
            sections=sections,
            templates=templates,
            inclusion_rules=inclusion_rules,
        )

        metric_ids = [uuid.UUID(v) for v in completed.source_metric_run_ids_json]
        risk_ids = [uuid.UUID(v) for v in completed.source_risk_run_ids_json]
        anomaly_ids = [uuid.UUID(v) for v in completed.source_anomaly_run_ids_json]
        metric_rows = await self._repository.list_metric_results_for_runs(
            tenant_id=tenant_id, run_ids=metric_ids
        )
        variance_rows = await self._repository.list_variance_results_for_runs(
            tenant_id=tenant_id, run_ids=metric_ids
        )
        trend_rows = await self._repository.list_trend_results_for_runs(
            tenant_id=tenant_id, run_ids=metric_ids
        )
        risk_rows = await self._repository.list_risk_results_for_runs(
            tenant_id=tenant_id, run_ids=risk_ids
        )
        anomaly_rows = await self._repository.list_anomaly_results_for_runs(
            tenant_id=tenant_id, run_ids=anomaly_ids
        )

        high_risk_count = len([row for row in risk_rows if row.severity in ("high", "critical")])
        elevated_anomaly_count = len(
            [
                row
                for row in anomaly_rows
                if row.severity in ("high", "critical")
                or row.persistence_classification in ("sustained", "escalating")
            ]
        )
        top_limit = self._inclusion_service.top_limit(rules=inclusion_rules)
        built_sections = self._section_service.build_sections(
            section_rows=sections,
            metric_rows=metric_rows,
            risk_rows=risk_rows,
            anomaly_rows=anomaly_rows,
            top_limit=top_limit,
        )
        included_sections = [
            row
            for row in built_sections
            if self._inclusion_service.should_include_section(
                section_code=row.section_code,
                rules=inclusion_rules,
                risk_count=high_risk_count,
                anomaly_count=elevated_anomaly_count,
            )
        ]
        narratives = self._narrative_service.render_blocks(
            sections=included_sections,
            templates=templates,
            reporting_period=completed.reporting_period.isoformat(),
        )
        board_pack = sorted(definitions, key=lambda item: (item.board_pack_code, item.id))[0]
        executive_summary = self._narrative_service.executive_summary(
            sections=included_sections,
            high_risk_count=high_risk_count,
            elevated_anomaly_count=elevated_anomaly_count,
        )
        overall = self._overall_health(
            high_risk_count=high_risk_count, elevated_anomaly_count=elevated_anomaly_count
        )
        await self._repository.create_board_pack_result(
            tenant_id=tenant_id,
            run_id=completed.id,
            reporting_period=completed.reporting_period,
            row=ComputedBoardPack(
                board_pack_code=board_pack.board_pack_code,
                executive_summary_text=executive_summary,
                overall_health_classification=overall.value,
                status="generated",
            ),
            created_by=actor_user_id,
        )
        inserted_sections = await self._repository.insert_section_results(
            tenant_id=tenant_id,
            run_id=completed.id,
            rows=included_sections,
            created_by=actor_user_id,
        )
        narrative_by_section = {
            section.section_code: narrative
            for section, narrative in zip(included_sections, narratives, strict=False)
        }
        inserted_narrative_ids: list[uuid.UUID] = []
        for section in inserted_sections:
            narrative = narrative_by_section.get(section.section_code)
            if narrative is None:
                continue
            inserted = await self._repository.insert_narrative_blocks(
                tenant_id=tenant_id,
                run_id=completed.id,
                section_result_id=section.id,
                rows=[narrative],
                created_by=actor_user_id,
            )
            inserted_narrative_ids.extend([row.id for row in inserted])

        evidence_rows = self._evidence_rows(
            run=completed,
            metric_rows=metric_rows,
            variance_rows=variance_rows,
            trend_rows=trend_rows,
            risk_rows=risk_rows,
            anomaly_rows=anomaly_rows,
            board_pack=board_pack,
            inserted_sections=inserted_sections,
            inserted_narrative_ids=inserted_narrative_ids,
        )
        await self._repository.insert_evidence_links(
            tenant_id=tenant_id,
            run_id=completed.id,
            rows=evidence_rows,
            created_by=actor_user_id,
        )
        summary = await self._repository.summarize_run(tenant_id=tenant_id, run_id=completed.id)
        return {
            "run_id": str(completed.id),
            "run_token": completed.run_token,
            "status": completed.status,
            "idempotent": False,
            **summary,
        }

    async def get_run(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> dict[str, Any] | None:
        row = await self._repository.get_board_pack_run(tenant_id=tenant_id, run_id=run_id)
        if row is None:
            return None
        return {
            "id": str(row.id),
            "run_token": row.run_token,
            "status": row.status,
            "reporting_period": row.reporting_period.isoformat(),
            "created_at": row.created_at.isoformat(),
        }

    async def summary(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> dict[str, Any]:
        run = await self._repository.get_board_pack_run(tenant_id=tenant_id, run_id=run_id)
        if run is None:
            raise ValueError("Board pack run not found")
        result = await self._repository.get_board_pack_result(tenant_id=tenant_id, run_id=run_id)
        return {
            "run_id": str(run.id),
            "run_token": run.run_token,
            "status": run.status,
            "board_pack_code": result.board_pack_code if result is not None else None,
            "executive_summary_text": result.executive_summary_text if result is not None else None,
            "overall_health_classification": result.overall_health_classification
            if result is not None
            else None,
            **(await self._repository.summarize_run(tenant_id=tenant_id, run_id=run_id)),
        }

    async def list_sections(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> list[dict[str, Any]]:
        rows = await self._repository.list_section_results(tenant_id=tenant_id, run_id=run_id)
        return [
            {
                "id": str(row.id),
                "section_code": row.section_code,
                "section_order": row.section_order,
                "section_title": row.section_title,
                "section_summary_text": row.section_summary_text,
                "section_payload_json": row.section_payload_json,
            }
            for row in rows
        ]

    async def list_narratives(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> list[dict[str, Any]]:
        rows = await self._repository.list_narrative_blocks(tenant_id=tenant_id, run_id=run_id)
        return [
            {
                "id": str(row.id),
                "section_result_id": str(row.section_result_id),
                "narrative_template_code": row.narrative_template_code,
                "narrative_text": row.narrative_text,
                "narrative_payload_json": row.narrative_payload_json,
                "block_order": row.block_order,
            }
            for row in rows
        ]

    async def list_evidence(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> list[dict[str, Any]]:
        rows = await self._repository.list_evidence_links(tenant_id=tenant_id, run_id=run_id)
        return [
            {
                "id": str(row.id),
                "section_result_id": str(row.section_result_id)
                if row.section_result_id is not None
                else None,
                "narrative_block_id": str(row.narrative_block_id)
                if row.narrative_block_id is not None
                else None,
                "evidence_type": row.evidence_type,
                "evidence_ref": row.evidence_ref,
                "evidence_label": row.evidence_label,
                "evidence_payload_json": row.evidence_payload_json,
                "board_attention_flag": bool(row.board_attention_flag),
                "severity_rank": str(row.severity_rank),
            }
            for row in rows
        ]

    def _version_token(self, rows: list[Any], *, code_field: str) -> str:
        return build_definition_version_token(
            DefinitionVersionTokenInput(
                rows=[
                    {code_field: getattr(row, code_field), "version_token": row.version_token}
                    for row in sorted(rows, key=lambda item: (getattr(item, code_field), item.id))
                ]
            )
        )

    def _run_token(self, *, run: Any, status: RunStatus) -> str:
        return build_board_pack_run_token(
            BoardPackRunTokenInput(
                tenant_id=run.tenant_id,
                organisation_id=run.organisation_id,
                reporting_period=run.reporting_period,
                board_pack_definition_version_token=run.board_pack_definition_version_token,
                section_definition_version_token=run.section_definition_version_token,
                narrative_template_version_token=run.narrative_template_version_token,
                inclusion_rule_version_token=run.inclusion_rule_version_token,
                source_metric_run_ids=list(run.source_metric_run_ids_json),
                source_risk_run_ids=list(run.source_risk_run_ids_json),
                source_anomaly_run_ids=list(run.source_anomaly_run_ids_json),
                status=status.value,
            )
        )

    async def _ensure_status_row(
        self,
        *,
        tenant_id: uuid.UUID,
        run: Any,
        status: RunStatus,
        created_by: uuid.UUID,
    ) -> Any:
        token = self._run_token(run=run, status=status)
        existing = await self._repository.get_board_pack_run_by_token(
            tenant_id=tenant_id, run_token=token
        )
        if existing is not None:
            return existing
        return await self._repository.create_board_pack_run(
            tenant_id=tenant_id,
            organisation_id=run.organisation_id,
            reporting_period=run.reporting_period,
            board_pack_definition_version_token=run.board_pack_definition_version_token,
            section_definition_version_token=run.section_definition_version_token,
            narrative_template_version_token=run.narrative_template_version_token,
            inclusion_rule_version_token=run.inclusion_rule_version_token,
            source_metric_run_ids_json=list(run.source_metric_run_ids_json),
            source_risk_run_ids_json=list(run.source_risk_run_ids_json),
            source_anomaly_run_ids_json=list(run.source_anomaly_run_ids_json),
            run_token=token,
            status=status.value,
            validation_summary_json=run.validation_summary_json,
            created_by=created_by,
        )

    def _overall_health(
        self, *, high_risk_count: int, elevated_anomaly_count: int
    ) -> HealthClassification:
        score = high_risk_count + elevated_anomaly_count
        if score >= 6:
            return HealthClassification.CRITICAL
        if score >= 3:
            return HealthClassification.STRESSED
        if score >= 1:
            return HealthClassification.WATCH
        return HealthClassification.HEALTHY

    def _evidence_rows(
        self,
        *,
        run: Any,
        metric_rows: list[Any],
        variance_rows: list[Any],
        trend_rows: list[Any],
        risk_rows: list[Any],
        anomaly_rows: list[Any],
        board_pack: Any,
        inserted_sections: list[Any],
        inserted_narrative_ids: list[uuid.UUID],
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = [
            {
                "section_result_id": None,
                "narrative_block_id": None,
                "evidence_type": "definition_token",
                "evidence_ref": f"board_pack_definition_token:{run.board_pack_definition_version_token}",
                "evidence_label": f"Board pack definition {board_pack.board_pack_code}",
                "evidence_payload_json": {},
                "board_attention_flag": False,
                "severity_rank": "0",
            }
        ]
        for metric in metric_rows[:5]:
            rows.append(
                {
                    "section_result_id": None,
                    "narrative_block_id": None,
                    "evidence_type": "metric_result",
                    "evidence_ref": f"metric_result:{metric.id}",
                    "evidence_label": metric.metric_code,
                    "evidence_payload_json": {"metric_code": metric.metric_code},
                    "board_attention_flag": False,
                    "severity_rank": "0",
                }
            )
        for variance in variance_rows[:3]:
            rows.append(
                {
                    "section_result_id": None,
                    "narrative_block_id": None,
                    "evidence_type": "variance_result",
                    "evidence_ref": f"variance_result:{variance.id}",
                    "evidence_label": variance.metric_code,
                    "evidence_payload_json": {"comparison_type": variance.comparison_type},
                    "board_attention_flag": False,
                    "severity_rank": "0",
                }
            )
        for trend in trend_rows[:3]:
            rows.append(
                {
                    "section_result_id": None,
                    "narrative_block_id": None,
                    "evidence_type": "trend_result",
                    "evidence_ref": f"trend_result:{trend.id}",
                    "evidence_label": trend.metric_code,
                    "evidence_payload_json": {"trend_type": trend.trend_type},
                    "board_attention_flag": False,
                    "severity_rank": "0",
                }
            )
        risk_rank = {"critical": 5, "high": 4, "medium": 3, "low": 2, "info": 1}
        for risk in risk_rows[:10]:
            rows.append(
                {
                    "section_result_id": str(inserted_sections[0].id) if inserted_sections else None,
                    "narrative_block_id": str(inserted_narrative_ids[0]) if inserted_narrative_ids else None,
                    "evidence_type": "risk_result",
                    "evidence_ref": f"risk_result:{risk.id}",
                    "evidence_label": risk.risk_code,
                    "evidence_payload_json": {"severity": risk.severity},
                    "board_attention_flag": risk.severity in ("high", "critical"),
                    "severity_rank": str(risk_rank.get(risk.severity, 0)),
                }
            )
        anomaly_rank = {"critical": 5, "high": 4, "medium": 3, "low": 2, "info": 1}
        for anomaly in anomaly_rows[:10]:
            rows.append(
                {
                    "section_result_id": str(inserted_sections[0].id) if inserted_sections else None,
                    "narrative_block_id": str(inserted_narrative_ids[0]) if inserted_narrative_ids else None,
                    "evidence_type": "anomaly_result",
                    "evidence_ref": f"anomaly_result:{anomaly.id}",
                    "evidence_label": anomaly.anomaly_code,
                    "evidence_payload_json": {"severity": anomaly.severity},
                    "board_attention_flag": anomaly.severity in ("high", "critical"),
                    "severity_rank": str(anomaly_rank.get(anomaly.severity, 0)),
                }
            )
        return rows
