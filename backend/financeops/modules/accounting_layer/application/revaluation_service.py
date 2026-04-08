from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import ValidationError
from financeops.core.governance.approvals import ApprovalPolicyResolver, ApprovalRequest
from financeops.core.governance.events import GovernanceActor, emit_governance_event
from financeops.core.governance.guards import GuardEngine, MutationGuardContext
from financeops.core.intent.enums import IntentSourceChannel, IntentType
from financeops.core.intent.journal_pipeline import submit_governed_journal_intent
from financeops.db.models.accounting_jv import AccountingJVAggregate, AccountingJVLine, EntryType, JVStatus
from financeops.db.models.fx_ias21 import AccountingFxRevaluationLine, AccountingFxRevaluationRun
from financeops.db.models.users import IamUser, UserRole
from financeops.modules.accounting_layer.domain.schemas import JournalCreate
from financeops.modules.coa.models import CoaLedgerAccount, TenantCoaAccount
from financeops.platform.db.models.entities import CpEntity
from financeops.services.audit_writer import AuditWriter
from financeops.services.fx.ias21_math import compute_revaluation_delta
from financeops.services.fx.rate_master_service import get_required_latest_fx_rate

_ZERO = Decimal("0")
_GAIN_LOSS_ACCOUNT_CODE = "FX_GAIN_LOSS"
_GAIN_LOSS_ACCOUNT_NAME = "Foreign Exchange Gain/Loss"


@dataclass(frozen=True)
class _Exposure:
    account_code: str
    account_name: str
    transaction_currency: str
    functional_currency: str
    foreign_balance: Decimal
    historical_base_balance: Decimal


def _is_monetary_fallback(code: str, name: str) -> bool:
    text = f"{code} {name}".upper()
    return any(token in text for token in ("CASH", "BANK", "RECEIVABLE", "PAYABLE", "DUE FROM", "DUE TO"))


def _is_finance_operator_role(actor_role: str | None) -> bool:
    normalized = (actor_role or "").strip().lower()
    return normalized in {
        UserRole.finance_team.value,
        UserRole.finance_leader.value,
        UserRole.super_admin.value,
        UserRole.platform_owner.value,
        UserRole.platform_admin.value,
    }


async def _resolve_distinct_approver(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    initiated_by: uuid.UUID,
) -> IamUser:
    result = await db.execute(
        select(IamUser)
        .where(
            IamUser.tenant_id == tenant_id,
            IamUser.is_active.is_(True),
            IamUser.id != initiated_by,
            IamUser.role.in_(
                [
                    UserRole.finance_leader,
                    UserRole.super_admin,
                    UserRole.platform_owner,
                    UserRole.platform_admin,
                ]
            ),
        )
        .order_by(IamUser.created_at.asc())
        .limit(1)
    )
    approver = result.scalar_one_or_none()
    if approver is None:
        raise ValidationError(
            "FX revaluation requires a distinct active finance approver to complete the governed journal pipeline."
        )
    return approver


