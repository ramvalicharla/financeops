from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.fx_translation_reporting import FxTranslationRun
from financeops.db.models.multi_entity_consolidation import (
    MultiEntityConsolidationMetricResult,
    MultiEntityConsolidationRun,
    MultiEntityConsolidationVarianceResult,
)
from financeops.db.models.ownership_consolidation import (
    MinorityInterestRuleDefinition,
    OwnershipConsolidationEvidenceLink,
    OwnershipConsolidationMetricResult,
    OwnershipConsolidationRuleDefinition,
    OwnershipConsolidationRun,
    OwnershipConsolidationVarianceResult,
    OwnershipRelationship,
    OwnershipStructureDefinition,
)
from financeops.services.audit_writer import AuditEvent, AuditWriter


class OwnershipConsolidationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_structure_definition(self, **values: Any) -> OwnershipStructureDefinition:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=OwnershipStructureDefinition,
            tenant_id=values["tenant_id"],
            record_data={"ownership_structure_code": values["ownership_structure_code"]},
            values=values,
            audit=AuditEvent(
                tenant_id=values["tenant_id"],
                user_id=values["created_by"],
                action="ownership_consolidation.structure.created",
                resource_type="ownership_structure_definition",
                resource_name=values["ownership_structure_code"],
            ),
        )

    async def list_structure_definitions(
        self, *, tenant_id: uuid.UUID, organisation_id: uuid.UUID | None = None
    ) -> list[OwnershipStructureDefinition]:
        stmt = select(OwnershipStructureDefinition).where(
            OwnershipStructureDefinition.tenant_id == tenant_id
        )
        if organisation_id is not None:
            stmt = stmt.where(OwnershipStructureDefinition.organisation_id == organisation_id)
        result = await self._session.execute(
            stmt.order_by(
                OwnershipStructureDefinition.ownership_structure_code.asc(),
                OwnershipStructureDefinition.effective_from.desc(),
                OwnershipStructureDefinition.created_at.desc(),
            )
        )
        return list(result.scalars().all())

    async def get_structure_definition(
        self, *, tenant_id: uuid.UUID, definition_id: uuid.UUID
    ) -> OwnershipStructureDefinition | None:
        result = await self._session.execute(
            select(OwnershipStructureDefinition).where(
                OwnershipStructureDefinition.tenant_id == tenant_id,
                OwnershipStructureDefinition.id == definition_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_structure_versions(
        self, *, tenant_id: uuid.UUID, definition_id: uuid.UUID
    ) -> list[OwnershipStructureDefinition]:
        current = await self.get_structure_definition(tenant_id=tenant_id, definition_id=definition_id)
        if current is None:
            return []
        result = await self._session.execute(
            select(OwnershipStructureDefinition)
            .where(
                OwnershipStructureDefinition.tenant_id == tenant_id,
                OwnershipStructureDefinition.organisation_id == current.organisation_id,
                OwnershipStructureDefinition.ownership_structure_code
                == current.ownership_structure_code,
            )
            .order_by(
                OwnershipStructureDefinition.effective_from.desc(),
                OwnershipStructureDefinition.created_at.desc(),
                OwnershipStructureDefinition.id.desc(),
            )
        )
        return list(result.scalars().all())

    async def active_structure_definitions(
        self, *, tenant_id: uuid.UUID, organisation_id: uuid.UUID, reporting_period: date
    ) -> list[OwnershipStructureDefinition]:
        result = await self._session.execute(
            select(OwnershipStructureDefinition)
            .where(
                OwnershipStructureDefinition.tenant_id == tenant_id,
                OwnershipStructureDefinition.organisation_id == organisation_id,
                OwnershipStructureDefinition.status == "active",
                OwnershipStructureDefinition.effective_from <= reporting_period,
            )
            .order_by(
                OwnershipStructureDefinition.ownership_structure_code.asc(),
                OwnershipStructureDefinition.id.asc(),
            )
        )
        return list(result.scalars().all())

    async def create_relationship(self, **values: Any) -> OwnershipRelationship:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=OwnershipRelationship,
            tenant_id=values["tenant_id"],
            record_data={
                "ownership_structure_id": str(values["ownership_structure_id"]),
                "parent_entity_id": str(values["parent_entity_id"]),
                "child_entity_id": str(values["child_entity_id"]),
            },
            values=values,
            audit=AuditEvent(
                tenant_id=values["tenant_id"],
                user_id=values["created_by"],
                action="ownership_consolidation.relationship.created",
                resource_type="ownership_relationship",
                resource_name=f"{values['parent_entity_id']}->{values['child_entity_id']}",
            ),
        )

    async def list_relationships(
        self, *, tenant_id: uuid.UUID, ownership_structure_id: uuid.UUID | None = None
    ) -> list[OwnershipRelationship]:
        stmt = select(OwnershipRelationship).where(OwnershipRelationship.tenant_id == tenant_id)
        if ownership_structure_id is not None:
            stmt = stmt.where(OwnershipRelationship.ownership_structure_id == ownership_structure_id)
        result = await self._session.execute(
            stmt.order_by(
                OwnershipRelationship.ownership_structure_id.asc(),
                OwnershipRelationship.parent_entity_id.asc(),
                OwnershipRelationship.child_entity_id.asc(),
                OwnershipRelationship.effective_from.desc(),
                OwnershipRelationship.created_at.desc(),
            )
        )
        return list(result.scalars().all())

    async def get_relationship(
        self, *, tenant_id: uuid.UUID, relationship_id: uuid.UUID
    ) -> OwnershipRelationship | None:
        result = await self._session.execute(
            select(OwnershipRelationship).where(
                OwnershipRelationship.tenant_id == tenant_id,
                OwnershipRelationship.id == relationship_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_relationship_versions(
        self, *, tenant_id: uuid.UUID, relationship_id: uuid.UUID
    ) -> list[OwnershipRelationship]:
        current = await self.get_relationship(tenant_id=tenant_id, relationship_id=relationship_id)
        if current is None:
            return []
        result = await self._session.execute(
            select(OwnershipRelationship)
            .where(
                OwnershipRelationship.tenant_id == tenant_id,
                OwnershipRelationship.organisation_id == current.organisation_id,
                OwnershipRelationship.ownership_structure_id == current.ownership_structure_id,
                OwnershipRelationship.parent_entity_id == current.parent_entity_id,
                OwnershipRelationship.child_entity_id == current.child_entity_id,
            )
            .order_by(
                OwnershipRelationship.effective_from.desc(),
                OwnershipRelationship.created_at.desc(),
                OwnershipRelationship.id.desc(),
            )
        )
        return list(result.scalars().all())

    async def active_relationships(
        self,
        *,
        tenant_id: uuid.UUID,
        ownership_structure_id: uuid.UUID,
        reporting_period: date,
    ) -> list[OwnershipRelationship]:
        result = await self._session.execute(
            select(OwnershipRelationship)
            .where(
                OwnershipRelationship.tenant_id == tenant_id,
                OwnershipRelationship.ownership_structure_id == ownership_structure_id,
                OwnershipRelationship.status == "active",
                OwnershipRelationship.effective_from <= reporting_period,
            )
            .order_by(
                OwnershipRelationship.parent_entity_id.asc(),
                OwnershipRelationship.child_entity_id.asc(),
                OwnershipRelationship.id.asc(),
            )
        )
        return list(result.scalars().all())

    async def create_ownership_rule_definition(
        self, **values: Any
    ) -> OwnershipConsolidationRuleDefinition:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=OwnershipConsolidationRuleDefinition,
            tenant_id=values["tenant_id"],
            record_data={"rule_code": values["rule_code"]},
            values=values,
            audit=AuditEvent(
                tenant_id=values["tenant_id"],
                user_id=values["created_by"],
                action="ownership_consolidation.rule.created",
                resource_type="ownership_consolidation_rule_definition",
                resource_name=values["rule_code"],
            ),
        )

    async def list_ownership_rule_definitions(
        self, *, tenant_id: uuid.UUID, organisation_id: uuid.UUID | None = None
    ) -> list[OwnershipConsolidationRuleDefinition]:
        stmt = select(OwnershipConsolidationRuleDefinition).where(
            OwnershipConsolidationRuleDefinition.tenant_id == tenant_id
        )
        if organisation_id is not None:
            stmt = stmt.where(OwnershipConsolidationRuleDefinition.organisation_id == organisation_id)
        result = await self._session.execute(
            stmt.order_by(
                OwnershipConsolidationRuleDefinition.rule_code.asc(),
                OwnershipConsolidationRuleDefinition.effective_from.desc(),
                OwnershipConsolidationRuleDefinition.created_at.desc(),
            )
        )
        return list(result.scalars().all())

    async def get_ownership_rule_definition(
        self, *, tenant_id: uuid.UUID, rule_id: uuid.UUID
    ) -> OwnershipConsolidationRuleDefinition | None:
        result = await self._session.execute(
            select(OwnershipConsolidationRuleDefinition).where(
                OwnershipConsolidationRuleDefinition.tenant_id == tenant_id,
                OwnershipConsolidationRuleDefinition.id == rule_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_ownership_rule_versions(
        self, *, tenant_id: uuid.UUID, rule_id: uuid.UUID
    ) -> list[OwnershipConsolidationRuleDefinition]:
        current = await self.get_ownership_rule_definition(tenant_id=tenant_id, rule_id=rule_id)
        if current is None:
            return []
        result = await self._session.execute(
            select(OwnershipConsolidationRuleDefinition)
            .where(
                OwnershipConsolidationRuleDefinition.tenant_id == tenant_id,
                OwnershipConsolidationRuleDefinition.organisation_id == current.organisation_id,
                OwnershipConsolidationRuleDefinition.rule_code == current.rule_code,
            )
            .order_by(
                OwnershipConsolidationRuleDefinition.effective_from.desc(),
                OwnershipConsolidationRuleDefinition.created_at.desc(),
                OwnershipConsolidationRuleDefinition.id.desc(),
            )
        )
        return list(result.scalars().all())

    async def active_ownership_rules(
        self, *, tenant_id: uuid.UUID, organisation_id: uuid.UUID, reporting_period: date
    ) -> list[OwnershipConsolidationRuleDefinition]:
        result = await self._session.execute(
            select(OwnershipConsolidationRuleDefinition)
            .where(
                OwnershipConsolidationRuleDefinition.tenant_id == tenant_id,
                OwnershipConsolidationRuleDefinition.organisation_id == organisation_id,
                OwnershipConsolidationRuleDefinition.status == "active",
                OwnershipConsolidationRuleDefinition.effective_from <= reporting_period,
            )
            .order_by(
                OwnershipConsolidationRuleDefinition.rule_code.asc(),
                OwnershipConsolidationRuleDefinition.id.asc(),
            )
        )
        return list(result.scalars().all())

    async def create_minority_interest_rule_definition(
        self, **values: Any
    ) -> MinorityInterestRuleDefinition:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=MinorityInterestRuleDefinition,
            tenant_id=values["tenant_id"],
            record_data={"rule_code": values["rule_code"]},
            values=values,
            audit=AuditEvent(
                tenant_id=values["tenant_id"],
                user_id=values["created_by"],
                action="ownership_consolidation.minority_rule.created",
                resource_type="minority_interest_rule_definition",
                resource_name=values["rule_code"],
            ),
        )

    async def list_minority_interest_rule_definitions(
        self, *, tenant_id: uuid.UUID, organisation_id: uuid.UUID | None = None
    ) -> list[MinorityInterestRuleDefinition]:
        stmt = select(MinorityInterestRuleDefinition).where(
            MinorityInterestRuleDefinition.tenant_id == tenant_id
        )
        if organisation_id is not None:
            stmt = stmt.where(MinorityInterestRuleDefinition.organisation_id == organisation_id)
        result = await self._session.execute(
            stmt.order_by(
                MinorityInterestRuleDefinition.rule_code.asc(),
                MinorityInterestRuleDefinition.effective_from.desc(),
                MinorityInterestRuleDefinition.created_at.desc(),
            )
        )
        return list(result.scalars().all())

    async def get_minority_interest_rule_definition(
        self, *, tenant_id: uuid.UUID, rule_id: uuid.UUID
    ) -> MinorityInterestRuleDefinition | None:
        result = await self._session.execute(
            select(MinorityInterestRuleDefinition).where(
                MinorityInterestRuleDefinition.tenant_id == tenant_id,
                MinorityInterestRuleDefinition.id == rule_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_minority_interest_rule_versions(
        self, *, tenant_id: uuid.UUID, rule_id: uuid.UUID
    ) -> list[MinorityInterestRuleDefinition]:
        current = await self.get_minority_interest_rule_definition(tenant_id=tenant_id, rule_id=rule_id)
        if current is None:
            return []
        result = await self._session.execute(
            select(MinorityInterestRuleDefinition)
            .where(
                MinorityInterestRuleDefinition.tenant_id == tenant_id,
                MinorityInterestRuleDefinition.organisation_id == current.organisation_id,
                MinorityInterestRuleDefinition.rule_code == current.rule_code,
            )
            .order_by(
                MinorityInterestRuleDefinition.effective_from.desc(),
                MinorityInterestRuleDefinition.created_at.desc(),
                MinorityInterestRuleDefinition.id.desc(),
            )
        )
        return list(result.scalars().all())

    async def active_minority_interest_rules(
        self, *, tenant_id: uuid.UUID, organisation_id: uuid.UUID, reporting_period: date
    ) -> list[MinorityInterestRuleDefinition]:
        result = await self._session.execute(
            select(MinorityInterestRuleDefinition)
            .where(
                MinorityInterestRuleDefinition.tenant_id == tenant_id,
                MinorityInterestRuleDefinition.organisation_id == organisation_id,
                MinorityInterestRuleDefinition.status == "active",
                MinorityInterestRuleDefinition.effective_from <= reporting_period,
            )
            .order_by(
                MinorityInterestRuleDefinition.rule_code.asc(),
                MinorityInterestRuleDefinition.id.asc(),
            )
        )
        return list(result.scalars().all())

    async def get_fx_translation_run(
        self, *, tenant_id: uuid.UUID, run_id: uuid.UUID
    ) -> FxTranslationRun | None:
        result = await self._session.execute(
            select(FxTranslationRun).where(
                FxTranslationRun.tenant_id == tenant_id,
                FxTranslationRun.id == run_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_source_runs(
        self, *, tenant_id: uuid.UUID, run_ids: Iterable[uuid.UUID]
    ) -> list[MultiEntityConsolidationRun]:
        ids = list(run_ids)
        if not ids:
            return []
        result = await self._session.execute(
            select(MultiEntityConsolidationRun)
            .where(
                MultiEntityConsolidationRun.tenant_id == tenant_id,
                MultiEntityConsolidationRun.id.in_(ids),
            )
            .order_by(MultiEntityConsolidationRun.id.asc())
        )
        return list(result.scalars().all())

    async def list_source_metric_results_for_runs(
        self, *, tenant_id: uuid.UUID, run_ids: Iterable[uuid.UUID]
    ) -> list[MultiEntityConsolidationMetricResult]:
        ids = list(run_ids)
        if not ids:
            return []
        result = await self._session.execute(
            select(MultiEntityConsolidationMetricResult)
            .where(
                MultiEntityConsolidationMetricResult.tenant_id == tenant_id,
                MultiEntityConsolidationMetricResult.run_id.in_(ids),
            )
            .order_by(
                MultiEntityConsolidationMetricResult.run_id.asc(),
                MultiEntityConsolidationMetricResult.line_no.asc(),
                MultiEntityConsolidationMetricResult.id.asc(),
            )
        )
        return list(result.scalars().all())

    async def list_source_variance_results_for_runs(
        self, *, tenant_id: uuid.UUID, run_ids: Iterable[uuid.UUID]
    ) -> list[MultiEntityConsolidationVarianceResult]:
        ids = list(run_ids)
        if not ids:
            return []
        result = await self._session.execute(
            select(MultiEntityConsolidationVarianceResult)
            .where(
                MultiEntityConsolidationVarianceResult.tenant_id == tenant_id,
                MultiEntityConsolidationVarianceResult.run_id.in_(ids),
            )
            .order_by(
                MultiEntityConsolidationVarianceResult.run_id.asc(),
                MultiEntityConsolidationVarianceResult.line_no.asc(),
                MultiEntityConsolidationVarianceResult.id.asc(),
            )
        )
        return list(result.scalars().all())

    async def create_run(self, **values: Any) -> OwnershipConsolidationRun:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=OwnershipConsolidationRun,
            tenant_id=values["tenant_id"],
            record_data={"run_token": values["run_token"]},
            values=values,
            audit=AuditEvent(
                tenant_id=values["tenant_id"],
                user_id=values["created_by"],
                action="ownership_consolidation.run.created",
                resource_type="ownership_consolidation_run",
                resource_name=values["run_token"],
            ),
        )

    async def get_run_by_token(
        self, *, tenant_id: uuid.UUID, run_token: str
    ) -> OwnershipConsolidationRun | None:
        result = await self._session.execute(
            select(OwnershipConsolidationRun).where(
                OwnershipConsolidationRun.tenant_id == tenant_id,
                OwnershipConsolidationRun.run_token == run_token,
            )
        )
        return result.scalar_one_or_none()

    async def get_run(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> OwnershipConsolidationRun | None:
        result = await self._session.execute(
            select(OwnershipConsolidationRun).where(
                OwnershipConsolidationRun.tenant_id == tenant_id,
                OwnershipConsolidationRun.id == run_id,
            )
        )
        return result.scalar_one_or_none()

    async def create_metric_results(
        self,
        *,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
        rows: list[dict[str, Any]],
        created_by: uuid.UUID,
    ) -> list[OwnershipConsolidationMetricResult]:
        created: list[OwnershipConsolidationMetricResult] = []
        for row in rows:
            db_row = await AuditWriter.insert_financial_record(
                self._session,
                model_class=OwnershipConsolidationMetricResult,
                tenant_id=tenant_id,
                record_data={"ownership_consolidation_run_id": str(run_id), "line_no": row["line_no"]},
                values={**row, "ownership_consolidation_run_id": run_id, "created_by": created_by},
                audit=AuditEvent(
                    tenant_id=tenant_id,
                    user_id=created_by,
                    action="ownership_consolidation.metric_result.created",
                    resource_type="ownership_consolidation_metric_result",
                    resource_name=f"{run_id}:{row['line_no']}",
                ),
            )
            created.append(db_row)
        return created

    async def create_variance_results(
        self,
        *,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
        rows: list[dict[str, Any]],
        created_by: uuid.UUID,
    ) -> list[OwnershipConsolidationVarianceResult]:
        created: list[OwnershipConsolidationVarianceResult] = []
        for row in rows:
            db_row = await AuditWriter.insert_financial_record(
                self._session,
                model_class=OwnershipConsolidationVarianceResult,
                tenant_id=tenant_id,
                record_data={"ownership_consolidation_run_id": str(run_id), "line_no": row["line_no"]},
                values={**row, "ownership_consolidation_run_id": run_id, "created_by": created_by},
                audit=AuditEvent(
                    tenant_id=tenant_id,
                    user_id=created_by,
                    action="ownership_consolidation.variance_result.created",
                    resource_type="ownership_consolidation_variance_result",
                    resource_name=f"{run_id}:{row['line_no']}",
                ),
            )
            created.append(db_row)
        return created

    async def create_evidence_links(
        self,
        *,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
        rows: list[dict[str, Any]],
        created_by: uuid.UUID,
    ) -> list[OwnershipConsolidationEvidenceLink]:
        created: list[OwnershipConsolidationEvidenceLink] = []
        for row in rows:
            db_row = await AuditWriter.insert_financial_record(
                self._session,
                model_class=OwnershipConsolidationEvidenceLink,
                tenant_id=tenant_id,
                record_data={
                    "ownership_consolidation_run_id": str(run_id),
                    "evidence_type": row["evidence_type"],
                    "evidence_ref": row["evidence_ref"],
                },
                values={**row, "ownership_consolidation_run_id": run_id, "created_by": created_by},
                audit=AuditEvent(
                    tenant_id=tenant_id,
                    user_id=created_by,
                    action="ownership_consolidation.evidence_link.created",
                    resource_type="ownership_consolidation_evidence_link",
                    resource_name=row["evidence_type"],
                ),
            )
            created.append(db_row)
        return created

    async def list_metric_results(
        self, *, tenant_id: uuid.UUID, run_id: uuid.UUID
    ) -> list[OwnershipConsolidationMetricResult]:
        result = await self._session.execute(
            select(OwnershipConsolidationMetricResult)
            .where(
                OwnershipConsolidationMetricResult.tenant_id == tenant_id,
                OwnershipConsolidationMetricResult.ownership_consolidation_run_id == run_id,
            )
            .order_by(
                OwnershipConsolidationMetricResult.line_no.asc(),
                OwnershipConsolidationMetricResult.id.asc(),
            )
        )
        return list(result.scalars().all())

    async def list_variance_results(
        self, *, tenant_id: uuid.UUID, run_id: uuid.UUID
    ) -> list[OwnershipConsolidationVarianceResult]:
        result = await self._session.execute(
            select(OwnershipConsolidationVarianceResult)
            .where(
                OwnershipConsolidationVarianceResult.tenant_id == tenant_id,
                OwnershipConsolidationVarianceResult.ownership_consolidation_run_id == run_id,
            )
            .order_by(
                OwnershipConsolidationVarianceResult.line_no.asc(),
                OwnershipConsolidationVarianceResult.id.asc(),
            )
        )
        return list(result.scalars().all())

    async def list_evidence_links(
        self, *, tenant_id: uuid.UUID, run_id: uuid.UUID
    ) -> list[OwnershipConsolidationEvidenceLink]:
        result = await self._session.execute(
            select(OwnershipConsolidationEvidenceLink)
            .where(
                OwnershipConsolidationEvidenceLink.tenant_id == tenant_id,
                OwnershipConsolidationEvidenceLink.ownership_consolidation_run_id == run_id,
            )
            .order_by(
                OwnershipConsolidationEvidenceLink.created_at.asc(),
                OwnershipConsolidationEvidenceLink.id.asc(),
            )
        )
        return list(result.scalars().all())

    async def summarize_run(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> dict[str, int]:
        metric_count = await self._session.scalar(
            select(func.count())
            .select_from(OwnershipConsolidationMetricResult)
            .where(
                OwnershipConsolidationMetricResult.tenant_id == tenant_id,
                OwnershipConsolidationMetricResult.ownership_consolidation_run_id == run_id,
            )
        )
        variance_count = await self._session.scalar(
            select(func.count())
            .select_from(OwnershipConsolidationVarianceResult)
            .where(
                OwnershipConsolidationVarianceResult.tenant_id == tenant_id,
                OwnershipConsolidationVarianceResult.ownership_consolidation_run_id == run_id,
            )
        )
        evidence_count = await self._session.scalar(
            select(func.count())
            .select_from(OwnershipConsolidationEvidenceLink)
            .where(
                OwnershipConsolidationEvidenceLink.tenant_id == tenant_id,
                OwnershipConsolidationEvidenceLink.ownership_consolidation_run_id == run_id,
            )
        )
        return {
            "metric_count": int(metric_count or 0),
            "variance_count": int(variance_count or 0),
            "evidence_count": int(evidence_count or 0),
        }
