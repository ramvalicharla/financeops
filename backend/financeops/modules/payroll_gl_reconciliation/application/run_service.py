from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from financeops.modules.payroll_gl_reconciliation.application.classification_service import (
    ClassificationService,
)
from financeops.modules.payroll_gl_reconciliation.application.mapping_service import (
    MappingService,
)
from financeops.modules.payroll_gl_reconciliation.application.matching_service import (
    MatchingService,
)
from financeops.modules.payroll_gl_reconciliation.application.rule_service import RuleService
from financeops.modules.payroll_gl_reconciliation.application.validation_service import (
    ValidationService,
)
from financeops.modules.payroll_gl_reconciliation.domain.entities import (
    PayrollGlComputedException,
)
from financeops.modules.payroll_gl_reconciliation.domain.enums import (
    PayrollGlRunStatus,
)
from financeops.modules.payroll_gl_reconciliation.domain.value_objects import (
    PayrollGlRunTokenInput,
)
from financeops.modules.payroll_gl_reconciliation.infrastructure.repository import (
    PayrollGlReconciliationRepository,
)
from financeops.modules.payroll_gl_reconciliation.infrastructure.token_builder import (
    build_payroll_gl_run_token,
)
from financeops.utils.determinism import canonical_json_dumps, sha256_hex_text