async def _run_adjustment_journal_pipeline(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    as_of_date: date,
    initiated_by: uuid.UUID,
    actor_role: str | None,
    lines: list[dict[str, object]],
) -> tuple[uuid.UUID, dict[str, dict[str, object]]]:
    if not _is_finance_operator_role(actor_role):
        raise ValidationError("FX revaluation requires a finance operator role to create the adjustment journal.")

    approver = await _resolve_distinct_approver(
        db,
        tenant_id=tenant_id,
        initiated_by=initiated_by,
    )
    journal_payload = JournalCreate(
        org_entity_id=entity_id,
        journal_date=as_of_date,
        reference=f"FX_REVAL:{as_of_date.isoformat()}",
        narration=f"FX Revaluation run for {as_of_date.isoformat()}",
        lines=[
            {
                "account_code": str(line["account_code"]),
                "debit": Decimal(str(line["amount"])) if line["entry_type"] == EntryType.DEBIT else Decimal("0"),
                "credit": Decimal(str(line["amount"])) if line["entry_type"] == EntryType.CREDIT else Decimal("0"),
                "memo": line.get("narration"),
                "transaction_currency": line.get("transaction_currency"),
                "functional_currency": line.get("functional_currency"),
                "fx_rate": line.get("fx_rate"),
                "base_amount": line.get("base_amount"),
            }
            for line in lines
        ],
    )
    create_payload = journal_payload.model_dump(mode="json")
    create_payload["source"] = "FX_REVALUATION"
    create_payload["external_reference_id"] = f"FX_REVAL:{as_of_date.isoformat()}"

    create_result = await submit_governed_journal_intent(
        db,
        intent_type=IntentType.CREATE_JOURNAL,
        tenant_id=tenant_id,
        user_id=initiated_by,
        actor_role=actor_role or UserRole.finance_team.value,
        source_channel=IntentSourceChannel.API.value,
        namespace=f"fx_revaluation_create:{entity_id}:{as_of_date.isoformat()}",
        payload=create_payload,
    )
    journal_id = create_result.require_journal_id()
    submit_result = await submit_governed_journal_intent(
        db,
        intent_type=IntentType.SUBMIT_JOURNAL,
        tenant_id=tenant_id,
        user_id=initiated_by,
        actor_role=actor_role or UserRole.finance_team.value,
        source_channel=IntentSourceChannel.API.value,
        namespace=f"fx_revaluation_submit:{journal_id}",
        target_id=journal_id,
    )
    review_result = await submit_governed_journal_intent(
        db,
        intent_type=IntentType.REVIEW_JOURNAL,
        tenant_id=tenant_id,
        user_id=initiated_by,
        actor_role=actor_role or UserRole.finance_team.value,
        source_channel=IntentSourceChannel.API.value,
        namespace=f"fx_revaluation_review:{journal_id}",
        target_id=journal_id,
    )
    approve_result = await submit_governed_journal_intent(
        db,
        intent_type=IntentType.APPROVE_JOURNAL,
        tenant_id=tenant_id,
        user_id=approver.id,
        actor_role=approver.role.value,
        source_channel=IntentSourceChannel.SYSTEM.value,
        namespace=f"fx_revaluation_approve:{journal_id}",
        target_id=journal_id,
    )
    post_result = await submit_governed_journal_intent(
        db,
        intent_type=IntentType.POST_JOURNAL,
        tenant_id=tenant_id,
        user_id=approver.id,
        actor_role=approver.role.value,
        source_channel=IntentSourceChannel.SYSTEM.value,
        namespace=f"fx_revaluation_post:{journal_id}",
        target_id=journal_id,
    )
    pipeline = {
        "create": create_result.model_dump(),
        "submit": submit_result.model_dump(),
        "review": review_result.model_dump(),
        "approve": approve_result.model_dump(),
        "post": post_result.model_dump(),
    }
    return journal_id, pipeline


async def _get_entity_for_tenant(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
) -> CpEntity:
    stmt = select(CpEntity).where(
        CpEntity.id == entity_id,
        CpEntity.tenant_id == tenant_id,
    )
    result = await db.execute(stmt)
    entity = result.scalar_one_or_none()
    if entity is None:
        raise ValidationError("Entity does not belong to tenant.")
    return entity


