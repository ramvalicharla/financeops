from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.cash_flow_engine import (
    CashFlowBridgeRuleDefinition,
    CashFlowEvidenceLink,
    CashFlowLineMapping,
    CashFlowLineResult,
    CashFlowRun,
    CashFlowStatementDefinition,
)
from financeops.db.models.fx_translation_reporting import (
    FxTranslatedMetricResult,
    FxTranslationRun,
)
from financeops.db.models.multi_entity_consolidation import (
    MultiEntityConsolidationMetricResult,
    MultiEntityConsolidationRun,
)
from financeops.db.models.ownership_consolidation import (
    OwnershipConsolidationMetricResult,
    OwnershipConsolidationRun,
)
from financeops.services.audit_writer import AuditEvent, AuditWriter


class CashFlowRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_statement_definition(self, **values: Any) -> CashFlowStatementDefinition:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=CashFlowStatementDefinition,
            tenant_id=values["tenant_id"],
            record_data={"definition_code": values["definition_code"]},
            values=values,
            audit=AuditEvent(
                tenant_id=values["tenant_id"],
                user_id=values["created_by"],
                action="cash_flow.statement_definition.created",
                resource_type="cash_flow_statement_definition",
                resource_name=values["definition_code"],
            ),
        )

    async def list_statement_definitions(
        self, *, tenant_id: uuid.UUID, organisation_id: uuid.UUID | None = None
    ) -> list[CashFlowStatementDefinition]:
        stmt = select(CashFlowStatementDefinition).where(
            CashFlowStatementDefinition.tenant_id == tenant_id
        )
        if organisation_id is not None:
            stmt = stmt.where(CashFlowStatementDefinition.organisation_id == organisation_id)
        rows = await self._session.execute(
            stmt.order_by(
                CashFlowStatementDefinition.definition_code.asc(),
                CashFlowStatementDefinition.effective_from.desc(),
                CashFlowStatementDefinition.created_at.desc(),
            )
        )
        return list(rows.scalars().all())

    async def get_statement_definition(
        self, *, tenant_id: uuid.UUID, definition_id: uuid.UUID
    ) -> CashFlowStatementDefinition | None:
        row = await self._session.execute(
            select(CashFlowStatementDefinition).where(
                CashFlowStatementDefinition.tenant_id == tenant_id,
                CashFlowStatementDefinition.id == definition_id,
            )
        )
        return row.scalar_one_or_none()

    async def list_statement_definition_versions(
        self, *, tenant_id: uuid.UUID, definition_id: uuid.UUID
    ) -> list[CashFlowStatementDefinition]:
        current = await self.get_statement_definition(
            tenant_id=tenant_id, definition_id=definition_id
        )
        if current is None:
            return []
        rows = await self._session.execute(
            select(CashFlowStatementDefinition)
            .where(
                CashFlowStatementDefinition.tenant_id == tenant_id,
                CashFlowStatementDefinition.organisation_id == current.organisation_id,
                CashFlowStatementDefinition.definition_code == current.definition_code,
            )
            .order_by(
                CashFlowStatementDefinition.effective_from.desc(),
                CashFlowStatementDefinition.created_at.desc(),
                CashFlowStatementDefinition.id.desc(),
            )
        )
        return list(rows.scalars().all())

    async def active_statement_definitions(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        reporting_period: date,
    ) -> list[CashFlowStatementDefinition]:
        rows = await self._session.execute(
            select(CashFlowStatementDefinition)
            .where(
                CashFlowStatementDefinition.tenant_id == tenant_id,
                CashFlowStatementDefinition.organisation_id == organisation_id,
                CashFlowStatementDefinition.status == "active",
                CashFlowStatementDefinition.effective_from <= reporting_period,
                (
                    (CashFlowStatementDefinition.effective_to.is_(None))
                    | (CashFlowStatementDefinition.effective_to >= reporting_period)
                ),
            )
            .order_by(
                CashFlowStatementDefinition.definition_code.asc(),
                CashFlowStatementDefinition.id.asc(),
            )
        )
        return list(rows.scalars().all())

    async def statement_definitions_by_version_token(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        version_token: str,
    ) -> list[CashFlowStatementDefinition]:
        rows = await self._session.execute(
            select(CashFlowStatementDefinition)
            .where(
                CashFlowStatementDefinition.tenant_id == tenant_id,
                CashFlowStatementDefinition.organisation_id == organisation_id,
                CashFlowStatementDefinition.version_token == version_token,
            )
            .order_by(CashFlowStatementDefinition.id.asc())
        )
        return list(rows.scalars().all())

    async def create_line_mapping(self, **values: Any) -> CashFlowLineMapping:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=CashFlowLineMapping,
            tenant_id=values["tenant_id"],
            record_data={
                "mapping_code": values["mapping_code"],
                "line_code": values["line_code"],
            },
            values=values,
            audit=AuditEvent(
                tenant_id=values["tenant_id"],
                user_id=values["created_by"],
                action="cash_flow.line_mapping.created",
                resource_type="cash_flow_line_mapping",
                resource_name=f"{values['mapping_code']}:{values['line_code']}",
            ),
        )

    async def list_line_mappings(
        self, *, tenant_id: uuid.UUID, organisation_id: uuid.UUID | None = None
    ) -> list[CashFlowLineMapping]:
        stmt = select(CashFlowLineMapping).where(CashFlowLineMapping.tenant_id == tenant_id)
        if organisation_id is not None:
            stmt = stmt.where(CashFlowLineMapping.organisation_id == organisation_id)
        rows = await self._session.execute(
            stmt.order_by(
                CashFlowLineMapping.mapping_code.asc(),
                CashFlowLineMapping.line_order.asc(),
                CashFlowLineMapping.created_at.desc(),
            )
        )
        return list(rows.scalars().all())

    async def get_line_mapping(
        self, *, tenant_id: uuid.UUID, mapping_id: uuid.UUID
    ) -> CashFlowLineMapping | None:
        row = await self._session.execute(
            select(CashFlowLineMapping).where(
                CashFlowLineMapping.tenant_id == tenant_id,
                CashFlowLineMapping.id == mapping_id,
            )
        )
        return row.scalar_one_or_none()

    async def list_line_mapping_versions(
        self, *, tenant_id: uuid.UUID, mapping_id: uuid.UUID
    ) -> list[CashFlowLineMapping]:
        current = await self.get_line_mapping(tenant_id=tenant_id, mapping_id=mapping_id)
        if current is None:
            return []
        rows = await self._session.execute(
            select(CashFlowLineMapping)
            .where(
                CashFlowLineMapping.tenant_id == tenant_id,
                CashFlowLineMapping.organisation_id == current.organisation_id,
                CashFlowLineMapping.mapping_code == current.mapping_code,
            )
            .order_by(
                CashFlowLineMapping.effective_from.desc(),
                CashFlowLineMapping.line_order.asc(),
                CashFlowLineMapping.created_at.desc(),
                CashFlowLineMapping.id.desc(),
            )
        )
        return list(rows.scalars().all())

    async def active_line_mappings(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        reporting_period: date,
    ) -> list[CashFlowLineMapping]:
        rows = await self._session.execute(
            select(CashFlowLineMapping)
            .where(
                CashFlowLineMapping.tenant_id == tenant_id,
                CashFlowLineMapping.organisation_id == organisation_id,
                CashFlowLineMapping.status == "active",
                CashFlowLineMapping.effective_from <= reporting_period,
                (
                    (CashFlowLineMapping.effective_to.is_(None))
                    | (CashFlowLineMapping.effective_to >= reporting_period)
                ),
            )
            .order_by(
                CashFlowLineMapping.mapping_code.asc(),
                CashFlowLineMapping.line_order.asc(),
                CashFlowLineMapping.id.asc(),
            )
        )
        return list(rows.scalars().all())

    async def line_mappings_by_version_token(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        version_token: str,
    ) -> list[CashFlowLineMapping]:
        rows = await self._session.execute(
            select(CashFlowLineMapping)
            .where(
                CashFlowLineMapping.tenant_id == tenant_id,
                CashFlowLineMapping.organisation_id == organisation_id,
                CashFlowLineMapping.version_token == version_token,
            )
            .order_by(
                CashFlowLineMapping.mapping_code.asc(),
                CashFlowLineMapping.line_order.asc(),
                CashFlowLineMapping.id.asc(),
            )
        )
        return list(rows.scalars().all())

    async def list_line_mappings_by_ids(
        self, *, tenant_id: uuid.UUID, mapping_ids: list[uuid.UUID]
    ) -> list[CashFlowLineMapping]:
        if not mapping_ids:
            return []
        rows = await self._session.execute(
            select(CashFlowLineMapping)
            .where(
                CashFlowLineMapping.tenant_id == tenant_id,
                CashFlowLineMapping.id.in_(mapping_ids),
            )
            .order_by(
                CashFlowLineMapping.mapping_code.asc(),
                CashFlowLineMapping.line_order.asc(),
                CashFlowLineMapping.id.asc(),
            )
        )
        return list(rows.scalars().all())

    async def create_bridge_rule(self, **values: Any) -> CashFlowBridgeRuleDefinition:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=CashFlowBridgeRuleDefinition,
            tenant_id=values["tenant_id"],
            record_data={"rule_code": values["rule_code"]},
            values=values,
            audit=AuditEvent(
                tenant_id=values["tenant_id"],
                user_id=values["created_by"],
                action="cash_flow.bridge_rule.created",
                resource_type="cash_flow_bridge_rule_definition",
                resource_name=values["rule_code"],
            ),
        )

    async def list_bridge_rules(
        self, *, tenant_id: uuid.UUID, organisation_id: uuid.UUID | None = None
    ) -> list[CashFlowBridgeRuleDefinition]:
        stmt = select(CashFlowBridgeRuleDefinition).where(
            CashFlowBridgeRuleDefinition.tenant_id == tenant_id
        )
        if organisation_id is not None:
            stmt = stmt.where(CashFlowBridgeRuleDefinition.organisation_id == organisation_id)
        rows = await self._session.execute(
            stmt.order_by(
                CashFlowBridgeRuleDefinition.rule_code.asc(),
                CashFlowBridgeRuleDefinition.effective_from.desc(),
                CashFlowBridgeRuleDefinition.created_at.desc(),
            )
        )
        return list(rows.scalars().all())

    async def get_bridge_rule(
        self, *, tenant_id: uuid.UUID, rule_id: uuid.UUID
    ) -> CashFlowBridgeRuleDefinition | None:
        row = await self._session.execute(
            select(CashFlowBridgeRuleDefinition).where(
                CashFlowBridgeRuleDefinition.tenant_id == tenant_id,
                CashFlowBridgeRuleDefinition.id == rule_id,
            )
        )
        return row.scalar_one_or_none()

    async def list_bridge_rule_versions(
        self, *, tenant_id: uuid.UUID, rule_id: uuid.UUID
    ) -> list[CashFlowBridgeRuleDefinition]:
        current = await self.get_bridge_rule(tenant_id=tenant_id, rule_id=rule_id)
        if current is None:
            return []
        rows = await self._session.execute(
            select(CashFlowBridgeRuleDefinition)
            .where(
                CashFlowBridgeRuleDefinition.tenant_id == tenant_id,
                CashFlowBridgeRuleDefinition.organisation_id == current.organisation_id,
                CashFlowBridgeRuleDefinition.rule_code == current.rule_code,
            )
            .order_by(
                CashFlowBridgeRuleDefinition.effective_from.desc(),
                CashFlowBridgeRuleDefinition.created_at.desc(),
                CashFlowBridgeRuleDefinition.id.desc(),
            )
        )
        return list(rows.scalars().all())

    async def active_bridge_rules(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        reporting_period: date,
    ) -> list[CashFlowBridgeRuleDefinition]:
        rows = await self._session.execute(
            select(CashFlowBridgeRuleDefinition)
            .where(
                CashFlowBridgeRuleDefinition.tenant_id == tenant_id,
                CashFlowBridgeRuleDefinition.organisation_id == organisation_id,
                CashFlowBridgeRuleDefinition.status == "active",
                CashFlowBridgeRuleDefinition.effective_from <= reporting_period,
                (
                    (CashFlowBridgeRuleDefinition.effective_to.is_(None))
                    | (CashFlowBridgeRuleDefinition.effective_to >= reporting_period)
                ),
            )
            .order_by(
                CashFlowBridgeRuleDefinition.rule_code.asc(),
                CashFlowBridgeRuleDefinition.id.asc(),
            )
        )
        return list(rows.scalars().all())

    async def bridge_rules_by_version_token(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        version_token: str,
    ) -> list[CashFlowBridgeRuleDefinition]:
        rows = await self._session.execute(
            select(CashFlowBridgeRuleDefinition)
            .where(
                CashFlowBridgeRuleDefinition.tenant_id == tenant_id,
                CashFlowBridgeRuleDefinition.organisation_id == organisation_id,
                CashFlowBridgeRuleDefinition.version_token == version_token,
            )
            .order_by(CashFlowBridgeRuleDefinition.id.asc())
        )
        return list(rows.scalars().all())

    async def get_consolidation_run(
        self, *, tenant_id: uuid.UUID, run_id: uuid.UUID
    ) -> MultiEntityConsolidationRun | None:
        row = await self._session.execute(
            select(MultiEntityConsolidationRun).where(
                MultiEntityConsolidationRun.tenant_id == tenant_id,
                MultiEntityConsolidationRun.id == run_id,
            )
        )
        return row.scalar_one_or_none()

    async def get_fx_translation_run(
        self, *, tenant_id: uuid.UUID, run_id: uuid.UUID
    ) -> FxTranslationRun | None:
        row = await self._session.execute(
            select(FxTranslationRun).where(
                FxTranslationRun.tenant_id == tenant_id,
                FxTranslationRun.id == run_id,
            )
        )
        return row.scalar_one_or_none()

    async def get_ownership_run(
        self, *, tenant_id: uuid.UUID, run_id: uuid.UUID
    ) -> OwnershipConsolidationRun | None:
        row = await self._session.execute(
            select(OwnershipConsolidationRun).where(
                OwnershipConsolidationRun.tenant_id == tenant_id,
                OwnershipConsolidationRun.id == run_id,
            )
        )
        return row.scalar_one_or_none()

    async def create_run(self, **values: Any) -> CashFlowRun:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=CashFlowRun,
            tenant_id=values["tenant_id"],
            record_data={"run_token": values["run_token"]},
            values=values,
            audit=AuditEvent(
                tenant_id=values["tenant_id"],
                user_id=values["created_by"],
                action="cash_flow.run.created",
                resource_type="cash_flow_run",
                resource_name=values["run_token"],
            ),
        )

    async def get_run_by_token(
        self, *, tenant_id: uuid.UUID, run_token: str
    ) -> CashFlowRun | None:
        row = await self._session.execute(
            select(CashFlowRun).where(
                CashFlowRun.tenant_id == tenant_id,
                CashFlowRun.run_token == run_token,
            )
        )
        return row.scalar_one_or_none()

    async def get_run(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> CashFlowRun | None:
        row = await self._session.execute(
            select(CashFlowRun).where(
                CashFlowRun.tenant_id == tenant_id,
                CashFlowRun.id == run_id,
            )
        )
        return row.scalar_one_or_none()

    async def list_runs(
        self, *, tenant_id: uuid.UUID, organisation_id: uuid.UUID | None = None
    ) -> list[CashFlowRun]:
        stmt = select(CashFlowRun).where(CashFlowRun.tenant_id == tenant_id)
        if organisation_id is not None:
            stmt = stmt.where(CashFlowRun.organisation_id == organisation_id)
        rows = await self._session.execute(
            stmt.order_by(CashFlowRun.created_at.desc(), CashFlowRun.id.desc())
        )
        return list(rows.scalars().all())

    async def list_line_results(
        self, *, tenant_id: uuid.UUID, run_id: uuid.UUID
    ) -> list[CashFlowLineResult]:
        rows = await self._session.execute(
            select(CashFlowLineResult)
            .where(
                CashFlowLineResult.tenant_id == tenant_id,
                CashFlowLineResult.run_id == run_id,
            )
            .order_by(
                CashFlowLineResult.line_no.asc(),
                CashFlowLineResult.line_order.asc(),
                CashFlowLineResult.id.asc(),
            )
        )
        return list(rows.scalars().all())

    async def list_evidence(
        self, *, tenant_id: uuid.UUID, run_id: uuid.UUID
    ) -> list[CashFlowEvidenceLink]:
        rows = await self._session.execute(
            select(CashFlowEvidenceLink)
            .where(
                CashFlowEvidenceLink.tenant_id == tenant_id,
                CashFlowEvidenceLink.run_id == run_id,
            )
            .order_by(CashFlowEvidenceLink.created_at.asc(), CashFlowEvidenceLink.id.asc())
        )
        return list(rows.scalars().all())

    async def create_line_results(
        self,
        *,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
        rows: Iterable[dict[str, Any]],
        created_by: uuid.UUID,
    ) -> list[CashFlowLineResult]:
        created: list[CashFlowLineResult] = []
        for payload in rows:
            row = await AuditWriter.insert_financial_record(
                self._session,
                model_class=CashFlowLineResult,
                tenant_id=tenant_id,
                record_data={"run_id": str(run_id), "line_no": payload["line_no"]},
                values={
                    "run_id": run_id,
                    "created_by": created_by,
                    **payload,
                },
                audit=AuditEvent(
                    tenant_id=tenant_id,
                    user_id=created_by,
                    action="cash_flow.line_result.created",
                    resource_type="cash_flow_line_result",
                    resource_name=str(payload["line_code"]),
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
    ) -> list[CashFlowEvidenceLink]:
        created: list[CashFlowEvidenceLink] = []
        for payload in rows:
            row = await AuditWriter.insert_financial_record(
                self._session,
                model_class=CashFlowEvidenceLink,
                tenant_id=tenant_id,
                record_data={
                    "run_id": str(run_id),
                    "evidence_type": payload["evidence_type"],
                    "evidence_ref": payload["evidence_ref"],
                },
                values={
                    "run_id": run_id,
                    "created_by": created_by,
                    **payload,
                },
                audit=AuditEvent(
                    tenant_id=tenant_id,
                    user_id=created_by,
                    action="cash_flow.evidence.created",
                    resource_type="cash_flow_evidence_link",
                    resource_name=payload["evidence_type"],
                ),
            )
            created.append(row)
        return created

    async def list_source_consolidation_metric_results(
        self, *, tenant_id: uuid.UUID, run_id: uuid.UUID
    ) -> list[MultiEntityConsolidationMetricResult]:
        rows = await self._session.execute(
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
        return list(rows.scalars().all())

    async def list_source_fx_metric_results(
        self, *, tenant_id: uuid.UUID, run_id: uuid.UUID
    ) -> list[FxTranslatedMetricResult]:
        rows = await self._session.execute(
            select(FxTranslatedMetricResult)
            .where(
                FxTranslatedMetricResult.tenant_id == tenant_id,
                FxTranslatedMetricResult.run_id == run_id,
            )
            .order_by(FxTranslatedMetricResult.line_no.asc(), FxTranslatedMetricResult.id.asc())
        )
        return list(rows.scalars().all())

    async def list_source_ownership_metric_results(
        self, *, tenant_id: uuid.UUID, run_id: uuid.UUID
    ) -> list[OwnershipConsolidationMetricResult]:
        rows = await self._session.execute(
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
        return list(rows.scalars().all())

    async def summarize_run(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> dict[str, int]:
        line_count = await self._session.scalar(
            select(func.count()).select_from(CashFlowLineResult).where(
                CashFlowLineResult.tenant_id == tenant_id,
                CashFlowLineResult.run_id == run_id,
            )
        )
        evidence_count = await self._session.scalar(
            select(func.count()).select_from(CashFlowEvidenceLink).where(
                CashFlowEvidenceLink.tenant_id == tenant_id,
                CashFlowEvidenceLink.run_id == run_id,
            )
        )
        return {
            "line_count": int(line_count or 0),
            "evidence_count": int(evidence_count or 0),
        }
