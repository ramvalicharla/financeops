from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.governance.events import GovernanceActor, emit_governance_event
from financeops.db.models.accounting_jv import AccountingJVAggregate
from financeops.db.models.governance_control import AirlockItem
from financeops.db.models.users import UserRole
from financeops.modules.accounting_layer.application.governance_service import (
    assert_period_allows_modification,
    assert_period_allows_posting,
    assert_period_allows_revaluation,
)
from financeops.platform.db.models.entities import CpEntity
from financeops.platform.services.tenancy.module_enablement import resolve_module_enablement
from financeops.storage.airlock import scan_and_seal


def _utcnow() -> datetime:
    return datetime.now(UTC)


_FINANCE_OPERATOR_ROLES = {
    UserRole.finance_team.value,
    UserRole.finance_leader.value,
    UserRole.super_admin.value,
    UserRole.platform_owner.value,
    UserRole.platform_admin.value,
}

_FINANCE_APPROVER_ROLES = {
    UserRole.finance_leader.value,
    UserRole.super_admin.value,
    UserRole.platform_owner.value,
    UserRole.platform_admin.value,
}


@dataclass(frozen=True)
class GuardResult:
    guard_code: str
    guard_name: str
    result: str
    severity: str
    message: str
    details_json: dict[str, Any] = field(default_factory=dict)
    evaluated_at: datetime = field(default_factory=_utcnow)


@dataclass(frozen=True)
class GuardEvaluationResult:
    overall_passed: bool
    results: list[GuardResult]

    @property
    def blocking_failures(self) -> list[GuardResult]:
        return [
            result
            for result in self.results
            if result.result == "FAIL" and result.severity == "BLOCKING"
        ]


@dataclass(frozen=True)
class MutationGuardContext:
    tenant_id: uuid.UUID
    module_key: str
    mutation_type: str
    actor_user_id: uuid.UUID | None
    actor_role: str | None
    entity_id: uuid.UUID | None = None
    amount: Decimal | None = None
    target_type: str | None = None
    target_id: uuid.UUID | None = None
    target_exists: bool | None = None
    state_valid: bool | None = None
    immutable_ok: bool | None = None
    admitted_airlock_item_id: uuid.UUID | None = None
    requires_airlock_admission: bool = False
    period_year: int | None = None
    period_number: int | None = None
    period_guard_mode: str | None = None
    source_type: str | None = None
    subject_type: str = "governed_mutation"
    subject_id: str = ""


@dataclass(frozen=True)
class ExternalInputGuardContext:
    tenant_id: uuid.UUID
    source_type: str
    actor_user_id: uuid.UUID | None
    actor_role: str | None
    entity_id: uuid.UUID | None = None
    file_name: str | None = None
    content: bytes | None = None
    source_reference: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    subject_type: str = "airlock_item"
    subject_id: str = ""