async def _load_monetary_exposures(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    as_of_date: date,
    functional_currency: str,
) -> list[_Exposure]:
    signed_foreign = case(
        (AccountingJVLine.entry_type == EntryType.DEBIT, AccountingJVLine.amount),
        else_=-AccountingJVLine.amount,
    )
    signed_base = case(
        (
            AccountingJVLine.entry_type == EntryType.DEBIT,
            func.coalesce(AccountingJVLine.base_amount, AccountingJVLine.amount_inr, AccountingJVLine.amount),
        ),
        else_=-func.coalesce(AccountingJVLine.base_amount, AccountingJVLine.amount_inr, AccountingJVLine.amount),
    )
    stmt = (
        select(
            AccountingJVLine.account_code,
            func.coalesce(AccountingJVLine.account_name, AccountingJVLine.account_code).label("account_name"),
            func.coalesce(
                AccountingJVLine.transaction_currency,
                AccountingJVLine.currency,
                functional_currency,
            ).label("transaction_currency"),
            func.coalesce(AccountingJVLine.functional_currency, functional_currency).label("functional_currency"),
            func.coalesce(func.sum(signed_foreign), _ZERO).label("foreign_balance"),
            func.coalesce(func.sum(signed_base), _ZERO).label("historical_base_balance"),
            func.bool_or(func.coalesce(CoaLedgerAccount.is_monetary, False)).label("is_monetary"),
        )
        .join(
            AccountingJVAggregate,
            and_(
                AccountingJVAggregate.id == AccountingJVLine.jv_id,
                AccountingJVAggregate.tenant_id == tenant_id,
            ),
        )
        .outerjoin(
            TenantCoaAccount,
            and_(
                TenantCoaAccount.tenant_id == tenant_id,
                TenantCoaAccount.account_code == AccountingJVLine.account_code,
                TenantCoaAccount.is_active.is_(True),
            ),
        )
        .outerjoin(
            CoaLedgerAccount,
            CoaLedgerAccount.id == TenantCoaAccount.ledger_account_id,
        )
        .where(
            AccountingJVLine.tenant_id == tenant_id,
            AccountingJVAggregate.entity_id == entity_id,
            AccountingJVAggregate.period_date <= as_of_date,
            AccountingJVAggregate.status.in_([JVStatus.PUSHED, JVStatus.PUSH_IN_PROGRESS]),
        )
        .group_by(
            AccountingJVLine.account_code,
            func.coalesce(AccountingJVLine.account_name, AccountingJVLine.account_code),
            func.coalesce(
                AccountingJVLine.transaction_currency,
                AccountingJVLine.currency,
                functional_currency,
            ),
            func.coalesce(AccountingJVLine.functional_currency, functional_currency),
        )
        .order_by(AccountingJVLine.account_code.asc())
    )

    result = await db.execute(stmt)
    exposures: list[_Exposure] = []
    for row in result.all():
        transaction_currency = str(row.transaction_currency or functional_currency).upper()
        local_functional_currency = str(row.functional_currency or functional_currency).upper()
        if transaction_currency == local_functional_currency:
            continue
        is_monetary = bool(row.is_monetary) or _is_monetary_fallback(
            str(row.account_code),
            str(row.account_name),
        )
        if not is_monetary:
            continue
        exposures.append(
            _Exposure(
                account_code=str(row.account_code),
                account_name=str(row.account_name),
                transaction_currency=transaction_currency,
                functional_currency=local_functional_currency,
                foreign_balance=Decimal(str(row.foreign_balance or "0")),
                historical_base_balance=Decimal(str(row.historical_base_balance or "0")),
            )
        )
    return exposures