class PayrollGlReconciliationRunService:
    def __init__(
        self,
        *,
        repository: PayrollGlReconciliationRepository,
        mapping_service: MappingService,
        rule_service: RuleService,
        matching_service: MatchingService,
        classification_service: ClassificationService,
        validation_service: ValidationService,
    ) -> None:
        self._repository = repository
        self._mapping_service = mapping_service
        self._rule_service = rule_service
        self._matching_service = matching_service
        self._classification_service = classification_service
        self._validation_service = validation_service

    async def create_run(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        payroll_run_id: uuid.UUID,
        gl_run_id: uuid.UUID,
        reporting_period: date,
        created_by: uuid.UUID,
    ) -> dict[str, Any]:
        payroll_run = await self._repository.get_normalization_run(
            tenant_id=tenant_id, run_id=payroll_run_id
        )
        gl_run = await self._repository.get_normalization_run(
            tenant_id=tenant_id, run_id=gl_run_id
        )
        mappings = self._mapping_service.validate_active_set(
            await self._repository.active_mappings(
                tenant_id=tenant_id,
                organisation_id=organisation_id,
                reporting_period=reporting_period,
            ),
            reporting_period=reporting_period,
        )
        rules = self._rule_service.validate_active_set(
            await self._repository.active_rules(
                tenant_id=tenant_id,
                organisation_id=organisation_id,
                reporting_period=reporting_period,
            ),
            reporting_period=reporting_period,
        )
        self._validation_service.validate_run_inputs(
            payroll_run=payroll_run,
            gl_run=gl_run,
            organisation_id=str(organisation_id),
            reporting_period=reporting_period,
            mappings=mappings,
            rules=rules,
        )
        mapping_version_token = self._mapping_service.mapping_version_token(mappings)
        rule_version_token = self._rule_service.rule_version_token(rules)

        run_token = self._run_token(
            tenant_id=tenant_id,
            organisation_id=organisation_id,
            payroll_run_id=payroll_run_id,
            gl_run_id=gl_run_id,
            mapping_version_token=mapping_version_token,
            rule_version_token=rule_version_token,
            reporting_period=reporting_period,
            status=PayrollGlRunStatus.CREATED,
        )
        existing = await self._repository.get_payroll_gl_run_by_token(
            tenant_id=tenant_id, run_token=run_token
        )
        if existing is not None:
            return {
                "run_id": str(existing.id),
                "reconciliation_session_id": str(existing.reconciliation_session_id),
                "run_token": existing.run_token,
                "status": existing.status,
                "idempotent": True,
            }

        session_token = self._session_token(
            tenant_id=tenant_id,
            organisation_id=organisation_id,
            payroll_run_id=payroll_run_id,
            gl_run_id=gl_run_id,
            mapping_version_token=mapping_version_token,
            rule_version_token=rule_version_token,
            reporting_period=reporting_period,
        )
        session = await self._repository.get_reconciliation_session_by_token(
            tenant_id=tenant_id, session_token=session_token
        )
        if session is None:
            session = await self._repository.create_reconciliation_session(
                tenant_id=tenant_id,
                organisation_id=organisation_id,
                source_a_ref=str(payroll_run_id),
                source_b_ref=str(gl_run_id),
                reporting_period=reporting_period,
                matching_rule_version=rule_version_token,
                tolerance_rule_version=rule_version_token,
                session_token=session_token,
                materiality_config_json=self._rule_service.merged_materiality(rules),
                created_by=created_by,
            )

        row = await self._repository.create_payroll_gl_run(
            tenant_id=tenant_id,
            organisation_id=organisation_id,
            reconciliation_session_id=session.id,
            payroll_run_id=payroll_run_id,
            gl_run_id=gl_run_id,
            mapping_version_token=mapping_version_token,
            rule_version_token=rule_version_token,
            reporting_period=reporting_period,
            run_token=run_token,
            status=PayrollGlRunStatus.CREATED,
            created_by=created_by,
        )
        return {
            "run_id": str(row.id),
            "reconciliation_session_id": str(row.reconciliation_session_id),
            "run_token": row.run_token,
            "status": row.status,
            "idempotent": False,
        }

    async def execute_run(
        self,
        *,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
        actor_user_id: uuid.UUID,
    ) -> dict[str, Any]:
        run = await self._repository.get_payroll_gl_run(tenant_id=tenant_id, run_id=run_id)
        if run is None:
            raise ValueError("Payroll-GL reconciliation run not found")

        session_id = run.reconciliation_session_id
        session = await self._repository.get_reconciliation_session(
            tenant_id=tenant_id, session_id=session_id
        )
        if session is None:
            raise ValueError("Reconciliation session not found")

        existing_lines = await self._repository.list_reconciliation_lines(
            tenant_id=tenant_id, session_id=session_id
        )
        if existing_lines:
            completed = await self._ensure_status_row(
                tenant_id=tenant_id,
                run=run,
                status=PayrollGlRunStatus.COMPLETED,
                created_by=actor_user_id,
            )
            summary = await self._repository.summarize_reconciliation_session(
                tenant_id=tenant_id, session_id=session_id
            )
            return {
                "run_id": str(completed.id),
                "reconciliation_session_id": str(session_id),
                "status": completed.status,
                "line_count": summary["line_count"],
                "exception_count": summary["exception_count"],
                "idempotent": True,
            }

        payroll_run = await self._repository.get_normalization_run(
            tenant_id=tenant_id, run_id=run.payroll_run_id
        )
        gl_run = await self._repository.get_normalization_run(
            tenant_id=tenant_id, run_id=run.gl_run_id
        )
        mappings = self._mapping_service.validate_active_set(
            await self._repository.active_mappings(
                tenant_id=tenant_id,
                organisation_id=run.organisation_id,
                reporting_period=run.reporting_period,
            ),
            reporting_period=run.reporting_period,
        )
        rules = self._rule_service.validate_active_set(
            await self._repository.active_rules(
                tenant_id=tenant_id,
                organisation_id=run.organisation_id,
                reporting_period=run.reporting_period,
            ),
            reporting_period=run.reporting_period,
        )
        self._validation_service.validate_run_inputs(
            payroll_run=payroll_run,
            gl_run=gl_run,
            organisation_id=str(run.organisation_id),
            reporting_period=run.reporting_period,
            mappings=mappings,
            rules=rules,
        )

        mapping_version_token = self._mapping_service.mapping_version_token(mappings)
        rule_version_token = self._rule_service.rule_version_token(rules)
        if mapping_version_token != run.mapping_version_token:
            raise ValueError("Active mapping set drift detected for run")
        if rule_version_token != run.rule_version_token:
            raise ValueError("Active rule set drift detected for run")

        payroll_lines = await self._repository.list_payroll_lines(
            tenant_id=tenant_id, run_id=run.payroll_run_id
        )
        gl_lines = await self._repository.list_gl_lines(
            tenant_id=tenant_id, run_id=run.gl_run_id
        )
        materiality = self._rule_service.merged_materiality(rules)
        tolerance = self._rule_service.merged_tolerance(rules)
        max_timing_lag_days = self._rule_service.max_timing_lag_days(rules)

        computed = self._matching_service.match(
            payroll_lines=payroll_lines,
            gl_lines=gl_lines,
            mappings=mappings,
            reporting_period=run.reporting_period,
            materiality_config_json=materiality,
            tolerance_json=tolerance,
            max_timing_lag_days=max_timing_lag_days,
        )
        persisted_lines = await self._repository.insert_reconciliation_lines(
            tenant_id=tenant_id,
            session_id=session_id,
            created_by=actor_user_id,
            lines=computed,
        )
        by_key = {line.line_key: line for line in computed}
        for row in persisted_lines:
            classified = self._classification_service.classify_line(by_key[row.line_key])
            if classified is None:
                continue
            inserted_exception = await self._repository.insert_reconciliation_exception(
                tenant_id=tenant_id,
                session_id=session_id,
                line_id=row.id,
                exception=classified,
                created_by=actor_user_id,
                resolution_status="open",
            )
            await self._repository.insert_resolution_event(
                tenant_id=tenant_id,
                session_id=session_id,
                line_id=row.id,
                exception_id=inserted_exception.id,
                event_type="exception_opened",
                event_payload_json={
                    "exception_code": inserted_exception.exception_code,
                    "severity": inserted_exception.severity,
                },
                actor_user_id=actor_user_id,
            )
            await self._repository.insert_evidence_link(
                tenant_id=tenant_id,
                session_id=session_id,
                line_id=row.id,
                evidence_type="uploaded_artifact",
                evidence_ref=f"payroll_run:{run.payroll_run_id}",
                evidence_label="Payroll normalization run",
                created_by=actor_user_id,
            )
            await self._repository.insert_evidence_link(
                tenant_id=tenant_id,
                session_id=session_id,
                line_id=row.id,
                evidence_type="uploaded_artifact",
                evidence_ref=f"gl_run:{run.gl_run_id}",
                evidence_label="GL normalization run",
                created_by=actor_user_id,
            )

        completed = await self._ensure_status_row(
            tenant_id=tenant_id,
            run=run,
            status=PayrollGlRunStatus.COMPLETED,
            created_by=actor_user_id,
        )
        summary = await self._repository.summarize_reconciliation_session(
            tenant_id=tenant_id, session_id=session_id
        )
        return {
            "run_id": str(completed.id),
            "reconciliation_session_id": str(session_id),
            "status": completed.status,
            "line_count": summary["line_count"],
            "exception_count": summary["exception_count"],
            "idempotent": False,
        }

    async def get_run(
        self, *, tenant_id: uuid.UUID, run_id: uuid.UUID
    ) -> dict[str, Any] | None:
        row = await self._repository.get_payroll_gl_run(tenant_id=tenant_id, run_id=run_id)
        if row is None:
            return None
        return {
            "id": str(row.id),
            "reconciliation_session_id": str(row.reconciliation_session_id),
            "payroll_run_id": str(row.payroll_run_id),
            "gl_run_id": str(row.gl_run_id),
            "mapping_version_token": row.mapping_version_token,
            "rule_version_token": row.rule_version_token,
            "reporting_period": row.reporting_period.isoformat(),
            "run_token": row.run_token,
            "status": row.status,
            "created_at": row.created_at.isoformat(),
        }

    async def summary(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> dict[str, Any]:
        run = await self._repository.get_payroll_gl_run(tenant_id=tenant_id, run_id=run_id)
        if run is None:
            raise ValueError("Payroll-GL reconciliation run not found")
        summary = await self._repository.summarize_reconciliation_session(
            tenant_id=tenant_id, session_id=run.reconciliation_session_id
        )
        return {
            "run_id": str(run.id),
            "reconciliation_session_id": str(run.reconciliation_session_id),
            **summary,
        }

    async def list_lines(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> list[dict[str, Any]]:
        run = await self._repository.get_payroll_gl_run(tenant_id=tenant_id, run_id=run_id)
        if run is None:
            raise ValueError("Payroll-GL reconciliation run not found")
        rows = await self._repository.list_reconciliation_lines(
            tenant_id=tenant_id, session_id=run.reconciliation_session_id
        )
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
        self, *, tenant_id: uuid.UUID, run_id: uuid.UUID
    ) -> list[dict[str, Any]]:
        run = await self._repository.get_payroll_gl_run(tenant_id=tenant_id, run_id=run_id)
        if run is None:
            raise ValueError("Payroll-GL reconciliation run not found")
        rows = await self._repository.list_reconciliation_exceptions(
            tenant_id=tenant_id, session_id=run.reconciliation_session_id
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
        line = await self._repository.get_reconciliation_line(
            tenant_id=tenant_id, line_id=line_id
        )
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
        event = await self._repository.insert_resolution_event(
            tenant_id=tenant_id,
            session_id=line.session_id,
            line_id=line.id,
            exception_id=None,
            event_type="evidence_linked",
            event_payload_json={
                "evidence_type": evidence_type,
                "evidence_ref": evidence_ref,
            },
            actor_user_id=actor_user_id,
        )
        return {"evidence_id": str(evidence.id), "event_id": str(event.id)}

    async def resolve_line(
        self, *, tenant_id: uuid.UUID, line_id: uuid.UUID, actor_user_id: uuid.UUID
    ) -> dict[str, Any]:
        line = await self._repository.get_reconciliation_line(
            tenant_id=tenant_id, line_id=line_id
        )
        if line is None:
            raise ValueError("Reconciliation line not found")
        latest = await self._repository.get_latest_exception_for_line(
            tenant_id=tenant_id, line_id=line_id
        )
        fallback = PayrollGlComputedException(
            line_key=line.line_key,
            exception_code="PAYROLL_GL_RESOLVED",
            severity="warning",
            message="Line resolved without prior exception",
            owner_role="finance_controller",
        )
        exception = await self._repository.insert_reconciliation_exception(
            tenant_id=tenant_id,
            session_id=line.session_id,
            line_id=line.id,
            exception=(
                PayrollGlComputedException(
                    line_key=line.line_key,
                    exception_code=latest.exception_code,
                    severity=latest.severity,
                    message=latest.message,
                    owner_role=latest.owner_role,
                )
                if latest is not None
                else fallback
            ),
            created_by=actor_user_id,
            resolution_status="resolved",
        )
        event = await self._repository.insert_resolution_event(
            tenant_id=tenant_id,
            session_id=line.session_id,
            line_id=line.id,
            exception_id=exception.id,
            event_type="resolved",
            event_payload_json={"resolution_status": "resolved"},
            actor_user_id=actor_user_id,
        )
        return {"exception_id": str(exception.id), "event_id": str(event.id)}

    async def reopen_line(
        self, *, tenant_id: uuid.UUID, line_id: uuid.UUID, actor_user_id: uuid.UUID
    ) -> dict[str, Any]:
        line = await self._repository.get_reconciliation_line(
            tenant_id=tenant_id, line_id=line_id
        )
        if line is None:
            raise ValueError("Reconciliation line not found")
        latest = await self._repository.get_latest_exception_for_line(
            tenant_id=tenant_id, line_id=line_id
        )
        if latest is None:
            raise ValueError("No exception exists for line")
        exception = await self._repository.insert_reconciliation_exception(
            tenant_id=tenant_id,
            session_id=line.session_id,
            line_id=line.id,
            exception=PayrollGlComputedException(
                line_key=line.line_key,
                exception_code=latest.exception_code,
                severity=latest.severity,
                message=latest.message,
                owner_role=latest.owner_role,
            ),
            created_by=actor_user_id,
            resolution_status="reopened",
        )
        event = await self._repository.insert_resolution_event(
            tenant_id=tenant_id,
            session_id=line.session_id,
            line_id=line.id,
            exception_id=exception.id,
            event_type="reopened",
            event_payload_json={"resolution_status": "reopened"},
            actor_user_id=actor_user_id,
        )
        return {"exception_id": str(exception.id), "event_id": str(event.id)}

    async def _ensure_status_row(
        self,
        *,
        tenant_id: uuid.UUID,
        run: Any,
        status: PayrollGlRunStatus,
        created_by: uuid.UUID,
    ) -> Any:
        token = self._run_token(
            tenant_id=tenant_id,
            organisation_id=run.organisation_id,
            payroll_run_id=run.payroll_run_id,
            gl_run_id=run.gl_run_id,
            mapping_version_token=run.mapping_version_token,
            rule_version_token=run.rule_version_token,
            reporting_period=run.reporting_period,
            status=status,
        )
        existing = await self._repository.get_payroll_gl_run_by_token(
            tenant_id=tenant_id, run_token=token
        )
        if existing is not None:
            return existing
        return await self._repository.create_payroll_gl_run(
            tenant_id=tenant_id,
            organisation_id=run.organisation_id,
            reconciliation_session_id=run.reconciliation_session_id,
            payroll_run_id=run.payroll_run_id,
            gl_run_id=run.gl_run_id,
            mapping_version_token=run.mapping_version_token,
            rule_version_token=run.rule_version_token,
            reporting_period=run.reporting_period,
            run_token=token,
            status=status,
            created_by=created_by,
        )

    def _session_token(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        payroll_run_id: uuid.UUID,
        gl_run_id: uuid.UUID,
        mapping_version_token: str,
        rule_version_token: str,
        reporting_period: date,
    ) -> str:
        payload = {
            "tenant_id": str(tenant_id),
            "organisation_id": str(organisation_id),
            "source_a_type": "payroll_normalization_run",
            "source_a_ref": str(payroll_run_id),
            "source_b_type": "gl_normalization_run",
            "source_b_ref": str(gl_run_id),
            "period_start": reporting_period.replace(day=1).isoformat(),
            "period_end": reporting_period.isoformat(),
            "matching_rule_version": rule_version_token,
            "tolerance_rule_version": rule_version_token,
            "mapping_version_token": mapping_version_token,
        }
        return sha256_hex_text(canonical_json_dumps(payload))

    def _run_token(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        payroll_run_id: uuid.UUID,
        gl_run_id: uuid.UUID,
        mapping_version_token: str,
        rule_version_token: str,
        reporting_period: date,
        status: PayrollGlRunStatus,
    ) -> str:
        return build_payroll_gl_run_token(
            PayrollGlRunTokenInput(
                tenant_id=tenant_id,
                organisation_id=organisation_id,
                payroll_run_id=payroll_run_id,
                gl_run_id=gl_run_id,
                mapping_version_token=mapping_version_token,
                rule_version_token=rule_version_token,
                reporting_period=reporting_period,
            ),
            status=status.value,
        )

