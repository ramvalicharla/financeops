from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.multi_entity_consolidation import (
    ConsolidationAdjustmentDefinition,
    ConsolidationRuleDefinition,
    ConsolidationScope,
    EntityHierarchy,
    EntityHierarchyNode,
    IntercompanyMappingRule,
    MultiEntityConsolidationEvidenceLink,
    MultiEntityConsolidationMetricResult,
    MultiEntityConsolidationRun,
    MultiEntityConsolidationVarianceResult,
)
from financeops.db.models.ratio_variance_engine import MetricResult, MetricRun, VarianceResult
from financeops.services.audit_writer import AuditEvent, AuditWriter


class MultiEntityConsolidationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_entity_hierarchy(self, **values: Any) -> EntityHierarchy:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=EntityHierarchy,
            tenant_id=values["tenant_id"],
            record_data={"hierarchy_code": values["hierarchy_code"]},
            values=values,
            audit=AuditEvent(
                tenant_id=values["tenant_id"],
                user_id=values["created_by"],
                action="multi_entity_consolidation.hierarchy.created",
                resource_type="entity_hierarchy",
                resource_name=values["hierarchy_code"],
            ),
        )

    async def create_entity_hierarchy_nodes(
        self,
        *,
        tenant_id: uuid.UUID,
        created_by: uuid.UUID,
        rows: list[dict[str, Any]],
    ) -> list[EntityHierarchyNode]:
        created: list[EntityHierarchyNode] = []
        for payload in rows:
            row = await AuditWriter.insert_financial_record(
                self._session,
                model_class=EntityHierarchyNode,
                tenant_id=tenant_id,
                record_data={
                    "hierarchy_id": str(payload["hierarchy_id"]),
                    "entity_id": str(payload["entity_id"]),
                },
                values={**payload, "created_by": created_by},
                audit=AuditEvent(
                    tenant_id=tenant_id,
                    user_id=created_by,
                    action="multi_entity_consolidation.hierarchy_node.created",
                    resource_type="entity_hierarchy_node",
                    resource_name=str(payload["entity_id"]),
                ),
            )
            created.append(row)
        return created

    async def list_entity_hierarchies(
        self, *, tenant_id: uuid.UUID, organisation_id: uuid.UUID | None = None
    ) -> list[EntityHierarchy]:
        stmt = select(EntityHierarchy).where(EntityHierarchy.tenant_id == tenant_id)
        if organisation_id is not None:
            stmt = stmt.where(EntityHierarchy.organisation_id == organisation_id)
        result = await self._session.execute(
            stmt.order_by(
                EntityHierarchy.hierarchy_code.asc(),
                EntityHierarchy.effective_from.desc(),
                EntityHierarchy.created_at.desc(),
            )
        )
        return list(result.scalars().all())

    async def get_entity_hierarchy(
        self, *, tenant_id: uuid.UUID, hierarchy_id: uuid.UUID
    ) -> EntityHierarchy | None:
        result = await self._session.execute(
            select(EntityHierarchy).where(
                EntityHierarchy.tenant_id == tenant_id,
                EntityHierarchy.id == hierarchy_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_entity_hierarchy_versions(
        self, *, tenant_id: uuid.UUID, hierarchy_id: uuid.UUID
    ) -> list[EntityHierarchy]:
        current = await self.get_entity_hierarchy(tenant_id=tenant_id, hierarchy_id=hierarchy_id)
        if current is None:
            return []
        result = await self._session.execute(
            select(EntityHierarchy)
            .where(
                EntityHierarchy.tenant_id == tenant_id,
                EntityHierarchy.organisation_id == current.organisation_id,
                EntityHierarchy.hierarchy_code == current.hierarchy_code,
            )
            .order_by(
                EntityHierarchy.effective_from.desc(),
                EntityHierarchy.created_at.desc(),
                EntityHierarchy.id.desc(),
            )
        )
        return list(result.scalars().all())

    async def active_entity_hierarchies(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        reporting_period: date,
    ) -> list[EntityHierarchy]:
        result = await self._session.execute(
            select(EntityHierarchy)
            .where(
                EntityHierarchy.tenant_id == tenant_id,
                EntityHierarchy.organisation_id == organisation_id,
                EntityHierarchy.status == "active",
                EntityHierarchy.effective_from <= reporting_period,
            )
            .order_by(EntityHierarchy.hierarchy_code.asc(), EntityHierarchy.id.asc())
        )
        return list(result.scalars().all())

    async def active_hierarchy_nodes(
        self, *, tenant_id: uuid.UUID, hierarchy_id: uuid.UUID
    ) -> list[EntityHierarchyNode]:
        result = await self._session.execute(
            select(EntityHierarchyNode)
            .where(
                EntityHierarchyNode.tenant_id == tenant_id,
                EntityHierarchyNode.hierarchy_id == hierarchy_id,
                EntityHierarchyNode.status == "active",
            )
            .order_by(EntityHierarchyNode.node_level.asc(), EntityHierarchyNode.id.asc())
        )
        return list(result.scalars().all())

    async def create_scope(self, **values: Any) -> ConsolidationScope:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=ConsolidationScope,
            tenant_id=values["tenant_id"],
            record_data={"scope_code": values["scope_code"]},
            values=values,
            audit=AuditEvent(
                tenant_id=values["tenant_id"],
                user_id=values["created_by"],
                action="multi_entity_consolidation.scope.created",
                resource_type="consolidation_scope",
                resource_name=values["scope_code"],
            ),
        )

    async def list_scopes(
        self, *, tenant_id: uuid.UUID, organisation_id: uuid.UUID | None = None
    ) -> list[ConsolidationScope]:
        stmt = select(ConsolidationScope).where(ConsolidationScope.tenant_id == tenant_id)
        if organisation_id is not None:
            stmt = stmt.where(ConsolidationScope.organisation_id == organisation_id)
        result = await self._session.execute(
            stmt.order_by(
                ConsolidationScope.scope_code.asc(),
                ConsolidationScope.effective_from.desc(),
                ConsolidationScope.created_at.desc(),
            )
        )
        return list(result.scalars().all())

    async def get_scope(self, *, tenant_id: uuid.UUID, scope_id: uuid.UUID) -> ConsolidationScope | None:
        result = await self._session.execute(
            select(ConsolidationScope).where(
                ConsolidationScope.tenant_id == tenant_id,
                ConsolidationScope.id == scope_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_scope_versions(
        self, *, tenant_id: uuid.UUID, scope_id: uuid.UUID
    ) -> list[ConsolidationScope]:
        current = await self.get_scope(tenant_id=tenant_id, scope_id=scope_id)
        if current is None:
            return []
        result = await self._session.execute(
            select(ConsolidationScope)
            .where(
                ConsolidationScope.tenant_id == tenant_id,
                ConsolidationScope.organisation_id == current.organisation_id,
                ConsolidationScope.scope_code == current.scope_code,
            )
            .order_by(
                ConsolidationScope.effective_from.desc(),
                ConsolidationScope.created_at.desc(),
                ConsolidationScope.id.desc(),
            )
        )
        return list(result.scalars().all())

    async def active_scopes(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        reporting_period: date,
    ) -> list[ConsolidationScope]:
        result = await self._session.execute(
            select(ConsolidationScope)
            .where(
                ConsolidationScope.tenant_id == tenant_id,
                ConsolidationScope.organisation_id == organisation_id,
                ConsolidationScope.status == "active",
                ConsolidationScope.effective_from <= reporting_period,
            )
            .order_by(ConsolidationScope.scope_code.asc(), ConsolidationScope.id.asc())
        )
        return list(result.scalars().all())

    async def create_rule_definition(self, **values: Any) -> ConsolidationRuleDefinition:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=ConsolidationRuleDefinition,
            tenant_id=values["tenant_id"],
            record_data={"rule_code": values["rule_code"]},
            values=values,
            audit=AuditEvent(
                tenant_id=values["tenant_id"],
                user_id=values["created_by"],
                action="multi_entity_consolidation.rule.created",
                resource_type="consolidation_rule_definition",
                resource_name=values["rule_code"],
            ),
        )

    async def list_rule_definitions(
        self, *, tenant_id: uuid.UUID, organisation_id: uuid.UUID | None = None
    ) -> list[ConsolidationRuleDefinition]:
        stmt = select(ConsolidationRuleDefinition).where(
            ConsolidationRuleDefinition.tenant_id == tenant_id
        )
        if organisation_id is not None:
            stmt = stmt.where(ConsolidationRuleDefinition.organisation_id == organisation_id)
        result = await self._session.execute(
            stmt.order_by(
                ConsolidationRuleDefinition.rule_code.asc(),
                ConsolidationRuleDefinition.effective_from.desc(),
                ConsolidationRuleDefinition.created_at.desc(),
            )
        )
        return list(result.scalars().all())

    async def get_rule_definition(
        self, *, tenant_id: uuid.UUID, rule_id: uuid.UUID
    ) -> ConsolidationRuleDefinition | None:
        result = await self._session.execute(
            select(ConsolidationRuleDefinition).where(
                ConsolidationRuleDefinition.tenant_id == tenant_id,
                ConsolidationRuleDefinition.id == rule_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_rule_versions(
        self, *, tenant_id: uuid.UUID, rule_id: uuid.UUID
    ) -> list[ConsolidationRuleDefinition]:
        current = await self.get_rule_definition(tenant_id=tenant_id, rule_id=rule_id)
        if current is None:
            return []
        result = await self._session.execute(
            select(ConsolidationRuleDefinition)
            .where(
                ConsolidationRuleDefinition.tenant_id == tenant_id,
                ConsolidationRuleDefinition.organisation_id == current.organisation_id,
                ConsolidationRuleDefinition.rule_code == current.rule_code,
            )
            .order_by(
                ConsolidationRuleDefinition.effective_from.desc(),
                ConsolidationRuleDefinition.created_at.desc(),
                ConsolidationRuleDefinition.id.desc(),
            )
        )
        return list(result.scalars().all())

    async def active_rule_definitions(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        reporting_period: date,
    ) -> list[ConsolidationRuleDefinition]:
        result = await self._session.execute(
            select(ConsolidationRuleDefinition)
            .where(
                ConsolidationRuleDefinition.tenant_id == tenant_id,
                ConsolidationRuleDefinition.organisation_id == organisation_id,
                ConsolidationRuleDefinition.status == "active",
                ConsolidationRuleDefinition.effective_from <= reporting_period,
            )
            .order_by(ConsolidationRuleDefinition.rule_code.asc(), ConsolidationRuleDefinition.id.asc())
        )
        return list(result.scalars().all())

    async def create_intercompany_rule(self, **values: Any) -> IntercompanyMappingRule:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=IntercompanyMappingRule,
            tenant_id=values["tenant_id"],
            record_data={"rule_code": values["rule_code"]},
            values=values,
            audit=AuditEvent(
                tenant_id=values["tenant_id"],
                user_id=values["created_by"],
                action="multi_entity_consolidation.intercompany_rule.created",
                resource_type="intercompany_mapping_rule",
                resource_name=values["rule_code"],
            ),
        )

    async def list_intercompany_rules(
        self, *, tenant_id: uuid.UUID, organisation_id: uuid.UUID | None = None
    ) -> list[IntercompanyMappingRule]:
        stmt = select(IntercompanyMappingRule).where(IntercompanyMappingRule.tenant_id == tenant_id)
        if organisation_id is not None:
            stmt = stmt.where(IntercompanyMappingRule.organisation_id == organisation_id)
        result = await self._session.execute(
            stmt.order_by(
                IntercompanyMappingRule.rule_code.asc(),
                IntercompanyMappingRule.effective_from.desc(),
                IntercompanyMappingRule.created_at.desc(),
            )
        )
        return list(result.scalars().all())

    async def get_intercompany_rule(
        self, *, tenant_id: uuid.UUID, rule_id: uuid.UUID
    ) -> IntercompanyMappingRule | None:
        result = await self._session.execute(
            select(IntercompanyMappingRule).where(
                IntercompanyMappingRule.tenant_id == tenant_id,
                IntercompanyMappingRule.id == rule_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_intercompany_rule_versions(
        self, *, tenant_id: uuid.UUID, rule_id: uuid.UUID
    ) -> list[IntercompanyMappingRule]:
        current = await self.get_intercompany_rule(tenant_id=tenant_id, rule_id=rule_id)
        if current is None:
            return []
        result = await self._session.execute(
            select(IntercompanyMappingRule)
            .where(
                IntercompanyMappingRule.tenant_id == tenant_id,
                IntercompanyMappingRule.organisation_id == current.organisation_id,
                IntercompanyMappingRule.rule_code == current.rule_code,
            )
            .order_by(
                IntercompanyMappingRule.effective_from.desc(),
                IntercompanyMappingRule.created_at.desc(),
                IntercompanyMappingRule.id.desc(),
            )
        )
        return list(result.scalars().all())

    async def active_intercompany_rules(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        reporting_period: date,
    ) -> list[IntercompanyMappingRule]:
        result = await self._session.execute(
            select(IntercompanyMappingRule)
            .where(
                IntercompanyMappingRule.tenant_id == tenant_id,
                IntercompanyMappingRule.organisation_id == organisation_id,
                IntercompanyMappingRule.status == "active",
                IntercompanyMappingRule.effective_from <= reporting_period,
            )
            .order_by(IntercompanyMappingRule.rule_code.asc(), IntercompanyMappingRule.id.asc())
        )
        return list(result.scalars().all())

    async def create_adjustment_definition(self, **values: Any) -> ConsolidationAdjustmentDefinition:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=ConsolidationAdjustmentDefinition,
            tenant_id=values["tenant_id"],
            record_data={"adjustment_code": values["adjustment_code"]},
            values=values,
            audit=AuditEvent(
                tenant_id=values["tenant_id"],
                user_id=values["created_by"],
                action="multi_entity_consolidation.adjustment_definition.created",
                resource_type="consolidation_adjustment_definition",
                resource_name=values["adjustment_code"],
            ),
        )

    async def list_adjustment_definitions(
        self, *, tenant_id: uuid.UUID, organisation_id: uuid.UUID | None = None
    ) -> list[ConsolidationAdjustmentDefinition]:
        stmt = select(ConsolidationAdjustmentDefinition).where(
            ConsolidationAdjustmentDefinition.tenant_id == tenant_id
        )
        if organisation_id is not None:
            stmt = stmt.where(ConsolidationAdjustmentDefinition.organisation_id == organisation_id)
        result = await self._session.execute(
            stmt.order_by(
                ConsolidationAdjustmentDefinition.adjustment_code.asc(),
                ConsolidationAdjustmentDefinition.effective_from.desc(),
                ConsolidationAdjustmentDefinition.created_at.desc(),
            )
        )
        return list(result.scalars().all())

    async def get_adjustment_definition(
        self, *, tenant_id: uuid.UUID, adjustment_id: uuid.UUID
    ) -> ConsolidationAdjustmentDefinition | None:
        result = await self._session.execute(
            select(ConsolidationAdjustmentDefinition).where(
                ConsolidationAdjustmentDefinition.tenant_id == tenant_id,
                ConsolidationAdjustmentDefinition.id == adjustment_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_adjustment_versions(
        self, *, tenant_id: uuid.UUID, adjustment_id: uuid.UUID
    ) -> list[ConsolidationAdjustmentDefinition]:
        current = await self.get_adjustment_definition(
            tenant_id=tenant_id, adjustment_id=adjustment_id
        )
        if current is None:
            return []
        result = await self._session.execute(
            select(ConsolidationAdjustmentDefinition)
            .where(
                ConsolidationAdjustmentDefinition.tenant_id == tenant_id,
                ConsolidationAdjustmentDefinition.organisation_id == current.organisation_id,
                ConsolidationAdjustmentDefinition.adjustment_code == current.adjustment_code,
            )
            .order_by(
                ConsolidationAdjustmentDefinition.effective_from.desc(),
                ConsolidationAdjustmentDefinition.created_at.desc(),
                ConsolidationAdjustmentDefinition.id.desc(),
            )
        )
        return list(result.scalars().all())

    async def active_adjustment_definitions(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        reporting_period: date,
    ) -> list[ConsolidationAdjustmentDefinition]:
        result = await self._session.execute(
            select(ConsolidationAdjustmentDefinition)
            .where(
                ConsolidationAdjustmentDefinition.tenant_id == tenant_id,
                ConsolidationAdjustmentDefinition.organisation_id == organisation_id,
                ConsolidationAdjustmentDefinition.status == "active",
                ConsolidationAdjustmentDefinition.effective_from <= reporting_period,
            )
            .order_by(
                ConsolidationAdjustmentDefinition.adjustment_code.asc(),
                ConsolidationAdjustmentDefinition.id.asc(),
            )
        )
        return list(result.scalars().all())

    async def create_run(self, **values: Any) -> MultiEntityConsolidationRun:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=MultiEntityConsolidationRun,
            tenant_id=values["tenant_id"],
            record_data={"run_token": values["run_token"]},
            values=values,
            audit=AuditEvent(
                tenant_id=values["tenant_id"],
                user_id=values["created_by"],
                action="multi_entity_consolidation.run.created",
                resource_type="multi_entity_consolidation_run",
                resource_name=values["run_token"],
            ),
        )

    async def get_run_by_token(
        self, *, tenant_id: uuid.UUID, run_token: str
    ) -> MultiEntityConsolidationRun | None:
        result = await self._session.execute(
            select(MultiEntityConsolidationRun).where(
                MultiEntityConsolidationRun.tenant_id == tenant_id,
                MultiEntityConsolidationRun.run_token == run_token,
            )
        )
        return result.scalar_one_or_none()

    async def get_run(
        self, *, tenant_id: uuid.UUID, run_id: uuid.UUID
    ) -> MultiEntityConsolidationRun | None:
        result = await self._session.execute(
            select(MultiEntityConsolidationRun).where(
                MultiEntityConsolidationRun.tenant_id == tenant_id,
                MultiEntityConsolidationRun.id == run_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_metric_runs(self, *, tenant_id: uuid.UUID, run_ids: list[uuid.UUID]) -> list[MetricRun]:
        if not run_ids:
            return []
        result = await self._session.execute(
            select(MetricRun).where(
                MetricRun.tenant_id == tenant_id,
                MetricRun.id.in_(run_ids),
            )
        )
        return list(result.scalars().all())

    async def list_metric_results_for_runs(
        self, *, tenant_id: uuid.UUID, run_ids: Iterable[uuid.UUID]
    ) -> list[MetricResult]:
        ids = list(run_ids)
        if not ids:
            return []
        result = await self._session.execute(
            select(MetricResult)
            .where(
                MetricResult.tenant_id == tenant_id,
                MetricResult.run_id.in_(ids),
            )
            .order_by(MetricResult.metric_code.asc(), MetricResult.id.asc())
        )
        return list(result.scalars().all())

    async def list_variance_results_for_runs(
        self, *, tenant_id: uuid.UUID, run_ids: Iterable[uuid.UUID]
    ) -> list[VarianceResult]:
        ids = list(run_ids)
        if not ids:
            return []
        result = await self._session.execute(
            select(VarianceResult)
            .where(
                VarianceResult.tenant_id == tenant_id,
                VarianceResult.run_id.in_(ids),
            )
            .order_by(VarianceResult.metric_code.asc(), VarianceResult.id.asc())
        )
        return list(result.scalars().all())

    async def create_metric_results(
        self,
        *,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
        rows: Iterable[dict[str, Any]],
        created_by: uuid.UUID,
    ) -> list[MultiEntityConsolidationMetricResult]:
        created: list[MultiEntityConsolidationMetricResult] = []
        for payload in rows:
            row = await AuditWriter.insert_financial_record(
                self._session,
                model_class=MultiEntityConsolidationMetricResult,
                tenant_id=tenant_id,
                record_data={"run_id": str(run_id), "metric_code": payload["metric_code"]},
                values={**payload, "run_id": run_id, "created_by": created_by},
                audit=AuditEvent(
                    tenant_id=tenant_id,
                    user_id=created_by,
                    action="multi_entity_consolidation.metric_result.created",
                    resource_type="multi_entity_consolidation_metric_result",
                    resource_name=payload["metric_code"],
                ),
            )
            created.append(row)
        return created

    async def create_variance_results(
        self,
        *,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
        rows: Iterable[dict[str, Any]],
        created_by: uuid.UUID,
    ) -> list[MultiEntityConsolidationVarianceResult]:
        created: list[MultiEntityConsolidationVarianceResult] = []
        for payload in rows:
            row = await AuditWriter.insert_financial_record(
                self._session,
                model_class=MultiEntityConsolidationVarianceResult,
                tenant_id=tenant_id,
                record_data={"run_id": str(run_id), "metric_code": payload["metric_code"]},
                values={**payload, "run_id": run_id, "created_by": created_by},
                audit=AuditEvent(
                    tenant_id=tenant_id,
                    user_id=created_by,
                    action="multi_entity_consolidation.variance_result.created",
                    resource_type="multi_entity_consolidation_variance_result",
                    resource_name=payload["metric_code"],
                ),
            )
            created.append(row)
        return created

    async def create_evidence_links(
        self,
        *,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
        rows: Iterable[dict[str, Any]],
        created_by: uuid.UUID,
    ) -> list[MultiEntityConsolidationEvidenceLink]:
        created: list[MultiEntityConsolidationEvidenceLink] = []
        for payload in rows:
            row = await AuditWriter.insert_financial_record(
                self._session,
                model_class=MultiEntityConsolidationEvidenceLink,
                tenant_id=tenant_id,
                record_data={"run_id": str(run_id), "evidence_type": payload["evidence_type"]},
                values={**payload, "run_id": run_id, "created_by": created_by},
                audit=AuditEvent(
                    tenant_id=tenant_id,
                    user_id=created_by,
                    action="multi_entity_consolidation.evidence_link.created",
                    resource_type="multi_entity_consolidation_evidence_link",
                    resource_name=payload["evidence_type"],
                ),
            )
            created.append(row)
        return created

    async def list_metric_results(
        self, *, tenant_id: uuid.UUID, run_id: uuid.UUID
    ) -> list[MultiEntityConsolidationMetricResult]:
        result = await self._session.execute(
            select(MultiEntityConsolidationMetricResult)
            .where(
                MultiEntityConsolidationMetricResult.tenant_id == tenant_id,
                MultiEntityConsolidationMetricResult.run_id == run_id,
            )
            .order_by(
                MultiEntityConsolidationMetricResult.line_no.asc(),
                MultiEntityConsolidationMetricResult.id.asc(),
            )
        )
        return list(result.scalars().all())

    async def list_variance_results(
        self, *, tenant_id: uuid.UUID, run_id: uuid.UUID
    ) -> list[MultiEntityConsolidationVarianceResult]:
        result = await self._session.execute(
            select(MultiEntityConsolidationVarianceResult)
            .where(
                MultiEntityConsolidationVarianceResult.tenant_id == tenant_id,
                MultiEntityConsolidationVarianceResult.run_id == run_id,
            )
            .order_by(
                MultiEntityConsolidationVarianceResult.line_no.asc(),
                MultiEntityConsolidationVarianceResult.id.asc(),
            )
        )
        return list(result.scalars().all())

    async def list_evidence_links(
        self, *, tenant_id: uuid.UUID, run_id: uuid.UUID
    ) -> list[MultiEntityConsolidationEvidenceLink]:
        result = await self._session.execute(
            select(MultiEntityConsolidationEvidenceLink)
            .where(
                MultiEntityConsolidationEvidenceLink.tenant_id == tenant_id,
                MultiEntityConsolidationEvidenceLink.run_id == run_id,
            )
            .order_by(
                MultiEntityConsolidationEvidenceLink.created_at.asc(),
                MultiEntityConsolidationEvidenceLink.id.asc(),
            )
        )
        return list(result.scalars().all())

    async def summarize_run(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> dict[str, int]:
        metric_count = await self._session.scalar(
            select(func.count())
            .select_from(MultiEntityConsolidationMetricResult)
            .where(
                MultiEntityConsolidationMetricResult.tenant_id == tenant_id,
                MultiEntityConsolidationMetricResult.run_id == run_id,
            )
        )
        variance_count = await self._session.scalar(
            select(func.count())
            .select_from(MultiEntityConsolidationVarianceResult)
            .where(
                MultiEntityConsolidationVarianceResult.tenant_id == tenant_id,
                MultiEntityConsolidationVarianceResult.run_id == run_id,
            )
        )
        evidence_count = await self._session.scalar(
            select(func.count())
            .select_from(MultiEntityConsolidationEvidenceLink)
            .where(
                MultiEntityConsolidationEvidenceLink.tenant_id == tenant_id,
                MultiEntityConsolidationEvidenceLink.run_id == run_id,
            )
        )
        return {
            "metric_count": int(metric_count or 0),
            "variance_count": int(variance_count or 0),
            "evidence_count": int(evidence_count or 0),
        }
