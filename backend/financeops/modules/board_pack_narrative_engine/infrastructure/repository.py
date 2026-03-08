from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.anomaly_pattern_engine import AnomalyResult, AnomalyRun
from financeops.db.models.board_pack_narrative_engine import (
    BoardPackDefinition,
    BoardPackEvidenceLink,
    BoardPackInclusionRule,
    BoardPackNarrativeBlock,
    BoardPackResult,
    BoardPackRun,
    BoardPackSectionDefinition,
    BoardPackSectionResult,
    NarrativeTemplate,
)
from financeops.db.models.financial_risk_engine import RiskResult, RiskRun
from financeops.db.models.ratio_variance_engine import (
    MetricResult,
    MetricRun,
    TrendResult,
    VarianceResult,
)
from financeops.modules.board_pack_narrative_engine.domain.entities import (
    ComputedBoardPack,
    ComputedNarrativeBlock,
    ComputedSection,
)
from financeops.services.audit_writer import AuditEvent, AuditWriter


class BoardPackNarrativeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_board_pack_definition(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        board_pack_code: str,
        board_pack_name: str,
        audience_scope: str,
        section_order_json: dict[str, Any],
        inclusion_config_json: dict[str, Any],
        version_token: str,
        effective_from: date,
        effective_to: date | None,
        supersedes_id: uuid.UUID | None,
        status: str,
        created_by: uuid.UUID,
    ) -> BoardPackDefinition:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=BoardPackDefinition,
            tenant_id=tenant_id,
            record_data={"board_pack_code": board_pack_code},
            values={
                "organisation_id": organisation_id,
                "board_pack_code": board_pack_code,
                "board_pack_name": board_pack_name,
                "audience_scope": audience_scope,
                "section_order_json": section_order_json,
                "inclusion_config_json": inclusion_config_json,
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
                action="board_pack.definition.created",
                resource_type="board_pack_definition",
                resource_name=board_pack_code,
            ),
        )

    async def list_board_pack_definitions(self, *, tenant_id: uuid.UUID) -> list[BoardPackDefinition]:
        result = await self._session.execute(
            select(BoardPackDefinition)
            .where(BoardPackDefinition.tenant_id == tenant_id)
            .order_by(
                BoardPackDefinition.board_pack_code.asc(),
                BoardPackDefinition.effective_from.desc(),
                BoardPackDefinition.created_at.desc(),
            )
        )
        return list(result.scalars().all())

    async def get_board_pack_definition(
        self, *, tenant_id: uuid.UUID, definition_id: uuid.UUID
    ) -> BoardPackDefinition | None:
        result = await self._session.execute(
            select(BoardPackDefinition).where(
                BoardPackDefinition.tenant_id == tenant_id,
                BoardPackDefinition.id == definition_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_board_pack_definition_versions(
        self, *, tenant_id: uuid.UUID, definition_id: uuid.UUID
    ) -> list[BoardPackDefinition]:
        current = await self.get_board_pack_definition(tenant_id=tenant_id, definition_id=definition_id)
        if current is None:
            return []
        result = await self._session.execute(
            select(BoardPackDefinition)
            .where(
                BoardPackDefinition.tenant_id == tenant_id,
                BoardPackDefinition.organisation_id == current.organisation_id,
                BoardPackDefinition.board_pack_code == current.board_pack_code,
            )
            .order_by(
                BoardPackDefinition.effective_from.desc(),
                BoardPackDefinition.created_at.desc(),
                BoardPackDefinition.id.desc(),
            )
        )
        return list(result.scalars().all())

    async def create_section_definition(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        section_code: str,
        section_name: str,
        section_type: str,
        render_logic_json: dict[str, Any],
        section_order_default: int,
        narrative_template_ref: str | None,
        risk_inclusion_rule_json: dict[str, Any],
        anomaly_inclusion_rule_json: dict[str, Any],
        metric_inclusion_rule_json: dict[str, Any],
        version_token: str,
        effective_from: date,
        effective_to: date | None,
        supersedes_id: uuid.UUID | None,
        status: str,
        created_by: uuid.UUID,
    ) -> BoardPackSectionDefinition:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=BoardPackSectionDefinition,
            tenant_id=tenant_id,
            record_data={"section_code": section_code},
            values={
                "organisation_id": organisation_id,
                "section_code": section_code,
                "section_name": section_name,
                "section_type": section_type,
                "render_logic_json": render_logic_json,
                "section_order_default": section_order_default,
                "narrative_template_ref": narrative_template_ref,
                "risk_inclusion_rule_json": risk_inclusion_rule_json,
                "anomaly_inclusion_rule_json": anomaly_inclusion_rule_json,
                "metric_inclusion_rule_json": metric_inclusion_rule_json,
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
                action="board_pack.section_definition.created",
                resource_type="board_pack_section_definition",
                resource_name=section_code,
            ),
        )

    async def list_section_definitions(self, *, tenant_id: uuid.UUID) -> list[BoardPackSectionDefinition]:
        result = await self._session.execute(
            select(BoardPackSectionDefinition)
            .where(BoardPackSectionDefinition.tenant_id == tenant_id)
            .order_by(
                BoardPackSectionDefinition.section_code.asc(),
                BoardPackSectionDefinition.effective_from.desc(),
                BoardPackSectionDefinition.created_at.desc(),
            )
        )
        return list(result.scalars().all())

    async def get_section_definition(
        self, *, tenant_id: uuid.UUID, section_id: uuid.UUID
    ) -> BoardPackSectionDefinition | None:
        result = await self._session.execute(
            select(BoardPackSectionDefinition).where(
                BoardPackSectionDefinition.tenant_id == tenant_id,
                BoardPackSectionDefinition.id == section_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_section_definition_versions(
        self, *, tenant_id: uuid.UUID, section_id: uuid.UUID
    ) -> list[BoardPackSectionDefinition]:
        current = await self.get_section_definition(tenant_id=tenant_id, section_id=section_id)
        if current is None:
            return []
        result = await self._session.execute(
            select(BoardPackSectionDefinition)
            .where(
                BoardPackSectionDefinition.tenant_id == tenant_id,
                BoardPackSectionDefinition.organisation_id == current.organisation_id,
                BoardPackSectionDefinition.section_code == current.section_code,
            )
            .order_by(
                BoardPackSectionDefinition.effective_from.desc(),
                BoardPackSectionDefinition.created_at.desc(),
                BoardPackSectionDefinition.id.desc(),
            )
        )
        return list(result.scalars().all())

    async def create_narrative_template(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        template_code: str,
        template_name: str,
        template_type: str,
        template_text: str,
        template_body_json: dict[str, Any],
        placeholder_schema_json: dict[str, Any],
        version_token: str,
        effective_from: date,
        effective_to: date | None,
        supersedes_id: uuid.UUID | None,
        status: str,
        created_by: uuid.UUID,
    ) -> NarrativeTemplate:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=NarrativeTemplate,
            tenant_id=tenant_id,
            record_data={"template_code": template_code},
            values={
                "organisation_id": organisation_id,
                "template_code": template_code,
                "template_name": template_name,
                "template_type": template_type,
                "template_text": template_text,
                "template_body_json": template_body_json,
                "placeholder_schema_json": placeholder_schema_json,
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
                action="board_pack.narrative_template.created",
                resource_type="narrative_template",
                resource_name=template_code,
            ),
        )

    async def list_narrative_templates(self, *, tenant_id: uuid.UUID) -> list[NarrativeTemplate]:
        result = await self._session.execute(
            select(NarrativeTemplate)
            .where(NarrativeTemplate.tenant_id == tenant_id)
            .order_by(
                NarrativeTemplate.template_code.asc(),
                NarrativeTemplate.effective_from.desc(),
                NarrativeTemplate.created_at.desc(),
            )
        )
        return list(result.scalars().all())

    async def get_narrative_template(
        self, *, tenant_id: uuid.UUID, template_id: uuid.UUID
    ) -> NarrativeTemplate | None:
        result = await self._session.execute(
            select(NarrativeTemplate).where(
                NarrativeTemplate.tenant_id == tenant_id,
                NarrativeTemplate.id == template_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_narrative_template_versions(
        self, *, tenant_id: uuid.UUID, template_id: uuid.UUID
    ) -> list[NarrativeTemplate]:
        current = await self.get_narrative_template(tenant_id=tenant_id, template_id=template_id)
        if current is None:
            return []
        result = await self._session.execute(
            select(NarrativeTemplate)
            .where(
                NarrativeTemplate.tenant_id == tenant_id,
                NarrativeTemplate.organisation_id == current.organisation_id,
                NarrativeTemplate.template_code == current.template_code,
            )
            .order_by(
                NarrativeTemplate.effective_from.desc(),
                NarrativeTemplate.created_at.desc(),
                NarrativeTemplate.id.desc(),
            )
        )
        return list(result.scalars().all())

    async def create_inclusion_rule(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        rule_code: str,
        rule_name: str,
        rule_type: str,
        inclusion_logic_json: dict[str, Any],
        version_token: str,
        effective_from: date,
        effective_to: date | None,
        supersedes_id: uuid.UUID | None,
        status: str,
        created_by: uuid.UUID,
    ) -> BoardPackInclusionRule:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=BoardPackInclusionRule,
            tenant_id=tenant_id,
            record_data={"rule_code": rule_code},
            values={
                "organisation_id": organisation_id,
                "rule_code": rule_code,
                "rule_name": rule_name,
                "rule_type": rule_type,
                "inclusion_logic_json": inclusion_logic_json,
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
                action="board_pack.inclusion_rule.created",
                resource_type="board_pack_inclusion_rule",
                resource_name=rule_code,
            ),
        )

    async def list_inclusion_rules(self, *, tenant_id: uuid.UUID) -> list[BoardPackInclusionRule]:
        result = await self._session.execute(
            select(BoardPackInclusionRule)
            .where(BoardPackInclusionRule.tenant_id == tenant_id)
            .order_by(
                BoardPackInclusionRule.rule_code.asc(),
                BoardPackInclusionRule.effective_from.desc(),
                BoardPackInclusionRule.created_at.desc(),
            )
        )
        return list(result.scalars().all())

    async def get_inclusion_rule(
        self, *, tenant_id: uuid.UUID, rule_id: uuid.UUID
    ) -> BoardPackInclusionRule | None:
        result = await self._session.execute(
            select(BoardPackInclusionRule).where(
                BoardPackInclusionRule.tenant_id == tenant_id,
                BoardPackInclusionRule.id == rule_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_inclusion_rule_versions(
        self, *, tenant_id: uuid.UUID, rule_id: uuid.UUID
    ) -> list[BoardPackInclusionRule]:
        current = await self.get_inclusion_rule(tenant_id=tenant_id, rule_id=rule_id)
        if current is None:
            return []
        result = await self._session.execute(
            select(BoardPackInclusionRule)
            .where(
                BoardPackInclusionRule.tenant_id == tenant_id,
                BoardPackInclusionRule.organisation_id == current.organisation_id,
                BoardPackInclusionRule.rule_code == current.rule_code,
            )
            .order_by(
                BoardPackInclusionRule.effective_from.desc(),
                BoardPackInclusionRule.created_at.desc(),
                BoardPackInclusionRule.id.desc(),
            )
        )
        return list(result.scalars().all())

    async def active_board_pack_definitions(
        self, *, tenant_id: uuid.UUID, organisation_id: uuid.UUID, reporting_period: date
    ) -> list[BoardPackDefinition]:
        result = await self._session.execute(
            select(BoardPackDefinition)
            .where(
                BoardPackDefinition.tenant_id == tenant_id,
                BoardPackDefinition.organisation_id == organisation_id,
                BoardPackDefinition.status == "active",
                BoardPackDefinition.effective_from <= reporting_period,
                (BoardPackDefinition.effective_to.is_(None))
                | (BoardPackDefinition.effective_to >= reporting_period),
            )
            .order_by(BoardPackDefinition.board_pack_code.asc(), BoardPackDefinition.id.asc())
        )
        return list(result.scalars().all())

    async def active_section_definitions(
        self, *, tenant_id: uuid.UUID, organisation_id: uuid.UUID, reporting_period: date
    ) -> list[BoardPackSectionDefinition]:
        result = await self._session.execute(
            select(BoardPackSectionDefinition)
            .where(
                BoardPackSectionDefinition.tenant_id == tenant_id,
                BoardPackSectionDefinition.organisation_id == organisation_id,
                BoardPackSectionDefinition.status == "active",
                BoardPackSectionDefinition.effective_from <= reporting_period,
                (BoardPackSectionDefinition.effective_to.is_(None))
                | (BoardPackSectionDefinition.effective_to >= reporting_period),
            )
            .order_by(
                BoardPackSectionDefinition.section_order_default.asc(),
                BoardPackSectionDefinition.section_code.asc(),
                BoardPackSectionDefinition.id.asc(),
            )
        )
        return list(result.scalars().all())

    async def active_narrative_templates(
        self, *, tenant_id: uuid.UUID, organisation_id: uuid.UUID, reporting_period: date
    ) -> list[NarrativeTemplate]:
        result = await self._session.execute(
            select(NarrativeTemplate)
            .where(
                NarrativeTemplate.tenant_id == tenant_id,
                NarrativeTemplate.organisation_id == organisation_id,
                NarrativeTemplate.status == "active",
                NarrativeTemplate.effective_from <= reporting_period,
                (NarrativeTemplate.effective_to.is_(None))
                | (NarrativeTemplate.effective_to >= reporting_period),
            )
            .order_by(NarrativeTemplate.template_code.asc(), NarrativeTemplate.id.asc())
        )
        return list(result.scalars().all())

    async def active_inclusion_rules(
        self, *, tenant_id: uuid.UUID, organisation_id: uuid.UUID, reporting_period: date
    ) -> list[BoardPackInclusionRule]:
        result = await self._session.execute(
            select(BoardPackInclusionRule)
            .where(
                BoardPackInclusionRule.tenant_id == tenant_id,
                BoardPackInclusionRule.organisation_id == organisation_id,
                BoardPackInclusionRule.status == "active",
                BoardPackInclusionRule.effective_from <= reporting_period,
                (BoardPackInclusionRule.effective_to.is_(None))
                | (BoardPackInclusionRule.effective_to >= reporting_period),
            )
            .order_by(BoardPackInclusionRule.rule_code.asc(), BoardPackInclusionRule.id.asc())
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

    async def get_anomaly_run(
        self, *, tenant_id: uuid.UUID, run_id: uuid.UUID
    ) -> AnomalyRun | None:
        result = await self._session.execute(
            select(AnomalyRun).where(AnomalyRun.tenant_id == tenant_id, AnomalyRun.id == run_id)
        )
        return result.scalar_one_or_none()

    async def list_anomaly_runs(
        self, *, tenant_id: uuid.UUID, run_ids: list[uuid.UUID]
    ) -> list[AnomalyRun]:
        if not run_ids:
            return []
        result = await self._session.execute(
            select(AnomalyRun)
            .where(AnomalyRun.tenant_id == tenant_id, AnomalyRun.id.in_(run_ids))
            .order_by(AnomalyRun.id.asc())
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

    async def list_anomaly_results_for_runs(
        self, *, tenant_id: uuid.UUID, run_ids: list[uuid.UUID]
    ) -> list[AnomalyResult]:
        if not run_ids:
            return []
        result = await self._session.execute(
            select(AnomalyResult)
            .where(AnomalyResult.tenant_id == tenant_id, AnomalyResult.run_id.in_(run_ids))
            .order_by(
                AnomalyResult.run_id.asc(),
                AnomalyResult.anomaly_code.asc(),
                AnomalyResult.id.asc(),
            )
        )
        return list(result.scalars().all())

    async def get_board_pack_run_by_token(
        self, *, tenant_id: uuid.UUID, run_token: str
    ) -> BoardPackRun | None:
        result = await self._session.execute(
            select(BoardPackRun).where(
                BoardPackRun.tenant_id == tenant_id, BoardPackRun.run_token == run_token
            )
        )
        return result.scalar_one_or_none()

    async def create_board_pack_run(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        reporting_period: date,
        board_pack_definition_version_token: str,
        section_definition_version_token: str,
        narrative_template_version_token: str,
        inclusion_rule_version_token: str,
        source_metric_run_ids_json: list[str],
        source_risk_run_ids_json: list[str],
        source_anomaly_run_ids_json: list[str],
        run_token: str,
        status: str,
        validation_summary_json: dict[str, Any],
        created_by: uuid.UUID,
    ) -> BoardPackRun:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=BoardPackRun,
            tenant_id=tenant_id,
            record_data={"run_token": run_token, "status": status},
            values={
                "organisation_id": organisation_id,
                "reporting_period": reporting_period,
                "board_pack_definition_version_token": board_pack_definition_version_token,
                "section_definition_version_token": section_definition_version_token,
                "narrative_template_version_token": narrative_template_version_token,
                "inclusion_rule_version_token": inclusion_rule_version_token,
                "source_metric_run_ids_json": source_metric_run_ids_json,
                "source_risk_run_ids_json": source_risk_run_ids_json,
                "source_anomaly_run_ids_json": source_anomaly_run_ids_json,
                "run_token": run_token,
                "status": status,
                "validation_summary_json": validation_summary_json,
                "created_by": created_by,
            },
            audit=AuditEvent(
                tenant_id=tenant_id,
                user_id=created_by,
                action="board_pack.run.created",
                resource_type="board_pack_run",
                resource_name=run_token,
            ),
        )

    async def get_board_pack_run(
        self, *, tenant_id: uuid.UUID, run_id: uuid.UUID
    ) -> BoardPackRun | None:
        result = await self._session.execute(
            select(BoardPackRun).where(BoardPackRun.tenant_id == tenant_id, BoardPackRun.id == run_id)
        )
        return result.scalar_one_or_none()

    async def create_board_pack_result(
        self,
        *,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
        reporting_period: date,
        row: ComputedBoardPack,
        created_by: uuid.UUID,
    ) -> BoardPackResult:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=BoardPackResult,
            tenant_id=tenant_id,
            record_data={"run_id": str(run_id), "board_pack_code": row.board_pack_code},
            values={
                "run_id": run_id,
                "board_pack_code": row.board_pack_code,
                "reporting_period": reporting_period,
                "status": row.status,
                "executive_summary_text": row.executive_summary_text,
                "overall_health_classification": row.overall_health_classification,
                "created_by": created_by,
            },
            audit=AuditEvent(
                tenant_id=tenant_id,
                user_id=created_by,
                action="board_pack.result.created",
                resource_type="board_pack_result",
                resource_name=row.board_pack_code,
            ),
        )

    async def insert_section_results(
        self,
        *,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
        rows: Iterable[ComputedSection],
        created_by: uuid.UUID,
    ) -> list[BoardPackSectionResult]:
        inserted: list[BoardPackSectionResult] = []
        for row in rows:
            inserted.append(
                await AuditWriter.insert_financial_record(
                    self._session,
                    model_class=BoardPackSectionResult,
                    tenant_id=tenant_id,
                    record_data={"run_id": str(run_id), "section_code": row.section_code},
                    values={
                        "run_id": run_id,
                        "section_code": row.section_code,
                        "section_order": row.section_order,
                        "section_title": row.section_title,
                        "section_summary_text": row.section_summary_text,
                        "section_payload_json": row.section_payload_json,
                        "created_by": created_by,
                    },
                    audit=AuditEvent(
                        tenant_id=tenant_id,
                        user_id=created_by,
                        action="board_pack.section_result.created",
                        resource_type="board_pack_section_result",
                        resource_name=row.section_code,
                    ),
                )
            )
        return inserted

    async def insert_narrative_blocks(
        self,
        *,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
        section_result_id: uuid.UUID,
        rows: Iterable[ComputedNarrativeBlock],
        created_by: uuid.UUID,
    ) -> list[BoardPackNarrativeBlock]:
        inserted: list[BoardPackNarrativeBlock] = []
        for row in rows:
            inserted.append(
                await AuditWriter.insert_financial_record(
                    self._session,
                    model_class=BoardPackNarrativeBlock,
                    tenant_id=tenant_id,
                    record_data={
                        "run_id": str(run_id),
                        "section_result_id": str(section_result_id),
                        "narrative_template_code": row.narrative_template_code,
                    },
                    values={
                        "run_id": run_id,
                        "section_result_id": section_result_id,
                        "narrative_template_code": row.narrative_template_code,
                        "narrative_text": row.narrative_text,
                        "narrative_payload_json": row.narrative_payload_json,
                        "block_order": row.block_order,
                        "created_by": created_by,
                    },
                    audit=AuditEvent(
                        tenant_id=tenant_id,
                        user_id=created_by,
                        action="board_pack.narrative_block.created",
                        resource_type="board_pack_narrative_block",
                        resource_name=row.narrative_template_code,
                    ),
                )
            )
        return inserted

    async def insert_evidence_links(
        self,
        *,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
        rows: list[dict[str, Any]],
        created_by: uuid.UUID,
    ) -> list[BoardPackEvidenceLink]:
        inserted: list[BoardPackEvidenceLink] = []
        for row in rows:
            inserted.append(
                await AuditWriter.insert_financial_record(
                    self._session,
                    model_class=BoardPackEvidenceLink,
                    tenant_id=tenant_id,
                    record_data={
                        "run_id": str(run_id),
                        "evidence_type": row["evidence_type"],
                        "evidence_ref": row["evidence_ref"],
                    },
                    values={
                        "run_id": run_id,
                        "section_result_id": row.get("section_result_id"),
                        "narrative_block_id": row.get("narrative_block_id"),
                        "evidence_type": row["evidence_type"],
                        "evidence_ref": row["evidence_ref"],
                        "evidence_label": row["evidence_label"],
                        "evidence_payload_json": row.get("evidence_payload_json", {}),
                        "board_attention_flag": bool(row.get("board_attention_flag", False)),
                        "severity_rank": Decimal(str(row.get("severity_rank", "0"))),
                        "created_by": created_by,
                    },
                    audit=AuditEvent(
                        tenant_id=tenant_id,
                        user_id=created_by,
                        action="board_pack.evidence_link.created",
                        resource_type="board_pack_evidence_link",
                        resource_name=row["evidence_type"],
                    ),
                )
            )
        return inserted

    async def list_section_results(
        self, *, tenant_id: uuid.UUID, run_id: uuid.UUID
    ) -> list[BoardPackSectionResult]:
        result = await self._session.execute(
            select(BoardPackSectionResult)
            .where(
                BoardPackSectionResult.tenant_id == tenant_id,
                BoardPackSectionResult.run_id == run_id,
            )
            .order_by(BoardPackSectionResult.section_order.asc(), BoardPackSectionResult.id.asc())
        )
        return list(result.scalars().all())

    async def list_narrative_blocks(
        self, *, tenant_id: uuid.UUID, run_id: uuid.UUID
    ) -> list[BoardPackNarrativeBlock]:
        result = await self._session.execute(
            select(BoardPackNarrativeBlock)
            .where(
                BoardPackNarrativeBlock.tenant_id == tenant_id,
                BoardPackNarrativeBlock.run_id == run_id,
            )
            .order_by(
                BoardPackNarrativeBlock.section_result_id.asc(),
                BoardPackNarrativeBlock.block_order.asc(),
                BoardPackNarrativeBlock.id.asc(),
            )
        )
        return list(result.scalars().all())

    async def list_evidence_links(
        self, *, tenant_id: uuid.UUID, run_id: uuid.UUID
    ) -> list[BoardPackEvidenceLink]:
        result = await self._session.execute(
            select(BoardPackEvidenceLink)
            .where(
                BoardPackEvidenceLink.tenant_id == tenant_id,
                BoardPackEvidenceLink.run_id == run_id,
            )
            .order_by(
                BoardPackEvidenceLink.board_attention_flag.desc(),
                BoardPackEvidenceLink.severity_rank.desc(),
                BoardPackEvidenceLink.id.asc(),
            )
        )
        return list(result.scalars().all())

    async def get_board_pack_result(
        self, *, tenant_id: uuid.UUID, run_id: uuid.UUID
    ) -> BoardPackResult | None:
        result = await self._session.execute(
            select(BoardPackResult).where(
                BoardPackResult.tenant_id == tenant_id, BoardPackResult.run_id == run_id
            )
        )
        return result.scalar_one_or_none()

    async def summarize_run(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> dict[str, int]:
        row = (
            await self._session.execute(
                select(
                    select(func.count())
                    .select_from(BoardPackSectionResult)
                    .where(
                        BoardPackSectionResult.tenant_id == tenant_id,
                        BoardPackSectionResult.run_id == run_id,
                    )
                    .scalar_subquery()
                    .label("section_count"),
                    select(func.count())
                    .select_from(BoardPackNarrativeBlock)
                    .where(
                        BoardPackNarrativeBlock.tenant_id == tenant_id,
                        BoardPackNarrativeBlock.run_id == run_id,
                    )
                    .scalar_subquery()
                    .label("narrative_count"),
                    select(func.count())
                    .select_from(BoardPackEvidenceLink)
                    .where(
                        BoardPackEvidenceLink.tenant_id == tenant_id,
                        BoardPackEvidenceLink.run_id == run_id,
                    )
                    .scalar_subquery()
                    .label("evidence_count"),
                )
            )
        ).one()
        return {
            "section_count": int(row.section_count or 0),
            "narrative_count": int(row.narrative_count or 0),
            "evidence_count": int(row.evidence_count or 0),
        }
