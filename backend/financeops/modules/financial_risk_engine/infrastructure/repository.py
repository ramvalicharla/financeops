from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.financial_risk_engine import (
    RiskContributingSignal,
    RiskDefinition,
    RiskDefinitionDependency,
    RiskEvidenceLink,
    RiskMaterialityRule,
    RiskResult,
    RiskRollforwardEvent,
    RiskRun,
    RiskWeightConfiguration,
)
from financeops.db.models.ratio_variance_engine import (
    MetricResult,
    MetricRun,
    TrendResult,
    VarianceResult,
)
from financeops.db.models.reconciliation_bridge import (
    ReconciliationException,
    ReconciliationSession,
)
from financeops.modules.financial_risk_engine.domain.entities import (
    ComputedRisk,
    RiskRollforward,
    RiskSignal,
)
from financeops.services.audit_writer import AuditEvent, AuditWriter


class FinancialRiskRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_risk_definition(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        risk_code: str,
        risk_name: str,
        risk_domain: str,
        signal_selector_json: dict[str, Any],
        definition_json: dict[str, Any],
        version_token: str,
        effective_from: date,
        effective_to: date | None,
        supersedes_id: uuid.UUID | None,
        status: str,
        dependencies: list[dict[str, Any]],
        created_by: uuid.UUID,
    ) -> RiskDefinition:
        definition = await AuditWriter.insert_financial_record(
            self._session,
            model_class=RiskDefinition,
            tenant_id=tenant_id,
            record_data={"risk_code": risk_code, "risk_domain": risk_domain},
            values={
                "organisation_id": organisation_id,
                "risk_code": risk_code,
                "risk_name": risk_name,
                "risk_domain": risk_domain,
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
                action="financial_risk.definition.created",
                resource_type="risk_definition",
                resource_name=risk_code,
            ),
        )
        for dependency in dependencies:
            await AuditWriter.insert_financial_record(
                self._session,
                model_class=RiskDefinitionDependency,
                tenant_id=tenant_id,
                record_data={
                    "risk_definition_id": str(definition.id),
                    "dependency_type": dependency["dependency_type"],
                    "signal_reference_code": dependency.get("signal_reference_code", ""),
                },
                values={
                    "risk_definition_id": definition.id,
                    "dependency_type": dependency["dependency_type"],
                    "depends_on_risk_definition_id": dependency.get(
                        "depends_on_risk_definition_id"
                    ),
                    "signal_reference_code": dependency.get("signal_reference_code"),
                    "propagation_factor": dependency.get("propagation_factor", Decimal("1")),
                    "amplification_rule_json": dependency.get(
                        "amplification_rule_json", {}
                    ),
                    "attenuation_rule_json": dependency.get("attenuation_rule_json", {}),
                    "cap_limit": dependency.get("cap_limit", Decimal("1")),
                    "created_by": created_by,
                },
                audit=AuditEvent(
                    tenant_id=tenant_id,
                    user_id=created_by,
                    action="financial_risk.definition_dependency.created",
                    resource_type="risk_definition_dependency",
                    resource_name=dependency["dependency_type"],
                ),
            )
        return definition

    async def list_risk_definitions(
        self, *, tenant_id: uuid.UUID, organisation_id: uuid.UUID | None = None
    ) -> list[RiskDefinition]:
        stmt = select(RiskDefinition).where(RiskDefinition.tenant_id == tenant_id)
        if organisation_id is not None:
            stmt = stmt.where(RiskDefinition.organisation_id == organisation_id)
        result = await self._session.execute(
            stmt.order_by(
                RiskDefinition.risk_code.asc(),
                RiskDefinition.effective_from.desc(),
                RiskDefinition.created_at.desc(),
            )
        )
        return list(result.scalars().all())

    async def get_risk_definition(
        self, *, tenant_id: uuid.UUID, definition_id: uuid.UUID
    ) -> RiskDefinition | None:
        result = await self._session.execute(
            select(RiskDefinition).where(
                RiskDefinition.tenant_id == tenant_id,
                RiskDefinition.id == definition_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_risk_definition_versions(
        self, *, tenant_id: uuid.UUID, definition_id: uuid.UUID
    ) -> list[RiskDefinition]:
        current = await self.get_risk_definition(
            tenant_id=tenant_id,
            definition_id=definition_id,
        )
        if current is None:
            return []
        result = await self._session.execute(
            select(RiskDefinition)
            .where(
                RiskDefinition.tenant_id == tenant_id,
                RiskDefinition.organisation_id == current.organisation_id,
                RiskDefinition.risk_code == current.risk_code,
            )
            .order_by(
                RiskDefinition.effective_from.desc(),
                RiskDefinition.created_at.desc(),
                RiskDefinition.id.desc(),
            )
        )
        return list(result.scalars().all())

    async def list_dependencies(
        self, *, tenant_id: uuid.UUID, definition_ids: list[uuid.UUID]
    ) -> list[RiskDefinitionDependency]:
        if not definition_ids:
            return []
        result = await self._session.execute(
            select(RiskDefinitionDependency)
            .where(
                RiskDefinitionDependency.tenant_id == tenant_id,
                RiskDefinitionDependency.risk_definition_id.in_(definition_ids),
            )
            .order_by(
                RiskDefinitionDependency.risk_definition_id.asc(),
                RiskDefinitionDependency.dependency_type.asc(),
                RiskDefinitionDependency.id.asc(),
            )
        )
        return list(result.scalars().all())

    async def create_weight_configuration(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        weight_code: str,
        risk_code: str,
        scope_type: str,
        scope_value: str | None,
        weight_value: Decimal,
        board_critical_override: bool,
        configuration_json: dict[str, Any],
        version_token: str,
        effective_from: date,
        supersedes_id: uuid.UUID | None,
        status: str,
        created_by: uuid.UUID,
    ) -> RiskWeightConfiguration:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=RiskWeightConfiguration,
            tenant_id=tenant_id,
            record_data={"weight_code": weight_code, "risk_code": risk_code},
            values={
                "organisation_id": organisation_id,
                "weight_code": weight_code,
                "risk_code": risk_code,
                "scope_type": scope_type,
                "scope_value": scope_value,
                "weight_value": weight_value,
                "board_critical_override": board_critical_override,
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
                action="financial_risk.weight.created",
                resource_type="risk_weight_configuration",
                resource_name=weight_code,
            ),
        )

    async def list_weight_configurations(
        self, *, tenant_id: uuid.UUID, organisation_id: uuid.UUID | None = None
    ) -> list[RiskWeightConfiguration]:
        stmt = select(RiskWeightConfiguration).where(
            RiskWeightConfiguration.tenant_id == tenant_id
        )
        if organisation_id is not None:
            stmt = stmt.where(RiskWeightConfiguration.organisation_id == organisation_id)
        result = await self._session.execute(
            stmt.order_by(
                RiskWeightConfiguration.weight_code.asc(),
                RiskWeightConfiguration.effective_from.desc(),
                RiskWeightConfiguration.created_at.desc(),
            )
        )
        return list(result.scalars().all())

    async def get_weight_configuration(
        self, *, tenant_id: uuid.UUID, weight_id: uuid.UUID
    ) -> RiskWeightConfiguration | None:
        result = await self._session.execute(
            select(RiskWeightConfiguration).where(
                RiskWeightConfiguration.tenant_id == tenant_id,
                RiskWeightConfiguration.id == weight_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_weight_versions(
        self, *, tenant_id: uuid.UUID, weight_id: uuid.UUID
    ) -> list[RiskWeightConfiguration]:
        current = await self.get_weight_configuration(tenant_id=tenant_id, weight_id=weight_id)
        if current is None:
            return []
        result = await self._session.execute(
            select(RiskWeightConfiguration)
            .where(
                RiskWeightConfiguration.tenant_id == tenant_id,
                RiskWeightConfiguration.organisation_id == current.organisation_id,
                RiskWeightConfiguration.weight_code == current.weight_code,
            )
            .order_by(
                RiskWeightConfiguration.effective_from.desc(),
                RiskWeightConfiguration.created_at.desc(),
                RiskWeightConfiguration.id.desc(),
            )
        )
        return list(result.scalars().all())

    async def create_materiality_rule(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        rule_code: str,
        rule_name: str,
        threshold_json: dict[str, Any],
        severity_mapping_json: dict[str, Any],
        propagation_behavior_json: dict[str, Any],
        escalation_rule_json: dict[str, Any],
        version_token: str,
        effective_from: date,
        supersedes_id: uuid.UUID | None,
        status: str,
        created_by: uuid.UUID,
    ) -> RiskMaterialityRule:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=RiskMaterialityRule,
            tenant_id=tenant_id,
            record_data={"rule_code": rule_code},
            values={
                "organisation_id": organisation_id,
                "rule_code": rule_code,
                "rule_name": rule_name,
                "threshold_json": threshold_json,
                "severity_mapping_json": severity_mapping_json,
                "propagation_behavior_json": propagation_behavior_json,
                "escalation_rule_json": escalation_rule_json,
                "version_token": version_token,
                "effective_from": effective_from,
                "supersedes_id": supersedes_id,
                "status": status,
                "created_by": created_by,
            },
            audit=AuditEvent(
                tenant_id=tenant_id,
                user_id=created_by,
                action="financial_risk.materiality.created",
                resource_type="risk_materiality_rule",
                resource_name=rule_code,
            ),
        )

    async def list_materiality_rules(
        self, *, tenant_id: uuid.UUID, organisation_id: uuid.UUID | None = None
    ) -> list[RiskMaterialityRule]:
        stmt = select(RiskMaterialityRule).where(RiskMaterialityRule.tenant_id == tenant_id)
        if organisation_id is not None:
            stmt = stmt.where(RiskMaterialityRule.organisation_id == organisation_id)
        result = await self._session.execute(
            stmt.order_by(
                RiskMaterialityRule.rule_code.asc(),
                RiskMaterialityRule.effective_from.desc(),
                RiskMaterialityRule.created_at.desc(),
            )
        )
        return list(result.scalars().all())

    async def get_materiality_rule(
        self, *, tenant_id: uuid.UUID, rule_id: uuid.UUID
    ) -> RiskMaterialityRule | None:
        result = await self._session.execute(
            select(RiskMaterialityRule).where(
                RiskMaterialityRule.tenant_id == tenant_id,
                RiskMaterialityRule.id == rule_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_materiality_rule_versions(
        self, *, tenant_id: uuid.UUID, rule_id: uuid.UUID
    ) -> list[RiskMaterialityRule]:
        current = await self.get_materiality_rule(tenant_id=tenant_id, rule_id=rule_id)
        if current is None:
            return []
        result = await self._session.execute(
            select(RiskMaterialityRule)
            .where(
                RiskMaterialityRule.tenant_id == tenant_id,
                RiskMaterialityRule.organisation_id == current.organisation_id,
                RiskMaterialityRule.rule_code == current.rule_code,
            )
            .order_by(
                RiskMaterialityRule.effective_from.desc(),
                RiskMaterialityRule.created_at.desc(),
                RiskMaterialityRule.id.desc(),
            )
        )
        return list(result.scalars().all())

    async def active_risk_definitions(
        self, *, tenant_id: uuid.UUID, organisation_id: uuid.UUID, reporting_period: date
    ) -> list[RiskDefinition]:
        result = await self._session.execute(
            select(RiskDefinition)
            .where(
                RiskDefinition.tenant_id == tenant_id,
                RiskDefinition.organisation_id == organisation_id,
                RiskDefinition.status == "active",
                RiskDefinition.effective_from <= reporting_period,
                (RiskDefinition.effective_to.is_(None))
                | (RiskDefinition.effective_to >= reporting_period),
            )
            .order_by(
                RiskDefinition.risk_code.asc(),
                RiskDefinition.effective_from.desc(),
                RiskDefinition.id.desc(),
            )
        )
        return list(result.scalars().all())

    async def active_weight_configurations(
        self, *, tenant_id: uuid.UUID, organisation_id: uuid.UUID, reporting_period: date
    ) -> list[RiskWeightConfiguration]:
        result = await self._session.execute(
            select(RiskWeightConfiguration)
            .where(
                RiskWeightConfiguration.tenant_id == tenant_id,
                RiskWeightConfiguration.organisation_id == organisation_id,
                RiskWeightConfiguration.status == "active",
                RiskWeightConfiguration.effective_from <= reporting_period,
            )
            .order_by(
                RiskWeightConfiguration.weight_code.asc(),
                RiskWeightConfiguration.effective_from.desc(),
                RiskWeightConfiguration.id.desc(),
            )
        )
        return list(result.scalars().all())

    async def active_materiality_rules(
        self, *, tenant_id: uuid.UUID, organisation_id: uuid.UUID, reporting_period: date
    ) -> list[RiskMaterialityRule]:
        result = await self._session.execute(
            select(RiskMaterialityRule)
            .where(
                RiskMaterialityRule.tenant_id == tenant_id,
                RiskMaterialityRule.organisation_id == organisation_id,
                RiskMaterialityRule.status == "active",
                RiskMaterialityRule.effective_from <= reporting_period,
            )
            .order_by(
                RiskMaterialityRule.rule_code.asc(),
                RiskMaterialityRule.effective_from.desc(),
                RiskMaterialityRule.id.desc(),
            )
        )
        return list(result.scalars().all())

    async def get_metric_run(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> MetricRun | None:
        result = await self._session.execute(
            select(MetricRun).where(MetricRun.tenant_id == tenant_id, MetricRun.id == run_id)
        )
        return result.scalar_one_or_none()

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

    async def list_metric_results_for_runs(
        self, *, tenant_id: uuid.UUID, run_ids: list[uuid.UUID]
    ) -> list[MetricResult]:
        if not run_ids:
            return []
        result = await self._session.execute(
            select(MetricResult)
            .where(
                MetricResult.tenant_id == tenant_id,
                MetricResult.run_id.in_(run_ids),
            )
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
            .where(
                VarianceResult.tenant_id == tenant_id,
                VarianceResult.run_id.in_(run_ids),
            )
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
            .where(
                TrendResult.tenant_id == tenant_id,
                TrendResult.run_id.in_(run_ids),
            )
            .order_by(
                TrendResult.run_id.asc(),
                TrendResult.metric_code.asc(),
                TrendResult.trend_type.asc(),
                TrendResult.id.asc(),
            )
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
            .order_by(
                ReconciliationException.session_id.asc(),
                ReconciliationException.severity.asc(),
                ReconciliationException.id.asc(),
            )
        )
        return list(result.scalars().all())

    async def get_risk_run_by_token(self, *, tenant_id: uuid.UUID, run_token: str) -> RiskRun | None:
        result = await self._session.execute(
            select(RiskRun).where(RiskRun.tenant_id == tenant_id, RiskRun.run_token == run_token)
        )
        return result.scalar_one_or_none()

    async def create_risk_run(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        reporting_period: date,
        risk_definition_version_token: str,
        propagation_version_token: str,
        weight_version_token: str,
        materiality_version_token: str,
        source_metric_run_ids_json: list[str],
        source_variance_run_ids_json: list[str],
        source_trend_run_ids_json: list[str],
        source_reconciliation_session_ids_json: list[str],
        run_token: str,
        status: str,
        validation_summary_json: dict[str, Any],
        created_by: uuid.UUID,
    ) -> RiskRun:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=RiskRun,
            tenant_id=tenant_id,
            record_data={"run_token": run_token, "status": status},
            values={
                "organisation_id": organisation_id,
                "reporting_period": reporting_period,
                "risk_definition_version_token": risk_definition_version_token,
                "propagation_version_token": propagation_version_token,
                "weight_version_token": weight_version_token,
                "materiality_version_token": materiality_version_token,
                "source_metric_run_ids_json": source_metric_run_ids_json,
                "source_variance_run_ids_json": source_variance_run_ids_json,
                "source_trend_run_ids_json": source_trend_run_ids_json,
                "source_reconciliation_session_ids_json": source_reconciliation_session_ids_json,
                "run_token": run_token,
                "status": status,
                "validation_summary_json": validation_summary_json,
                "created_by": created_by,
            },
            audit=AuditEvent(
                tenant_id=tenant_id,
                user_id=created_by,
                action="financial_risk.run.created",
                resource_type="risk_run",
                resource_name=run_token,
            ),
        )

    async def get_risk_run(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> RiskRun | None:
        result = await self._session.execute(
            select(RiskRun).where(RiskRun.tenant_id == tenant_id, RiskRun.id == run_id)
        )
        return result.scalar_one_or_none()

    async def insert_risk_results(
        self,
        *,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
        rows: Iterable[ComputedRisk],
        created_by: uuid.UUID,
    ) -> list[RiskResult]:
        inserted: list[RiskResult] = []
        for line_no, row in enumerate(rows, start=1):
            inserted.append(
                await AuditWriter.insert_financial_record(
                    self._session,
                    model_class=RiskResult,
                    tenant_id=tenant_id,
                    record_data={"run_id": str(run_id), "risk_code": row.risk_code},
                    values={
                        "run_id": run_id,
                        "line_no": line_no,
                        "risk_code": row.risk_code,
                        "risk_name": row.risk_name,
                        "risk_domain": row.risk_domain,
                        "risk_score": row.risk_score,
                        "severity": row.severity.value,
                        "confidence_score": row.confidence_score,
                        "materiality_flag": row.materiality_flag,
                        "board_attention_flag": row.board_attention_flag,
                        "persistence_state": row.persistence_state.value,
                        "unresolved_dependency_flag": row.unresolved_dependency_flag,
                        "source_summary_json": row.source_summary_json,
                        "created_by": created_by,
                    },
                    audit=AuditEvent(
                        tenant_id=tenant_id,
                        user_id=created_by,
                        action="financial_risk.result.created",
                        resource_type="risk_result",
                        resource_name=row.risk_code,
                    ),
                )
            )
        return inserted

    async def insert_risk_signals(
        self,
        *,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
        risk_result_id: uuid.UUID,
        rows: Iterable[RiskSignal],
        created_by: uuid.UUID,
    ) -> list[RiskContributingSignal]:
        inserted: list[RiskContributingSignal] = []
        for row in rows:
            inserted.append(
                await AuditWriter.insert_financial_record(
                    self._session,
                    model_class=RiskContributingSignal,
                    tenant_id=tenant_id,
                    record_data={
                        "run_id": str(run_id),
                        "risk_result_id": str(risk_result_id),
                        "signal_type": row.signal_type,
                    },
                    values={
                        "run_id": run_id,
                        "risk_result_id": risk_result_id,
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
                        action="financial_risk.signal.created",
                        resource_type="risk_contributing_signal",
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
        risk_result_id: uuid.UUID,
        rows: Iterable[RiskRollforward],
        actor_user_id: uuid.UUID,
        created_by: uuid.UUID,
    ) -> list[RiskRollforwardEvent]:
        inserted: list[RiskRollforwardEvent] = []
        for row in rows:
            inserted.append(
                await AuditWriter.insert_financial_record(
                    self._session,
                    model_class=RiskRollforwardEvent,
                    tenant_id=tenant_id,
                    record_data={
                        "run_id": str(run_id),
                        "risk_result_id": str(risk_result_id),
                        "event_type": row.event_type,
                    },
                    values={
                        "run_id": run_id,
                        "risk_result_id": risk_result_id,
                        "event_type": row.event_type,
                        "event_payload_json": row.event_payload_json,
                        "actor_user_id": actor_user_id,
                        "created_by": created_by,
                    },
                    audit=AuditEvent(
                        tenant_id=tenant_id,
                        user_id=created_by,
                        action="financial_risk.rollforward.created",
                        resource_type="risk_rollforward_event",
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
        risk_result_id: uuid.UUID,
        rows: Iterable[dict[str, Any]],
        created_by: uuid.UUID,
    ) -> list[RiskEvidenceLink]:
        inserted: list[RiskEvidenceLink] = []
        for row in rows:
            inserted.append(
                await AuditWriter.insert_financial_record(
                    self._session,
                    model_class=RiskEvidenceLink,
                    tenant_id=tenant_id,
                    record_data={
                        "run_id": str(run_id),
                        "risk_result_id": str(risk_result_id),
                        "evidence_type": row["evidence_type"],
                    },
                    values={
                        "run_id": run_id,
                        "risk_result_id": risk_result_id,
                        "evidence_type": row["evidence_type"],
                        "evidence_ref": row["evidence_ref"],
                        "evidence_label": row["evidence_label"],
                        "created_by": created_by,
                    },
                    audit=AuditEvent(
                        tenant_id=tenant_id,
                        user_id=created_by,
                        action="financial_risk.evidence.created",
                        resource_type="risk_evidence_link",
                        resource_name=row["evidence_type"],
                    ),
                )
            )
        return inserted

    async def list_risk_results(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> list[RiskResult]:
        result = await self._session.execute(
            select(RiskResult)
            .where(RiskResult.tenant_id == tenant_id, RiskResult.run_id == run_id)
            .order_by(RiskResult.line_no.asc(), RiskResult.id.asc())
        )
        return list(result.scalars().all())

    async def list_risk_signals(
        self, *, tenant_id: uuid.UUID, run_id: uuid.UUID
    ) -> list[RiskContributingSignal]:
        result = await self._session.execute(
            select(RiskContributingSignal)
            .where(
                RiskContributingSignal.tenant_id == tenant_id,
                RiskContributingSignal.run_id == run_id,
            )
            .order_by(
                RiskContributingSignal.risk_result_id.asc(),
                RiskContributingSignal.id.asc(),
            )
        )
        return list(result.scalars().all())

    async def list_rollforward_events(
        self, *, tenant_id: uuid.UUID, run_id: uuid.UUID
    ) -> list[RiskRollforwardEvent]:
        result = await self._session.execute(
            select(RiskRollforwardEvent)
            .where(
                RiskRollforwardEvent.tenant_id == tenant_id,
                RiskRollforwardEvent.run_id == run_id,
            )
            .order_by(
                RiskRollforwardEvent.created_at.asc(),
                RiskRollforwardEvent.id.asc(),
            )
        )
        return list(result.scalars().all())

    async def list_evidence_links(
        self, *, tenant_id: uuid.UUID, run_id: uuid.UUID
    ) -> list[RiskEvidenceLink]:
        result = await self._session.execute(
            select(RiskEvidenceLink)
            .where(RiskEvidenceLink.tenant_id == tenant_id, RiskEvidenceLink.run_id == run_id)
            .order_by(RiskEvidenceLink.created_at.asc(), RiskEvidenceLink.id.asc())
        )
        return list(result.scalars().all())

    async def latest_prior_risk_result(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        risk_code: str,
        before_reporting_period: date,
    ) -> RiskResult | None:
        result = await self._session.execute(
            select(RiskResult)
            .join(RiskRun, RiskRun.id == RiskResult.run_id)
            .where(
                RiskResult.tenant_id == tenant_id,
                RiskResult.risk_code == risk_code,
                RiskRun.tenant_id == tenant_id,
                RiskRun.organisation_id == organisation_id,
                RiskRun.status == "completed",
                RiskRun.reporting_period < before_reporting_period,
            )
            .order_by(RiskRun.reporting_period.desc(), RiskRun.id.desc(), RiskResult.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def summarize_run(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> dict[str, int]:
        result_count = (
            await self._session.execute(
                select(func.count())
                .select_from(RiskResult)
                .where(RiskResult.tenant_id == tenant_id, RiskResult.run_id == run_id)
            )
        ).scalar_one()
        signal_count = (
            await self._session.execute(
                select(func.count())
                .select_from(RiskContributingSignal)
                .where(
                    RiskContributingSignal.tenant_id == tenant_id,
                    RiskContributingSignal.run_id == run_id,
                )
            )
        ).scalar_one()
        rollforward_count = (
            await self._session.execute(
                select(func.count())
                .select_from(RiskRollforwardEvent)
                .where(
                    RiskRollforwardEvent.tenant_id == tenant_id,
                    RiskRollforwardEvent.run_id == run_id,
                )
            )
        ).scalar_one()
        evidence_count = (
            await self._session.execute(
                select(func.count())
                .select_from(RiskEvidenceLink)
                .where(RiskEvidenceLink.tenant_id == tenant_id, RiskEvidenceLink.run_id == run_id)
            )
        ).scalar_one()
        return {
            "result_count": int(result_count or 0),
            "signal_count": int(signal_count or 0),
            "rollforward_count": int(rollforward_count or 0),
            "evidence_count": int(evidence_count or 0),
        }
