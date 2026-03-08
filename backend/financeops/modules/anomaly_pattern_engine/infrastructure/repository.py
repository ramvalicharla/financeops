from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.anomaly_pattern_engine import (
    AnomalyContributingSignal,
    AnomalyCorrelationRule,
    AnomalyDefinition,
    AnomalyEvidenceLink,
    AnomalyPatternRule,
    AnomalyPersistenceRule,
    AnomalyResult,
    AnomalyRollforwardEvent,
    AnomalyRun,
    AnomalyStatisticalRule,
)
from financeops.db.models.financial_risk_engine import RiskResult, RiskRun
from financeops.db.models.ratio_variance_engine import MetricResult, MetricRun, TrendResult, VarianceResult
from financeops.db.models.reconciliation_bridge import ReconciliationException, ReconciliationSession
from financeops.modules.anomaly_pattern_engine.domain.entities import (
    AnomalyRollforward,
    AnomalySignal,
    ComputedAnomaly,
)
from financeops.services.audit_writer import AuditEvent, AuditWriter


class AnomalyPatternRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_anomaly_definition(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        anomaly_code: str,
        anomaly_name: str,
        anomaly_domain: str,
        signal_selector_json: dict[str, Any],
        definition_json: dict[str, Any],
        version_token: str,
        effective_from: date,
        effective_to: date | None,
        supersedes_id: uuid.UUID | None,
        status: str,
        created_by: uuid.UUID,
    ) -> AnomalyDefinition:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=AnomalyDefinition,
            tenant_id=tenant_id,
            record_data={"anomaly_code": anomaly_code},
            values={
                "organisation_id": organisation_id,
                "anomaly_code": anomaly_code,
                "anomaly_name": anomaly_name,
                "anomaly_domain": anomaly_domain,
                "signal_selector_json": signal_selector_json,
                "definition_json": definition_json,
                "version_token": version_token,
                "effective_from": effective_from,
                "effective_to": effective_to,
                "supersedes_id": supersedes_id,
                "status": status,
                "created_by": created_by,
            },
            audit=AuditEvent(
                tenant_id=tenant_id,
                user_id=created_by,
                action="anomaly_pattern.definition.created",
                resource_type="anomaly_definition",
                resource_name=anomaly_code,
            ),
        )

    async def list_anomaly_definitions(self, *, tenant_id: uuid.UUID) -> list[AnomalyDefinition]:
        result = await self._session.execute(
            select(AnomalyDefinition)
            .where(AnomalyDefinition.tenant_id == tenant_id)
            .order_by(
                AnomalyDefinition.anomaly_code.asc(),
                AnomalyDefinition.effective_from.desc(),
                AnomalyDefinition.created_at.desc(),
            )
        )
        return list(result.scalars().all())

    async def get_anomaly_definition(
        self, *, tenant_id: uuid.UUID, definition_id: uuid.UUID
    ) -> AnomalyDefinition | None:
        result = await self._session.execute(
            select(AnomalyDefinition).where(
                AnomalyDefinition.tenant_id == tenant_id,
                AnomalyDefinition.id == definition_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_anomaly_definition_versions(
        self, *, tenant_id: uuid.UUID, definition_id: uuid.UUID
    ) -> list[AnomalyDefinition]:
        current = await self.get_anomaly_definition(tenant_id=tenant_id, definition_id=definition_id)
        if current is None:
            return []
        result = await self._session.execute(
            select(AnomalyDefinition)
            .where(
                AnomalyDefinition.tenant_id == tenant_id,
                AnomalyDefinition.organisation_id == current.organisation_id,
                AnomalyDefinition.anomaly_code == current.anomaly_code,
            )
            .order_by(
                AnomalyDefinition.effective_from.desc(),
                AnomalyDefinition.created_at.desc(),
                AnomalyDefinition.id.desc(),
            )
        )
        return list(result.scalars().all())

    async def create_pattern_rule(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        rule_code: str,
        rule_name: str,
        pattern_signature_json: dict[str, Any],
        classification_behavior_json: dict[str, Any],
        version_token: str,
        effective_from: date,
        supersedes_id: uuid.UUID | None,
        status: str,
        created_by: uuid.UUID,
    ) -> AnomalyPatternRule:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=AnomalyPatternRule,
            tenant_id=tenant_id,
            record_data={"rule_code": rule_code},
            values={
                "organisation_id": organisation_id,
                "rule_code": rule_code,
                "rule_name": rule_name,
                "pattern_signature_json": pattern_signature_json,
                "classification_behavior_json": classification_behavior_json,
                "version_token": version_token,
                "effective_from": effective_from,
                "supersedes_id": supersedes_id,
                "status": status,
                "created_by": created_by,
            },
            audit=AuditEvent(
                tenant_id=tenant_id,
                user_id=created_by,
                action="anomaly_pattern.pattern_rule.created",
                resource_type="anomaly_pattern_rule",
                resource_name=rule_code,
            ),
        )

    async def list_pattern_rules(self, *, tenant_id: uuid.UUID) -> list[AnomalyPatternRule]:
        result = await self._session.execute(
            select(AnomalyPatternRule)
            .where(AnomalyPatternRule.tenant_id == tenant_id)
            .order_by(
                AnomalyPatternRule.rule_code.asc(),
                AnomalyPatternRule.effective_from.desc(),
                AnomalyPatternRule.created_at.desc(),
            )
        )
        return list(result.scalars().all())

    async def create_persistence_rule(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        rule_code: str,
        rule_name: str,
        rolling_window: int,
        recurrence_threshold: int,
        escalation_logic_json: dict[str, Any],
        version_token: str,
        effective_from: date,
        supersedes_id: uuid.UUID | None,
        status: str,
        created_by: uuid.UUID,
    ) -> AnomalyPersistenceRule:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=AnomalyPersistenceRule,
            tenant_id=tenant_id,
            record_data={"rule_code": rule_code},
            values={
                "organisation_id": organisation_id,
                "rule_code": rule_code,
                "rule_name": rule_name,
                "rolling_window": rolling_window,
                "recurrence_threshold": recurrence_threshold,
                "escalation_logic_json": escalation_logic_json,
                "version_token": version_token,
                "effective_from": effective_from,
                "supersedes_id": supersedes_id,
                "status": status,
                "created_by": created_by,
            },
            audit=AuditEvent(
                tenant_id=tenant_id,
                user_id=created_by,
                action="anomaly_pattern.persistence_rule.created",
                resource_type="anomaly_persistence_rule",
                resource_name=rule_code,
            ),
        )

    async def list_persistence_rules(self, *, tenant_id: uuid.UUID) -> list[AnomalyPersistenceRule]:
        result = await self._session.execute(
            select(AnomalyPersistenceRule)
            .where(AnomalyPersistenceRule.tenant_id == tenant_id)
            .order_by(
                AnomalyPersistenceRule.rule_code.asc(),
                AnomalyPersistenceRule.effective_from.desc(),
                AnomalyPersistenceRule.created_at.desc(),
            )
        )
        return list(result.scalars().all())

    async def create_correlation_rule(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        rule_code: str,
        rule_name: str,
        correlation_window: int,
        min_signal_count: int,
        correlation_logic_json: dict[str, Any],
        version_token: str,
        effective_from: date,
        supersedes_id: uuid.UUID | None,
        status: str,
        created_by: uuid.UUID,
    ) -> AnomalyCorrelationRule:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=AnomalyCorrelationRule,
            tenant_id=tenant_id,
            record_data={"rule_code": rule_code},
            values={
                "organisation_id": organisation_id,
                "rule_code": rule_code,
                "rule_name": rule_name,
                "correlation_window": correlation_window,
                "min_signal_count": min_signal_count,
                "correlation_logic_json": correlation_logic_json,
                "version_token": version_token,
                "effective_from": effective_from,
                "supersedes_id": supersedes_id,
                "status": status,
                "created_by": created_by,
            },
            audit=AuditEvent(
                tenant_id=tenant_id,
                user_id=created_by,
                action="anomaly_pattern.correlation_rule.created",
                resource_type="anomaly_correlation_rule",
                resource_name=rule_code,
            ),
        )

    async def list_correlation_rules(self, *, tenant_id: uuid.UUID) -> list[AnomalyCorrelationRule]:
        result = await self._session.execute(
            select(AnomalyCorrelationRule)
            .where(AnomalyCorrelationRule.tenant_id == tenant_id)
            .order_by(
                AnomalyCorrelationRule.rule_code.asc(),
                AnomalyCorrelationRule.effective_from.desc(),
                AnomalyCorrelationRule.created_at.desc(),
            )
        )
        return list(result.scalars().all())

    async def create_statistical_rule(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        rule_code: str,
        rule_name: str,
        rolling_window: int,
        baseline_type: str,
        z_threshold: str,
        regime_shift_threshold_pct: str,
        seasonal_period: int | None,
        seasonal_adjustment_flag: bool,
        benchmark_group_id: str | None,
        configuration_json: dict[str, Any],
        version_token: str,
        effective_from: date,
        supersedes_id: uuid.UUID | None,
        status: str,
        created_by: uuid.UUID,
    ) -> AnomalyStatisticalRule:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=AnomalyStatisticalRule,
            tenant_id=tenant_id,
            record_data={"rule_code": rule_code},
            values={
                "organisation_id": organisation_id,
                "rule_code": rule_code,
                "rule_name": rule_name,
                "rolling_window": rolling_window,
                "baseline_type": baseline_type,
                "z_threshold": z_threshold,
                "regime_shift_threshold_pct": regime_shift_threshold_pct,
                "seasonal_period": seasonal_period,
                "seasonal_adjustment_flag": seasonal_adjustment_flag,
                "benchmark_group_id": benchmark_group_id,
                "configuration_json": configuration_json,
                "version_token": version_token,
                "effective_from": effective_from,
                "supersedes_id": supersedes_id,
                "status": status,
                "created_by": created_by,
            },
            audit=AuditEvent(
                tenant_id=tenant_id,
                user_id=created_by,
                action="anomaly_pattern.statistical_rule.created",
                resource_type="anomaly_statistical_rule",
                resource_name=rule_code,
            ),
        )

    async def list_statistical_rules(self, *, tenant_id: uuid.UUID) -> list[AnomalyStatisticalRule]:
        result = await self._session.execute(
            select(AnomalyStatisticalRule)
            .where(AnomalyStatisticalRule.tenant_id == tenant_id)
            .order_by(
                AnomalyStatisticalRule.rule_code.asc(),
                AnomalyStatisticalRule.effective_from.desc(),
                AnomalyStatisticalRule.created_at.desc(),
            )
        )
        return list(result.scalars().all())

    async def active_anomaly_definitions(
        self, *, tenant_id: uuid.UUID, organisation_id: uuid.UUID, reporting_period: date
    ) -> list[AnomalyDefinition]:
        result = await self._session.execute(
            select(AnomalyDefinition)
            .where(
                AnomalyDefinition.tenant_id == tenant_id,
                AnomalyDefinition.organisation_id == organisation_id,
                AnomalyDefinition.status == "active",
                AnomalyDefinition.effective_from <= reporting_period,
                (AnomalyDefinition.effective_to.is_(None))
                | (AnomalyDefinition.effective_to >= reporting_period),
            )
            .order_by(AnomalyDefinition.anomaly_code.asc(), AnomalyDefinition.id.asc())
        )
        return list(result.scalars().all())

    async def active_pattern_rules(
        self, *, tenant_id: uuid.UUID, organisation_id: uuid.UUID, reporting_period: date
    ) -> list[AnomalyPatternRule]:
        result = await self._session.execute(
            select(AnomalyPatternRule)
            .where(
                AnomalyPatternRule.tenant_id == tenant_id,
                AnomalyPatternRule.organisation_id == organisation_id,
                AnomalyPatternRule.status == "active",
                AnomalyPatternRule.effective_from <= reporting_period,
            )
            .order_by(AnomalyPatternRule.rule_code.asc(), AnomalyPatternRule.id.asc())
        )
        return list(result.scalars().all())

    async def active_persistence_rules(
        self, *, tenant_id: uuid.UUID, organisation_id: uuid.UUID, reporting_period: date
    ) -> list[AnomalyPersistenceRule]:
        result = await self._session.execute(
            select(AnomalyPersistenceRule)
            .where(
                AnomalyPersistenceRule.tenant_id == tenant_id,
                AnomalyPersistenceRule.organisation_id == organisation_id,
                AnomalyPersistenceRule.status == "active",
                AnomalyPersistenceRule.effective_from <= reporting_period,
            )
            .order_by(AnomalyPersistenceRule.rule_code.asc(), AnomalyPersistenceRule.id.asc())
        )
        return list(result.scalars().all())

    async def active_correlation_rules(
        self, *, tenant_id: uuid.UUID, organisation_id: uuid.UUID, reporting_period: date
    ) -> list[AnomalyCorrelationRule]:
        result = await self._session.execute(
            select(AnomalyCorrelationRule)
            .where(
                AnomalyCorrelationRule.tenant_id == tenant_id,
                AnomalyCorrelationRule.organisation_id == organisation_id,
                AnomalyCorrelationRule.status == "active",
                AnomalyCorrelationRule.effective_from <= reporting_period,
            )
            .order_by(AnomalyCorrelationRule.rule_code.asc(), AnomalyCorrelationRule.id.asc())
        )
        return list(result.scalars().all())

    async def active_statistical_rules(
        self, *, tenant_id: uuid.UUID, organisation_id: uuid.UUID, reporting_period: date
    ) -> list[AnomalyStatisticalRule]:
        result = await self._session.execute(
            select(AnomalyStatisticalRule)
            .where(
                AnomalyStatisticalRule.tenant_id == tenant_id,
                AnomalyStatisticalRule.organisation_id == organisation_id,
                AnomalyStatisticalRule.status == "active",
                AnomalyStatisticalRule.effective_from <= reporting_period,
            )
            .order_by(AnomalyStatisticalRule.rule_code.asc(), AnomalyStatisticalRule.id.asc())
        )
        return list(result.scalars().all())

    async def get_metric_run(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> MetricRun | None:
        result = await self._session.execute(
            select(MetricRun).where(MetricRun.tenant_id == tenant_id, MetricRun.id == run_id)
        )
        return result.scalar_one_or_none()

    async def list_metric_runs(
        self, *, tenant_id: uuid.UUID, run_ids: list[uuid.UUID]
    ) -> list[MetricRun]:
        if not run_ids:
            return []
        result = await self._session.execute(
            select(MetricRun)
            .where(MetricRun.tenant_id == tenant_id, MetricRun.id.in_(run_ids))
            .order_by(MetricRun.id.asc())
        )
        return list(result.scalars().all())

    async def get_risk_run(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> RiskRun | None:
        result = await self._session.execute(
            select(RiskRun).where(RiskRun.tenant_id == tenant_id, RiskRun.id == run_id)
        )
        return result.scalar_one_or_none()

    async def list_risk_runs(self, *, tenant_id: uuid.UUID, run_ids: list[uuid.UUID]) -> list[RiskRun]:
        if not run_ids:
            return []
        result = await self._session.execute(
            select(RiskRun)
            .where(RiskRun.tenant_id == tenant_id, RiskRun.id.in_(run_ids))
            .order_by(RiskRun.id.asc())
        )
        return list(result.scalars().all())

    async def get_reconciliation_session(
        self, *, tenant_id: uuid.UUID, session_id: uuid.UUID
    ) -> ReconciliationSession | None:
        result = await self._session.execute(
            select(ReconciliationSession).where(
                ReconciliationSession.tenant_id == tenant_id,
                ReconciliationSession.id == session_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_reconciliation_sessions(
        self, *, tenant_id: uuid.UUID, session_ids: list[uuid.UUID]
    ) -> list[ReconciliationSession]:
        if not session_ids:
            return []
        result = await self._session.execute(
            select(ReconciliationSession)
            .where(
                ReconciliationSession.tenant_id == tenant_id,
                ReconciliationSession.id.in_(session_ids),
            )
            .order_by(ReconciliationSession.id.asc())
        )
        return list(result.scalars().all())

    async def list_metric_results_for_runs(
        self, *, tenant_id: uuid.UUID, run_ids: list[uuid.UUID]
    ) -> list[MetricResult]:
        if not run_ids:
            return []
        result = await self._session.execute(
            select(MetricResult)
            .where(MetricResult.tenant_id == tenant_id, MetricResult.run_id.in_(run_ids))
            .order_by(MetricResult.run_id.asc(), MetricResult.metric_code.asc(), MetricResult.id.asc())
        )
        return list(result.scalars().all())

    async def list_variance_results_for_runs(
        self, *, tenant_id: uuid.UUID, run_ids: list[uuid.UUID]
    ) -> list[VarianceResult]:
        if not run_ids:
            return []
        result = await self._session.execute(
            select(VarianceResult)
            .where(VarianceResult.tenant_id == tenant_id, VarianceResult.run_id.in_(run_ids))
            .order_by(
                VarianceResult.run_id.asc(),
                VarianceResult.metric_code.asc(),
                VarianceResult.comparison_type.asc(),
                VarianceResult.id.asc(),
            )
        )
        return list(result.scalars().all())

    async def list_trend_results_for_runs(
        self, *, tenant_id: uuid.UUID, run_ids: list[uuid.UUID]
    ) -> list[TrendResult]:
        if not run_ids:
            return []
        result = await self._session.execute(
            select(TrendResult)
            .where(TrendResult.tenant_id == tenant_id, TrendResult.run_id.in_(run_ids))
            .order_by(TrendResult.run_id.asc(), TrendResult.metric_code.asc(), TrendResult.id.asc())
        )
        return list(result.scalars().all())

    async def list_risk_results_for_runs(
        self, *, tenant_id: uuid.UUID, run_ids: list[uuid.UUID]
    ) -> list[RiskResult]:
        if not run_ids:
            return []
        result = await self._session.execute(
            select(RiskResult)
            .where(RiskResult.tenant_id == tenant_id, RiskResult.run_id.in_(run_ids))
            .order_by(RiskResult.run_id.asc(), RiskResult.risk_code.asc(), RiskResult.id.asc())
        )
        return list(result.scalars().all())

    async def list_reconciliation_exceptions_for_sessions(
        self, *, tenant_id: uuid.UUID, session_ids: list[uuid.UUID]
    ) -> list[ReconciliationException]:
        if not session_ids:
            return []
        result = await self._session.execute(
            select(ReconciliationException)
            .where(
                ReconciliationException.tenant_id == tenant_id,
                ReconciliationException.session_id.in_(session_ids),
            )
            .order_by(ReconciliationException.session_id.asc(), ReconciliationException.id.asc())
        )
        return list(result.scalars().all())

    async def get_anomaly_run_by_token(self, *, tenant_id: uuid.UUID, run_token: str) -> AnomalyRun | None:
        result = await self._session.execute(
            select(AnomalyRun).where(AnomalyRun.tenant_id == tenant_id, AnomalyRun.run_token == run_token)
        )
        return result.scalar_one_or_none()

    async def create_anomaly_run(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        reporting_period: date,
        anomaly_definition_version_token: str,
        pattern_rule_version_token: str,
        persistence_rule_version_token: str,
        correlation_rule_version_token: str,
        statistical_rule_version_token: str,
        source_metric_run_ids_json: list[str],
        source_variance_run_ids_json: list[str],
        source_trend_run_ids_json: list[str],
        source_risk_run_ids_json: list[str],
        source_reconciliation_session_ids_json: list[str],
        run_token: str,
        status: str,
        validation_summary_json: dict[str, Any],
        created_by: uuid.UUID,
    ) -> AnomalyRun:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=AnomalyRun,
            tenant_id=tenant_id,
            record_data={"run_token": run_token, "status": status},
            values={
                "organisation_id": organisation_id,
                "reporting_period": reporting_period,
                "anomaly_definition_version_token": anomaly_definition_version_token,
                "pattern_rule_version_token": pattern_rule_version_token,
                "persistence_rule_version_token": persistence_rule_version_token,
                "correlation_rule_version_token": correlation_rule_version_token,
                "statistical_rule_version_token": statistical_rule_version_token,
                "source_metric_run_ids_json": source_metric_run_ids_json,
                "source_variance_run_ids_json": source_variance_run_ids_json,
                "source_trend_run_ids_json": source_trend_run_ids_json,
                "source_risk_run_ids_json": source_risk_run_ids_json,
                "source_reconciliation_session_ids_json": source_reconciliation_session_ids_json,
                "run_token": run_token,
                "status": status,
                "validation_summary_json": validation_summary_json,
                "created_by": created_by,
            },
            audit=AuditEvent(
                tenant_id=tenant_id,
                user_id=created_by,
                action="anomaly_pattern.run.created",
                resource_type="anomaly_run",
                resource_name=run_token,
            ),
        )

    async def get_anomaly_run(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> AnomalyRun | None:
        result = await self._session.execute(
            select(AnomalyRun).where(AnomalyRun.tenant_id == tenant_id, AnomalyRun.id == run_id)
        )
        return result.scalar_one_or_none()

    async def insert_anomaly_results(
        self,
        *,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
        rows: Iterable[ComputedAnomaly],
        created_by: uuid.UUID,
    ) -> list[AnomalyResult]:
        inserted: list[AnomalyResult] = []
        for line_no, row in enumerate(rows, start=1):
            inserted.append(
                await AuditWriter.insert_financial_record(
                    self._session,
                    model_class=AnomalyResult,
                    tenant_id=tenant_id,
                    record_data={"run_id": str(run_id), "anomaly_code": row.anomaly_code},
                    values={
                        "run_id": run_id,
                        "line_no": line_no,
                        "anomaly_code": row.anomaly_code,
                        "anomaly_name": row.anomaly_name,
                        "anomaly_domain": row.anomaly_domain,
                        "anomaly_score": row.anomaly_score,
                        "z_score": row.z_score,
                        "severity": row.severity.value,
                        "persistence_classification": row.persistence_classification.value,
                        "correlation_flag": row.correlation_flag,
                        "materiality_elevated": row.materiality_elevated,
                        "risk_elevated": row.risk_elevated,
                        "board_flag": row.board_flag,
                        "confidence_score": row.confidence_score,
                        "seasonal_adjustment_flag": row.seasonal_adjustment_flag,
                        "seasonal_normalized_value": row.seasonal_normalized_value,
                        "benchmark_group_id": row.benchmark_group_id,
                        "benchmark_baseline_value": row.benchmark_baseline_value,
                        "benchmark_deviation_score": row.benchmark_deviation_score,
                        "source_summary_json": row.source_summary_json,
                        "created_by": created_by,
                    },
                    audit=AuditEvent(
                        tenant_id=tenant_id,
                        user_id=created_by,
                        action="anomaly_pattern.result.created",
                        resource_type="anomaly_result",
                        resource_name=row.anomaly_code,
                    ),
                )
            )
        return inserted

    async def insert_anomaly_signals(
        self,
        *,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
        anomaly_result_id: uuid.UUID,
        rows: Iterable[AnomalySignal],
        created_by: uuid.UUID,
    ) -> list[AnomalyContributingSignal]:
        inserted: list[AnomalyContributingSignal] = []
        for row in rows:
            inserted.append(
                await AuditWriter.insert_financial_record(
                    self._session,
                    model_class=AnomalyContributingSignal,
                    tenant_id=tenant_id,
                    record_data={
                        "run_id": str(run_id),
                        "anomaly_result_id": str(anomaly_result_id),
                        "signal_type": row.signal_type,
                    },
                    values={
                        "run_id": run_id,
                        "anomaly_result_id": anomaly_result_id,
                        "signal_type": row.signal_type,
                        "signal_ref": row.signal_ref,
                        "contribution_weight": row.contribution_weight,
                        "contribution_score": row.contribution_score,
                        "signal_payload_json": row.signal_payload_json,
                        "created_by": created_by,
                    },
                    audit=AuditEvent(
                        tenant_id=tenant_id,
                        user_id=created_by,
                        action="anomaly_pattern.signal.created",
                        resource_type="anomaly_contributing_signal",
                        resource_name=row.signal_type,
                    ),
                )
            )
        return inserted

    async def insert_rollforward_events(
        self,
        *,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
        anomaly_result_id: uuid.UUID,
        rows: Iterable[AnomalyRollforward],
        actor_user_id: uuid.UUID,
        created_by: uuid.UUID,
    ) -> list[AnomalyRollforwardEvent]:
        inserted: list[AnomalyRollforwardEvent] = []
        for row in rows:
            inserted.append(
                await AuditWriter.insert_financial_record(
                    self._session,
                    model_class=AnomalyRollforwardEvent,
                    tenant_id=tenant_id,
                    record_data={
                        "run_id": str(run_id),
                        "anomaly_result_id": str(anomaly_result_id),
                        "event_type": row.event_type,
                    },
                    values={
                        "run_id": run_id,
                        "anomaly_result_id": anomaly_result_id,
                        "event_type": row.event_type,
                        "event_payload_json": row.event_payload_json,
                        "actor_user_id": actor_user_id,
                        "created_by": created_by,
                    },
                    audit=AuditEvent(
                        tenant_id=tenant_id,
                        user_id=created_by,
                        action="anomaly_pattern.rollforward.created",
                        resource_type="anomaly_rollforward_event",
                        resource_name=row.event_type,
                    ),
                )
            )
        return inserted

    async def insert_evidence_links(
        self,
        *,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
        anomaly_result_id: uuid.UUID,
        rows: Iterable[dict[str, Any]],
        created_by: uuid.UUID,
    ) -> list[AnomalyEvidenceLink]:
        inserted: list[AnomalyEvidenceLink] = []
        for row in rows:
            inserted.append(
                await AuditWriter.insert_financial_record(
                    self._session,
                    model_class=AnomalyEvidenceLink,
                    tenant_id=tenant_id,
                    record_data={
                        "run_id": str(run_id),
                        "anomaly_result_id": str(anomaly_result_id),
                        "evidence_type": row["evidence_type"],
                    },
                    values={
                        "run_id": run_id,
                        "anomaly_result_id": anomaly_result_id,
                        "evidence_type": row["evidence_type"],
                        "evidence_ref": row["evidence_ref"],
                        "evidence_label": row["evidence_label"],
                        "created_by": created_by,
                    },
                    audit=AuditEvent(
                        tenant_id=tenant_id,
                        user_id=created_by,
                        action="anomaly_pattern.evidence.created",
                        resource_type="anomaly_evidence_link",
                        resource_name=row["evidence_type"],
                    ),
                )
            )
        return inserted

    async def list_anomaly_results(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> list[AnomalyResult]:
        result = await self._session.execute(
            select(AnomalyResult)
            .where(AnomalyResult.tenant_id == tenant_id, AnomalyResult.run_id == run_id)
            .order_by(AnomalyResult.line_no.asc(), AnomalyResult.id.asc())
        )
        return list(result.scalars().all())

    async def list_anomaly_signals(
        self, *, tenant_id: uuid.UUID, run_id: uuid.UUID
    ) -> list[AnomalyContributingSignal]:
        result = await self._session.execute(
            select(AnomalyContributingSignal)
            .where(
                AnomalyContributingSignal.tenant_id == tenant_id,
                AnomalyContributingSignal.run_id == run_id,
            )
            .order_by(
                AnomalyContributingSignal.anomaly_result_id.asc(),
                AnomalyContributingSignal.id.asc(),
            )
        )
        return list(result.scalars().all())

    async def list_rollforward_events(
        self, *, tenant_id: uuid.UUID, run_id: uuid.UUID
    ) -> list[AnomalyRollforwardEvent]:
        result = await self._session.execute(
            select(AnomalyRollforwardEvent)
            .where(
                AnomalyRollforwardEvent.tenant_id == tenant_id,
                AnomalyRollforwardEvent.run_id == run_id,
            )
            .order_by(AnomalyRollforwardEvent.created_at.asc(), AnomalyRollforwardEvent.id.asc())
        )
        return list(result.scalars().all())

    async def list_evidence_links(
        self, *, tenant_id: uuid.UUID, run_id: uuid.UUID
    ) -> list[AnomalyEvidenceLink]:
        result = await self._session.execute(
            select(AnomalyEvidenceLink)
            .where(AnomalyEvidenceLink.tenant_id == tenant_id, AnomalyEvidenceLink.run_id == run_id)
            .order_by(AnomalyEvidenceLink.created_at.asc(), AnomalyEvidenceLink.id.asc())
        )
        return list(result.scalars().all())

    async def latest_prior_anomaly_result(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        anomaly_code: str,
        before_reporting_period: date,
    ) -> AnomalyResult | None:
        result = await self._session.execute(
            select(AnomalyResult)
            .join(AnomalyRun, AnomalyRun.id == AnomalyResult.run_id)
            .where(
                AnomalyResult.tenant_id == tenant_id,
                AnomalyResult.anomaly_code == anomaly_code,
                AnomalyRun.tenant_id == tenant_id,
                AnomalyRun.organisation_id == organisation_id,
                AnomalyRun.status == "completed",
                AnomalyRun.reporting_period < before_reporting_period,
            )
            .order_by(AnomalyRun.reporting_period.desc(), AnomalyRun.id.desc(), AnomalyResult.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def latest_prior_anomaly_results_by_codes(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        anomaly_codes: list[str],
        before_reporting_period: date,
    ) -> dict[str, AnomalyResult]:
        if not anomaly_codes:
            return {}
        result = await self._session.execute(
            select(AnomalyResult, AnomalyRun.reporting_period)
            .join(AnomalyRun, AnomalyRun.id == AnomalyResult.run_id)
            .where(
                AnomalyResult.tenant_id == tenant_id,
                AnomalyResult.anomaly_code.in_(anomaly_codes),
                AnomalyRun.tenant_id == tenant_id,
                AnomalyRun.organisation_id == organisation_id,
                AnomalyRun.status == "completed",
                AnomalyRun.reporting_period < before_reporting_period,
            )
            .order_by(
                AnomalyResult.anomaly_code.asc(),
                AnomalyRun.reporting_period.desc(),
                AnomalyRun.id.desc(),
                AnomalyResult.id.desc(),
            )
        )
        grouped: dict[str, AnomalyResult] = {}
        for row, _reporting_period in result.all():
            grouped.setdefault(row.anomaly_code, row)
        return grouped

    async def summarize_run(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> dict[str, int]:
        row = (
            await self._session.execute(
                select(
                    select(func.count())
                    .select_from(AnomalyResult)
                    .where(AnomalyResult.tenant_id == tenant_id, AnomalyResult.run_id == run_id)
                    .scalar_subquery()
                    .label("result_count"),
                    select(func.count())
                    .select_from(AnomalyContributingSignal)
                    .where(
                        AnomalyContributingSignal.tenant_id == tenant_id,
                        AnomalyContributingSignal.run_id == run_id,
                    )
                    .scalar_subquery()
                    .label("signal_count"),
                    select(func.count())
                    .select_from(AnomalyRollforwardEvent)
                    .where(
                        AnomalyRollforwardEvent.tenant_id == tenant_id,
                        AnomalyRollforwardEvent.run_id == run_id,
                    )
                    .scalar_subquery()
                    .label("rollforward_count"),
                    select(func.count())
                    .select_from(AnomalyEvidenceLink)
                    .where(
                        AnomalyEvidenceLink.tenant_id == tenant_id,
                        AnomalyEvidenceLink.run_id == run_id,
                    )
                    .scalar_subquery()
                    .label("evidence_count"),
                )
            )
        ).one()
        return {
            "result_count": int(row.result_count or 0),
            "signal_count": int(row.signal_count or 0),
            "rollforward_count": int(row.rollforward_count or 0),
            "evidence_count": int(row.evidence_count or 0),
        }
