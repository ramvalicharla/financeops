from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import UTC, date, datetime
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import NotFoundError, ValidationError
from financeops.core.intent.context import apply_mutation_linkage, require_mutation_context
from financeops.db.models.users import IamUser, UserRole
from financeops.modules.expense_management.models import ExpenseApproval, ExpenseClaim, ExpensePolicy
from financeops.modules.expense_management.policy_engine import ExpensePolicyEngine
from financeops.platform.db.models.entities import CpEntity


class PolicyViolationError(ValidationError):
    def __init__(self, message: str) -> None:
        super().__init__(message)


class JustificationRequiredError(ValidationError):
    def __init__(self, message: str) -> None:
        super().__init__(message)


def _q2(value: Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _q4(value: Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.0000"), rounding=ROUND_HALF_UP)


async def _get_or_create_policy(session: AsyncSession, tenant_id: uuid.UUID) -> ExpensePolicy:
    policy = (
        await session.execute(
            select(ExpensePolicy).where(ExpensePolicy.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if policy is not None:
        return policy

    require_mutation_context("Expense policy creation")
    policy = apply_mutation_linkage(ExpensePolicy(
        tenant_id=tenant_id,
        meal_limit_per_day=Decimal("2000.00"),
        travel_limit_per_night=Decimal("8000.00"),
        receipt_required_above=Decimal("500.00"),
        auto_approve_below=Decimal("0.00"),
        weekend_flag_enabled=True,
        round_number_flag_enabled=True,
        personal_merchant_keywords=["swiggy", "zomato", "amazon"],
    ))
    session.add(policy)
    await session.flush()
    return policy


async def get_policy(session: AsyncSession, tenant_id: uuid.UUID) -> ExpensePolicy | None:
    return (
        await session.execute(
            select(ExpensePolicy).where(ExpensePolicy.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()


async def _load_claim(session: AsyncSession, tenant_id: uuid.UUID, claim_id: uuid.UUID) -> ExpenseClaim:
    row = (
        await session.execute(
            select(ExpenseClaim).where(
                ExpenseClaim.tenant_id == tenant_id,
                ExpenseClaim.id == claim_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError("Expense claim not found")
    return row


async def _resolve_entity_id(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID | None,
) -> uuid.UUID:
    if entity_id is not None:
        exists = (
            await session.execute(
                select(CpEntity.id).where(
                    CpEntity.id == entity_id,
                    CpEntity.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if exists is None:
            raise ValidationError("Entity not found")
        return entity_id

    default_entity_id = (
        await session.execute(
            select(CpEntity.id)
            .where(
                CpEntity.tenant_id == tenant_id,
                CpEntity.status == "active",
            )
            .order_by(CpEntity.created_at.asc(), CpEntity.id.asc())
        )
    ).scalars().first()
    if default_entity_id is None:
        raise ValidationError("No active entity found for tenant")
    return default_entity_id


async def resolve_claim_status(
    session: AsyncSession,
    claim: ExpenseClaim,
) -> tuple[str, datetime | None, datetime | None]:
    approvals = (
        await session.execute(
            select(ExpenseApproval)
            .where(
                ExpenseApproval.tenant_id == claim.tenant_id,
                ExpenseApproval.claim_id == claim.id,
            )
            .order_by(ExpenseApproval.created_at.asc(), ExpenseApproval.id.asc())
        )
    ).scalars().all()

    manager_approved_at = claim.manager_approved_at
    finance_approved_at = claim.finance_approved_at
    status = claim.status

    for approval in approvals:
        action = approval.action
        if action == "rejected":
            status = "rejected"
        elif action == "returned":
            status = "submitted"
        elif action == "approved":
            if approval.approver_role in {
                UserRole.finance_team.value,
                "manager",
                "reviewer",
            } and manager_approved_at is None:
                manager_approved_at = approval.created_at
            if approval.approver_role in {
                UserRole.finance_leader.value,
                UserRole.super_admin.value,
                "finance",
            } and finance_approved_at is None:
                finance_approved_at = approval.created_at

    if status not in {"rejected", "returned"}:
        if manager_approved_at and finance_approved_at:
            status = "approved"
        elif manager_approved_at or finance_approved_at:
            status = "policy_checked"

    return status, manager_approved_at, finance_approved_at


async def submit_claim(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    submitted_by: uuid.UUID,
    vendor_name: str,
    description: str,
    category: str,
    amount: Decimal,
    currency: str,
    claim_date: date,
    has_receipt: bool,
    receipt_url: str | None = None,
    justification: str | None = None,
    location_id: uuid.UUID | None = None,
    cost_centre_id: uuid.UUID | None = None,
    entity_id: uuid.UUID | None = None,
) -> ExpenseClaim:
    """
    1. Load tenant expense_policy.
    2. Run policy engine check.
    3. If hard_block: raise PolicyViolationError(violation_message).
    4. If soft violation AND not justification provided:
       raise JustificationRequiredError(violation_message).
    5. Create expense_claim (append-only).
    6. If amount < auto_approve_below AND passed:
       auto-approve: set status='approved', finance_approved_at=now().
    7. Otherwise: status='submitted'.
    8. Return created claim.
    """
    require_mutation_context("Expense claim submission")
    policy = await _get_or_create_policy(session, tenant_id)
    engine = ExpensePolicyEngine(policy)
    amount_decimal = Decimal(str(amount))

    check = engine.check(
        category=category,
        amount=amount_decimal,
        currency=currency,
        claim_date=claim_date,
        vendor_name=vendor_name,
        has_receipt=has_receipt,
        existing_claims_same_day=[],
    )

    if check.is_hard_block:
        raise PolicyViolationError(check.violation_message or "Expense claim violates policy")
    if check.requires_justification and not str(justification or "").strip():
        raise JustificationRequiredError(check.violation_message or "Justification is required")

    auto_approve = bool(check.passed and amount_decimal < Decimal(str(policy.auto_approve_below)))
    now = datetime.now(UTC)
    resolved_entity_id = await _resolve_entity_id(session, tenant_id, entity_id)

    claim = apply_mutation_linkage(ExpenseClaim(
        tenant_id=tenant_id,
        entity_id=resolved_entity_id,
        location_id=location_id,
        cost_centre_id=cost_centre_id,
        submitted_by=submitted_by,
        period=claim_date.strftime("%Y-%m"),
        claim_date=claim_date,
        vendor_name=vendor_name,
        description=description,
        category=category,
        amount=_q2(amount_decimal),
        currency=currency,
        amount_inr=_q2(amount_decimal),
        receipt_url=receipt_url,
        status="approved" if auto_approve else "submitted",
        policy_violation_type=check.violation_type if check.violation_type else "none",
        policy_violation_requires_justification=check.requires_justification,
        justification=justification,
        finance_approved_at=now if auto_approve else None,
    ))
    session.add(claim)
    await session.flush()
    return claim


async def update_policy(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    updates: dict[str, object],
) -> ExpensePolicy:
    require_mutation_context("Expense policy update")
    policy = await _get_or_create_policy(session, tenant_id)
    for key, value in updates.items():
        setattr(policy, key, value)
    policy.updated_at = datetime.now(UTC)
    await session.flush()
    return policy


async def approve_claim(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    claim_id: uuid.UUID,
    approver_id: uuid.UUID,
    approver_role: str,
    action: str,
    comments: str | None = None,
) -> dict:
    """
    Create expense_approval record (append-only).
    Update claim status based on action:
      approved -> check if all required approval tiers done
      rejected -> status = 'rejected'
      returned -> status = 'submitted'
    Return updated claim payload.
    """
    require_mutation_context("Expense claim approval")
    action_value = str(action).strip().lower()
    if action_value not in {"approved", "rejected", "returned"}:
        raise ValidationError("Invalid approval action")

    claim = await _load_claim(session, tenant_id, claim_id)
    approval = apply_mutation_linkage(ExpenseApproval(
        claim_id=claim.id,
        tenant_id=tenant_id,
        approver_id=approver_id,
        approver_role=approver_role,
        action=action_value,
        comments=comments,
    ))
    session.add(approval)
    await session.flush()

    effective_status, manager_approved_at, finance_approved_at = await resolve_claim_status(session, claim)
    return {
        "id": str(claim.id),
        "status": effective_status,
        "manager_approved_at": manager_approved_at.isoformat() if manager_approved_at else None,
        "finance_approved_at": finance_approved_at.isoformat() if finance_approved_at else None,
    }


async def get_expense_analytics(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    period: str,
    entity_id: uuid.UUID | None = None,
) -> dict:
    """
    Returns for the period:
    - total_spend: Decimal
    - spend_by_category: { category: Decimal }
    - policy_violation_rate: Decimal (violations / total claims)
    - top_spenders: [{ user_id, user_name, total: Decimal }] top 5
    - itc_recovered: Decimal (sum of gst_amount where itc_eligible)
    All Decimal. Never float.
    """
    resolved_entity_id = await _resolve_entity_id(session, tenant_id, entity_id)
    claims = (
        await session.execute(
            select(ExpenseClaim).where(
                ExpenseClaim.tenant_id == tenant_id,
                ExpenseClaim.entity_id == resolved_entity_id,
                ExpenseClaim.period == period,
            )
        )
    ).scalars().all()

    total_spend = sum((Decimal(str(row.amount)) for row in claims), start=Decimal("0"))
    spend_by_category: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    violation_count = 0
    itc_recovered = Decimal("0")

    by_user: dict[uuid.UUID, Decimal] = defaultdict(lambda: Decimal("0"))
    for row in claims:
        spend_by_category[row.category] = spend_by_category[row.category] + Decimal(str(row.amount))
        by_user[row.submitted_by] = by_user[row.submitted_by] + Decimal(str(row.amount))
        if row.policy_violation_type and row.policy_violation_type != "none":
            violation_count += 1
        if row.itc_eligible:
            itc_recovered = itc_recovered + Decimal(str(row.gst_amount))

    users = (
        await session.execute(
            select(IamUser).where(
                IamUser.tenant_id == tenant_id,
                IamUser.id.in_(list(by_user.keys()) or [uuid.uuid4()]),
            )
        )
    ).scalars().all()
    user_map = {row.id: row.full_name for row in users}
    top_spenders = sorted(by_user.items(), key=lambda item: item[1], reverse=True)[:5]

    total_claims = Decimal(str(len(claims))) if claims else Decimal("0")
    if total_claims == Decimal("0"):
        violation_rate = Decimal("0.0000")
    else:
        violation_rate = _q4(Decimal(str(violation_count)) / total_claims)

    return {
        "total_spend": _q2(total_spend),
        "spend_by_category": {key: _q2(value) for key, value in spend_by_category.items()},
        "policy_violation_rate": violation_rate,
        "top_spenders": [
            {
                "user_id": str(user_id),
                "user_name": user_map.get(user_id, "Unknown"),
                "total": _q2(total),
            }
            for user_id, total in top_spenders
        ],
        "itc_recovered": _q2(itc_recovered),
    }

