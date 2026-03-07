from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from financeops.modules.ratio_variance_engine.application.materiality_service import (
    MaterialityService,
)
from financeops.modules.ratio_variance_engine.application.metric_definition_service import (
    MetricDefinitionService,
)
from financeops.modules.ratio_variance_engine.application.trend_service import TrendService
from financeops.modules.ratio_variance_engine.application.validation_service import (
    ValidationService,
)
from financeops.modules.ratio_variance_engine.application.variance_service import (
    VarianceService,
)
from financeops.modules.ratio_variance_engine.domain.enums import RunStatus
from financeops.modules.ratio_variance_engine.domain.value_objects import MetricRunTokenInput
from financeops.modules.ratio_variance_engine.infrastructure.repository import (
    RatioVarianceRepository,
)
from financeops.modules.ratio_variance_engine.infrastructure.token_builder import (
    build_metric_run_token,
)
from financeops.utils.determinism import canonical_json_dumps, sha256_hex_text


class RunService:
    def __init__(
        self,
        *,
        repository: RatioVarianceRepository,
        metric_definition_service: MetricDefinitionService,
        variance_service: VarianceService,
        trend_service: TrendService,
        materiality_service: MaterialityService,
        validation_service: ValidationService,
    ) -> None:
        self._repository = repository
        self._metric_definition_service = metric_definition_service
        self._variance_service = variance_service
        self._trend_service = trend_service
        self._materiality_service = materiality_service
        self._validation_service = validation_service

    async def create_run(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        reporting_period: date,
        scope_json: dict[str, Any],
        mis_snapshot_id: uuid.UUID | None,
        payroll_run_id: uuid.UUID | None,
        gl_run_id: uuid.UUID | None,
        reconciliation_session_id: uuid.UUID | None,
        payroll_gl_reconciliation_run_id: uuid.UUID | None,
        created_by: uuid.UUID,
    ) -> dict[str, Any]:
        self._validation_service.validate_scope(scope_json=scope_json)

        mis_snapshot = (
            await self._repository.get_mis_snapshot(
                tenant_id=tenant_id, snapshot_id=mis_snapshot_id
            )
            if mis_snapshot_id
            else None
        )
        payroll_run = (
            await self._repository.get_normalization_run(tenant_id=tenant_id, run_id=payroll_run_id)
            if payroll_run_id
            else None
        )
        gl_run = (
            await self._repository.get_normalization_run(tenant_id=tenant_id, run_id=gl_run_id)
            if gl_run_id
            else None
        )
        reconciliation_session = (
            await self._repository.get_reconciliation_session(
                tenant_id=tenant_id,
                session_id=reconciliation_session_id,
            )
            if reconciliation_session_id
            else None
        )
        payroll_gl_run = (
            await self._repository.get_payroll_gl_reconciliation_run(
                tenant_id=tenant_id,
                run_id=payroll_gl_reconciliation_run_id,
            )
            if payroll_gl_reconciliation_run_id
            else None
        )
        self._validation_service.validate_sources(
            reporting_period=reporting_period,
            mis_snapshot=mis_snapshot,
            payroll_run=payroll_run,
            gl_run=gl_run,
            reconciliation_session=reconciliation_session,
            payroll_gl_reconciliation_run=payroll_gl_run,
        )

        metric_definitions = await self._repository.active_metric_definitions(
            tenant_id=tenant_id,
            organisation_id=organisation_id,
            reporting_period=reporting_period,
        )
        variance_definitions = await self._repository.active_variance_definitions(
            tenant_id=tenant_id,
            organisation_id=organisation_id,
            reporting_period=reporting_period,
        )
        trend_definitions = await self._repository.active_trend_definitions(
            tenant_id=tenant_id,
            organisation_id=organisation_id,
            reporting_period=reporting_period,
        )
        materiality_rules = await self._repository.active_materiality_rules(
            tenant_id=tenant_id,
            organisation_id=organisation_id,
            reporting_period=reporting_period,
        )
        self._validation_service.validate_definition_sets(
            metric_definitions=metric_definitions,
            variance_definitions=variance_definitions,
            trend_definitions=trend_definitions,
            materiality_rules=materiality_rules,
        )

        components_by_definition = await self._components_by_definition(
            tenant_id=tenant_id,
            metric_definitions=metric_definitions,
        )
        metric_version_token = self._metric_definition_service.version_token(
            metric_definitions,
            components_by_definition,
        )
        variance_version_token = self._variance_service.version_token(variance_definitions)
        trend_version_token = self._trend_service.version_token(trend_definitions)
        materiality_version_token = self._materiality_service.version_token(materiality_rules)
        input_signature_hash = self._input_signature_hash(
            reporting_period=reporting_period,
            scope_json=scope_json,
            mis_snapshot_id=mis_snapshot_id,
            payroll_run_id=payroll_run_id,
            gl_run_id=gl_run_id,
            reconciliation_session_id=reconciliation_session_id,
            payroll_gl_reconciliation_run_id=payroll_gl_reconciliation_run_id,
        )
        run_token = self._run_token(
            tenant_id=tenant_id,
            organisation_id=organisation_id,
            reporting_period=reporting_period,
            scope_json=scope_json,
            mis_snapshot_id=mis_snapshot_id,
            payroll_run_id=payroll_run_id,
            gl_run_id=gl_run_id,
            reconciliation_session_id=reconciliation_session_id,
            payroll_gl_reconciliation_run_id=payroll_gl_reconciliation_run_id,
            metric_definition_version_token=metric_version_token,
            variance_definition_version_token=variance_version_token,
            trend_definition_version_token=trend_version_token,
            materiality_rule_version_token=materiality_version_token,
            input_signature_hash=input_signature_hash,
            status=RunStatus.CREATED,
        )
        existing = await self._repository.get_metric_run_by_token(
            tenant_id=tenant_id,
            run_token=run_token,
        )
        if existing is not None:
            return {
                "run_id": str(existing.id),
                "run_token": existing.run_token,
                "status": existing.status,
                "idempotent": True,
            }

        created = await self._repository.create_metric_run(
            tenant_id=tenant_id,
            organisation_id=organisation_id,
            reporting_period=reporting_period,
            scope_json=scope_json,
            mis_snapshot_id=mis_snapshot_id,
            payroll_run_id=payroll_run_id,
            gl_run_id=gl_run_id,
            reconciliation_session_id=reconciliation_session_id,
            payroll_gl_reconciliation_run_id=payroll_gl_reconciliation_run_id,
            metric_definition_version_token=metric_version_token,
            variance_definition_version_token=variance_version_token,
            trend_definition_version_token=trend_version_token,
            materiality_rule_version_token=materiality_version_token,
            input_signature_hash=input_signature_hash,
            run_token=run_token,
            status=RunStatus.CREATED.value,
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
        run = await self._repository.get_metric_run(tenant_id=tenant_id, run_id=run_id)
        if run is None:
            raise ValueError("Ratio/Variance run not found")

        completed = await self._ensure_status_row(
            tenant_id=tenant_id,
            run=run,
            status=RunStatus.COMPLETED,
            created_by=actor_user_id,
        )

        existing_metrics = await self._repository.list_metric_results(
            tenant_id=tenant_id,
            run_id=completed.id,
        )
        if existing_metrics:
            summary = await self._repository.summarize_run(
                tenant_id=tenant_id,
                run_id=completed.id,
            )
            return {
                "run_id": str(completed.id),
                "run_token": completed.run_token,
                "status": completed.status,
                "metric_count": summary["metric_count"],
                "variance_count": summary["variance_count"],
                "trend_count": summary["trend_count"],
                "idempotent": True,
            }

        metric_definitions = await self._repository.active_metric_definitions(
            tenant_id=tenant_id,
            organisation_id=completed.organisation_id,
            reporting_period=completed.reporting_period,
        )
        variance_definitions = await self._repository.active_variance_definitions(
            tenant_id=tenant_id,
            organisation_id=completed.organisation_id,
            reporting_period=completed.reporting_period,
        )
        trend_definitions = await self._repository.active_trend_definitions(
            tenant_id=tenant_id,
            organisation_id=completed.organisation_id,
            reporting_period=completed.reporting_period,
        )
        materiality_rules = await self._repository.active_materiality_rules(
            tenant_id=tenant_id,
            organisation_id=completed.organisation_id,
            reporting_period=completed.reporting_period,
        )
        self._validation_service.validate_definition_sets(
            metric_definitions=metric_definitions,
            variance_definitions=variance_definitions,
            trend_definitions=trend_definitions,
            materiality_rules=materiality_rules,
        )
        components_by_definition = await self._components_by_definition(
            tenant_id=tenant_id,
            metric_definitions=metric_definitions,
        )
        if self._metric_definition_service.version_token(
            metric_definitions,
            components_by_definition,
        ) != completed.metric_definition_version_token:
            raise ValueError("Metric definition drift detected for run")
        if self._variance_service.version_token(variance_definitions) != completed.variance_definition_version_token:
            raise ValueError("Variance definition drift detected for run")
        if self._trend_service.version_token(trend_definitions) != completed.trend_definition_version_token:
            raise ValueError("Trend definition drift detected for run")

        source_values = await self._repository.aggregate_source_values(
            tenant_id=tenant_id,
            mis_snapshot_id=completed.mis_snapshot_id,
            payroll_run_id=completed.payroll_run_id,
            gl_run_id=completed.gl_run_id,
            reconciliation_session_id=completed.reconciliation_session_id,
        )
        materiality_rule_json = self._materiality_service.merged_rule_json(materiality_rules)
        metric_rows = self._metric_definition_service.compute_metrics(
            definitions=metric_definitions,
            components_by_definition=components_by_definition,
            source_values=source_values,
            rule_json=materiality_rule_json,
            scope_json=completed.scope_json,
            materiality_service=self._materiality_service,
        )
        metric_inserted = await self._repository.insert_metric_results(
            tenant_id=tenant_id,
            run_id=completed.id,
            rows=metric_rows,
            created_by=actor_user_id,
        )

        metric_values = {row.metric_code: row.metric_value for row in metric_rows}
        directionality_by_metric = {
            row.metric_code: row.directionality for row in metric_definitions
        }
        prior_lookup: dict[str, list[tuple[date, Decimal]]] = {}
        for metric_code in sorted(metric_values.keys()):
            prior_lookup[metric_code] = await self._repository.prior_metric_series(
                tenant_id=tenant_id,
                organisation_id=completed.organisation_id,
                scope_json=completed.scope_json,
                metric_code=metric_code,
                before_reporting_period=completed.reporting_period,
            )

        variance_rows = self._variance_service.compute_variances(
            definitions=variance_definitions,
            metric_values=metric_values,
            prior_series_lookup=prior_lookup,
            scope_json=completed.scope_json,
            materiality_rule_json=materiality_rule_json,
            directionality_by_metric=directionality_by_metric,
            materiality_service=self._materiality_service,
        )
        variance_inserted = await self._repository.insert_variance_results(
            tenant_id=tenant_id,
            run_id=completed.id,
            rows=variance_rows,
            created_by=actor_user_id,
        )

        trend_rows = self._trend_service.compute_trends(
            definitions=trend_definitions,
            metric_values=metric_values,
            prior_series_lookup=prior_lookup,
        )
        trend_inserted = await self._repository.insert_trend_results(
            tenant_id=tenant_id,
            run_id=completed.id,
            rows=trend_rows,
            created_by=actor_user_id,
        )

        links: list[dict[str, Any]] = []
        for row in metric_inserted:
            links.extend(self._run_input_evidence(completed=completed, result_type="metric", result_id=row.id))
            links.append(
                {
                    "result_type": "metric",
                    "result_id": row.id,
                    "evidence_type": "definition",
                    "evidence_ref": f"metric_definition_token:{completed.metric_definition_version_token}",
                    "evidence_label": "Metric definition set",
                }
            )
        for row in variance_inserted:
            links.append(
                {
                    "result_type": "variance",
                    "result_id": row.id,
                    "evidence_type": "definition",
                    "evidence_ref": f"variance_definition_token:{completed.variance_definition_version_token}",
                    "evidence_label": "Variance definition set",
                }
            )
        for row in trend_inserted:
            links.append(
                {
                    "result_type": "trend",
                    "result_id": row.id,
                    "evidence_type": "definition",
                    "evidence_ref": f"trend_definition_token:{completed.trend_definition_version_token}",
                    "evidence_label": "Trend definition set",
                }
            )
        await self._repository.insert_metric_evidence_links(
            tenant_id=tenant_id,
            run_id=completed.id,
            links=links,
            created_by=actor_user_id,
        )

        summary = await self._repository.summarize_run(
            tenant_id=tenant_id,
            run_id=completed.id,
        )
        return {
            "run_id": str(completed.id),
            "run_token": completed.run_token,
            "status": completed.status,
            "metric_count": summary["metric_count"],
            "variance_count": summary["variance_count"],
            "trend_count": summary["trend_count"],
            "idempotent": False,
        }

    async def get_run(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> dict[str, Any] | None:
        row = await self._repository.get_metric_run(tenant_id=tenant_id, run_id=run_id)
        if row is None:
            return None
        return {
            "id": str(row.id),
            "organisation_id": str(row.organisation_id),
            "reporting_period": row.reporting_period.isoformat(),
            "scope_json": row.scope_json,
            "mis_snapshot_id": str(row.mis_snapshot_id) if row.mis_snapshot_id else None,
            "payroll_run_id": str(row.payroll_run_id) if row.payroll_run_id else None,
            "gl_run_id": str(row.gl_run_id) if row.gl_run_id else None,
            "reconciliation_session_id": (
                str(row.reconciliation_session_id) if row.reconciliation_session_id else None
            ),
            "payroll_gl_reconciliation_run_id": (
                str(row.payroll_gl_reconciliation_run_id)
                if row.payroll_gl_reconciliation_run_id
                else None
            ),
            "metric_definition_version_token": row.metric_definition_version_token,
            "variance_definition_version_token": row.variance_definition_version_token,
            "trend_definition_version_token": row.trend_definition_version_token,
            "materiality_rule_version_token": row.materiality_rule_version_token,
            "input_signature_hash": row.input_signature_hash,
            "run_token": row.run_token,
            "status": row.status,
            "created_at": row.created_at.isoformat(),
        }

    async def summary(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> dict[str, Any]:
        row = await self._repository.get_metric_run(tenant_id=tenant_id, run_id=run_id)
        if row is None:
            raise ValueError("Ratio/Variance run not found")
        summary = await self._repository.summarize_run(tenant_id=tenant_id, run_id=run_id)
        return {
            "run_id": str(row.id),
            "run_token": row.run_token,
            "status": row.status,
            **summary,
        }

    async def list_metrics(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> list[dict[str, Any]]:
        rows = await self._repository.list_metric_results(tenant_id=tenant_id, run_id=run_id)
        return [
            {
                "id": str(row.id),
                "line_no": row.line_no,
                "metric_code": row.metric_code,
                "unit_type": row.unit_type,
                "dimension_json": row.dimension_json,
                "metric_value": str(row.metric_value),
                "favorable_status": row.favorable_status,
                "materiality_flag": row.materiality_flag,
                "source_summary_json": row.source_summary_json,
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
                "base_period": row.base_period.isoformat() if row.base_period else None,
                "current_value": str(row.current_value),
                "baseline_value": str(row.baseline_value),
                "variance_abs": str(row.variance_abs),
                "variance_pct": str(row.variance_pct),
                "variance_bps": str(row.variance_bps),
                "days_change": str(row.days_change),
                "favorable_status": row.favorable_status,
                "materiality_flag": row.materiality_flag,
                "explanation_hint": row.explanation_hint,
            }
            for row in rows
        ]

    async def list_trends(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> list[dict[str, Any]]:
        rows = await self._repository.list_trend_results(tenant_id=tenant_id, run_id=run_id)
        return [
            {
                "id": str(row.id),
                "line_no": row.line_no,
                "metric_code": row.metric_code,
                "trend_type": row.trend_type,
                "window_size": row.window_size,
                "trend_value": str(row.trend_value),
                "trend_direction": row.trend_direction,
                "source_summary_json": row.source_summary_json,
            }
            for row in rows
        ]

    async def list_evidence(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> list[dict[str, Any]]:
        rows = await self._repository.list_metric_evidence(tenant_id=tenant_id, run_id=run_id)
        return [
            {
                "id": str(row.id),
                "result_type": row.result_type,
                "result_id": str(row.result_id),
                "evidence_type": row.evidence_type,
                "evidence_ref": row.evidence_ref,
                "evidence_label": row.evidence_label,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]

    async def _components_by_definition(
        self,
        *,
        tenant_id: uuid.UUID,
        metric_definitions: list[Any],
    ) -> dict[str, list[Any]]:
        result: dict[str, list[Any]] = {}
        for definition in metric_definitions:
            result[str(definition.id)] = await self._repository.list_metric_definition_components(
                tenant_id=tenant_id,
                definition_id=definition.id,
            )
        return result

    def _input_signature_hash(
        self,
        *,
        reporting_period: date,
        scope_json: dict[str, Any],
        mis_snapshot_id: uuid.UUID | None,
        payroll_run_id: uuid.UUID | None,
        gl_run_id: uuid.UUID | None,
        reconciliation_session_id: uuid.UUID | None,
        payroll_gl_reconciliation_run_id: uuid.UUID | None,
    ) -> str:
        payload = {
            "reporting_period": reporting_period.isoformat(),
            "scope_json": scope_json,
            "mis_snapshot_id": str(mis_snapshot_id) if mis_snapshot_id else None,
            "payroll_run_id": str(payroll_run_id) if payroll_run_id else None,
            "gl_run_id": str(gl_run_id) if gl_run_id else None,
            "reconciliation_session_id": (
                str(reconciliation_session_id) if reconciliation_session_id else None
            ),
            "payroll_gl_reconciliation_run_id": (
                str(payroll_gl_reconciliation_run_id)
                if payroll_gl_reconciliation_run_id
                else None
            ),
        }
        return sha256_hex_text(canonical_json_dumps(payload))

    def _run_token(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        reporting_period: date,
        scope_json: dict[str, Any],
        mis_snapshot_id: uuid.UUID | None,
        payroll_run_id: uuid.UUID | None,
        gl_run_id: uuid.UUID | None,
        reconciliation_session_id: uuid.UUID | None,
        payroll_gl_reconciliation_run_id: uuid.UUID | None,
        metric_definition_version_token: str,
        variance_definition_version_token: str,
        trend_definition_version_token: str,
        materiality_rule_version_token: str,
        input_signature_hash: str,
        status: RunStatus,
    ) -> str:
        return build_metric_run_token(
            MetricRunTokenInput(
                tenant_id=tenant_id,
                organisation_id=organisation_id,
                reporting_period=reporting_period,
                scope_json=scope_json,
                mis_snapshot_id=mis_snapshot_id,
                payroll_run_id=payroll_run_id,
                gl_run_id=gl_run_id,
                reconciliation_session_id=reconciliation_session_id,
                payroll_gl_reconciliation_run_id=payroll_gl_reconciliation_run_id,
                metric_definition_version_token=metric_definition_version_token,
                variance_definition_version_token=variance_definition_version_token,
                trend_definition_version_token=trend_definition_version_token,
                materiality_rule_version_token=materiality_rule_version_token,
                input_signature_hash=input_signature_hash,
            ),
            status=status.value,
        )

    async def _ensure_status_row(
        self,
        *,
        tenant_id: uuid.UUID,
        run: Any,
        status: RunStatus,
        created_by: uuid.UUID,
    ) -> Any:
        token = self._run_token(
            tenant_id=tenant_id,
            organisation_id=run.organisation_id,
            reporting_period=run.reporting_period,
            scope_json=run.scope_json,
            mis_snapshot_id=run.mis_snapshot_id,
            payroll_run_id=run.payroll_run_id,
            gl_run_id=run.gl_run_id,
            reconciliation_session_id=run.reconciliation_session_id,
            payroll_gl_reconciliation_run_id=run.payroll_gl_reconciliation_run_id,
            metric_definition_version_token=run.metric_definition_version_token,
            variance_definition_version_token=run.variance_definition_version_token,
            trend_definition_version_token=run.trend_definition_version_token,
            materiality_rule_version_token=run.materiality_rule_version_token,
            input_signature_hash=run.input_signature_hash,
            status=status,
        )
        existing = await self._repository.get_metric_run_by_token(
            tenant_id=tenant_id,
            run_token=token,
        )
        if existing is not None:
            return existing
        return await self._repository.create_metric_run(
            tenant_id=tenant_id,
            organisation_id=run.organisation_id,
            reporting_period=run.reporting_period,
            scope_json=run.scope_json,
            mis_snapshot_id=run.mis_snapshot_id,
            payroll_run_id=run.payroll_run_id,
            gl_run_id=run.gl_run_id,
            reconciliation_session_id=run.reconciliation_session_id,
            payroll_gl_reconciliation_run_id=run.payroll_gl_reconciliation_run_id,
            metric_definition_version_token=run.metric_definition_version_token,
            variance_definition_version_token=run.variance_definition_version_token,
            trend_definition_version_token=run.trend_definition_version_token,
            materiality_rule_version_token=run.materiality_rule_version_token,
            input_signature_hash=run.input_signature_hash,
            run_token=token,
            status=status.value,
            created_by=created_by,
        )

    def _run_input_evidence(self, *, completed: Any, result_type: str, result_id: uuid.UUID) -> list[dict[str, Any]]:
        links: list[dict[str, Any]] = []
        if completed.mis_snapshot_id:
            links.append(
                {
                    "result_type": result_type,
                    "result_id": result_id,
                    "evidence_type": "run_input",
                    "evidence_ref": f"mis_snapshot:{completed.mis_snapshot_id}",
                    "evidence_label": "MIS snapshot input",
                }
            )
        if completed.payroll_run_id:
            links.append(
                {
                    "result_type": result_type,
                    "result_id": result_id,
                    "evidence_type": "run_input",
                    "evidence_ref": f"payroll_normalization_run:{completed.payroll_run_id}",
                    "evidence_label": "Payroll normalization input",
                }
            )
        if completed.gl_run_id:
            links.append(
                {
                    "result_type": result_type,
                    "result_id": result_id,
                    "evidence_type": "run_input",
                    "evidence_ref": f"gl_normalization_run:{completed.gl_run_id}",
                    "evidence_label": "GL normalization input",
                }
            )
        if completed.reconciliation_session_id:
            links.append(
                {
                    "result_type": result_type,
                    "result_id": result_id,
                    "evidence_type": "reconciliation_line",
                    "evidence_ref": f"reconciliation_session:{completed.reconciliation_session_id}",
                    "evidence_label": "Reconciliation bridge input",
                }
            )
        return links
