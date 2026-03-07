from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.payroll_gl_normalization import (
    GlNormalizedLine,
    NormalizationRun,
    PayrollNormalizedLine,
)
from financeops.db.models.payroll_gl_reconciliation import (
    PayrollGlReconciliationMapping,
    PayrollGlReconciliationRule,
    PayrollGlReconciliationRun,
    PayrollGlReconciliationRunScope,
)
from financeops.db.models.reconciliation_bridge import (
    ReconciliationEvidenceLink,
    ReconciliationException,
    ReconciliationLine,
    ReconciliationResolutionEvent,
    ReconciliationSession,
)
from financeops.modules.payroll_gl_reconciliation.domain.entities import (
    PayrollGlComparisonLine,
    PayrollGlComputedException,
)
from financeops.modules.payroll_gl_reconciliation.domain.enums import (
    CoreDifferenceType,
    PayrollGlRunStatus,
)
from financeops.services.audit_writer import AuditEvent, AuditWriter


class PayrollGlReconciliationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_mapping(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        mapping_code: str,
        mapping_name: str,
        payroll_metric_code: str,
        gl_account_selector_json: dict[str, Any],
        cost_center_rule_json: dict[str, Any],
        department_rule_json: dict[str, Any],
        entity_rule_json: dict[str, Any],
        effective_from: date,
        supersedes_id: uuid.UUID | None,
        status: str,
        created_by: uuid.UUID,
    ) -> PayrollGlReconciliationMapping:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=PayrollGlReconciliationMapping,
            tenant_id=tenant_id,
            record_data={
                "mapping_code": mapping_code,
                "payroll_metric_code": payroll_metric_code,
            },
            values={
                "organisation_id": organisation_id,
                "mapping_code": mapping_code,
                "mapping_name": mapping_name,
                "payroll_metric_code": payroll_metric_code,
                "gl_account_selector_json": gl_account_selector_json,
                "cost_center_rule_json": cost_center_rule_json,
                "department_rule_json": department_rule_json,
                "entity_rule_json": entity_rule_json,
                "effective_from": effective_from,
                "supersedes_id": supersedes_id,
                "status": status,
                "created_by": created_by,
            },
            audit=AuditEvent(
                tenant_id=tenant_id,
                user_id=created_by,
                action="payroll_gl_reconciliation.mapping.created",
                resource_type="payroll_gl_reconciliation_mapping",
                resource_name=mapping_code,
            ),
        )

    async def get_mapping(
        self, *, tenant_id: uuid.UUID, mapping_id: uuid.UUID
    ) -> PayrollGlReconciliationMapping | None:
        result = await self._session.execute(
            select(PayrollGlReconciliationMapping).where(
                PayrollGlReconciliationMapping.tenant_id == tenant_id,
                PayrollGlReconciliationMapping.id == mapping_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_mappings(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID | None = None,
        status: str | None = None,
    ) -> list[PayrollGlReconciliationMapping]:
        stmt = select(PayrollGlReconciliationMapping).where(
            PayrollGlReconciliationMapping.tenant_id == tenant_id
        )
        if organisation_id is not None:
            stmt = stmt.where(PayrollGlReconciliationMapping.organisation_id == organisation_id)
        if status is not None:
            stmt = stmt.where(PayrollGlReconciliationMapping.status == status)
        result = await self._session.execute(
            stmt.order_by(
                PayrollGlReconciliationMapping.mapping_code.asc(),
                PayrollGlReconciliationMapping.effective_from.desc(),
                PayrollGlReconciliationMapping.created_at.desc(),
            )
        )
        return list(result.scalars().all())

    async def list_mapping_versions(
        self, *, tenant_id: uuid.UUID, mapping_id: uuid.UUID
    ) -> list[PayrollGlReconciliationMapping]:
        current = await self.get_mapping(tenant_id=tenant_id, mapping_id=mapping_id)
        if current is None:
            return []
        result = await self._session.execute(
            select(PayrollGlReconciliationMapping)
            .where(
                PayrollGlReconciliationMapping.tenant_id == tenant_id,
                PayrollGlReconciliationMapping.organisation_id == current.organisation_id,
                PayrollGlReconciliationMapping.mapping_code == current.mapping_code,
            )
            .order_by(
                PayrollGlReconciliationMapping.effective_from.desc(),
                PayrollGlReconciliationMapping.created_at.desc(),
                PayrollGlReconciliationMapping.id.desc(),
            )
        )
        return list(result.scalars().all())

    async def active_mappings(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        reporting_period: date,
    ) -> list[PayrollGlReconciliationMapping]:
        result = await self._session.execute(
            select(PayrollGlReconciliationMapping)
            .where(
                PayrollGlReconciliationMapping.tenant_id == tenant_id,
                PayrollGlReconciliationMapping.organisation_id == organisation_id,
                PayrollGlReconciliationMapping.status == "active",
                PayrollGlReconciliationMapping.effective_from <= reporting_period,
            )
            .order_by(
                PayrollGlReconciliationMapping.mapping_code.asc(),
                PayrollGlReconciliationMapping.effective_from.desc(),
                PayrollGlReconciliationMapping.id.desc(),
            )
        )
        return list(result.scalars().all())

    async def create_rule(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        rule_code: str,
        rule_name: str,
        rule_type: str,
        tolerance_json: dict[str, Any],
        materiality_json: dict[str, Any],
        timing_window_json: dict[str, Any],
        classification_behavior_json: dict[str, Any],
        effective_from: date,
        supersedes_id: uuid.UUID | None,
        status: str,
        created_by: uuid.UUID,
    ) -> PayrollGlReconciliationRule:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=PayrollGlReconciliationRule,
            tenant_id=tenant_id,
            record_data={"rule_code": rule_code, "rule_type": rule_type},
            values={
                "organisation_id": organisation_id,
                "rule_code": rule_code,
                "rule_name": rule_name,
                "rule_type": rule_type,
                "tolerance_json": tolerance_json,
                "materiality_json": materiality_json,
                "timing_window_json": timing_window_json,
                "classification_behavior_json": classification_behavior_json,
                "effective_from": effective_from,
                "supersedes_id": supersedes_id,
                "status": status,
                "created_by": created_by,
            },
            audit=AuditEvent(
                tenant_id=tenant_id,
                user_id=created_by,
                action="payroll_gl_reconciliation.rule.created",
                resource_type="payroll_gl_reconciliation_rule",
                resource_name=rule_code,
            ),
        )

    async def get_rule(
        self, *, tenant_id: uuid.UUID, rule_id: uuid.UUID
    ) -> PayrollGlReconciliationRule | None:
        result = await self._session.execute(
            select(PayrollGlReconciliationRule).where(
                PayrollGlReconciliationRule.tenant_id == tenant_id,
                PayrollGlReconciliationRule.id == rule_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_rules(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID | None = None,
        status: str | None = None,
    ) -> list[PayrollGlReconciliationRule]:
        stmt = select(PayrollGlReconciliationRule).where(
            PayrollGlReconciliationRule.tenant_id == tenant_id
        )
        if organisation_id is not None:
            stmt = stmt.where(PayrollGlReconciliationRule.organisation_id == organisation_id)
        if status is not None:
            stmt = stmt.where(PayrollGlReconciliationRule.status == status)
        result = await self._session.execute(
            stmt.order_by(
                PayrollGlReconciliationRule.rule_code.asc(),
                PayrollGlReconciliationRule.effective_from.desc(),
                PayrollGlReconciliationRule.created_at.desc(),
            )
        )
        return list(result.scalars().all())

    async def list_rule_versions(
        self, *, tenant_id: uuid.UUID, rule_id: uuid.UUID
    ) -> list[PayrollGlReconciliationRule]:
        current = await self.get_rule(tenant_id=tenant_id, rule_id=rule_id)
        if current is None:
            return []
        result = await self._session.execute(
            select(PayrollGlReconciliationRule)
            .where(
                PayrollGlReconciliationRule.tenant_id == tenant_id,
                PayrollGlReconciliationRule.organisation_id == current.organisation_id,
                PayrollGlReconciliationRule.rule_code == current.rule_code,
            )
            .order_by(
                PayrollGlReconciliationRule.effective_from.desc(),
                PayrollGlReconciliationRule.created_at.desc(),
                PayrollGlReconciliationRule.id.desc(),
            )
        )
        return list(result.scalars().all())

    async def active_rules(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        reporting_period: date,
    ) -> list[PayrollGlReconciliationRule]:
        result = await self._session.execute(
            select(PayrollGlReconciliationRule)
            .where(
                PayrollGlReconciliationRule.tenant_id == tenant_id,
                PayrollGlReconciliationRule.organisation_id == organisation_id,
                PayrollGlReconciliationRule.status == "active",
                PayrollGlReconciliationRule.effective_from <= reporting_period,
            )
            .order_by(
                PayrollGlReconciliationRule.rule_code.asc(),
                PayrollGlReconciliationRule.effective_from.desc(),
                PayrollGlReconciliationRule.id.desc(),
            )
        )
        return list(result.scalars().all())

    async def get_normalization_run(
        self, *, tenant_id: uuid.UUID, run_id: uuid.UUID
    ) -> NormalizationRun | None:
        result = await self._session.execute(
            select(NormalizationRun).where(
                NormalizationRun.tenant_id == tenant_id, NormalizationRun.id == run_id
            )
        )
        return result.scalar_one_or_none()

    async def list_payroll_lines(
        self, *, tenant_id: uuid.UUID, run_id: uuid.UUID
    ) -> list[PayrollNormalizedLine]:
        result = await self._session.execute(
            select(PayrollNormalizedLine)
            .where(
                PayrollNormalizedLine.tenant_id == tenant_id,
                PayrollNormalizedLine.run_id == run_id,
            )
            .order_by(PayrollNormalizedLine.row_no.asc(), PayrollNormalizedLine.id.asc())
        )
        return list(result.scalars().all())

    async def list_gl_lines(
        self, *, tenant_id: uuid.UUID, run_id: uuid.UUID
    ) -> list[GlNormalizedLine]:
        result = await self._session.execute(
            select(GlNormalizedLine)
            .where(
                GlNormalizedLine.tenant_id == tenant_id,
                GlNormalizedLine.run_id == run_id,
            )
            .order_by(GlNormalizedLine.row_no.asc(), GlNormalizedLine.id.asc())
        )
        return list(result.scalars().all())

    async def get_reconciliation_session_by_token(
        self, *, tenant_id: uuid.UUID, session_token: str
    ) -> ReconciliationSession | None:
        result = await self._session.execute(
            select(ReconciliationSession).where(
                ReconciliationSession.tenant_id == tenant_id,
                ReconciliationSession.session_token == session_token,
            )
        )
        return result.scalar_one_or_none()

    async def create_reconciliation_session(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        source_a_ref: str,
        source_b_ref: str,
        reporting_period: date,
        matching_rule_version: str,
        tolerance_rule_version: str,
        session_token: str,
        materiality_config_json: dict[str, Any],
        created_by: uuid.UUID,
    ) -> ReconciliationSession:
        period_start = reporting_period.replace(day=1)
        period_end = reporting_period
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=ReconciliationSession,
            tenant_id=tenant_id,
            record_data={
                "reconciliation_type": "payroll_gl_reconciliation",
                "source_a_ref": source_a_ref,
                "source_b_ref": source_b_ref,
                "period": reporting_period.isoformat(),
            },
            values={
                "organisation_id": organisation_id,
                "reconciliation_type": "payroll_gl_reconciliation",
                "source_a_type": "payroll_normalization_run",
                "source_a_ref": source_a_ref,
                "source_b_type": "gl_normalization_run",
                "source_b_ref": source_b_ref,
                "period_start": period_start,
                "period_end": period_end,
                "matching_rule_version": matching_rule_version,
                "tolerance_rule_version": tolerance_rule_version,
                "session_token": session_token,
                "materiality_config_json": materiality_config_json,
                "status": "created",
                "created_by": created_by,
            },
        )

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

    async def insert_reconciliation_lines(
        self,
        *,
        tenant_id: uuid.UUID,
        session_id: uuid.UUID,
        created_by: uuid.UUID,
        lines: Iterable[PayrollGlComparisonLine],
    ) -> list[ReconciliationLine]:
        rows: list[ReconciliationLine] = []
        for line in lines:
            status = "matched"
            if line.core_difference_type != CoreDifferenceType.NONE:
                status = "exception"
            row = await AuditWriter.insert_financial_record(
                self._session,
                model_class=ReconciliationLine,
                tenant_id=tenant_id,
                record_data={
                    "session_id": str(session_id),
                    "line_key": line.line_key,
                    "difference_type": line.core_difference_type.value,
                },
                values={
                    "session_id": session_id,
                    "scope_id": None,
                    "line_key": line.line_key,
                    "comparison_dimension_json": {
                        **line.comparison_dimension_json,
                        "payroll_gl_difference_type": line.payroll_difference_type.value,
                    },
                    "source_a_value": line.payroll_value,
                    "source_b_value": line.gl_value,
                    "variance_value": line.variance_value,
                    "variance_abs": line.variance_abs,
                    "variance_pct": line.variance_pct,
                    "currency_code": line.currency_code,
                    "reconciliation_status": status,
                    "difference_type": line.core_difference_type.value,
                    "materiality_flag": line.materiality_flag,
                    "explanation_hint": line.explanation_hint,
                    "created_by": created_by,
                },
            )
            rows.append(row)
        return rows

    async def list_reconciliation_lines(
        self, *, tenant_id: uuid.UUID, session_id: uuid.UUID
    ) -> list[ReconciliationLine]:
        result = await self._session.execute(
            select(ReconciliationLine)
            .where(
                ReconciliationLine.tenant_id == tenant_id,
                ReconciliationLine.session_id == session_id,
            )
            .order_by(ReconciliationLine.line_key.asc(), ReconciliationLine.id.asc())
        )
        return list(result.scalars().all())

    async def get_reconciliation_line(
        self, *, tenant_id: uuid.UUID, line_id: uuid.UUID
    ) -> ReconciliationLine | None:
        result = await self._session.execute(
            select(ReconciliationLine).where(
                ReconciliationLine.tenant_id == tenant_id,
                ReconciliationLine.id == line_id,
            )
        )
        return result.scalar_one_or_none()

    async def insert_reconciliation_exception(
        self,
        *,
        tenant_id: uuid.UUID,
        session_id: uuid.UUID,
        line_id: uuid.UUID,
        exception: PayrollGlComputedException,
        created_by: uuid.UUID,
        resolution_status: str = "open",
    ) -> ReconciliationException:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=ReconciliationException,
            tenant_id=tenant_id,
            record_data={
                "session_id": str(session_id),
                "line_id": str(line_id),
                "exception_code": exception.exception_code,
                "severity": exception.severity,
            },
            values={
                "session_id": session_id,
                "line_id": line_id,
                "exception_code": exception.exception_code,
                "severity": exception.severity,
                "message": exception.message,
                "owner_role": exception.owner_role,
                "resolution_status": resolution_status,
                "created_by": created_by,
            },
        )

    async def list_reconciliation_exceptions(
        self, *, tenant_id: uuid.UUID, session_id: uuid.UUID
    ) -> list[ReconciliationException]:
        result = await self._session.execute(
            select(ReconciliationException)
            .where(
                ReconciliationException.tenant_id == tenant_id,
                ReconciliationException.session_id == session_id,
            )
            .order_by(
                ReconciliationException.created_at.asc(),
                ReconciliationException.id.asc(),
            )
        )
        return list(result.scalars().all())

    async def get_latest_exception_for_line(
        self, *, tenant_id: uuid.UUID, line_id: uuid.UUID
    ) -> ReconciliationException | None:
        result = await self._session.execute(
            select(ReconciliationException)
            .where(
                ReconciliationException.tenant_id == tenant_id,
                ReconciliationException.line_id == line_id,
            )
            .order_by(
                ReconciliationException.created_at.desc(),
                ReconciliationException.id.desc(),
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def insert_resolution_event(
        self,
        *,
        tenant_id: uuid.UUID,
        session_id: uuid.UUID,
        line_id: uuid.UUID,
        exception_id: uuid.UUID | None,
        event_type: str,
        event_payload_json: dict[str, Any],
        actor_user_id: uuid.UUID,
    ) -> ReconciliationResolutionEvent:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=ReconciliationResolutionEvent,
            tenant_id=tenant_id,
            record_data={
                "session_id": str(session_id),
                "line_id": str(line_id),
                "event_type": event_type,
            },
            values={
                "session_id": session_id,
                "line_id": line_id,
                "exception_id": exception_id,
                "event_type": event_type,
                "event_payload_json": event_payload_json,
                "actor_user_id": actor_user_id,
            },
        )

    async def insert_evidence_link(
        self,
        *,
        tenant_id: uuid.UUID,
        session_id: uuid.UUID,
        line_id: uuid.UUID,
        evidence_type: str,
        evidence_ref: str,
        evidence_label: str,
        created_by: uuid.UUID,
    ) -> ReconciliationEvidenceLink:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=ReconciliationEvidenceLink,
            tenant_id=tenant_id,
            record_data={
                "session_id": str(session_id),
                "line_id": str(line_id),
                "evidence_type": evidence_type,
                "evidence_ref": evidence_ref,
            },
            values={
                "session_id": session_id,
                "line_id": line_id,
                "evidence_type": evidence_type,
                "evidence_ref": evidence_ref,
                "evidence_label": evidence_label,
                "created_by": created_by,
            },
        )

    async def summarize_reconciliation_session(
        self, *, tenant_id: uuid.UUID, session_id: uuid.UUID
    ) -> dict[str, Any]:
        line_counts = await self._session.execute(
            select(
                func.count(ReconciliationLine.id),
                func.count(ReconciliationLine.id).filter(
                    ReconciliationLine.reconciliation_status == "exception"
                ),
            ).where(
                ReconciliationLine.tenant_id == tenant_id,
                ReconciliationLine.session_id == session_id,
            )
        )
        total_lines, exception_lines = line_counts.one()
        exception_count = (
            await self._session.execute(
                select(func.count(ReconciliationException.id)).where(
                    ReconciliationException.tenant_id == tenant_id,
                    ReconciliationException.session_id == session_id,
                )
            )
        ).scalar_one()
        return {
            "line_count": int(total_lines or 0),
            "exception_line_count": int(exception_lines or 0),
            "exception_count": int(exception_count or 0),
        }

    async def get_payroll_gl_run_by_token(
        self, *, tenant_id: uuid.UUID, run_token: str
    ) -> PayrollGlReconciliationRun | None:
        result = await self._session.execute(
            select(PayrollGlReconciliationRun).where(
                PayrollGlReconciliationRun.tenant_id == tenant_id,
                PayrollGlReconciliationRun.run_token == run_token,
            )
        )
        return result.scalar_one_or_none()

    async def create_payroll_gl_run(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        reconciliation_session_id: uuid.UUID,
        payroll_run_id: uuid.UUID,
        gl_run_id: uuid.UUID,
        mapping_version_token: str,
        rule_version_token: str,
        reporting_period: date,
        run_token: str,
        status: PayrollGlRunStatus,
        created_by: uuid.UUID,
    ) -> PayrollGlReconciliationRun:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=PayrollGlReconciliationRun,
            tenant_id=tenant_id,
            record_data={
                "payroll_run_id": str(payroll_run_id),
                "gl_run_id": str(gl_run_id),
                "run_token": run_token,
            },
            values={
                "organisation_id": organisation_id,
                "reconciliation_session_id": reconciliation_session_id,
                "payroll_run_id": payroll_run_id,
                "gl_run_id": gl_run_id,
                "mapping_version_token": mapping_version_token,
                "rule_version_token": rule_version_token,
                "reporting_period": reporting_period,
                "run_token": run_token,
                "status": status.value,
                "created_by": created_by,
            },
        )

    async def get_payroll_gl_run(
        self, *, tenant_id: uuid.UUID, run_id: uuid.UUID
    ) -> PayrollGlReconciliationRun | None:
        result = await self._session.execute(
            select(PayrollGlReconciliationRun).where(
                PayrollGlReconciliationRun.tenant_id == tenant_id,
                PayrollGlReconciliationRun.id == run_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_payroll_gl_runs(
        self, *, tenant_id: uuid.UUID
    ) -> list[PayrollGlReconciliationRun]:
        result = await self._session.execute(
            select(PayrollGlReconciliationRun)
            .where(PayrollGlReconciliationRun.tenant_id == tenant_id)
            .order_by(
                PayrollGlReconciliationRun.created_at.desc(),
                PayrollGlReconciliationRun.id.desc(),
            )
        )
        return list(result.scalars().all())

    async def create_run_scope(
        self,
        *,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
        scope_code: str,
        scope_label: str,
        scope_json: dict[str, Any],
        created_by: uuid.UUID,
    ) -> PayrollGlReconciliationRunScope:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=PayrollGlReconciliationRunScope,
            tenant_id=tenant_id,
            record_data={"run_id": str(run_id), "scope_code": scope_code},
            values={
                "payroll_gl_reconciliation_run_id": run_id,
                "scope_code": scope_code,
                "scope_label": scope_label,
                "scope_json": scope_json,
                "created_by": created_by,
            },
        )