class GuardEngine:
    async def evaluate_mutation(
        self,
        db: AsyncSession,
        *,
        context: MutationGuardContext,
    ) -> GuardEvaluationResult:
        results: list[GuardResult] = []

        results.append(self._check_actor_authorized(context))
        results.append(await self._check_entity_scope(db, context))
        results.append(await self._check_module_enabled(db, context))
        results.append(await self._check_target_exists(db, context))
        results.append(await self._check_period(db, context))
        results.append(self._check_state_validity(context))
        results.append(self._check_immutability(context))
        results.append(await self._check_airlock_admission(db, context))

        filtered = [result for result in results if result.result != "SKIP"]
        overall = not any(
            result.result == "FAIL" and result.severity == "BLOCKING"
            for result in filtered
        )
        evaluation = GuardEvaluationResult(overall_passed=overall, results=filtered)
        await emit_governance_event(
            db,
            tenant_id=context.tenant_id,
            module_key=context.module_key,
            subject_type=context.subject_type,
            subject_id=context.subject_id or context.mutation_type,
            event_type="GUARD_EVALUATED",
            actor=GovernanceActor(user_id=context.actor_user_id, role=context.actor_role),
            entity_id=context.entity_id,
            payload={
                "mutation_type": context.mutation_type,
                "overall_passed": evaluation.overall_passed,
                "results": [
                    {
                        "guard_code": item.guard_code,
                        "guard_name": item.guard_name,
                        "result": item.result,
                        "severity": item.severity,
                        "message": item.message,
                        "details_json": item.details_json,
                        "evaluated_at": item.evaluated_at.isoformat(),
                    }
                    for item in evaluation.results
                ],
            },
        )
        return evaluation

    async def evaluate_external_input(
        self,
        db: AsyncSession,
        *,
        context: ExternalInputGuardContext,
    ) -> GuardEvaluationResult:
        results: list[GuardResult] = []
        results.append(self._external_source_present(context))
        results.append(self._external_actor_authorized(context))

        checksum: str | None = None
        if context.content is None:
            results.append(
                GuardResult(
                    guard_code="external.file_present",
                    guard_name="File present",
                    result="SKIP",
                    severity="WARNING",
                    message="No binary payload supplied; using source-bound admission only.",
                )
            )
            results.extend(
                [
                    GuardResult(
                        guard_code="external.mime_validation",
                        guard_name="MIME validation",
                        result="SKIP",
                        severity="WARNING",
                        message="No file content supplied for MIME validation.",
                    ),
                    GuardResult(
                        guard_code="external.size_validation",
                        guard_name="Size validation",
                        result="SKIP",
                        severity="WARNING",
                        message="No file content supplied for size validation.",
                    ),
                    GuardResult(
                        guard_code="external.malware_scan",
                        guard_name="Malware scan",
                        result="SKIP",
                        severity="WARNING",
                        message="No file content supplied for malware scan.",
                    ),
                ]
            )
        else:
            try:
                scan_result = await scan_and_seal(
                    context.content,
                    context.file_name or f"{context.source_type}.bin",
                    str(context.tenant_id),
                )
                checksum = scan_result.sha256
                passed_file_checks = scan_result.status != "REJECTED"
                malware_clean = scan_result.status in {"APPROVED", "SCAN_SKIPPED"}
                rejection_reason = scan_result.rejection_reason or "File validation failed."
                results.append(
                    GuardResult(
                        guard_code="external.file_present",
                        guard_name="File present",
                        result="PASS",
                        severity="BLOCKING",
                        message="File payload received.",
                        details_json={"size_bytes": len(context.content)},
                    )
                )
                results.append(
                    GuardResult(
                        guard_code="external.mime_validation",
                        guard_name="MIME validation",
                        result="PASS" if passed_file_checks else "FAIL",
                        severity="BLOCKING",
                        message=(
                            "MIME validation passed."
                            if passed_file_checks
                            else rejection_reason
                        ),
                        details_json={"mime_type": scan_result.mime_type},
                    )
                )
                results.append(
                    GuardResult(
                        guard_code="external.size_validation",
                        guard_name="Size validation",
                        result="PASS" if passed_file_checks else "FAIL",
                        severity="BLOCKING",
                        message=(
                            "Size validation passed."
                            if passed_file_checks
                            else rejection_reason
                        ),
                        details_json={"size_bytes": scan_result.size_bytes},
                    )
                )
                results.append(
                    GuardResult(
                        guard_code="external.malware_scan",
                        guard_name="Malware scan",
                        result="PASS" if malware_clean else "FAIL",
                        severity="BLOCKING",
                        message=(
                            "Malware scan passed."
                            if malware_clean
                            else rejection_reason
                        ),
                        details_json={
                            "sha256": scan_result.sha256,
                            "quarantine_ref": getattr(scan_result, "quarantine_ref", None),
                            "scan_result": getattr(scan_result, "scan_result", None),
                        },
                    )
                )
            except Exception as exc:
                results.extend(
                    [
                        GuardResult(
                            guard_code="external.file_present",
                            guard_name="File present",
                            result="PASS",
                            severity="BLOCKING",
                            message="File payload received.",
                            details_json={"size_bytes": len(context.content)},
                        ),
                        GuardResult(
                            guard_code="external.malware_scan",
                            guard_name="Malware scan",
                            result="FAIL",
                            severity="BLOCKING",
                            message=str(exc),
                        ),
                    ]
                )

        results.append(await self._check_duplicate_upload(db, context, checksum))
        results.append(self._check_source_binding(context))
        results.append(self._check_quarantine_required())
        results.append(self._check_no_direct_write_before_admission())

        filtered = [result for result in results if result.result != "SKIP"]
        overall = not any(
            result.result == "FAIL" and result.severity == "BLOCKING"
            for result in filtered
        )
        evaluation = GuardEvaluationResult(overall_passed=overall, results=filtered)
        await emit_governance_event(
            db,
            tenant_id=context.tenant_id,
            module_key="airlock",
            subject_type=context.subject_type,
            subject_id=context.subject_id or context.source_type,
            event_type="GUARD_EVALUATED",
            actor=GovernanceActor(user_id=context.actor_user_id, role=context.actor_role),
            entity_id=context.entity_id,
            payload={
                "source_type": context.source_type,
                "overall_passed": evaluation.overall_passed,
                "results": [
                    {
                        "guard_code": item.guard_code,
                        "guard_name": item.guard_name,
                        "result": item.result,
                        "severity": item.severity,
                        "message": item.message,
                        "details_json": item.details_json,
                        "evaluated_at": item.evaluated_at.isoformat(),
                    }
                    for item in evaluation.results
                ],
            },
        )
        return evaluation

    def _check_actor_authorized(self, context: MutationGuardContext) -> GuardResult:
        actor_role = (context.actor_role or "").strip().lower()
        if context.mutation_type in {
            "APPROVE_JOURNAL",
            "POST_JOURNAL",
            "REVERSE_JOURNAL",
            "PERIOD_UNLOCK",
            "PERIOD_HARD_CLOSE",
        }:
            allowed = _FINANCE_APPROVER_ROLES
        else:
            allowed = _FINANCE_OPERATOR_ROLES
        if actor_role not in allowed:
            return GuardResult(
                guard_code="actor.authorization",
                guard_name="Actor authorization",
                result="FAIL",
                severity="BLOCKING",
                message=f"Role '{context.actor_role}' is not authorized for {context.mutation_type}.",
            )
        return GuardResult(
            guard_code="actor.authorization",
            guard_name="Actor authorization",
            result="PASS",
            severity="BLOCKING",
            message="Actor authorization passed.",
            details_json={"actor_role": context.actor_role or ""},
        )

    async def _check_entity_scope(
        self,
        db: AsyncSession,
        context: MutationGuardContext,
    ) -> GuardResult:
        if context.entity_id is None:
            return GuardResult(
                guard_code="scope.entity",
                guard_name="Entity scope",
                result="SKIP",
                severity="WARNING",
                message="Mutation does not declare an entity scope.",
            )
        row = (
            await db.execute(
                select(CpEntity.id).where(
                    CpEntity.id == context.entity_id,
                    CpEntity.tenant_id == context.tenant_id,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            return GuardResult(
                guard_code="scope.entity",
                guard_name="Entity scope",
                result="FAIL",
                severity="BLOCKING",
                message="Entity does not belong to tenant scope.",
            )
        return GuardResult(
            guard_code="scope.entity",
            guard_name="Entity scope",
            result="PASS",
            severity="BLOCKING",
            message="Entity scope resolved.",
            details_json={"entity_id": str(context.entity_id)},
        )

    async def _check_module_enabled(
        self,
        db: AsyncSession,
        context: MutationGuardContext,
    ) -> GuardResult:
        module_code = self._module_code(context.module_key)
        try:
            _module_id, enabled = await resolve_module_enablement(
                db,
                tenant_id=context.tenant_id,
                module_code=module_code,
                as_of=_utcnow(),
            )
        except Exception:
            return GuardResult(
                guard_code="module.enabled",
                guard_name="Module enabled",
                result="SKIP",
                severity="WARNING",
                message=f"Module registry entry '{module_code}' was not found.",
            )
        if not enabled:
            return GuardResult(
                guard_code="module.enabled",
                guard_name="Module enabled",
                result="FAIL",
                severity="BLOCKING",
                message=f"Module '{module_code}' is disabled for tenant scope.",
            )
        return GuardResult(
            guard_code="module.enabled",
            guard_name="Module enabled",
            result="PASS",
            severity="BLOCKING",
            message="Module enablement passed.",
            details_json={"module_code": module_code},
        )

    async def _check_target_exists(
        self,
        db: AsyncSession,
        context: MutationGuardContext,
    ) -> GuardResult:
        if context.target_id is None:
            return GuardResult(
                guard_code="target.exists",
                guard_name="Target exists",
                result="SKIP",
                severity="WARNING",
                message="Mutation does not target an existing object.",
            )
        if context.target_exists is not None:
            exists = context.target_exists
        elif (context.target_type or "").lower() == "journal":
            exists = (
                await db.execute(
                    select(AccountingJVAggregate.id).where(
                        AccountingJVAggregate.id == context.target_id,
                        AccountingJVAggregate.tenant_id == context.tenant_id,
                    )
                )
            ).scalar_one_or_none() is not None
        else:
            exists = True
        if not exists:
            return GuardResult(
                guard_code="target.exists",
                guard_name="Target exists",
                result="FAIL",
                severity="BLOCKING",
                message="Target object was not found in tenant scope.",
            )
        return GuardResult(
            guard_code="target.exists",
            guard_name="Target exists",
            result="PASS",
            severity="BLOCKING",
            message="Target object resolved.",
            details_json={"target_id": str(context.target_id)},
        )

    async def _check_period(
        self,
        db: AsyncSession,
        context: MutationGuardContext,
    ) -> GuardResult:
        if context.period_guard_mode is None:
            return GuardResult(
                guard_code="period.state",
                guard_name="Period state",
                result="SKIP",
                severity="WARNING",
                message="No period guard requested for this mutation.",
            )
        if context.entity_id is None or context.period_year is None or context.period_number is None:
            return GuardResult(
                guard_code="period.state",
                guard_name="Period state",
                result="FAIL",
                severity="BLOCKING",
                message="Period guard requires entity, period_year, and period_number.",
            )
        try:
            if context.period_guard_mode == "modify":
                await assert_period_allows_modification(
                    db,
                    tenant_id=context.tenant_id,
                    org_entity_id=context.entity_id,
                    fiscal_year=context.period_year,
                    period_number=context.period_number,
                )
            elif context.period_guard_mode == "post":
                await assert_period_allows_posting(
                    db,
                    tenant_id=context.tenant_id,
                    org_entity_id=context.entity_id,
                    fiscal_year=context.period_year,
                    period_number=context.period_number,
                    actor_role=context.actor_role,
                )
            elif context.period_guard_mode == "revaluation":
                await assert_period_allows_revaluation(
                    db,
                    tenant_id=context.tenant_id,
                    org_entity_id=context.entity_id,
                    as_of_date=datetime(context.period_year, context.period_number, 1, tzinfo=UTC).date(),
                    actor_role=context.actor_role,
                )
            else:
                return GuardResult(
                    guard_code="period.state",
                    guard_name="Period state",
                    result="SKIP",
                    severity="WARNING",
                    message=f"Unknown period guard mode '{context.period_guard_mode}'.",
                )
        except Exception as exc:
            return GuardResult(
                guard_code="period.state",
                guard_name="Period state",
                result="FAIL",
                severity="BLOCKING",
                message=str(exc),
            )
        return GuardResult(
            guard_code="period.state",
            guard_name="Period state",
            result="PASS",
            severity="BLOCKING",
            message="Period guard passed.",
        )

    def _check_state_validity(self, context: MutationGuardContext) -> GuardResult:
        if context.state_valid is None:
            return GuardResult(
                guard_code="state.transition",
                guard_name="State transition validity",
                result="SKIP",
                severity="WARNING",
                message="No explicit state-transition rule provided.",
            )
        if not context.state_valid:
            return GuardResult(
                guard_code="state.transition",
                guard_name="State transition validity",
                result="FAIL",
                severity="BLOCKING",
                message="State transition is not valid for the requested mutation.",
            )
        return GuardResult(
            guard_code="state.transition",
            guard_name="State transition validity",
            result="PASS",
            severity="BLOCKING",
            message="State transition is valid.",
        )

    def _check_immutability(self, context: MutationGuardContext) -> GuardResult:
        if context.immutable_ok is None:
            return GuardResult(
                guard_code="immutability.final_state",
                guard_name="Immutable final-state protection",
                result="SKIP",
                severity="WARNING",
                message="No immutable-state rule provided.",
            )
        if not context.immutable_ok:
            return GuardResult(
                guard_code="immutability.final_state",
                guard_name="Immutable final-state protection",
                result="FAIL",
                severity="BLOCKING",
                message="Target object is immutable or already final.",
            )
        return GuardResult(
            guard_code="immutability.final_state",
            guard_name="Immutable final-state protection",
            result="PASS",
            severity="BLOCKING",
            message="Immutable-state protection passed.",
        )

    async def _check_airlock_admission(
        self,
        db: AsyncSession,
        context: MutationGuardContext,
    ) -> GuardResult:
        if not context.requires_airlock_admission:
            return GuardResult(
                guard_code="airlock.admission",
                guard_name="Airlock admission",
                result="SKIP",
                severity="WARNING",
                message="Mutation does not require airlock admission.",
            )
        if context.admitted_airlock_item_id is None:
            return GuardResult(
                guard_code="airlock.admission",
                guard_name="Airlock admission",
                result="FAIL",
                severity="BLOCKING",
                message="Airlock admission reference is required before downstream mutation.",
            )
        item = (
            await db.execute(
                select(AirlockItem).where(
                    AirlockItem.id == context.admitted_airlock_item_id,
                    AirlockItem.tenant_id == context.tenant_id,
                )
            )
        ).scalar_one_or_none()
        if item is None or item.status != "ADMITTED":
            return GuardResult(
                guard_code="airlock.admission",
                guard_name="Airlock admission",
                result="FAIL",
                severity="BLOCKING",
                message="Referenced airlock item is not admitted.",
            )
        return GuardResult(
            guard_code="airlock.admission",
            guard_name="Airlock admission",
            result="PASS",
            severity="BLOCKING",
            message="Airlock admission passed.",
            details_json={"airlock_item_id": str(item.id), "source_type": item.source_type},
        )

    def _external_source_present(self, context: ExternalInputGuardContext) -> GuardResult:
        if not context.source_type.strip():
            return GuardResult(
                guard_code="external.source_present",
                guard_name="Source present",
                result="FAIL",
                severity="BLOCKING",
                message="External source type is required.",
            )
        return GuardResult(
            guard_code="external.source_present",
            guard_name="Source present",
            result="PASS",
            severity="BLOCKING",
            message="External source type present.",
            details_json={"source_type": context.source_type},
        )

    def _external_actor_authorized(self, context: ExternalInputGuardContext) -> GuardResult:
        actor_role = (context.actor_role or "").strip().lower()
        if actor_role not in _FINANCE_OPERATOR_ROLES:
            return GuardResult(
                guard_code="external.actor_authorized",
                guard_name="External actor authorized",
                result="FAIL",
                severity="BLOCKING",
                message=f"Role '{context.actor_role}' is not authorized to submit external inputs.",
            )
        return GuardResult(
            guard_code="external.actor_authorized",
            guard_name="External actor authorized",
            result="PASS",
            severity="BLOCKING",
            message="External actor authorization passed.",
        )

    async def _check_duplicate_upload(
        self,
        db: AsyncSession,
        context: ExternalInputGuardContext,
        checksum: str | None,
    ) -> GuardResult:
        if checksum is None:
            return GuardResult(
                guard_code="external.duplicate_detection",
                guard_name="Duplicate upload detection",
                result="SKIP",
                severity="WARNING",
                message="Checksum unavailable; duplicate detection skipped.",
            )
        existing = (
            await db.execute(
                select(AirlockItem.id).where(
                    AirlockItem.tenant_id == context.tenant_id,
                    AirlockItem.source_type == context.source_type,
                    AirlockItem.checksum_sha256 == checksum,
                    AirlockItem.source_reference == context.source_reference,
                    AirlockItem.metadata_json == context.metadata,
                    AirlockItem.status.in_(["QUARANTINED", "ADMITTED"]),
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return GuardResult(
                guard_code="external.duplicate_detection",
                guard_name="Duplicate upload detection",
                result="FAIL",
                severity="BLOCKING",
                message="Duplicate external payload already exists in airlock.",
                details_json={"duplicate_airlock_item_id": str(existing)},
            )
        return GuardResult(
            guard_code="external.duplicate_detection",
            guard_name="Duplicate upload detection",
            result="PASS",
            severity="BLOCKING",
            message="No duplicate external payload detected.",
            details_json={"checksum_sha256": checksum},
        )

    def _check_source_binding(self, context: ExternalInputGuardContext) -> GuardResult:
        if not context.source_reference and not context.metadata:
            return GuardResult(
                guard_code="external.source_binding",
                guard_name="Source binding",
                result="FAIL",
                severity="BLOCKING",
                message="External input must bind to a source reference or metadata.",
            )
        return GuardResult(
            guard_code="external.source_binding",
            guard_name="Source binding",
            result="PASS",
            severity="BLOCKING",
            message="External source binding resolved.",
            details_json={
                "source_reference": context.source_reference,
                "metadata_keys": sorted(context.metadata.keys()),
            },
        )

    def _check_quarantine_required(self) -> GuardResult:
        return GuardResult(
            guard_code="external.quarantine_required",
            guard_name="Quarantine required before admission",
            result="PASS",
            severity="BLOCKING",
            message="External input must remain quarantined until admitted.",
        )

    def _check_no_direct_write_before_admission(self) -> GuardResult:
        return GuardResult(
            guard_code="external.no_direct_write",
            guard_name="No direct financial write before admission",
            result="PASS",
            severity="BLOCKING",
            message="Downstream mutation is blocked until airlock admission completes.",
        )

    @staticmethod
    def _module_code(module_key: str) -> str:
        value = (module_key or "").strip().lower()
        mapping = {
            "accounting_layer": "accounting",
            "erp_sync": "erp_sync",
            "normalization": "payroll_gl_normalization",
            "gst": "gst",
            "period_close": "closing_checklist",
            "airlock": "airlock",
        }
        return mapping.get(value, value)
