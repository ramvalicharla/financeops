from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.mis_manager import MisDataSnapshot, MisNormalizedLine
from financeops.db.models.payroll_gl_normalization import (
    GlNormalizedLine,
    NormalizationRun,
    PayrollNormalizedLine,
)
from financeops.db.models.payroll_gl_reconciliation import PayrollGlReconciliationRun
from financeops.db.models.ratio_variance_engine import (
    MaterialityRule,
    MetricDefinition,
    MetricDefinitionComponent,
    MetricEvidenceLink,
    MetricResult,
    MetricRun,
    TrendDefinition,
    TrendResult,
    VarianceDefinition,
    VarianceResult,
)
from financeops.db.models.reconciliation_bridge import ReconciliationLine, ReconciliationSession
from financeops.modules.ratio_variance_engine.domain.entities import (
    ComputedMetric,
    ComputedTrend,
    ComputedVariance,
)
from financeops.services.audit_writer import AuditEvent, AuditWriter
from financeops.utils.determinism import canonical_json_dumps


class RatioVarianceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_metric_definition(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        definition_code: str,
        definition_name: str,
        metric_code: str,
        formula_type: str,
        formula_json: dict[str, Any],
        unit_type: str,
        directionality: str,
        version_token: str,
        effective_from: date,
        supersedes_id: uuid.UUID | None,
        status: str,
        components: list[dict[str, Any]],
        created_by: uuid.UUID,
    ) -> MetricDefinition:
        definition = await AuditWriter.insert_financial_record(
            self._session,
            model_class=MetricDefinition,
            tenant_id=tenant_id,
            record_data={"definition_code": definition_code, "metric_code": metric_code},
            values={
                "organisation_id": organisation_id,
                "definition_code": definition_code,
                "definition_name": definition_name,
                "metric_code": metric_code,
                "formula_type": formula_type,
                "formula_json": formula_json,
                "unit_type": unit_type,
                "directionality": directionality,
                "version_token": version_token,
                "effective_from": effective_from,
                "supersedes_id": supersedes_id,
                "status": status,
                "created_by": created_by,
            },
            audit=AuditEvent(
                tenant_id=tenant_id,
                user_id=created_by,
                action="ratio_variance.metric_definition.created",
                resource_type="metric_definition",
                resource_name=definition_code,
            ),
        )
        for component in components:
            await AuditWriter.insert_financial_record(
                self._session,
                model_class=MetricDefinitionComponent,
                tenant_id=tenant_id,
                record_data={
                    "metric_definition_id": str(definition.id),
                    "component_code": component["component_code"],
                },
                values={
                    "metric_definition_id": definition.id,
                    "component_code": component["component_code"],
                    "source_type": component["source_type"],
                    "source_key": component["source_key"],
                    "operator": component.get("operator", "add"),
                    "weight": component.get("weight", Decimal("1")),
                    "ordinal_position": component["ordinal_position"],
                    "metadata_json": component.get("metadata_json", {}),
                    "created_by": created_by,
                },
                audit=AuditEvent(
                    tenant_id=tenant_id,
                    user_id=created_by,
                    action="ratio_variance.metric_definition_component.created",
                    resource_type="metric_definition_component",
                    resource_name=component["component_code"],
                ),
            )
        return definition

    async def list_metric_definitions(
        self, *, tenant_id: uuid.UUID, organisation_id: uuid.UUID | None = None
    ) -> list[MetricDefinition]:
        stmt = select(MetricDefinition).where(MetricDefinition.tenant_id == tenant_id)
        if organisation_id is not None:
            stmt = stmt.where(MetricDefinition.organisation_id == organisation_id)
        result = await self._session.execute(
            stmt.order_by(
                MetricDefinition.definition_code.asc(),
                MetricDefinition.effective_from.desc(),
                MetricDefinition.created_at.desc(),
            )
        )
        return list(result.scalars().all())

    async def get_metric_definition(
        self, *, tenant_id: uuid.UUID, definition_id: uuid.UUID
    ) -> MetricDefinition | None:
        result = await self._session.execute(
            select(MetricDefinition).where(
                MetricDefinition.tenant_id == tenant_id, MetricDefinition.id == definition_id
            )
        )
        return result.scalar_one_or_none()

    async def list_metric_definition_versions(
        self, *, tenant_id: uuid.UUID, definition_id: uuid.UUID
    ) -> list[MetricDefinition]:
        current = await self.get_metric_definition(
            tenant_id=tenant_id, definition_id=definition_id
        )
        if current is None:
            return []
        result = await self._session.execute(
            select(MetricDefinition)
            .where(
                MetricDefinition.tenant_id == tenant_id,
                MetricDefinition.organisation_id == current.organisation_id,
                MetricDefinition.definition_code == current.definition_code,
            )
            .order_by(
                MetricDefinition.effective_from.desc(),
                MetricDefinition.created_at.desc(),
                MetricDefinition.id.desc(),
            )
        )
        return list(result.scalars().all())

    async def list_metric_definition_components(
        self, *, tenant_id: uuid.UUID, definition_id: uuid.UUID
    ) -> list[MetricDefinitionComponent]:
        result = await self._session.execute(
            select(MetricDefinitionComponent)
            .where(
                MetricDefinitionComponent.tenant_id == tenant_id,
                MetricDefinitionComponent.metric_definition_id == definition_id,
            )
            .order_by(
                MetricDefinitionComponent.ordinal_position.asc(),
                MetricDefinitionComponent.id.asc(),
            )
        )
        return list(result.scalars().all())

    async def active_metric_definitions(
        self, *, tenant_id: uuid.UUID, organisation_id: uuid.UUID, reporting_period: date
    ) -> list[MetricDefinition]:
        result = await self._session.execute(
            select(MetricDefinition)
            .where(
                MetricDefinition.tenant_id == tenant_id,
                MetricDefinition.organisation_id == organisation_id,
                MetricDefinition.status == "active",
                MetricDefinition.effective_from <= reporting_period,
            )
            .order_by(
                MetricDefinition.definition_code.asc(),
                MetricDefinition.effective_from.desc(),
                MetricDefinition.id.desc(),
            )
        )
        return list(result.scalars().all())

    async def create_variance_definition(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        definition_code: str,
        definition_name: str,
        metric_code: str,
        comparison_type: str,
        configuration_json: dict[str, Any],
        version_token: str,
        effective_from: date,
        supersedes_id: uuid.UUID | None,
        status: str,
        created_by: uuid.UUID,
    ) -> VarianceDefinition:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=VarianceDefinition,
            tenant_id=tenant_id,
            record_data={"definition_code": definition_code, "metric_code": metric_code},
            values={
                "organisation_id": organisation_id,
                "definition_code": definition_code,
                "definition_name": definition_name,
                "metric_code": metric_code,
                "comparison_type": comparison_type,
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
                action="ratio_variance.variance_definition.created",
                resource_type="variance_definition",
                resource_name=definition_code,
            ),
        )

    async def list_variance_definitions(
        self, *, tenant_id: uuid.UUID, organisation_id: uuid.UUID | None = None
    ) -> list[VarianceDefinition]:
        stmt = select(VarianceDefinition).where(VarianceDefinition.tenant_id == tenant_id)
        if organisation_id is not None:
            stmt = stmt.where(VarianceDefinition.organisation_id == organisation_id)
        result = await self._session.execute(
            stmt.order_by(
                VarianceDefinition.definition_code.asc(),
                VarianceDefinition.effective_from.desc(),
                VarianceDefinition.created_at.desc(),
            )
        )
        return list(result.scalars().all())

    async def get_variance_definition(
        self, *, tenant_id: uuid.UUID, definition_id: uuid.UUID
    ) -> VarianceDefinition | None:
        result = await self._session.execute(
            select(VarianceDefinition).where(
                VarianceDefinition.tenant_id == tenant_id,
                VarianceDefinition.id == definition_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_variance_definition_versions(
        self, *, tenant_id: uuid.UUID, definition_id: uuid.UUID
    ) -> list[VarianceDefinition]:
        current = await self.get_variance_definition(
            tenant_id=tenant_id, definition_id=definition_id
        )
        if current is None:
            return []
        result = await self._session.execute(
            select(VarianceDefinition)
            .where(
                VarianceDefinition.tenant_id == tenant_id,
                VarianceDefinition.organisation_id == current.organisation_id,
                VarianceDefinition.definition_code == current.definition_code,
            )
            .order_by(
                VarianceDefinition.effective_from.desc(),
                VarianceDefinition.created_at.desc(),
                VarianceDefinition.id.desc(),
            )
        )
        return list(result.scalars().all())

    async def active_variance_definitions(
        self, *, tenant_id: uuid.UUID, organisation_id: uuid.UUID, reporting_period: date
    ) -> list[VarianceDefinition]:
        result = await self._session.execute(
            select(VarianceDefinition)
            .where(
                VarianceDefinition.tenant_id == tenant_id,
                VarianceDefinition.organisation_id == organisation_id,
                VarianceDefinition.status == "active",
                VarianceDefinition.effective_from <= reporting_period,
            )
            .order_by(
                VarianceDefinition.definition_code.asc(),
                VarianceDefinition.effective_from.desc(),
                VarianceDefinition.id.desc(),
            )
        )
        return list(result.scalars().all())

    async def create_trend_definition(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        definition_code: str,
        definition_name: str,
        metric_code: str,
        trend_type: str,
        window_size: int,
        configuration_json: dict[str, Any],
        version_token: str,
        effective_from: date,
        supersedes_id: uuid.UUID | None,
        status: str,
        created_by: uuid.UUID,
    ) -> TrendDefinition:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=TrendDefinition,
            tenant_id=tenant_id,
            record_data={"definition_code": definition_code, "metric_code": metric_code},
            values={
                "organisation_id": organisation_id,
                "definition_code": definition_code,
                "definition_name": definition_name,
                "metric_code": metric_code,
                "trend_type": trend_type,
                "window_size": window_size,
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
                action="ratio_variance.trend_definition.created",
                resource_type="trend_definition",
                resource_name=definition_code,
            ),
        )

    async def list_trend_definitions(
        self, *, tenant_id: uuid.UUID, organisation_id: uuid.UUID | None = None
    ) -> list[TrendDefinition]:
        stmt = select(TrendDefinition).where(TrendDefinition.tenant_id == tenant_id)
        if organisation_id is not None:
            stmt = stmt.where(TrendDefinition.organisation_id == organisation_id)
        result = await self._session.execute(
            stmt.order_by(
                TrendDefinition.definition_code.asc(),
                TrendDefinition.effective_from.desc(),
                TrendDefinition.created_at.desc(),
            )
        )
        return list(result.scalars().all())

    async def get_trend_definition(
        self, *, tenant_id: uuid.UUID, definition_id: uuid.UUID
    ) -> TrendDefinition | None:
        result = await self._session.execute(
            select(TrendDefinition).where(
                TrendDefinition.tenant_id == tenant_id, TrendDefinition.id == definition_id
            )
        )
        return result.scalar_one_or_none()

    async def list_trend_definition_versions(
        self, *, tenant_id: uuid.UUID, definition_id: uuid.UUID
    ) -> list[TrendDefinition]:
        current = await self.get_trend_definition(
            tenant_id=tenant_id, definition_id=definition_id
        )
        if current is None:
            return []
        result = await self._session.execute(
            select(TrendDefinition)
            .where(
                TrendDefinition.tenant_id == tenant_id,
                TrendDefinition.organisation_id == current.organisation_id,
                TrendDefinition.definition_code == current.definition_code,
            )
            .order_by(
                TrendDefinition.effective_from.desc(),
                TrendDefinition.created_at.desc(),
                TrendDefinition.id.desc(),
            )
        )
        return list(result.scalars().all())

    async def active_trend_definitions(
        self, *, tenant_id: uuid.UUID, organisation_id: uuid.UUID, reporting_period: date
    ) -> list[TrendDefinition]:
        result = await self._session.execute(
            select(TrendDefinition)
            .where(
                TrendDefinition.tenant_id == tenant_id,
                TrendDefinition.organisation_id == organisation_id,
                TrendDefinition.status == "active",
                TrendDefinition.effective_from <= reporting_period,
            )
            .order_by(
                TrendDefinition.definition_code.asc(),
                TrendDefinition.effective_from.desc(),
                TrendDefinition.id.desc(),
            )
        )
        return list(result.scalars().all())

    async def create_materiality_rule(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        definition_code: str,
        definition_name: str,
        rule_json: dict[str, Any],
        version_token: str,
        effective_from: date,
        supersedes_id: uuid.UUID | None,
        status: str,
        created_by: uuid.UUID,
    ) -> MaterialityRule:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=MaterialityRule,
            tenant_id=tenant_id,
            record_data={"definition_code": definition_code},
            values={
                "organisation_id": organisation_id,
                "definition_code": definition_code,
                "definition_name": definition_name,
                "rule_json": rule_json,
                "version_token": version_token,
                "effective_from": effective_from,
                "supersedes_id": supersedes_id,
                "status": status,
                "created_by": created_by,
            },
            audit=AuditEvent(
                tenant_id=tenant_id,
                user_id=created_by,
                action="ratio_variance.materiality_rule.created",
                resource_type="materiality_rule",
                resource_name=definition_code,
            ),
        )

    async def list_materiality_rules(
        self, *, tenant_id: uuid.UUID, organisation_id: uuid.UUID | None = None
    ) -> list[MaterialityRule]:
        stmt = select(MaterialityRule).where(MaterialityRule.tenant_id == tenant_id)
        if organisation_id is not None:
            stmt = stmt.where(MaterialityRule.organisation_id == organisation_id)
        result = await self._session.execute(
            stmt.order_by(
                MaterialityRule.definition_code.asc(),
                MaterialityRule.effective_from.desc(),
                MaterialityRule.created_at.desc(),
            )
        )
        return list(result.scalars().all())

    async def get_materiality_rule(
        self, *, tenant_id: uuid.UUID, definition_id: uuid.UUID
    ) -> MaterialityRule | None:
        result = await self._session.execute(
            select(MaterialityRule).where(
                MaterialityRule.tenant_id == tenant_id, MaterialityRule.id == definition_id
            )
        )
        return result.scalar_one_or_none()

    async def list_materiality_rule_versions(
        self, *, tenant_id: uuid.UUID, definition_id: uuid.UUID
    ) -> list[MaterialityRule]:
        current = await self.get_materiality_rule(
            tenant_id=tenant_id, definition_id=definition_id
        )
        if current is None:
            return []
        result = await self._session.execute(
            select(MaterialityRule)
            .where(
                MaterialityRule.tenant_id == tenant_id,
                MaterialityRule.organisation_id == current.organisation_id,
                MaterialityRule.definition_code == current.definition_code,
            )
            .order_by(
                MaterialityRule.effective_from.desc(),
                MaterialityRule.created_at.desc(),
                MaterialityRule.id.desc(),
            )
        )
        return list(result.scalars().all())

    async def active_materiality_rules(
        self, *, tenant_id: uuid.UUID, organisation_id: uuid.UUID, reporting_period: date
    ) -> list[MaterialityRule]:
        result = await self._session.execute(
            select(MaterialityRule)
            .where(
                MaterialityRule.tenant_id == tenant_id,
                MaterialityRule.organisation_id == organisation_id,
                MaterialityRule.status == "active",
                MaterialityRule.effective_from <= reporting_period,
            )
            .order_by(
                MaterialityRule.definition_code.asc(),
                MaterialityRule.effective_from.desc(),
                MaterialityRule.id.desc(),
            )
        )
        return list(result.scalars().all())

    async def get_mis_snapshot(
        self, *, tenant_id: uuid.UUID, snapshot_id: uuid.UUID
    ) -> MisDataSnapshot | None:
        result = await self._session.execute(
            select(MisDataSnapshot).where(
                MisDataSnapshot.tenant_id == tenant_id, MisDataSnapshot.id == snapshot_id
            )
        )
        return result.scalar_one_or_none()

    async def get_normalization_run(
        self, *, tenant_id: uuid.UUID, run_id: uuid.UUID
    ) -> NormalizationRun | None:
        result = await self._session.execute(
            select(NormalizationRun).where(
                NormalizationRun.tenant_id == tenant_id, NormalizationRun.id == run_id
            )
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

    async def get_payroll_gl_reconciliation_run(
        self, *, tenant_id: uuid.UUID, run_id: uuid.UUID
    ) -> PayrollGlReconciliationRun | None:
        result = await self._session.execute(
            select(PayrollGlReconciliationRun).where(
                PayrollGlReconciliationRun.tenant_id == tenant_id,
                PayrollGlReconciliationRun.id == run_id,
            )
        )
        return result.scalar_one_or_none()

    async def aggregate_source_values(
        self,
        *,
        tenant_id: uuid.UUID,
        mis_snapshot_id: uuid.UUID | None,
        payroll_run_id: uuid.UUID | None,
        gl_run_id: uuid.UUID | None,
        reconciliation_session_id: uuid.UUID | None,
    ) -> dict[str, dict[str, Decimal]]:
        mis_metrics: dict[str, Decimal] = defaultdict(Decimal)
        payroll_metrics: dict[str, Decimal] = defaultdict(Decimal)
        gl_accounts: dict[str, Decimal] = defaultdict(Decimal)
        recon_variances: dict[str, Decimal] = defaultdict(Decimal)

        if mis_snapshot_id is not None:
            rows = await self._session.execute(
                select(
                    MisNormalizedLine.canonical_metric_code,
                    func.coalesce(func.sum(MisNormalizedLine.period_value), 0),
                )
                .where(
                    MisNormalizedLine.tenant_id == tenant_id,
                    MisNormalizedLine.snapshot_id == mis_snapshot_id,
                )
                .group_by(MisNormalizedLine.canonical_metric_code)
            )
            for metric_code, value in rows.all():
                mis_metrics[str(metric_code)] = Decimal(str(value or 0))

        if payroll_run_id is not None:
            rows = await self._session.execute(
                select(
                    PayrollNormalizedLine.canonical_metric_code,
                    func.coalesce(func.sum(PayrollNormalizedLine.amount_value), 0),
                )
                .where(
                    PayrollNormalizedLine.tenant_id == tenant_id,
                    PayrollNormalizedLine.run_id == payroll_run_id,
                )
                .group_by(PayrollNormalizedLine.canonical_metric_code)
            )
            for metric_code, value in rows.all():
                payroll_metrics[str(metric_code)] = Decimal(str(value or 0))

        if gl_run_id is not None:
            rows = await self._session.execute(
                select(
                    GlNormalizedLine.account_code,
                    func.coalesce(func.sum(GlNormalizedLine.signed_amount), 0),
                )
                .where(
                    GlNormalizedLine.tenant_id == tenant_id,
                    GlNormalizedLine.run_id == gl_run_id,
                )
                .group_by(GlNormalizedLine.account_code)
            )
            for account_code, value in rows.all():
                gl_accounts[str(account_code)] = Decimal(str(value or 0))

        if reconciliation_session_id is not None:
            rows = await self._session.execute(
                select(
                    ReconciliationLine.difference_type,
                    func.coalesce(func.sum(ReconciliationLine.variance_value), 0),
                )
                .where(
                    ReconciliationLine.tenant_id == tenant_id,
                    ReconciliationLine.session_id == reconciliation_session_id,
                )
                .group_by(ReconciliationLine.difference_type)
            )
            for difference_type, value in rows.all():
                recon_variances[str(difference_type)] = Decimal(str(value or 0))

        return {
            "mis_metric": dict(mis_metrics),
            "payroll_metric": dict(payroll_metrics),
            "gl_account_prefix": dict(gl_accounts),
            "reconciliation": dict(recon_variances),
        }

    async def get_metric_run_by_token(
        self, *, tenant_id: uuid.UUID, run_token: str
    ) -> MetricRun | None:
        result = await self._session.execute(
            select(MetricRun).where(
                MetricRun.tenant_id == tenant_id, MetricRun.run_token == run_token
            )
        )
        return result.scalar_one_or_none()

    async def create_metric_run(
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
        run_token: str,
        status: str,
        created_by: uuid.UUID,
    ) -> MetricRun:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=MetricRun,
            tenant_id=tenant_id,
            record_data={"run_token": run_token, "status": status},
            values={
                "organisation_id": organisation_id,
                "reporting_period": reporting_period,
                "scope_json": scope_json,
                "mis_snapshot_id": mis_snapshot_id,
                "payroll_run_id": payroll_run_id,
                "gl_run_id": gl_run_id,
                "reconciliation_session_id": reconciliation_session_id,
                "payroll_gl_reconciliation_run_id": payroll_gl_reconciliation_run_id,
                "metric_definition_version_token": metric_definition_version_token,
                "variance_definition_version_token": variance_definition_version_token,
                "trend_definition_version_token": trend_definition_version_token,
                "materiality_rule_version_token": materiality_rule_version_token,
                "input_signature_hash": input_signature_hash,
                "run_token": run_token,
                "status": status,
                "created_by": created_by,
            },
            audit=AuditEvent(
                tenant_id=tenant_id,
                user_id=created_by,
                action="ratio_variance.run.created",
                resource_type="metric_run",
                resource_name=run_token,
            ),
        )

    async def get_metric_run(
        self, *, tenant_id: uuid.UUID, run_id: uuid.UUID
    ) -> MetricRun | None:
        result = await self._session.execute(
            select(MetricRun).where(MetricRun.tenant_id == tenant_id, MetricRun.id == run_id)
        )
        return result.scalar_one_or_none()

    async def insert_metric_results(
        self,
        *,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
        rows: Iterable[ComputedMetric],
        created_by: uuid.UUID,
    ) -> list[MetricResult]:
        inserted: list[MetricResult] = []
        for line_no, row in enumerate(rows, start=1):
            inserted.append(
                await AuditWriter.insert_financial_record(
                    self._session,
                    model_class=MetricResult,
                    tenant_id=tenant_id,
                    record_data={"run_id": str(run_id), "metric_code": row.metric_code},
                    values={
                        "run_id": run_id,
                        "line_no": line_no,
                        "metric_code": row.metric_code,
                        "unit_type": row.unit_type,
                        "dimension_json": row.dimension_json,
                        "metric_value": row.metric_value,
                        "favorable_status": row.favorable_status.value,
                        "materiality_flag": row.materiality_flag,
                        "source_summary_json": row.source_summary_json,
                        "created_by": created_by,
                    },
                    audit=AuditEvent(
                        tenant_id=tenant_id,
                        user_id=created_by,
                        action="ratio_variance.metric_result.created",
                        resource_type="metric_result",
                        resource_name=row.metric_code,
                    ),
                )
            )
        return inserted

    async def insert_variance_results(
        self,
        *,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
        rows: Iterable[ComputedVariance],
        created_by: uuid.UUID,
    ) -> list[VarianceResult]:
        inserted: list[VarianceResult] = []
        for line_no, row in enumerate(rows, start=1):
            inserted.append(
                await AuditWriter.insert_financial_record(
                    self._session,
                    model_class=VarianceResult,
                    tenant_id=tenant_id,
                    record_data={"run_id": str(run_id), "metric_code": row.metric_code},
                    values={
                        "run_id": run_id,
                        "line_no": line_no,
                        "metric_code": row.metric_code,
                        "comparison_type": row.comparison_type,
                        "base_period": row.base_period,
                        "current_value": row.current_value,
                        "baseline_value": row.baseline_value,
                        "variance_abs": row.variance_abs,
                        "variance_pct": row.variance_pct,
                        "variance_bps": row.variance_bps,
                        "days_change": row.days_change,
                        "favorable_status": row.favorable_status.value,
                        "materiality_flag": row.materiality_flag,
                        "explanation_hint": row.explanation_hint,
                        "created_by": created_by,
                    },
                    audit=AuditEvent(
                        tenant_id=tenant_id,
                        user_id=created_by,
                        action="ratio_variance.variance_result.created",
                        resource_type="variance_result",
                        resource_name=row.metric_code,
                    ),
                )
            )
        return inserted

    async def insert_trend_results(
        self,
        *,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
        rows: Iterable[ComputedTrend],
        created_by: uuid.UUID,
    ) -> list[TrendResult]:
        inserted: list[TrendResult] = []
        for line_no, row in enumerate(rows, start=1):
            inserted.append(
                await AuditWriter.insert_financial_record(
                    self._session,
                    model_class=TrendResult,
                    tenant_id=tenant_id,
                    record_data={"run_id": str(run_id), "metric_code": row.metric_code},
                    values={
                        "run_id": run_id,
                        "line_no": line_no,
                        "metric_code": row.metric_code,
                        "trend_type": row.trend_type,
                        "window_size": row.window_size,
                        "trend_value": row.trend_value,
                        "trend_direction": row.trend_direction,
                        "source_summary_json": row.source_summary_json,
                        "created_by": created_by,
                    },
                    audit=AuditEvent(
                        tenant_id=tenant_id,
                        user_id=created_by,
                        action="ratio_variance.trend_result.created",
                        resource_type="trend_result",
                        resource_name=row.metric_code,
                    ),
                )
            )
        return inserted

    async def insert_metric_evidence_links(
        self,
        *,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
        links: Iterable[dict[str, Any]],
        created_by: uuid.UUID,
    ) -> list[MetricEvidenceLink]:
        inserted: list[MetricEvidenceLink] = []
        for link in links:
            inserted.append(
                await AuditWriter.insert_financial_record(
                    self._session,
                    model_class=MetricEvidenceLink,
                    tenant_id=tenant_id,
                    record_data={
                        "run_id": str(run_id),
                        "result_type": link["result_type"],
                        "result_id": str(link["result_id"]),
                    },
                    values={
                        "run_id": run_id,
                        "result_type": link["result_type"],
                        "result_id": link["result_id"],
                        "evidence_type": link["evidence_type"],
                        "evidence_ref": link["evidence_ref"],
                        "evidence_label": link["evidence_label"],
                        "created_by": created_by,
                    },
                    audit=AuditEvent(
                        tenant_id=tenant_id,
                        user_id=created_by,
                        action="ratio_variance.evidence_link.created",
                        resource_type="metric_evidence_link",
                        resource_name=str(link["result_id"]),
                    ),
                )
            )
        return inserted

    async def list_metric_results(
        self, *, tenant_id: uuid.UUID, run_id: uuid.UUID
    ) -> list[MetricResult]:
        result = await self._session.execute(
            select(MetricResult)
            .where(MetricResult.tenant_id == tenant_id, MetricResult.run_id == run_id)
            .order_by(MetricResult.line_no.asc(), MetricResult.id.asc())
        )
        return list(result.scalars().all())

    async def list_variance_results(
        self, *, tenant_id: uuid.UUID, run_id: uuid.UUID
    ) -> list[VarianceResult]:
        result = await self._session.execute(
            select(VarianceResult)
            .where(VarianceResult.tenant_id == tenant_id, VarianceResult.run_id == run_id)
            .order_by(VarianceResult.line_no.asc(), VarianceResult.id.asc())
        )
        return list(result.scalars().all())

    async def list_trend_results(
        self, *, tenant_id: uuid.UUID, run_id: uuid.UUID
    ) -> list[TrendResult]:
        result = await self._session.execute(
            select(TrendResult)
            .where(TrendResult.tenant_id == tenant_id, TrendResult.run_id == run_id)
            .order_by(TrendResult.line_no.asc(), TrendResult.id.asc())
        )
        return list(result.scalars().all())

    async def list_metric_evidence(
        self, *, tenant_id: uuid.UUID, run_id: uuid.UUID
    ) -> list[MetricEvidenceLink]:
        result = await self._session.execute(
            select(MetricEvidenceLink)
            .where(
                MetricEvidenceLink.tenant_id == tenant_id,
                MetricEvidenceLink.run_id == run_id,
            )
            .order_by(MetricEvidenceLink.created_at.asc(), MetricEvidenceLink.id.asc())
        )
        return list(result.scalars().all())

    async def prior_metric_series(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        scope_json: dict[str, Any],
        metric_code: str,
        before_reporting_period: date,
        limit: int = 24,
    ) -> list[tuple[date, Decimal]]:
        result = await self._session.execute(
            select(MetricRun.reporting_period, MetricResult.metric_value)
            .join(MetricResult, MetricResult.run_id == MetricRun.id)
            .where(
                MetricRun.tenant_id == tenant_id,
                MetricRun.organisation_id == organisation_id,
                MetricRun.scope_json == scope_json,
                MetricRun.status == "completed",
                MetricRun.reporting_period < before_reporting_period,
                MetricResult.metric_code == metric_code,
                MetricResult.tenant_id == tenant_id,
            )
            .order_by(MetricRun.reporting_period.desc(), MetricRun.id.desc())
            .limit(limit)
        )
        return [(period, Decimal(str(value))) for period, value in result.all()]

    async def summarize_run(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> dict[str, int]:
        metric_count = (
            await self._session.execute(
                select(func.count())
                .select_from(MetricResult)
                .where(MetricResult.tenant_id == tenant_id, MetricResult.run_id == run_id)
            )
        ).scalar_one()
        variance_count = (
            await self._session.execute(
                select(func.count())
                .select_from(VarianceResult)
                .where(VarianceResult.tenant_id == tenant_id, VarianceResult.run_id == run_id)
            )
        ).scalar_one()
        trend_count = (
            await self._session.execute(
                select(func.count())
                .select_from(TrendResult)
                .where(TrendResult.tenant_id == tenant_id, TrendResult.run_id == run_id)
            )
        ).scalar_one()
        evidence_count = (
            await self._session.execute(
                select(func.count())
                .select_from(MetricEvidenceLink)
                .where(
                    MetricEvidenceLink.tenant_id == tenant_id,
                    MetricEvidenceLink.run_id == run_id,
                )
            )
        ).scalar_one()
        return {
            "metric_count": int(metric_count or 0),
            "variance_count": int(variance_count or 0),
            "trend_count": int(trend_count or 0),
            "evidence_count": int(evidence_count or 0),
        }

    @staticmethod
    def scope_key(scope_json: dict[str, Any]) -> str:
        return canonical_json_dumps(scope_json)
