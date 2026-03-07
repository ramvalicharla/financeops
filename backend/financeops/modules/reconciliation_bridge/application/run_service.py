from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from financeops.modules.reconciliation_bridge.application.exception_classification_service import (
    ExceptionClassificationService,
)
from financeops.modules.reconciliation_bridge.application.matching_service import (
    MatchingService,
)
from financeops.modules.reconciliation_bridge.domain.entities import (
    ReconciliationComputedException,
)
from financeops.modules.reconciliation_bridge.domain.enums import (
    ExceptionSeverity,
    ResolutionEventType,
    ResolutionStatus,
)
from financeops.modules.reconciliation_bridge.domain.value_objects import (
    SessionTokenInput,
)
from financeops.modules.reconciliation_bridge.infrastructure.repository import (
    ReconciliationBridgeRepository,
)
from financeops.modules.reconciliation_bridge.infrastructure.token_builder import (
    build_session_token,
)


class ReconciliationRunService:
    def __init__(
        self,
        *,
        repository: ReconciliationBridgeRepository,
        matching_service: MatchingService,
        exception_classification_service: ExceptionClassificationService,
    ) -> None:
        self._repository = repository
        self._matching_service = matching_service
        self._exception_classifier = exception_classification_service

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
        materiality_config_json: dict[str, Any],
        created_by: uuid.UUID,
    ) -> dict[str, Any]:
        if period_end < period_start:
            raise ValueError("period_end must be >= period_start")

        token = build_session_token(
            SessionTokenInput(
                tenant_id=tenant_id,
                organisation_id=organisation_id,
                reconciliation_type=reconciliation_type,
                source_a_type=source_a_type,
                source_a_ref=source_a_ref,
                source_b_type=source_b_type,
                source_b_ref=source_b_ref,
                period_start=period_start,
                period_end=period_end,
                matching_rule_version=matching_rule_version,
                tolerance_rule_version=tolerance_rule_version,
                materiality_config_json=materiality_config_json,
            )
        )
        existing = await self._repository.get_session_by_token(
            tenant_id=tenant_id, session_token=token
        )
        if existing is not None:
            return {
                "session_id": str(existing.id),
                "session_token": existing.session_token,
                "status": existing.status,
                "idempotent": True,
            }

        row = await self._repository.create_session(
            tenant_id=tenant_id,
            organisation_id=organisation_id,
            reconciliation_type=reconciliation_type,
            source_a_type=source_a_type,
            source_a_ref=source_a_ref,
            source_b_type=source_b_type,
            source_b_ref=source_b_ref,
            period_start=period_start,
            period_end=period_end,
            matching_rule_version=matching_rule_version,
            tolerance_rule_version=tolerance_rule_version,
            session_token=token,
            materiality_config_json=materiality_config_json,
            status="created",
            created_by=created_by,
        )
        return {
            "session_id": str(row.id),
            "session_token": row.session_token,
            "status": row.status,
            "idempotent": False,
        }

    async def run_session(
        self,
        *,
        tenant_id: uuid.UUID,
        session_id: uuid.UUID,
        actor_user_id: uuid.UUID,
    ) -> dict[str, Any]:
        session = await self._repository.get_session(tenant_id=tenant_id, session_id=session_id)
        if session is None:
            raise ValueError("Reconciliation session not found")

        existing_lines = await self._repository.list_lines(
            tenant_id=tenant_id, session_id=session_id
        )
        if existing_lines:
            summary = await self._repository.summarize_session(
                tenant_id=tenant_id, session_id=session_id
            )
            return {
                "session_id": str(session_id),
                "status": "completed",
                "line_count": summary["line_count"],
                "exception_count": summary["exception_count"],
                "idempotent": True,
            }

        materiality = session.materiality_config_json or {}
        if session.reconciliation_type == "gl_vs_trial_balance":
            source_a_rows = await self._repository.fetch_gl_source(
                tenant_id=tenant_id,
                period_start=session.period_start,
                period_end=session.period_end,
            )
            source_b_rows = await self._repository.fetch_tb_source(
                tenant_id=tenant_id,
                period_start=session.period_start,
                period_end=session.period_end,
            )
            computed_lines = self._matching_service.match_gl_vs_tb(
                source_a_rows=source_a_rows,
                source_b_rows=source_b_rows,
                materiality_config_json=materiality,
            )
        elif session.reconciliation_type == "mis_vs_trial_balance":
            source_a_rows = await self._repository.fetch_mis_source(
                tenant_id=tenant_id,
                source_a_ref=session.source_a_ref,
                period_start=session.period_start,
                period_end=session.period_end,
            )
            source_b_rows = await self._repository.fetch_tb_source(
                tenant_id=tenant_id,
                period_start=session.period_start,
                period_end=session.period_end,
            )
            computed_lines = self._matching_service.match_mis_vs_tb(
                source_a_rows=source_a_rows,
                source_b_rows=source_b_rows,
                materiality_config_json=materiality,
            )
        else:
            raise ValueError("Unsupported reconciliation_type")

        persisted_lines = await self._repository.insert_lines(
            tenant_id=tenant_id,
            session_id=session_id,
            created_by=actor_user_id,
            lines=computed_lines,
        )
        by_key = {line.line_key: line for line in computed_lines}
        for row in persisted_lines:
            computed = by_key[row.line_key]
            ex = self._exception_classifier.classify(computed)
            if ex is None:
                continue
            ex_row = await self._repository.insert_exception(
                tenant_id=tenant_id,
                session_id=session_id,
                line_id=row.id,
                exception=ex,
                created_by=actor_user_id,
                resolution_status=ResolutionStatus.OPEN,
            )
            await self._repository.insert_resolution_event(
                tenant_id=tenant_id,
                session_id=session_id,
                line_id=row.id,
                exception_id=ex_row.id,
                event_type=ResolutionEventType.EXCEPTION_OPENED.value,
                event_payload_json={
                    "exception_code": ex.exception_code,
                    "severity": ex.severity.value,
                },
                actor_user_id=actor_user_id,
            )

        summary = await self._repository.summarize_session(
            tenant_id=tenant_id, session_id=session_id
        )
        return {
            "session_id": str(session_id),
            "status": "completed",
            "line_count": summary["line_count"],
            "exception_count": summary["exception_count"],
            "idempotent": False,
        }

    async def get_session(
        self, *, tenant_id: uuid.UUID, session_id: uuid.UUID
    ) -> dict[str, Any] | None:
        session = await self._repository.get_session(tenant_id=tenant_id, session_id=session_id)
        if session is None:
            return None
        return {
            "id": str(session.id),
            "reconciliation_type": session.reconciliation_type,
            "source_a_type": session.source_a_type,
            "source_a_ref": session.source_a_ref,
            "source_b_type": session.source_b_type,
            "source_b_ref": session.source_b_ref,
            "period_start": session.period_start.isoformat(),
            "period_end": session.period_end.isoformat(),
            "matching_rule_version": session.matching_rule_version,
            "tolerance_rule_version": session.tolerance_rule_version,
            "session_token": session.session_token,
            "materiality_config_json": session.materiality_config_json,
            "status": session.status,
            "created_at": session.created_at.isoformat(),
        }

    async def get_summary(
        self, *, tenant_id: uuid.UUID, session_id: uuid.UUID
    ) -> dict[str, Any]:
        return await self._repository.summarize_session(
            tenant_id=tenant_id, session_id=session_id
        )

    async def list_lines(
        self, *, tenant_id: uuid.UUID, session_id: uuid.UUID
    ) -> list[dict[str, Any]]:
        rows = await self._repository.list_lines(tenant_id=tenant_id, session_id=session_id)
        return [
            {
                "id": str(row.id),
                "line_key": row.line_key,
                "comparison_dimension_json": row.comparison_dimension_json,
                "source_a_value": str(row.source_a_value),
                "source_b_value": str(row.source_b_value),
                "variance_value": str(row.variance_value),
                "variance_abs": str(row.variance_abs),
                "variance_pct": str(row.variance_pct),
                "currency_code": row.currency_code,
                "reconciliation_status": row.reconciliation_status,
                "difference_type": row.difference_type,
                "materiality_flag": row.materiality_flag,
                "explanation_hint": row.explanation_hint,
            }
            for row in rows
        ]

    async def list_exceptions(
        self, *, tenant_id: uuid.UUID, session_id: uuid.UUID
    ) -> list[dict[str, Any]]:
        rows = await self._repository.list_exceptions(
            tenant_id=tenant_id, session_id=session_id
        )
        return [
            {
                "id": str(row.id),
                "line_id": str(row.line_id),
                "exception_code": row.exception_code,
                "severity": row.severity,
                "message": row.message,
                "owner_role": row.owner_role,
                "resolution_status": row.resolution_status,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]

    async def add_explanation(
        self,
        *,
        tenant_id: uuid.UUID,
        line_id: uuid.UUID,
        explanation: str,
        actor_user_id: uuid.UUID,
    ) -> dict[str, Any]:
        line = await self._repository.get_line(tenant_id=tenant_id, line_id=line_id)
        if line is None:
            raise ValueError("Reconciliation line not found")
        event = await self._repository.insert_resolution_event(
            tenant_id=tenant_id,
            session_id=line.session_id,
            line_id=line.id,
            exception_id=None,
            event_type=ResolutionEventType.EXPLANATION_ADDED.value,
            event_payload_json={"explanation": explanation},
            actor_user_id=actor_user_id,
        )
        return {"event_id": str(event.id)}

    async def attach_evidence(
        self,
        *,
        tenant_id: uuid.UUID,
        line_id: uuid.UUID,
        evidence_type: str,
        evidence_ref: str,
        evidence_label: str,
        actor_user_id: uuid.UUID,
    ) -> dict[str, Any]:
        line = await self._repository.get_line(tenant_id=tenant_id, line_id=line_id)
        if line is None:
            raise ValueError("Reconciliation line not found")

        evidence = await self._repository.insert_evidence_link(
            tenant_id=tenant_id,
            session_id=line.session_id,
            line_id=line.id,
            evidence_type=evidence_type,
            evidence_ref=evidence_ref,
            evidence_label=evidence_label,
            created_by=actor_user_id,
        )
        await self._repository.insert_resolution_event(
            tenant_id=tenant_id,
            session_id=line.session_id,
            line_id=line.id,
            exception_id=None,
            event_type=ResolutionEventType.EVIDENCE_LINKED.value,
            event_payload_json={
                "evidence_type": evidence_type,
                "evidence_ref": evidence_ref,
            },
            actor_user_id=actor_user_id,
        )
        return {"evidence_id": str(evidence.id)}

    async def resolve_line(
        self,
        *,
        tenant_id: uuid.UUID,
        line_id: uuid.UUID,
        actor_user_id: uuid.UUID,
    ) -> dict[str, Any]:
        line = await self._repository.get_line(tenant_id=tenant_id, line_id=line_id)
        if line is None:
            raise ValueError("Reconciliation line not found")

        latest = await self._repository.get_latest_exception_for_line(
            tenant_id=tenant_id, line_id=line_id
        )
        if latest is None:
            computed = ReconciliationComputedException(
                line_key=line.line_key,
                exception_code="RECON_VALUE_MISMATCH",
                severity=ExceptionSeverity.WARNING,
                message="Manual resolution created",
                owner_role="finance_controller",
            )
        else:
            computed = ReconciliationComputedException(
                line_key=line.line_key,
                exception_code=latest.exception_code,
                severity=ExceptionSeverity(latest.severity),
                message=latest.message,
                owner_role=latest.owner_role,
            )
        ex = await self._repository.insert_exception(
            tenant_id=tenant_id,
            session_id=line.session_id,
            line_id=line.id,
            exception=computed,
            created_by=actor_user_id,
            resolution_status=ResolutionStatus.RESOLVED,
        )
        event = await self._repository.insert_resolution_event(
            tenant_id=tenant_id,
            session_id=line.session_id,
            line_id=line.id,
            exception_id=ex.id,
            event_type=ResolutionEventType.RESOLVED.value,
            event_payload_json={"resolution_status": ResolutionStatus.RESOLVED.value},
            actor_user_id=actor_user_id,
        )
        return {"exception_id": str(ex.id), "event_id": str(event.id)}

    async def reopen_line(
        self,
        *,
        tenant_id: uuid.UUID,
        line_id: uuid.UUID,
        actor_user_id: uuid.UUID,
    ) -> dict[str, Any]:
        line = await self._repository.get_line(tenant_id=tenant_id, line_id=line_id)
        if line is None:
            raise ValueError("Reconciliation line not found")
        latest = await self._repository.get_latest_exception_for_line(
            tenant_id=tenant_id, line_id=line_id
        )
        if latest is None:
            raise ValueError("No exception exists for line")
        computed = ReconciliationComputedException(
            line_key=line.line_key,
            exception_code=latest.exception_code,
            severity=ExceptionSeverity(latest.severity),
            message=latest.message,
            owner_role=latest.owner_role,
        )
        ex = await self._repository.insert_exception(
            tenant_id=tenant_id,
            session_id=line.session_id,
            line_id=line.id,
            exception=computed,
            created_by=actor_user_id,
            resolution_status=ResolutionStatus.REOPENED,
        )
        event = await self._repository.insert_resolution_event(
            tenant_id=tenant_id,
            session_id=line.session_id,
            line_id=line.id,
            exception_id=ex.id,
            event_type=ResolutionEventType.REOPENED.value,
            event_payload_json={"resolution_status": ResolutionStatus.REOPENED.value},
            actor_user_id=actor_user_id,
        )
        return {"exception_id": str(ex.id), "event_id": str(event.id)}