async def run_fx_revaluation(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    as_of_date: date,
    initiated_by: uuid.UUID,
    actor_role: str | None = None,
) -> dict[str, object]:
    entity = await _get_entity_for_tenant(db, tenant_id=tenant_id, entity_id=entity_id)
    guard_engine = GuardEngine()
    approval_resolver = ApprovalPolicyResolver()
    actor = GovernanceActor(user_id=initiated_by, role=actor_role)
    guard_result = await guard_engine.evaluate_mutation(
        db,
        context=MutationGuardContext(
            tenant_id=tenant_id,
            module_key="accounting_layer",
            mutation_type="FX_REVALUATION_RUN",
            actor_user_id=initiated_by,
            actor_role=actor_role,
            entity_id=entity_id,
            period_year=as_of_date.year,
            period_number=as_of_date.month,
            period_guard_mode="revaluation",
            subject_type="fx_revaluation_run",
            subject_id=f"{entity_id}:{as_of_date.isoformat()}",
        ),
    )
    if not guard_result.overall_passed:
        raise ValidationError("; ".join(item.message for item in guard_result.blocking_failures))
    approval = await approval_resolver.resolve_mutation(
        db,
        request=ApprovalRequest(
            tenant_id=tenant_id,
            module_key="accounting_layer",
            mutation_type="FX_REVALUATION_RUN",
            entity_id=entity_id,
            actor_user_id=initiated_by,
            actor_role=actor_role,
            subject_type="fx_revaluation_run",
            subject_id=f"{entity_id}:{as_of_date.isoformat()}",
        ),
    )
    if approval.approval_required and not approval.is_granted:
        raise ValidationError(approval.reason)
    await emit_governance_event(
        db,
        tenant_id=tenant_id,
        module_key="accounting_layer",
        subject_type="fx_revaluation_run",
        subject_id=f"{entity_id}:{as_of_date.isoformat()}",
        event_type="AUTH_CONTEXT_CAPTURED",
        actor=actor,
        entity_id=entity_id,
        payload={"as_of_date": as_of_date.isoformat()},
    )
    exposures = await _load_monetary_exposures(
        db,
        tenant_id=tenant_id,
        entity_id=entity_id,
        as_of_date=as_of_date,
        functional_currency=entity.base_currency,
    )

    line_results: list[dict[str, object]] = []
    adjustment_lines: list[dict[str, object]] = []
    total_fx_difference = _ZERO

    for exposure in exposures:
        if exposure.foreign_balance == _ZERO:
            continue
        closing_rate = await get_required_latest_fx_rate(
            db,
            tenant_id=tenant_id,
            from_currency=exposure.transaction_currency,
            to_currency=exposure.functional_currency,
            rate_type="CLOSING",
            as_of_date=as_of_date,
        )
        closing_rate_value = Decimal(str(closing_rate.rate))
        revalued_base, fx_difference = compute_revaluation_delta(
            foreign_balance=exposure.foreign_balance,
            closing_rate=closing_rate_value,
            historical_base_balance=exposure.historical_base_balance,
        )

        line_results.append(
            {
                "account_code": exposure.account_code,
                "account_name": exposure.account_name,
                "transaction_currency": exposure.transaction_currency,
                "functional_currency": exposure.functional_currency,
                "foreign_balance": exposure.foreign_balance,
                "historical_base_balance": exposure.historical_base_balance,
                "closing_rate": closing_rate_value,
                "revalued_base_balance": revalued_base,
                "fx_difference": fx_difference,
            }
        )
        if fx_difference == _ZERO:
            continue

        adjustment_amount = abs(fx_difference)
        total_fx_difference += fx_difference

        if fx_difference > _ZERO:
            account_entry_type = EntryType.DEBIT
            gain_loss_entry_type = EntryType.CREDIT
        else:
            account_entry_type = EntryType.CREDIT
            gain_loss_entry_type = EntryType.DEBIT

        adjustment_lines.extend(
            [
                {
                    "account_code": exposure.account_code,
                    "account_name": exposure.account_name,
                    "entry_type": account_entry_type,
                    "amount": adjustment_amount,
                    "currency": exposure.functional_currency,
                    "transaction_currency": exposure.functional_currency,
                    "functional_currency": exposure.functional_currency,
                    "fx_rate": None,
                    "base_amount": adjustment_amount,
                    "amount_inr": adjustment_amount if exposure.functional_currency == "INR" else None,
                    "entity_id": entity_id,
                    "narration": f"FX revaluation @ {as_of_date.isoformat()}",
                },
                {
                    "account_code": _GAIN_LOSS_ACCOUNT_CODE,
                    "account_name": _GAIN_LOSS_ACCOUNT_NAME,
                    "entry_type": gain_loss_entry_type,
                    "amount": adjustment_amount,
                    "currency": exposure.functional_currency,
                    "transaction_currency": exposure.functional_currency,
                    "functional_currency": exposure.functional_currency,
                    "fx_rate": None,
                    "base_amount": adjustment_amount,
                    "amount_inr": adjustment_amount if exposure.functional_currency == "INR" else None,
                    "entity_id": entity_id,
                    "narration": f"FX revaluation offset @ {as_of_date.isoformat()}",
                },
            ]
        )

    adjustment_jv_id: uuid.UUID | None = None
    adjustment_pipeline: dict[str, dict[str, object]] | None = None
    run_status = "COMPLETED_NO_ADJUSTMENT"
    if adjustment_lines:
        adjustment_jv_id, adjustment_pipeline = await _run_adjustment_journal_pipeline(
            db,
            tenant_id=tenant_id,
            entity_id=entity_id,
            as_of_date=as_of_date,
            initiated_by=initiated_by,
            actor_role=actor_role,
            lines=adjustment_lines,
        )
        run_status = "COMPLETED"

    run = await AuditWriter.insert_financial_record(
        db,
        model_class=AccountingFxRevaluationRun,
        tenant_id=tenant_id,
        record_data={
            "entity_id": str(entity_id),
            "as_of_date": as_of_date.isoformat(),
            "status": run_status,
            "adjustment_jv_id": str(adjustment_jv_id) if adjustment_jv_id else None,
            "adjustment_pipeline": adjustment_pipeline,
        },
        values={
            "id": uuid.uuid4(),
            "entity_id": entity_id,
            "as_of_date": as_of_date,
            "status": run_status,
            "closing_rate_source": "fx_rates",
            "initiated_by": initiated_by,
            "adjustment_jv_id": adjustment_jv_id,
        },
    )

    for row in line_results:
        await AuditWriter.insert_financial_record(
            db,
            model_class=AccountingFxRevaluationLine,
            tenant_id=tenant_id,
            record_data={
                "run_id": str(run.id),
                "account_code": str(row["account_code"]),
                "transaction_currency": str(row["transaction_currency"]),
                "fx_difference": str(row["fx_difference"]),
            },
            values={
                "id": uuid.uuid4(),
                "run_id": run.id,
                "account_code": row["account_code"],
                "account_name": row["account_name"],
                "transaction_currency": row["transaction_currency"],
                "functional_currency": row["functional_currency"],
                "foreign_balance": row["foreign_balance"],
                "historical_base_balance": row["historical_base_balance"],
                "closing_rate": row["closing_rate"],
                "revalued_base_balance": row["revalued_base_balance"],
                "fx_difference": row["fx_difference"],
            },
        )

    await db.flush()
    await emit_governance_event(
        db,
        tenant_id=tenant_id,
        module_key="accounting_layer",
        subject_type="fx_revaluation_run",
        subject_id=str(run.id),
        event_type="RECORD_RECORDED",
        actor=actor,
        entity_id=entity_id,
        payload={
            "run_id": str(run.id),
            "entity_id": str(entity_id),
            "as_of_date": as_of_date.isoformat(),
            "status": run_status,
            "adjustment_jv_id": str(adjustment_jv_id) if adjustment_jv_id else None,
            "adjustment_pipeline": adjustment_pipeline,
        },
    )
    return {
        "run_id": str(run.id),
        "entity_id": str(entity_id),
        "as_of_date": as_of_date.isoformat(),
        "functional_currency": entity.base_currency,
        "status": run_status,
        "adjustment_jv_id": str(adjustment_jv_id) if adjustment_jv_id else None,
        "adjustment_pipeline": adjustment_pipeline,
        "line_count": len(line_results),
        "total_fx_difference": str(total_fx_difference.quantize(Decimal("0.0001"))),
    }
