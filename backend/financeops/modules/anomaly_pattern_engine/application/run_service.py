from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any

from financeops.modules.anomaly_pattern_engine.application.correlation_service import CorrelationService
from financeops.modules.anomaly_pattern_engine.application.materiality_service import MaterialityService
from financeops.modules.anomaly_pattern_engine.application.persistence_service import PersistenceService
from financeops.modules.anomaly_pattern_engine.application.scoring_service import ScoringService
from financeops.modules.anomaly_pattern_engine.application.statistical_service import StatisticalService
from financeops.modules.anomaly_pattern_engine.application.validation_service import ValidationService
from financeops.modules.anomaly_pattern_engine.domain.entities import (
    AnomalyRollforward,
    AnomalySignal,
    ComputedAnomaly,
)
from financeops.modules.anomaly_pattern_engine.domain.enums import (
    PersistenceClassification,
    RunStatus,
    SeverityLevel,
)
from financeops.modules.anomaly_pattern_engine.domain.value_objects import (
    AnomalyRunTokenInput,
    DefinitionVersionTokenInput,
)
from financeops.modules.anomaly_pattern_engine.infrastructure.repository import AnomalyPatternRepository
from financeops.modules.anomaly_pattern_engine.infrastructure.token_builder import (
    build_anomaly_run_token,
    build_definition_version_token,
)


