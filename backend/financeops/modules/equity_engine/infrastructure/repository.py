from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.equity_engine import (
    EquityEvidenceLink,
    EquityLineDefinition,
    EquityLineResult,
    EquityRollforwardRuleDefinition,
    EquityRun,
    EquitySourceMapping,
    EquityStatementDefinition,
    EquityStatementResult,
)
from financeops.db.models.fx_translation_reporting import FxTranslatedMetricResult, FxTranslationRun
from financeops.db.models.multi_entity_consolidation import (
    MultiEntityConsolidationMetricResult,
    MultiEntityConsolidationRun,
)
from financeops.db.models.ownership_consolidation import (
    OwnershipConsolidationMetricResult,
    OwnershipConsolidationRun,
)
from financeops.services.audit_writer import AuditEvent, AuditWriter


class EquityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_statement_definition(self, **values: Any) -> EquityStatementDefinition:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=EquityStatementDefinition,
            tenant_id=values["tenant_id"],
            record_data={"statement_code": values["statement_code"]},
            values=values,
            audit=AuditEvent(
                tenant_id=values["tenant_id"],
                user_id=values["created_by"],
                action="equity.statement_definition.created",
                resource_type="equity_statement_definition",
                resource_name=values["statement_code"],
            ),
        )

    async def list_statement_definitions(
        self, *, tenant_id: uuid.UUID, organisation_id: uuid.UUID | None = None
    ) -> list[EquityStatementDefinition]:
        stmt = select(EquityStatementDefinition).where(EquityStatementDefinition.tenant_id == tenant_id)
        if organisation_id is not None:
            stmt = stmt.where(EquityStatementDefinition.organisation_id == organisation_id)
        rows = await self._session.execute(
            stmt.order_by(
                EquityStatementDefinition.statement_code.asc(),
                EquityStatementDefinition.effective_from.desc(),
                EquityStatementDefinition.created_at.desc(),
            )
        )
        return list(rows.scalars().all())

    async def get_statement_definition(
        self, *, tenant_id: uuid.UUID, definition_id: uuid.UUID
    ) -> EquityStatementDefinition | None:
        row = await self._session.execute(
            select(EquityStatementDefinition).where(
                EquityStatementDefinition.tenant_id == tenant_id,
                EquityStatementDefinition.id == definition_id,
            )
        )
        return row.scalar_one_or_none()

    async def list_statement_definition_versions(
        self, *, tenant_id: uuid.UUID, definition_id: uuid.UUID
    ) -> list[EquityStatementDefinition]:
        current = await self.get_statement_definition(tenant_id=tenant_id, definition_id=definition_id)
        if current is None:
            return []
        rows = await self._session.execute(
            select(EquityStatementDefinition)
            .where(
                EquityStatementDefinition.tenant_id == tenant_id,
                EquityStatementDefinition.organisation_id == current.organisation_id,
                EquityStatementDefinition.statement_code == current.statement_code,
            )
            .order_by(
                EquityStatementDefinition.effective_from.desc(),
                EquityStatementDefinition.created_at.desc(),
                EquityStatementDefinition.id.desc(),
            )
        )
        return list(rows.scalars().all())

    async def active_statement_definitions(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        reporting_period: date,
    ) -> list[EquityStatementDefinition]:
        rows = await self._session.execute(
            select(EquityStatementDefinition)
            .where(
                EquityStatementDefinition.tenant_id == tenant_id,
                EquityStatementDefinition.organisation_id == organisation_id,
                EquityStatementDefinition.status == "active",
                EquityStatementDefinition.effective_from <= reporting_period,
                (
                    (EquityStatementDefinition.effective_to.is_(None))
                    | (EquityStatementDefinition.effective_to >= reporting_period)
                ),
            )
            .order_by(
                EquityStatementDefinition.statement_code.asc(),
                EquityStatementDefinition.id.asc(),
            )
        )
        return list(rows.scalars().all())

    async def create_line_definition(self, **values: Any) -> EquityLineDefinition:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=EquityLineDefinition,
            tenant_id=values["tenant_id"],
            record_data={"line_code": values["line_code"]},
            values=values,
            audit=AuditEvent(
                tenant_id=values["tenant_id"],
                user_id=values["created_by"],
                action="equity.line_definition.created",
                resource_type="equity_line_definition",
                resource_name=values["line_code"],
            ),
        )

    async def list_line_definitions(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID | None = None,
    ) -> list[EquityLineDefinition]:
        stmt = select(EquityLineDefinition).where(EquityLineDefinition.tenant_id == tenant_id)
        if organisation_id is not None:
            stmt = stmt.where(EquityLineDefinition.organisation_id == organisation_id)
        rows = await self._session.execute(
            stmt.order_by(
                EquityLineDefinition.statement_definition_id.asc(),
                EquityLineDefinition.presentation_order.asc(),
                EquityLineDefinition.created_at.desc(),
            )
        )
        return list(rows.scalars().all())

    async def active_line_definitions(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        statement_definition_id: uuid.UUID,
        reporting_period: date,
    ) -> list[EquityLineDefinition]:
        rows = await self._session.execute(
            select(EquityLineDefinition)
            .where(
                EquityLineDefinition.tenant_id == tenant_id,
                EquityLineDefinition.organisation_id == organisation_id,
                EquityLineDefinition.statement_definition_id == statement_definition_id,
                EquityLineDefinition.status == "active",
                EquityLineDefinition.effective_from <= reporting_period,
                (
                    (EquityLineDefinition.effective_to.is_(None))
                    | (EquityLineDefinition.effective_to >= reporting_period)
                ),
            )
            .order_by(EquityLineDefinition.presentation_order.asc(), EquityLineDefinition.id.asc())
        )
        return list(rows.scalars().all())

    async def line_definitions_by_ids(
        self, *, tenant_id: uuid.UUID, line_definition_ids: list[uuid.UUID]
    ) -> list[EquityLineDefinition]:
        if not line_definition_ids:
            return []
        rows = await self._session.execute(
            select(EquityLineDefinition)
            .where(
                EquityLineDefinition.tenant_id == tenant_id,
                EquityLineDefinition.id.in_(line_definition_ids),
            )
            .order_by(EquityLineDefinition.presentation_order.asc(), EquityLineDefinition.id.asc())
        )
        return list(rows.scalars().all())

    async def create_rollforward_rule(self, **values: Any) -> EquityRollforwardRuleDefinition:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=EquityRollforwardRuleDefinition,
            tenant_id=values["tenant_id"],
            record_data={"rule_code": values["rule_code"]},
            values=values,
            audit=AuditEvent(
                tenant_id=values["tenant_id"],
                user_id=values["created_by"],
                action="equity.rule.created",
                resource_type="equity_rollforward_rule_definition",
                resource_name=values["rule_code"],
            ),
        )

    async def list_rollforward_rules(
        self, *, tenant_id: uuid.UUID, organisation_id: uuid.UUID | None = None
    ) -> list[EquityRollforwardRuleDefinition]:
        stmt = select(EquityRollforwardRuleDefinition).where(EquityRollforwardRuleDefinition.tenant_id == tenant_id)
        if organisation_id is not None:
            stmt = stmt.where(EquityRollforwardRuleDefinition.organisation_id == organisation_id)
        rows = await self._session.execute(
            stmt.order_by(
                EquityRollforwardRuleDefinition.rule_code.asc(),
                EquityRollforwardRuleDefinition.effective_from.desc(),
                EquityRollforwardRuleDefinition.created_at.desc(),
            )
        )
        return list(rows.scalars().all())

    async def get_rollforward_rule(
        self, *, tenant_id: uuid.UUID, rule_id: uuid.UUID
    ) -> EquityRollforwardRuleDefinition | None:
        row = await self._session.execute(
            select(EquityRollforwardRuleDefinition).where(
                EquityRollforwardRuleDefinition.tenant_id == tenant_id,
                EquityRollforwardRuleDefinition.id == rule_id,
            )
        )
        return row.scalar_one_or_none()

    async def list_rollforward_rule_versions(
        self, *, tenant_id: uuid.UUID, rule_id: uuid.UUID
    ) -> list[EquityRollforwardRuleDefinition]:
        current = await self.get_rollforward_rule(tenant_id=tenant_id, rule_id=rule_id)
        if current is None:
            return []
        rows = await self._session.execute(
            select(EquityRollforwardRuleDefinition)
            .where(
                EquityRollforwardRuleDefinition.tenant_id == tenant_id,
                EquityRollforwardRuleDefinition.organisation_id == current.organisation_id,
                EquityRollforwardRuleDefinition.rule_code == current.rule_code,
            )
            .order_by(
                EquityRollforwardRuleDefinition.effective_from.desc(),
                EquityRollforwardRuleDefinition.created_at.desc(),
                EquityRollforwardRuleDefinition.id.desc(),
            )
        )
        return list(rows.scalars().all())

    async def active_rollforward_rules(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        reporting_period: date,
    ) -> list[EquityRollforwardRuleDefinition]:
        rows = await self._session.execute(
            select(EquityRollforwardRuleDefinition)
            .where(
                EquityRollforwardRuleDefinition.tenant_id == tenant_id,
                EquityRollforwardRuleDefinition.organisation_id == organisation_id,
                EquityRollforwardRuleDefinition.status == "active",
                EquityRollforwardRuleDefinition.effective_from <= reporting_period,
                (
                    (EquityRollforwardRuleDefinition.effective_to.is_(None))
                    | (EquityRollforwardRuleDefinition.effective_to >= reporting_period)
                ),
            )
            .order_by(
                EquityRollforwardRuleDefinition.rule_code.asc(),
                EquityRollforwardRuleDefinition.id.asc(),
            )
        )
        return list(rows.scalars().all())

    async def rollforward_rules_by_ids(
        self, *, tenant_id: uuid.UUID, rule_ids: list[uuid.UUID]
    ) -> list[EquityRollforwardRuleDefinition]:
        if not rule_ids:
            return []
        rows = await self._session.execute(
            select(EquityRollforwardRuleDefinition)
            .where(
                EquityRollforwardRuleDefinition.tenant_id == tenant_id,
                EquityRollforwardRuleDefinition.id.in_(rule_ids),
            )
            .order_by(
                EquityRollforwardRuleDefinition.rule_code.asc(),
                EquityRollforwardRuleDefinition.id.asc(),
            )
        )
        return list(rows.scalars().all())

    async def create_source_mapping(self, **values: Any) -> EquitySourceMapping:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=EquitySourceMapping,
            tenant_id=values["tenant_id"],
            record_data={"mapping_code": values["mapping_code"], "line_code": values["line_code"]},
            values=values,
            audit=AuditEvent(
                tenant_id=values["tenant_id"],
                user_id=values["created_by"],
                action="equity.mapping.created",
                resource_type="equity_source_mapping",
                resource_name=f"{values['mapping_code']}:{values['line_code']}",
            ),
        )

    async def list_source_mappings(
        self, *, tenant_id: uuid.UUID, organisation_id: uuid.UUID | None = None
    ) -> list[EquitySourceMapping]:
        stmt = select(EquitySourceMapping).where(EquitySourceMapping.tenant_id == tenant_id)
        if organisation_id is not None:
            stmt = stmt.where(EquitySourceMapping.organisation_id == organisation_id)
        rows = await self._session.execute(
            stmt.order_by(
                EquitySourceMapping.mapping_code.asc(),
                EquitySourceMapping.line_code.asc(),
                EquitySourceMapping.created_at.desc(),
            )
        )
        return list(rows.scalars().all())

    async def active_source_mappings(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        reporting_period: date,
    ) -> list[EquitySourceMapping]:
        rows = await self._session.execute(
            select(EquitySourceMapping)
            .where(
                EquitySourceMapping.tenant_id == tenant_id,
                EquitySourceMapping.organisation_id == organisation_id,
                EquitySourceMapping.status == "active",
                EquitySourceMapping.effective_from <= reporting_period,
                (
                    (EquitySourceMapping.effective_to.is_(None))
                    | (EquitySourceMapping.effective_to >= reporting_period)
                ),
            )
            .order_by(
                EquitySourceMapping.mapping_code.asc(),
                EquitySourceMapping.line_code.asc(),
                EquitySourceMapping.id.asc(),
            )
        )
        return list(rows.scalars().all())

    async def source_mappings_by_ids(
        self, *, tenant_id: uuid.UUID, mapping_ids: list[uuid.UUID]
    ) -> list[EquitySourceMapping]:
        if not mapping_ids:
            return []
        rows = await self._session.execute(
            select(EquitySourceMapping)
            .where(
                EquitySourceMapping.tenant_id == tenant_id,
                EquitySourceMapping.id.in_(mapping_ids),
            )
            .order_by(
                EquitySourceMapping.mapping_code.asc(),
                EquitySourceMapping.line_code.asc(),
                EquitySourceMapping.id.asc(),
            )
        )
        return list(rows.scalars().all())

    async def create_run(self, **values: Any) -> EquityRun:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=EquityRun,
            tenant_id=values["tenant_id"],
            record_data={"run_token": values["run_token"]},
            values=values,
            audit=AuditEvent(
                tenant_id=values["tenant_id"],
                user_id=values["created_by"],
                action="equity.run.created",
                resource_type="equity_run",
                resource_name=values["run_token"],
            ),
        )

    async def get_run_by_token(self, *, tenant_id: uuid.UUID, run_token: str) -> EquityRun | None:
        row = await self._session.execute(
            select(EquityRun).where(
                EquityRun.tenant_id == tenant_id,
                EquityRun.run_token == run_token,
            )
        )
        return row.scalar_one_or_none()

    async def get_run(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> EquityRun | None:
        row = await self._session.execute(
            select(EquityRun).where(
                EquityRun.tenant_id == tenant_id,
                EquityRun.id == run_id,
            )
        )
        return row.scalar_one_or_none()

    async def list_runs(self, *, tenant_id: uuid.UUID, organisation_id: uuid.UUID | None = None) -> list[EquityRun]:
        stmt = select(EquityRun).where(EquityRun.tenant_id == tenant_id)
        if organisation_id is not None:
            stmt = stmt.where(EquityRun.organisation_id == organisation_id)
        rows = await self._session.execute(stmt.order_by(EquityRun.created_at.desc(), EquityRun.id.desc()))
        return list(rows.scalars().all())

    async def create_line_results(
        self,
        *,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
        rows: Iterable[dict[str, Any]],
        created_by: uuid.UUID,
    ) -> list[EquityLineResult]:
        created: list[EquityLineResult] = []
        for payload in rows:
            row = await AuditWriter.insert_financial_record(
                self._session,
                model_class=EquityLineResult,
                tenant_id=tenant_id,
                record_data={"equity_run_id": str(run_id), "line_no": payload["line_no"]},
                values={"equity_run_id": run_id, "created_by": created_by, **payload},
                audit=AuditEvent(
                    tenant_id=tenant_id,
                    user_id=created_by,
                    action="equity.line_result.created",
                    resource_type="equity_line_result",
                    resource_name=str(payload["line_code"]),
                ),
            )
            created.append(row)
        return created

    async def list_line_results(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> list[EquityLineResult]:
        rows = await self._session.execute(
            select(EquityLineResult)
            .where(
                EquityLineResult.tenant_id == tenant_id,
                EquityLineResult.equity_run_id == run_id,
            )
            .order_by(EquityLineResult.line_no.asc(), EquityLineResult.id.asc())
        )
        return list(rows.scalars().all())

    async def create_statement_result(
        self,
        *,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
        total_equity_opening: Any,
        total_equity_closing: Any,
        statement_payload_json: dict[str, Any],
        created_by: uuid.UUID,
    ) -> EquityStatementResult:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=EquityStatementResult,
            tenant_id=tenant_id,
            record_data={"equity_run_id": str(run_id)},
            values={
                "equity_run_id": run_id,
                "total_equity_opening": total_equity_opening,
                "total_equity_closing": total_equity_closing,
                "statement_payload_json": statement_payload_json,
                "created_by": created_by,
            },
            audit=AuditEvent(
                tenant_id=tenant_id,
                user_id=created_by,
                action="equity.statement_result.created",
                resource_type="equity_statement_result",
                resource_name=str(run_id),
            ),
        )

    async def get_statement_result(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> EquityStatementResult | None:
        row = await self._session.execute(
            select(EquityStatementResult).where(
                EquityStatementResult.tenant_id == tenant_id,
                EquityStatementResult.equity_run_id == run_id,
            )
        )
        return row.scalar_one_or_none()

    async def create_evidence_links(
        self,
        *,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
        rows: Iterable[dict[str, Any]],
        created_by: uuid.UUID,
    ) -> list[EquityEvidenceLink]:
        created: list[EquityEvidenceLink] = []
        for payload in rows:
            row = await AuditWriter.insert_financial_record(
                self._session,
                model_class=EquityEvidenceLink,
                tenant_id=tenant_id,
                record_data={
                    "equity_run_id": str(run_id),
                    "evidence_type": payload["evidence_type"],
                    "evidence_ref": payload["evidence_ref"],
                },
                values={"equity_run_id": run_id, "created_by": created_by, **payload},
                audit=AuditEvent(
                    tenant_id=tenant_id,
                    user_id=created_by,
                    action="equity.evidence.created",
                    resource_type="equity_evidence_link",
                    resource_name=payload["evidence_type"],
                ),
            )
            created.append(row)
        return created

    async def list_evidence(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> list[EquityEvidenceLink]:
        rows = await self._session.execute(
            select(EquityEvidenceLink)
            .where(
                EquityEvidenceLink.tenant_id == tenant_id,
                EquityEvidenceLink.equity_run_id == run_id,
            )
            .order_by(EquityEvidenceLink.created_at.asc(), EquityEvidenceLink.id.asc())
        )
        return list(rows.scalars().all())

    async def get_consolidation_run(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> MultiEntityConsolidationRun | None:
        row = await self._session.execute(
            select(MultiEntityConsolidationRun).where(
                MultiEntityConsolidationRun.tenant_id == tenant_id,
                MultiEntityConsolidationRun.id == run_id,
            )
        )
        return row.scalar_one_or_none()

    async def get_fx_translation_run(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> FxTranslationRun | None:
        row = await self._session.execute(
            select(FxTranslationRun).where(
                FxTranslationRun.tenant_id == tenant_id,
                FxTranslationRun.id == run_id,
            )
        )
        return row.scalar_one_or_none()

    async def get_ownership_run(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> OwnershipConsolidationRun | None:
        row = await self._session.execute(
            select(OwnershipConsolidationRun).where(
                OwnershipConsolidationRun.tenant_id == tenant_id,
                OwnershipConsolidationRun.id == run_id,
            )
        )
        return row.scalar_one_or_none()

    async def list_source_consolidation_metric_results(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> list[MultiEntityConsolidationMetricResult]:
        rows = await self._session.execute(
            select(MultiEntityConsolidationMetricResult)
            .where(
                MultiEntityConsolidationMetricResult.tenant_id == tenant_id,
                MultiEntityConsolidationMetricResult.run_id == run_id,
            )
            .order_by(MultiEntityConsolidationMetricResult.line_no.asc(), MultiEntityConsolidationMetricResult.id.asc())
        )
        return list(rows.scalars().all())

    async def list_source_fx_metric_results(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> list[FxTranslatedMetricResult]:
        rows = await self._session.execute(
            select(FxTranslatedMetricResult)
            .where(
                FxTranslatedMetricResult.tenant_id == tenant_id,
                FxTranslatedMetricResult.run_id == run_id,
            )
            .order_by(FxTranslatedMetricResult.line_no.asc(), FxTranslatedMetricResult.id.asc())
        )
        return list(rows.scalars().all())

    async def list_source_ownership_metric_results(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> list[OwnershipConsolidationMetricResult]:
        rows = await self._session.execute(
            select(OwnershipConsolidationMetricResult)
            .where(
                OwnershipConsolidationMetricResult.tenant_id == tenant_id,
                OwnershipConsolidationMetricResult.ownership_consolidation_run_id == run_id,
            )
            .order_by(OwnershipConsolidationMetricResult.line_no.asc(), OwnershipConsolidationMetricResult.id.asc())
        )
        return list(rows.scalars().all())

    async def summarize_run(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> dict[str, int]:
        line_count = await self._session.scalar(
            select(func.count()).select_from(EquityLineResult).where(
                EquityLineResult.tenant_id == tenant_id,
                EquityLineResult.equity_run_id == run_id,
            )
        )
        evidence_count = await self._session.scalar(
            select(func.count()).select_from(EquityEvidenceLink).where(
                EquityEvidenceLink.tenant_id == tenant_id,
                EquityEvidenceLink.equity_run_id == run_id,
            )
        )
        return {
            "line_count": int(line_count or 0),
            "evidence_count": int(evidence_count or 0),
        }
