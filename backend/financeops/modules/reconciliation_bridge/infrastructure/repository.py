from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.mis_manager import MisDataSnapshot, MisNormalizedLine
from financeops.db.models.reconciliation import GlEntry, TrialBalanceRow
from financeops.db.models.reconciliation_bridge import (
    ReconciliationEvidenceLink,
    ReconciliationException,
    ReconciliationLine,
    ReconciliationResolutionEvent,
    ReconciliationSession,
)
from financeops.modules.reconciliation_bridge.domain.entities import (
    ReconciliationComputedException,
    ReconciliationComputedLine,
)
from financeops.modules.reconciliation_bridge.domain.enums import ResolutionStatus
from financeops.services.audit_writer import AuditEvent, AuditWriter


class ReconciliationBridgeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_session_by_token(
        self, *, tenant_id: uuid.UUID, session_token: str
    ) -> ReconciliationSession | None:
        result = await self._session.execute(
            select(ReconciliationSession).where(
                ReconciliationSession.tenant_id == tenant_id,
                ReconciliationSession.session_token == session_token,
            )
        )
        return result.scalar_one_or_none()

    async def get_session(
        self, *, tenant_id: uuid.UUID, session_id: uuid.UUID
    ) -> ReconciliationSession | None:
        result = await self._session.execute(
            select(ReconciliationSession).where(
                ReconciliationSession.tenant_id == tenant_id,
                ReconciliationSession.id == session_id,
            )
        )
        return result.scalar_one_or_none()

    async def create_session(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        reconciliation_type: str,
        source_a_type: str,
        source_a_ref: str,
        source_b_type: str,
        source_b_ref: str,
        period_start: date,
        period_end: date,
        matching_rule_version: str,
        tolerance_rule_version: str,
        session_token: str,
        materiality_config_json: dict[str, Any],
        status: str,
        created_by: uuid.UUID,
    ) -> ReconciliationSession:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=ReconciliationSession,
            tenant_id=tenant_id,
            record_data={
                "reconciliation_type": reconciliation_type,
                "source_a_type": source_a_type,
                "source_a_ref": source_a_ref,
                "source_b_type": source_b_type,
                "source_b_ref": source_b_ref,
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "matching_rule_version": matching_rule_version,
                "tolerance_rule_version": tolerance_rule_version,
            },
            values={
                "organisation_id": organisation_id,
                "reconciliation_type": reconciliation_type,
                "source_a_type": source_a_type,
                "source_a_ref": source_a_ref,
                "source_b_type": source_b_type,
                "source_b_ref": source_b_ref,
                "period_start": period_start,
                "period_end": period_end,
                "matching_rule_version": matching_rule_version,
                "tolerance_rule_version": tolerance_rule_version,
                "session_token": session_token,
                "materiality_config_json": materiality_config_json,
                "status": status,
                "created_by": created_by,
            },
            audit=AuditEvent(
                tenant_id=tenant_id,
                user_id=created_by,
                action="reconciliation.session.created",
                resource_type="reconciliation_session",
                resource_name=reconciliation_type,
            ),
        )

    async def list_lines(
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

    async def list_exceptions(
        self, *, tenant_id: uuid.UUID, session_id: uuid.UUID
    ) -> list[ReconciliationException]:
        result = await self._session.execute(
            select(ReconciliationException)
            .where(
                ReconciliationException.tenant_id == tenant_id,
                ReconciliationException.session_id == session_id,
            )
            .order_by(
                ReconciliationException.created_at.asc(), ReconciliationException.id.asc()
            )
        )
        return list(result.scalars().all())

    async def get_line(self, *, tenant_id: uuid.UUID, line_id: uuid.UUID) -> ReconciliationLine | None:
        result = await self._session.execute(
            select(ReconciliationLine).where(
                ReconciliationLine.tenant_id == tenant_id,
                ReconciliationLine.id == line_id,
            )
        )
        return result.scalar_one_or_none()

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
                ReconciliationException.created_at.desc(), ReconciliationException.id.desc()
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def insert_lines(
        self,
        *,
        tenant_id: uuid.UUID,
        session_id: uuid.UUID,
        created_by: uuid.UUID,
        lines: Iterable[ReconciliationComputedLine],
    ) -> list[ReconciliationLine]:
        rows: list[ReconciliationLine] = []
        for item in lines:
            row = await AuditWriter.insert_financial_record(
                self._session,
                model_class=ReconciliationLine,
                tenant_id=tenant_id,
                record_data={
                    "session_id": str(session_id),
                    "line_key": item.line_key,
                    "variance_value": str(item.variance_value),
                    "difference_type": item.difference_type.value,
                },
                values={
                    "session_id": session_id,
                    "scope_id": None,
                    "line_key": item.line_key,
                    "comparison_dimension_json": item.comparison_dimension_json,
                    "source_a_value": item.source_a_value,
                    "source_b_value": item.source_b_value,
                    "variance_value": item.variance_value,
                    "variance_abs": item.variance_abs,
                    "variance_pct": item.variance_pct,
                    "currency_code": item.currency_code,
                    "reconciliation_status": item.reconciliation_status.value,
                    "difference_type": item.difference_type.value,
                    "materiality_flag": item.materiality_flag,
                    "explanation_hint": item.explanation_hint,
                    "created_by": created_by,
                },
            )
            rows.append(row)
        return rows

    async def insert_exception(
        self,
        *,
        tenant_id: uuid.UUID,
        session_id: uuid.UUID,
        line_id: uuid.UUID,
        exception: ReconciliationComputedException,
        created_by: uuid.UUID,
        resolution_status: ResolutionStatus = ResolutionStatus.OPEN,
    ) -> ReconciliationException:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=ReconciliationException,
            tenant_id=tenant_id,
            record_data={
                "session_id": str(session_id),
                "line_id": str(line_id),
                "exception_code": exception.exception_code,
                "severity": exception.severity.value,
                "resolution_status": resolution_status.value,
            },
            values={
                "session_id": session_id,
                "line_id": line_id,
                "exception_code": exception.exception_code,
                "severity": exception.severity.value,
                "message": exception.message,
                "owner_role": exception.owner_role,
                "resolution_status": resolution_status.value,
                "created_by": created_by,
            },
        )

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

    async def summarize_session(
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
        exceptions = await self._session.execute(
            select(func.count(ReconciliationException.id)).where(
                ReconciliationException.tenant_id == tenant_id,
                ReconciliationException.session_id == session_id,
            )
        )
        return {
            "line_count": int(total_lines or 0),
            "exception_line_count": int(exception_lines or 0),
            "exception_count": int(exceptions.scalar_one() or 0),
        }

    async def fetch_gl_source(
        self, *, tenant_id: uuid.UUID, period_start: date, period_end: date
    ) -> list[dict[str, Any]]:
        result = await self._session.execute(
            select(
                GlEntry.account_code,
                GlEntry.entity_name,
                GlEntry.currency,
                GlEntry.period_year,
                GlEntry.period_month,
                func.coalesce(func.sum(GlEntry.debit_amount - GlEntry.credit_amount), 0),
            ).where(GlEntry.tenant_id == tenant_id)
            .group_by(
                GlEntry.account_code,
                GlEntry.entity_name,
                GlEntry.currency,
                GlEntry.period_year,
                GlEntry.period_month,
            )
        )
        rows: list[dict[str, Any]] = []
        for account, entity, currency, year, month, value in result.all():
            period = date(int(year), int(month), 1)
            if period < period_start.replace(day=1) or period > period_end.replace(day=1):
                continue
            rows.append(
                {
                    "account": account,
                    "entity": entity,
                    "currency": currency,
                    "period": f"{int(year):04d}-{int(month):02d}",
                    "value": Decimal(value),
                }
            )
        rows.sort(key=lambda item: (item["account"], item["entity"], item["currency"], item["period"]))
        return rows

    async def fetch_tb_source(
        self, *, tenant_id: uuid.UUID, period_start: date, period_end: date
    ) -> list[dict[str, Any]]:
        result = await self._session.execute(
            select(
                TrialBalanceRow.account_code,
                TrialBalanceRow.entity_name,
                TrialBalanceRow.currency,
                TrialBalanceRow.period_year,
                TrialBalanceRow.period_month,
                func.coalesce(func.sum(TrialBalanceRow.closing_balance), 0),
            )
            .where(TrialBalanceRow.tenant_id == tenant_id)
            .group_by(
                TrialBalanceRow.account_code,
                TrialBalanceRow.entity_name,
                TrialBalanceRow.currency,
                TrialBalanceRow.period_year,
                TrialBalanceRow.period_month,
            )
        )
        rows: list[dict[str, Any]] = []
        for account, entity, currency, year, month, value in result.all():
            period = date(int(year), int(month), 1)
            if period < period_start.replace(day=1) or period > period_end.replace(day=1):
                continue
            rows.append(
                {
                    "account": account,
                    "entity": entity,
                    "currency": currency,
                    "period": f"{int(year):04d}-{int(month):02d}",
                    "value": Decimal(value),
                }
            )
        rows.sort(key=lambda item: (item["account"], item["entity"], item["currency"], item["period"]))
        return rows

    async def fetch_mis_source(
        self,
        *,
        tenant_id: uuid.UUID,
        source_a_ref: str,
        period_start: date,
        period_end: date,
    ) -> list[dict[str, Any]]:
        stmt = (
            select(
                MisNormalizedLine.canonical_metric_code,
                MisNormalizedLine.canonical_dimension_json,
                MisNormalizedLine.currency_code,
                MisDataSnapshot.reporting_period,
                func.coalesce(func.sum(MisNormalizedLine.period_value), 0),
            )
            .join(
                MisDataSnapshot,
                MisDataSnapshot.id == MisNormalizedLine.snapshot_id,
            )
            .where(
                MisNormalizedLine.tenant_id == tenant_id,
                MisDataSnapshot.tenant_id == tenant_id,
                MisDataSnapshot.reporting_period >= period_start,
                MisDataSnapshot.reporting_period <= period_end,
            )
            .group_by(
                MisNormalizedLine.canonical_metric_code,
                MisNormalizedLine.canonical_dimension_json,
                MisNormalizedLine.currency_code,
                MisDataSnapshot.reporting_period,
            )
        )
        snapshot_id: uuid.UUID | None = None
        try:
            snapshot_id = uuid.UUID(source_a_ref)
        except ValueError:
            snapshot_id = None
        if snapshot_id is not None:
            stmt = stmt.where(MisDataSnapshot.id == snapshot_id)

        result = await self._session.execute(stmt)
        rows: list[dict[str, Any]] = []
        for metric, dimensions, currency, reporting_period, value in result.all():
            dims = dimensions or {}
            entity = str(dims.get("legal_entity") or dims.get("entity") or "default")
            rows.append(
                {
                    "metric": metric,
                    "entity": entity,
                    "currency": currency,
                    "period": reporting_period.strftime("%Y-%m"),
                    "value": Decimal(value),
                    "dimensions": dims,
                }
            )
        rows.sort(key=lambda item: (item["metric"], item["entity"], item["currency"], item["period"]))
        return rows