class RunService:
    def __init__(
        self,
        *,
        repository: AnomalyPatternRepository,
        validation_service: ValidationService,
        statistical_service: StatisticalService,
        scoring_service: ScoringService,
        materiality_service: MaterialityService,
        persistence_service: PersistenceService,
        correlation_service: CorrelationService,
    ) -> None:
        self._repository = repository
        self._validation_service = validation_service
        self._statistical_service = statistical_service
        self._scoring_service = scoring_service
        self._materiality_service = materiality_service
        self._persistence_service = persistence_service
        self._correlation_service = correlation_service

    async def create_run(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        reporting_period: date,
        source_metric_run_ids: list[uuid.UUID],
        source_variance_run_ids: list[uuid.UUID],
        source_trend_run_ids: list[uuid.UUID],
        source_risk_run_ids: list[uuid.UUID],
        source_reconciliation_session_ids: list[uuid.UUID],
        created_by: uuid.UUID,
    ) -> dict[str, Any]:
        self._validation_service.validate_run_inputs(
            source_metric_run_ids=source_metric_run_ids,
            source_variance_run_ids=source_variance_run_ids,
            source_trend_run_ids=source_trend_run_ids,
            source_risk_run_ids=source_risk_run_ids,
            source_reconciliation_session_ids=source_reconciliation_session_ids,
        )
        for run_id in source_metric_run_ids:
            run = await self._repository.get_metric_run(tenant_id=tenant_id, run_id=run_id)
            if run is None or run.status != "completed":
                raise ValueError(f"Missing or non-completed metric run: {run_id}")
        for run_id in source_variance_run_ids:
            run = await self._repository.get_metric_run(tenant_id=tenant_id, run_id=run_id)
            if run is None or run.status != "completed":
                raise ValueError(f"Missing or non-completed variance run: {run_id}")
        for run_id in source_trend_run_ids:
            run = await self._repository.get_metric_run(tenant_id=tenant_id, run_id=run_id)
            if run is None or run.status != "completed":
                raise ValueError(f"Missing or non-completed trend run: {run_id}")
        for run_id in source_risk_run_ids:
            run = await self._repository.get_risk_run(tenant_id=tenant_id, run_id=run_id)
            if run is None or run.status != "completed":
                raise ValueError(f"Missing or non-completed risk run: {run_id}")
        for session_id in source_reconciliation_session_ids:
            session = await self._repository.get_reconciliation_session(
                tenant_id=tenant_id, session_id=session_id
            )
            if session is None:
                raise ValueError(f"Missing reconciliation session: {session_id}")

        definitions = await self._repository.active_anomaly_definitions(
            tenant_id=tenant_id,
            organisation_id=organisation_id,
            reporting_period=reporting_period,
        )
        pattern_rules = await self._repository.active_pattern_rules(
            tenant_id=tenant_id,
            organisation_id=organisation_id,
            reporting_period=reporting_period,
        )
        persistence_rules = await self._repository.active_persistence_rules(
            tenant_id=tenant_id,
            organisation_id=organisation_id,
            reporting_period=reporting_period,
        )
        correlation_rules = await self._repository.active_correlation_rules(
            tenant_id=tenant_id,
            organisation_id=organisation_id,
            reporting_period=reporting_period,
        )
        statistical_rules = await self._repository.active_statistical_rules(
            tenant_id=tenant_id,
            organisation_id=organisation_id,
            reporting_period=reporting_period,
        )
        self._validation_service.validate_definition_sets(
            definitions=definitions,
            pattern_rules=pattern_rules,
            persistence_rules=persistence_rules,
            correlation_rules=correlation_rules,
            statistical_rules=statistical_rules,
        )
        for row in statistical_rules:
            self._validation_service.validate_statistical_rule(rule=row)

        run_token = build_anomaly_run_token(
            AnomalyRunTokenInput(
                tenant_id=tenant_id,
                organisation_id=organisation_id,
                reporting_period=reporting_period,
                anomaly_definition_version_token=self._definitions_version_token(definitions),
                pattern_rule_version_token=self._rules_version_token(pattern_rules),
                persistence_rule_version_token=self._rules_version_token(persistence_rules),
                correlation_rule_version_token=self._rules_version_token(correlation_rules),
                statistical_rule_version_token=self._rules_version_token(statistical_rules),
                source_metric_run_ids=[str(v) for v in source_metric_run_ids],
                source_variance_run_ids=[str(v) for v in source_variance_run_ids],
                source_trend_run_ids=[str(v) for v in source_trend_run_ids],
                source_risk_run_ids=[str(v) for v in source_risk_run_ids],
                source_reconciliation_session_ids=[str(v) for v in source_reconciliation_session_ids],
                status=RunStatus.CREATED.value,
            )
        )
        existing = await self._repository.get_anomaly_run_by_token(tenant_id=tenant_id, run_token=run_token)
        if existing is not None:
            return {"run_id": str(existing.id), "run_token": existing.run_token, "status": existing.status, "idempotent": True}

        created = await self._repository.create_anomaly_run(
            tenant_id=tenant_id,
            organisation_id=organisation_id,
            reporting_period=reporting_period,
            anomaly_definition_version_token=self._definitions_version_token(definitions),
            pattern_rule_version_token=self._rules_version_token(pattern_rules),
            persistence_rule_version_token=self._rules_version_token(persistence_rules),
            correlation_rule_version_token=self._rules_version_token(correlation_rules),
            statistical_rule_version_token=self._rules_version_token(statistical_rules),
            source_metric_run_ids_json=[str(v) for v in source_metric_run_ids],
            source_variance_run_ids_json=[str(v) for v in source_variance_run_ids],
            source_trend_run_ids_json=[str(v) for v in source_trend_run_ids],
            source_risk_run_ids_json=[str(v) for v in source_risk_run_ids],
            source_reconciliation_session_ids_json=[str(v) for v in source_reconciliation_session_ids],
            run_token=run_token,
            status=RunStatus.CREATED.value,
            validation_summary_json={"definitions": len(definitions)},
            created_by=created_by,
        )
        return {"run_id": str(created.id), "run_token": created.run_token, "status": created.status, "idempotent": False}

    async def get_run(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> dict[str, Any] | None:
        row = await self._repository.get_anomaly_run(tenant_id=tenant_id, run_id=run_id)
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
        row = await self._repository.get_anomaly_run(tenant_id=tenant_id, run_id=run_id)
        if row is None:
            raise ValueError("Anomaly run not found")
        return {
            "run_id": str(row.id),
            "run_token": row.run_token,
            "status": row.status,
            **(await self._repository.summarize_run(tenant_id=tenant_id, run_id=run_id)),
        }

    async def list_results(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> list[dict[str, Any]]:
        rows = await self._repository.list_anomaly_results(tenant_id=tenant_id, run_id=run_id)
        return [
            {
                "id": str(row.id),
                "anomaly_code": row.anomaly_code,
                "anomaly_name": row.anomaly_name,
                "anomaly_domain": row.anomaly_domain,
                "anomaly_score": str(row.anomaly_score),
                "z_score": str(row.z_score) if row.z_score is not None else None,
                "severity": row.severity,
                "persistence_classification": row.persistence_classification,
                "correlation_flag": bool(row.correlation_flag),
                "materiality_elevated": bool(row.materiality_elevated),
                "risk_elevated": bool(row.risk_elevated),
                "board_flag": bool(row.board_flag),
                "confidence_score": str(row.confidence_score),
            }
            for row in rows
        ]

    async def list_signals(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> list[dict[str, Any]]:
        rows = await self._repository.list_anomaly_signals(tenant_id=tenant_id, run_id=run_id)
        return [
            {
                "id": str(row.id),
                "anomaly_result_id": str(row.anomaly_result_id),
                "signal_type": row.signal_type,
                "signal_ref": row.signal_ref,
                "contribution_weight": str(row.contribution_weight),
                "contribution_score": str(row.contribution_score),
                "signal_payload_json": row.signal_payload_json,
            }
            for row in rows
        ]

    async def list_rollforwards(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> list[dict[str, Any]]:
        rows = await self._repository.list_rollforward_events(tenant_id=tenant_id, run_id=run_id)
        return [
            {
                "id": str(row.id),
                "anomaly_result_id": str(row.anomaly_result_id),
                "event_type": row.event_type,
                "event_payload_json": row.event_payload_json,
                "actor_user_id": str(row.actor_user_id),
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]

    async def list_evidence(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> list[dict[str, Any]]:
        rows = await self._repository.list_evidence_links(tenant_id=tenant_id, run_id=run_id)
        return [
            {
                "id": str(row.id),
                "anomaly_result_id": str(row.anomaly_result_id),
                "evidence_type": row.evidence_type,
                "evidence_ref": row.evidence_ref,
                "evidence_label": row.evidence_label,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]

    async def execute_run(
        self,
        *,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
        actor_user_id: uuid.UUID,
    ) -> dict[str, Any]:
        run = await self._repository.get_anomaly_run(tenant_id=tenant_id, run_id=run_id)
        if run is None:
            raise ValueError("Anomaly run not found")
        completed = await self._ensure_status_row(
            tenant_id=tenant_id, run=run, status=RunStatus.COMPLETED, created_by=actor_user_id
        )
        existing = await self._repository.list_anomaly_results(tenant_id=tenant_id, run_id=completed.id)
        if existing:
            summary = await self._repository.summarize_run(tenant_id=tenant_id, run_id=completed.id)
            return {"run_id": str(completed.id), "run_token": completed.run_token, "status": completed.status, "idempotent": True, **summary}

        definitions = await self._repository.active_anomaly_definitions(
            tenant_id=tenant_id,
            organisation_id=completed.organisation_id,
            reporting_period=completed.reporting_period,
        )
        pattern_rule = (await self._repository.active_pattern_rules(
            tenant_id=tenant_id,
            organisation_id=completed.organisation_id,
            reporting_period=completed.reporting_period,
        ))[0]
        persistence_rule = (await self._repository.active_persistence_rules(
            tenant_id=tenant_id,
            organisation_id=completed.organisation_id,
            reporting_period=completed.reporting_period,
        ))[0]
        correlation_rule = (await self._repository.active_correlation_rules(
            tenant_id=tenant_id,
            organisation_id=completed.organisation_id,
            reporting_period=completed.reporting_period,
        ))[0]
        statistical_rule = (await self._repository.active_statistical_rules(
            tenant_id=tenant_id,
            organisation_id=completed.organisation_id,
            reporting_period=completed.reporting_period,
        ))[0]
        thresholds = self._materiality_service.merged_thresholds([statistical_rule])

        metric_rows = await self._repository.list_metric_results_for_runs(
            tenant_id=tenant_id, run_ids=[uuid.UUID(v) for v in completed.source_metric_run_ids_json]
        )
        variance_rows = await self._repository.list_variance_results_for_runs(
            tenant_id=tenant_id, run_ids=[uuid.UUID(v) for v in completed.source_variance_run_ids_json]
        )
        trend_rows = await self._repository.list_trend_results_for_runs(
            tenant_id=tenant_id, run_ids=[uuid.UUID(v) for v in completed.source_trend_run_ids_json]
        )
        risk_rows = await self._repository.list_risk_results_for_runs(
            tenant_id=tenant_id, run_ids=[uuid.UUID(v) for v in completed.source_risk_run_ids_json]
        )
        recon_rows = await self._repository.list_reconciliation_exceptions_for_sessions(
            tenant_id=tenant_id, session_ids=[uuid.UUID(v) for v in completed.source_reconciliation_session_ids_json]
        )

        metric_map: dict[str, list[Decimal]] = defaultdict(list)
        for row in metric_rows:
            metric_map[row.metric_code].append(Decimal(str(row.metric_value)))
        variance_map: dict[str, list[Decimal]] = defaultdict(list)
        for row in variance_rows:
            variance_map[row.metric_code].append(Decimal(str(row.variance_abs)))
        trend_map: dict[str, list[Decimal]] = defaultdict(list)
        for row in trend_rows:
            trend_map[row.metric_code].append(Decimal(str(row.trend_value)))
        risk_high = {row.risk_code for row in risk_rows if row.severity in ("high", "critical")}
        open_recon = [row for row in recon_rows if row.resolution_status == "open"]

        computed: list[ComputedAnomaly] = []
        signals_map: dict[str, list[AnomalySignal]] = {}
        roll_map: dict[str, list[AnomalyRollforward]] = {}
        evidence_map: dict[str, list[dict[str, Any]]] = {}

        for definition in sorted(definitions, key=lambda item: (item.anomaly_code, item.id)):
            selector = definition.signal_selector_json or {}
            metric_codes = sorted(set(selector.get("metric_codes", [])))
            variance_codes = sorted(set(selector.get("variance_codes", [])))
            trend_codes = sorted(set(selector.get("trend_codes", [])))
            risk_codes = sorted(set(selector.get("risk_codes", [])))

            values: list[Decimal] = []
            for code in metric_codes:
                values.extend(metric_map.get(code, []))
            if len(values) < 2:
                values = [Decimal("0"), Decimal("1")]

            window_values = self._statistical_service.rolling_window(values, window=statistical_rule.rolling_window)
            baseline_mean = self._statistical_service.rolling_mean(window_values, window=statistical_rule.rolling_window)
            baseline_std = self._statistical_service.rolling_std(window_values, window=statistical_rule.rolling_window)
            current_value = window_values[-1]
            z_score = self._statistical_service.z_score(current_value=current_value, baseline_mean=baseline_mean, baseline_std=baseline_std)
            anomaly_score = self._scoring_service.normalized_score_from_z(z_score)
            severity = self._materiality_service.severity_from_z(z_score=z_score, thresholds=thresholds)
            materiality_elevated = self._materiality_service.materiality_flag(anomaly_score=anomaly_score, thresholds=thresholds)
            risk_elevated = bool(risk_high.intersection(risk_codes))
            severity = self._materiality_service.elevate_severity(
                current=severity,
                risk_elevated=risk_elevated,
                materiality_elevated=materiality_elevated,
                board_critical=bool(selector.get("board_critical", False)),
            )
            correlation_flag = self._correlation_service.correlation_flag(
                signal_scores=[
                    Decimal("1") if metric_codes else Decimal("0"),
                    Decimal("1") if variance_codes else Decimal("0"),
                    Decimal("1") if trend_codes else Decimal("0"),
                    Decimal("1") if risk_elevated else Decimal("0"),
                ],
                min_signal_count=correlation_rule.min_signal_count,
            )
            confidence_score = self._scoring_service.confidence(
                has_metric_signals=bool(metric_codes),
                has_variance_signals=bool(variance_codes),
                has_trend_signals=bool(trend_codes),
                has_risk_signals=bool(risk_codes),
                has_open_reconciliation=bool(open_recon),
            )
            prior = await self._repository.latest_prior_anomaly_result(
                tenant_id=tenant_id,
                organisation_id=completed.organisation_id,
                anomaly_code=definition.anomaly_code,
                before_reporting_period=completed.reporting_period,
            )
            persistence = self._persistence_service.classify(
                prior_severity=prior.severity if prior else None,
                current_severity=severity,
                recurrence_count=1 if prior else 0,
                recurrence_threshold=persistence_rule.recurrence_threshold,
            )

            computed.append(
                ComputedAnomaly(
                    anomaly_code=definition.anomaly_code,
                    anomaly_name=definition.anomaly_name,
                    anomaly_domain=definition.anomaly_domain,
                    anomaly_score=anomaly_score,
                    z_score=z_score,
                    severity=severity,
                    persistence_classification=persistence,
                    correlation_flag=correlation_flag,
                    materiality_elevated=materiality_elevated,
                    risk_elevated=risk_elevated,
                    board_flag=severity in (SeverityLevel.HIGH, SeverityLevel.CRITICAL),
                    confidence_score=confidence_score,
                    seasonal_adjustment_flag=bool(statistical_rule.seasonal_adjustment_flag),
                    seasonal_normalized_value=current_value if statistical_rule.seasonal_adjustment_flag else None,
                    benchmark_group_id=statistical_rule.benchmark_group_id,
                    benchmark_baseline_value=baseline_mean,
                    benchmark_deviation_score=abs(current_value - baseline_mean),
                    source_summary_json={"pattern_rule": pattern_rule.rule_code},
                )
            )

            signals_map[definition.anomaly_code] = [
                AnomalySignal(signal_type="metric_ref", signal_ref=f"metric:{c}", contribution_weight=Decimal("1"), contribution_score=Decimal("1"), signal_payload_json={"metric_code": c}) for c in metric_codes
            ]
            roll_map[definition.anomaly_code] = [
                AnomalyRollforward(event_type="rolled_forward", event_payload_json={"state": persistence.value}),
                AnomalyRollforward(event_type="correlation_strengthened", event_payload_json={}) if correlation_flag else AnomalyRollforward(event_type="correlation_weakened", event_payload_json={}),
            ]
            evidence_map[definition.anomaly_code] = self._evidence_for_run_inputs(run=completed, definition=definition)

        inserted = await self._repository.insert_anomaly_results(tenant_id=tenant_id, run_id=completed.id, rows=computed, created_by=actor_user_id)
        by_code = {row.anomaly_code: row for row in inserted}
        for code, row in by_code.items():
            await self._repository.insert_anomaly_signals(tenant_id=tenant_id, run_id=completed.id, anomaly_result_id=row.id, rows=signals_map.get(code, []), created_by=actor_user_id)
            await self._repository.insert_rollforward_events(tenant_id=tenant_id, run_id=completed.id, anomaly_result_id=row.id, rows=roll_map.get(code, []), actor_user_id=actor_user_id, created_by=actor_user_id)
            await self._repository.insert_evidence_links(tenant_id=tenant_id, run_id=completed.id, anomaly_result_id=row.id, rows=evidence_map.get(code, []), created_by=actor_user_id)

        summary = await self._repository.summarize_run(tenant_id=tenant_id, run_id=completed.id)
        return {"run_id": str(completed.id), "run_token": completed.run_token, "status": completed.status, "idempotent": False, **summary}

    def _definitions_version_token(self, rows: list[Any]) -> str:
        return build_definition_version_token(
            DefinitionVersionTokenInput(
                rows=[
                    {"anomaly_code": row.anomaly_code, "version_token": row.version_token}
                    for row in sorted(rows, key=lambda item: (item.anomaly_code, item.id))
                ]
            )
        )

    def _rules_version_token(self, rows: list[Any]) -> str:
        return build_definition_version_token(
            DefinitionVersionTokenInput(
                rows=[
                    {"rule_code": row.rule_code, "version_token": row.version_token}
                    for row in sorted(rows, key=lambda item: (item.rule_code, item.id))
                ]
            )
        )

    def _run_token(self, *, run: Any, status: RunStatus) -> str:
        return build_anomaly_run_token(
            AnomalyRunTokenInput(
                tenant_id=run.tenant_id,
                organisation_id=run.organisation_id,
                reporting_period=run.reporting_period,
                anomaly_definition_version_token=run.anomaly_definition_version_token,
                pattern_rule_version_token=run.pattern_rule_version_token,
                persistence_rule_version_token=run.persistence_rule_version_token,
                correlation_rule_version_token=run.correlation_rule_version_token,
                statistical_rule_version_token=run.statistical_rule_version_token,
                source_metric_run_ids=list(run.source_metric_run_ids_json),
                source_variance_run_ids=list(run.source_variance_run_ids_json),
                source_trend_run_ids=list(run.source_trend_run_ids_json),
                source_risk_run_ids=list(run.source_risk_run_ids_json),
                source_reconciliation_session_ids=list(run.source_reconciliation_session_ids_json),
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
        existing = await self._repository.get_anomaly_run_by_token(tenant_id=tenant_id, run_token=token)
        if existing is not None:
            return existing
        return await self._repository.create_anomaly_run(
            tenant_id=tenant_id,
            organisation_id=run.organisation_id,
            reporting_period=run.reporting_period,
            anomaly_definition_version_token=run.anomaly_definition_version_token,
            pattern_rule_version_token=run.pattern_rule_version_token,
            persistence_rule_version_token=run.persistence_rule_version_token,
            correlation_rule_version_token=run.correlation_rule_version_token,
            statistical_rule_version_token=run.statistical_rule_version_token,
            source_metric_run_ids_json=list(run.source_metric_run_ids_json),
            source_variance_run_ids_json=list(run.source_variance_run_ids_json),
            source_trend_run_ids_json=list(run.source_trend_run_ids_json),
            source_risk_run_ids_json=list(run.source_risk_run_ids_json),
            source_reconciliation_session_ids_json=list(run.source_reconciliation_session_ids_json),
            run_token=token,
            status=status.value,
            validation_summary_json=run.validation_summary_json,
            created_by=created_by,
        )

    def _evidence_for_run_inputs(self, *, run: Any, definition: Any) -> list[dict[str, Any]]:
        return [
            {
                "evidence_type": "definition_token",
                "evidence_ref": f"anomaly_definition_token:{run.anomaly_definition_version_token}",
                "evidence_label": f"Definition {definition.anomaly_code}",
            },
            {
                "evidence_type": "statistical_rule_token",
                "evidence_ref": f"statistical_rule_token:{run.statistical_rule_version_token}",
                "evidence_label": "Statistical rule set",
            },
            {
                "evidence_type": "persistence_rule_token",
                "evidence_ref": f"persistence_rule_token:{run.persistence_rule_version_token}",
                "evidence_label": "Persistence rule set",
            },
            {
                "evidence_type": "correlation_rule_token",
                "evidence_ref": f"correlation_rule_token:{run.correlation_rule_version_token}",
                "evidence_label": "Correlation rule set",
            },
        ]
