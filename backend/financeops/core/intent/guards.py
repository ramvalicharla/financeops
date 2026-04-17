from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.governance.guards import (
    GuardEngine as UniversalGuardEngine,
    GuardEvaluationResult as UniversalGuardEvaluationResult,
    MutationGuardContext,
)
from financeops.core.intent.enums import GuardResultStatus, IntentType
from financeops.db.models.accounting_jv import AccountingJVAggregate, EntryType, JVStatus
from financeops.db.models.board_pack_generator import BoardPackGeneratorDefinition
from financeops.db.models.board_pack_narrative_engine import BoardPackRun
from financeops.db.models.custom_report_builder import ReportDefinition
from financeops.db.models.intent_pipeline import CanonicalIntent


@dataclass(frozen=True)
class GuardResult:
    guard_code: str
    guard_name: str
    result: GuardResultStatus
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    severity: str = "BLOCKING"
    evaluated_at: datetime | None = None


@dataclass(frozen=True)
class GuardEvaluationResult:
    overall_passed: bool
    results: list[GuardResult]

    @property
    def blocking_failures(self) -> list[GuardResult]:
        return [result for result in self.results if result.result == GuardResultStatus.FAIL]


class IntentGuardAdapter:
    def __init__(self) -> None:
        self._universal = UniversalGuardEngine()

    async def evaluate(
        self,
        db: AsyncSession,
        *,
        intent: CanonicalIntent,
        actor_role: str | None,
    ) -> GuardEvaluationResult:
        payload = dict(intent.payload_json or {})
        target_journal = await self._get_target_journal(db, intent.target_id, intent.tenant_id)
        target_type, target_exists = await self._resolve_target_scope(
            db,
            intent=intent,
            target_journal=target_journal,
        )
        period_year, period_number = self._resolve_period(intent=intent, payload=payload, target_journal=target_journal)
        universal = await self._universal.evaluate_mutation(
            db,
            context=MutationGuardContext(
                tenant_id=intent.tenant_id,
                module_key=intent.module_key,
                mutation_type=intent.intent_type,
                actor_user_id=intent.requested_by_user_id,
                actor_role=actor_role,
                entity_id=intent.entity_id,
                target_type=target_type,
                target_id=intent.target_id,
                target_exists=target_exists,
                state_valid=self._state_valid(intent=intent, target_journal=target_journal),
                immutable_ok=self._immutable_ok(intent=intent, target_journal=target_journal),
                admitted_airlock_item_id=self._admitted_airlock_item_id(payload=payload),
                requires_airlock_admission=self._requires_airlock_admission(intent.intent_type),
                period_year=period_year,
                period_number=period_number,
                period_guard_mode=self._period_mode(intent.intent_type),
                source_type=str(payload.get("source_type") or ""),
                subject_type="intent",
                subject_id=str(intent.id),
            ),
        )
        results = [self._map_result(item) for item in universal.results]

        balance_result = self._check_balance(payload=payload, intent=intent, target_journal=target_journal)
        if balance_result is not None:
            results.append(balance_result)

        return GuardEvaluationResult(
            overall_passed=universal.overall_passed
            and not any(result.result == GuardResultStatus.FAIL for result in results),
            results=results,
        )

    def _map_result(self, item) -> GuardResult:
        return GuardResult(
            guard_code=item.guard_code,
            guard_name=item.guard_name,
            result=GuardResultStatus(item.result),
            message=item.message,
            details=item.details_json,
            severity=item.severity,
            evaluated_at=item.evaluated_at,
        )

    @staticmethod
    def _period_mode(intent_type: str) -> str | None:
        if intent_type in {
            IntentType.CREATE_ERP_SYNC_RUN.value,
            IntentType.CREATE_NORMALIZATION_RUN.value,
            IntentType.IMPORT_BANK_STATEMENT.value,
            IntentType.CREATE_REPORT_DEFINITION.value,
            IntentType.UPDATE_REPORT_DEFINITION.value,
            IntentType.DEACTIVATE_REPORT_DEFINITION.value,
            IntentType.GENERATE_REPORT.value,
            IntentType.CREATE_BOARD_PACK_DEFINITION.value,
            IntentType.UPDATE_BOARD_PACK_DEFINITION.value,
            IntentType.DEACTIVATE_BOARD_PACK_DEFINITION.value,
            IntentType.CREATE_BOARD_PACK_NARRATIVE_DEFINITION.value,
            IntentType.CREATE_BOARD_PACK_SECTION_DEFINITION.value,
            IntentType.CREATE_NARRATIVE_TEMPLATE.value,
            IntentType.CREATE_BOARD_PACK_INCLUSION_RULE.value,
            IntentType.CREATE_BOARD_PACK_NARRATIVE_RUN.value,
            IntentType.EXECUTE_BOARD_PACK_NARRATIVE_RUN.value,
            IntentType.GENERATE_BOARD_PACK.value,
            IntentType.START_LEGACY_CONSOLIDATION_RUN.value,
            IntentType.BATCH_MUTATION.value,
            IntentType.RETRY_BATCH_MUTATION.value,
            IntentType.CREATE_BUDGET_VERSION.value,
            IntentType.UPSERT_BUDGET_LINE.value,
            IntentType.SUBMIT_BUDGET_VERSION.value,
            IntentType.APPROVE_BUDGET_VERSION.value,
            IntentType.COMPUTE_WORKING_CAPITAL_SNAPSHOT.value,
            IntentType.CREATE_CHECKLIST_TEMPLATE.value,
            IntentType.ENSURE_CHECKLIST_RUN.value,
            IntentType.UPDATE_CHECKLIST_TASK_STATUS.value,
            IntentType.ASSIGN_CHECKLIST_TASK.value,
            IntentType.AUTO_COMPLETE_CHECKLIST_TASKS.value,
            IntentType.CREATE_MONTHEND_CHECKLIST.value,
            IntentType.ADD_MONTHEND_TASK.value,
            IntentType.UPDATE_MONTHEND_TASK_STATUS.value,
            IntentType.CLOSE_MONTHEND_CHECKLIST.value,
            IntentType.CREATE_FORECAST_RUN.value,
            IntentType.UPDATE_FORECAST_ASSUMPTION.value,
            IntentType.COMPUTE_FORECAST_LINES.value,
            IntentType.PUBLISH_FORECAST.value,
            IntentType.CREATE_CASH_FLOW_FORECAST.value,
            IntentType.UPDATE_CASH_FLOW_WEEK.value,
            IntentType.PUBLISH_CASH_FLOW_FORECAST.value,
            IntentType.COMPUTE_TAX_PROVISION.value,
            IntentType.UPSERT_TAX_POSITION.value,
            IntentType.ADD_TRANSFER_PRICING_TRANSACTION.value,
            IntentType.GENERATE_TRANSFER_PRICING_DOC.value,
            IntentType.ENSURE_EXPENSE_POLICY.value,
            IntentType.SUBMIT_EXPENSE_CLAIM.value,
            IntentType.UPDATE_EXPENSE_POLICY.value,
            IntentType.APPROVE_EXPENSE_CLAIM.value,
            IntentType.ENSURE_MULTI_GAAP_CONFIG.value,
            IntentType.UPDATE_MULTI_GAAP_CONFIG.value,
            IntentType.COMPUTE_MULTI_GAAP_VIEW.value,
            IntentType.ENSURE_STATUTORY_FILINGS.value,
            IntentType.MARK_STATUTORY_FILING.value,
            IntentType.ADD_STATUTORY_REGISTER_ENTRY.value,
            IntentType.CREATE_COVENANT_DEFINITION.value,
            IntentType.UPDATE_COVENANT_DEFINITION.value,
            IntentType.CHECK_COVENANTS.value,
        }:
            return None
        if intent_type in {IntentType.POST_JOURNAL.value, IntentType.REVERSE_JOURNAL.value}:
            return "post"
        return "modify"

    @staticmethod
    def _requires_airlock_admission(intent_type: str) -> bool:
        return intent_type in {
            IntentType.CREATE_ERP_SYNC_RUN.value,
            IntentType.CREATE_NORMALIZATION_RUN.value,
            IntentType.IMPORT_BANK_STATEMENT.value,
        }

    @staticmethod
    def _admitted_airlock_item_id(*, payload: dict[str, Any]) -> uuid.UUID | None:
        raw = payload.get("admitted_airlock_item_id")
        if raw in {None, ""}:
            return None
        return uuid.UUID(str(raw))

    @staticmethod
    def _resolve_period(
        *,
        intent: CanonicalIntent,
        payload: dict[str, Any],
        target_journal: AccountingJVAggregate | None,
    ) -> tuple[int | None, int | None]:
        if payload.get("journal_date"):
            return int(str(payload["journal_date"])[:4]), int(str(payload["journal_date"])[5:7])
        period_year = payload.get("period_year")
        period_number = payload.get("period_number", payload.get("period_month"))
        if period_year is not None and period_number is not None:
            return int(period_year), int(period_number)
        if target_journal is not None:
            return target_journal.fiscal_year, target_journal.fiscal_period
        return None, None

    @staticmethod
    def _state_valid(
        *,
        intent: CanonicalIntent,
        target_journal: AccountingJVAggregate | None,
    ) -> bool | None:
        if target_journal is None:
            return None
        if intent.intent_type == IntentType.POST_JOURNAL.value:
            return target_journal.status == JVStatus.APPROVED
        if intent.intent_type == IntentType.REVERSE_JOURNAL.value:
            return target_journal.status == JVStatus.PUSHED
        return True

    @staticmethod
    def _immutable_ok(
        *,
        intent: CanonicalIntent,
        target_journal: AccountingJVAggregate | None,
    ) -> bool | None:
        if target_journal is None:
            return None
        if intent.intent_type == IntentType.REVERSE_JOURNAL.value:
            return target_journal.status != JVStatus.VOIDED
        return True

    @staticmethod
    def _check_balance(
        *,
        payload: dict[str, Any],
        intent: CanonicalIntent,
        target_journal: AccountingJVAggregate | None,
    ) -> GuardResult | None:
        try:
            if intent.intent_type == IntentType.CREATE_JOURNAL.value:
                total_debit = sum(float(line.get("debit", 0) or 0) for line in payload.get("lines", []))
                total_credit = sum(float(line.get("credit", 0) or 0) for line in payload.get("lines", []))
                if total_debit != total_credit:
                    raise ValueError("Journal payload is not balanced.")
            elif target_journal is not None:
                latest_version = max((candidate.jv_version for candidate in target_journal.lines), default=target_journal.version)
                active_lines = [line for line in target_journal.lines if line.jv_version == latest_version]
                total_debit = sum(
                    float(line.base_amount if line.base_amount is not None else line.amount)
                    for line in active_lines
                    if line.entry_type == EntryType.DEBIT
                )
                total_credit = sum(
                    float(line.base_amount if line.base_amount is not None else line.amount)
                    for line in active_lines
                    if line.entry_type == EntryType.CREDIT
                )
                if total_debit != total_credit:
                    raise ValueError("Target journal is not balanced.")
            else:
                return None
        except Exception as exc:
            return GuardResult(
                guard_code="journal.balanced",
                guard_name="Journal balances",
                result=GuardResultStatus.FAIL,
                message=str(exc),
            )
        return GuardResult(
            guard_code="journal.balanced",
            guard_name="Journal balances",
            result=GuardResultStatus.PASS,
            message="Journal balance guard passed.",
        )

    @staticmethod
    async def _get_target_journal(
        db: AsyncSession,
        journal_id: uuid.UUID | None,
        tenant_id: uuid.UUID,
    ) -> AccountingJVAggregate | None:
        if journal_id is None:
            return None
        result = await db.execute(
            select(AccountingJVAggregate).where(
                AccountingJVAggregate.id == journal_id,
                AccountingJVAggregate.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def _resolve_target_scope(
        db: AsyncSession,
        *,
        intent: CanonicalIntent,
        target_journal: AccountingJVAggregate | None,
    ) -> tuple[str | None, bool | None]:
        if intent.target_id is None:
            return None, None
        if intent.intent_type in {
            IntentType.UPDATE_REPORT_DEFINITION.value,
            IntentType.DEACTIVATE_REPORT_DEFINITION.value,
        }:
            exists = (
                await db.execute(
                    select(ReportDefinition.id).where(
                        ReportDefinition.id == intent.target_id,
                        ReportDefinition.tenant_id == intent.tenant_id,
                    )
                )
            ).scalar_one_or_none() is not None
            return "report_definition", exists
        if intent.intent_type == IntentType.CREATE_BOARD_PACK_NARRATIVE_DEFINITION.value:
            return "board_pack_definition", None
        if intent.intent_type == IntentType.CREATE_BOARD_PACK_SECTION_DEFINITION.value:
            return "board_pack_section_definition", None
        if intent.intent_type == IntentType.CREATE_NARRATIVE_TEMPLATE.value:
            return "narrative_template", None
        if intent.intent_type == IntentType.CREATE_BOARD_PACK_INCLUSION_RULE.value:
            return "board_pack_inclusion_rule", None
        if intent.intent_type in {
            IntentType.UPDATE_BOARD_PACK_DEFINITION.value,
            IntentType.DEACTIVATE_BOARD_PACK_DEFINITION.value,
        }:
            exists = (
                await db.execute(
                    select(BoardPackGeneratorDefinition.id).where(
                        BoardPackGeneratorDefinition.id == intent.target_id,
                        BoardPackGeneratorDefinition.tenant_id == intent.tenant_id,
                    )
                )
            ).scalar_one_or_none() is not None
            return "board_pack_definition", exists
        if intent.intent_type == IntentType.EXECUTE_BOARD_PACK_NARRATIVE_RUN.value:
            exists = (
                await db.execute(
                    select(BoardPackRun.id).where(
                        BoardPackRun.tenant_id == intent.tenant_id,
                        BoardPackRun.id == intent.target_id,
                    )
                )
            ).scalar_one_or_none() is not None
            return "board_pack_run", exists
        return "journal", target_journal is not None
