from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user, require_finance_leader
from financeops.core.exceptions import NotFoundError, ValidationError
from financeops.db.models.users import IamUser, UserRole
from financeops.modules.expense_management.models import ExpenseApproval, ExpenseClaim, ExpensePolicy
from financeops.modules.expense_management.service import (
    JustificationRequiredError,
    PolicyViolationError,
    _get_or_create_policy,
    approve_claim,
    get_expense_analytics,
    resolve_claim_status,
    submit_claim,
)
from financeops.modules.notifications.service import send_notification
from financeops.shared_kernel.pagination import Paginated

router = APIRouter(prefix="/expenses", tags=["expenses"])


class SubmitExpenseRequest(BaseModel):
    vendor_name: str
    description: str
    category: str
    amount: str
    currency: str = "INR"
    claim_date: date
    has_receipt: bool
    receipt_url: str | None = None
    justification: str | None = None


class ApproveExpenseRequest(BaseModel):
    action: str
    comments: str | None = None


class PolicyPatchRequest(BaseModel):
    meal_limit_per_day: str | None = None
    travel_limit_per_night: str | None = None
    receipt_required_above: str | None = None
    auto_approve_below: str | None = None
    weekend_flag_enabled: bool | None = None
    round_number_flag_enabled: bool | None = None
    personal_merchant_keywords: list[str] | None = None


def _decimal_or_422(value: str, field_name: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"{field_name} must be a decimal string") from exc


async def _serialize_claim(session: AsyncSession, claim: ExpenseClaim) -> dict:
    status_value, manager_approved_at, finance_approved_at = await resolve_claim_status(session, claim)
    return {
        "id": str(claim.id),
        "tenant_id": str(claim.tenant_id),
        "submitted_by": str(claim.submitted_by),
        "period": claim.period,
        "claim_date": claim.claim_date.isoformat(),
        "vendor_name": claim.vendor_name,
        "description": claim.description,
        "category": claim.category,
        "amount": format(claim.amount, "f"),
        "currency": claim.currency,
        "amount_inr": format(claim.amount_inr, "f"),
        "receipt_url": claim.receipt_url,
        "status": status_value,
        "policy_violation_type": claim.policy_violation_type,
        "policy_violation_requires_justification": claim.policy_violation_requires_justification,
        "justification": claim.justification,
        "manager_id": str(claim.manager_id) if claim.manager_id else None,
        "manager_approved_at": manager_approved_at.isoformat() if manager_approved_at else None,
        "finance_approved_at": finance_approved_at.isoformat() if finance_approved_at else None,
        "created_at": claim.created_at.isoformat(),
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def submit_expense(
    body: SubmitExpenseRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    amount = _decimal_or_422(body.amount, "amount")
    try:
        claim = await submit_claim(
            session,
            tenant_id=user.tenant_id,
            submitted_by=user.id,
            vendor_name=body.vendor_name,
            description=body.description,
            category=body.category,
            amount=amount,
            currency=body.currency,
            claim_date=body.claim_date,
            has_receipt=body.has_receipt,
            receipt_url=body.receipt_url,
            justification=body.justification,
        )
    except PolicyViolationError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    except JustificationRequiredError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc

    await session.flush()
    return await _serialize_claim(session, claim)


@router.get("")
async def list_expenses(
    status_filter: str | None = Query(default=None, alias="status"),
    period: str | None = Query(default=None),
    submitted_by: uuid.UUID | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int | None = Query(default=None, ge=0),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Paginated[dict]:
    if submitted_by is not None and user.role not in {UserRole.finance_leader, UserRole.super_admin}:
        raise HTTPException(status_code=403, detail="Only finance leader can filter by submitted_by")

    effective_skip = offset if offset is not None else skip
    stmt = select(ExpenseClaim).where(ExpenseClaim.tenant_id == user.tenant_id)
    if period:
        stmt = stmt.where(ExpenseClaim.period == period)
    if submitted_by is not None:
        stmt = stmt.where(ExpenseClaim.submitted_by == submitted_by)
    elif user.role not in {UserRole.finance_leader, UserRole.super_admin}:
        stmt = stmt.where(ExpenseClaim.submitted_by == user.id)
    if status_filter:
        stmt = stmt.where(ExpenseClaim.status == status_filter)

    total = (
        await session.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()
    rows = (
        await session.execute(
            stmt.order_by(ExpenseClaim.created_at.desc(), ExpenseClaim.id.desc())
            .offset(effective_skip)
            .limit(limit)
        )
    ).scalars().all()

    serialized: list[dict] = []
    for row in rows:
        serialized.append(await _serialize_claim(session, row))

    return Paginated[dict](
        items=serialized,
        total=int(total),
        skip=effective_skip,
        limit=limit,
        has_more=(effective_skip + len(serialized)) < int(total),
    )


@router.get("/analytics")
async def analytics(
    period: str | None = Query(default=None),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    target_period = period or datetime.now(UTC).strftime("%Y-%m")
    payload = await get_expense_analytics(session, user.tenant_id, target_period)
    return {
        "total_spend": format(payload["total_spend"], "f"),
        "spend_by_category": {
            key: format(value, "f") for key, value in payload["spend_by_category"].items()
        },
        "policy_violation_rate": format(payload["policy_violation_rate"], "f"),
        "top_spenders": [
            {
                "user_id": item["user_id"],
                "user_name": item["user_name"],
                "total": format(item["total"], "f"),
            }
            for item in payload["top_spenders"]
        ],
        "itc_recovered": format(payload["itc_recovered"], "f"),
    }


@router.get("/policy")
async def get_policy(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    policy = await _get_or_create_policy(session, user.tenant_id)
    return {
        "id": str(policy.id),
        "tenant_id": str(policy.tenant_id),
        "meal_limit_per_day": format(policy.meal_limit_per_day, "f"),
        "travel_limit_per_night": format(policy.travel_limit_per_night, "f"),
        "receipt_required_above": format(policy.receipt_required_above, "f"),
        "auto_approve_below": format(policy.auto_approve_below, "f"),
        "weekend_flag_enabled": policy.weekend_flag_enabled,
        "round_number_flag_enabled": policy.round_number_flag_enabled,
        "personal_merchant_keywords": list(policy.personal_merchant_keywords or []),
    }


@router.patch("/policy")
async def patch_policy(
    body: PolicyPatchRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    policy = await _get_or_create_policy(session, user.tenant_id)

    if body.meal_limit_per_day is not None:
        policy.meal_limit_per_day = _decimal_or_422(body.meal_limit_per_day, "meal_limit_per_day")
    if body.travel_limit_per_night is not None:
        policy.travel_limit_per_night = _decimal_or_422(body.travel_limit_per_night, "travel_limit_per_night")
    if body.receipt_required_above is not None:
        policy.receipt_required_above = _decimal_or_422(body.receipt_required_above, "receipt_required_above")
    if body.auto_approve_below is not None:
        policy.auto_approve_below = _decimal_or_422(body.auto_approve_below, "auto_approve_below")
    if body.weekend_flag_enabled is not None:
        policy.weekend_flag_enabled = body.weekend_flag_enabled
    if body.round_number_flag_enabled is not None:
        policy.round_number_flag_enabled = body.round_number_flag_enabled
    if body.personal_merchant_keywords is not None:
        policy.personal_merchant_keywords = body.personal_merchant_keywords

    policy.updated_at = datetime.now(UTC)
    await session.flush()
    return await get_policy(session=session, user=user)


@router.get("/{claim_id}")
async def get_expense_claim(
    claim_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    claim = (
        await session.execute(
            select(ExpenseClaim).where(
                ExpenseClaim.id == claim_id,
                ExpenseClaim.tenant_id == user.tenant_id,
            )
        )
    ).scalar_one_or_none()
    if claim is None:
        raise HTTPException(status_code=404, detail="Expense claim not found")
    if user.role not in {UserRole.finance_leader, UserRole.super_admin} and claim.submitted_by != user.id:
        raise HTTPException(status_code=404, detail="Expense claim not found")

    approvals = (
        await session.execute(
            select(ExpenseApproval)
            .where(
                ExpenseApproval.tenant_id == user.tenant_id,
                ExpenseApproval.claim_id == claim.id,
            )
            .order_by(ExpenseApproval.created_at.asc(), ExpenseApproval.id.asc())
        )
    ).scalars().all()

    payload = await _serialize_claim(session, claim)
    payload["approvals"] = [
        {
            "id": str(row.id),
            "approver_id": str(row.approver_id),
            "approver_role": row.approver_role,
            "action": row.action,
            "comments": row.comments,
            "created_at": row.created_at.isoformat(),
        }
        for row in approvals
    ]
    return payload


@router.post("/{claim_id}/approve")
async def approve_expense_claim(
    claim_id: uuid.UUID,
    body: ApproveExpenseRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    if user.role not in {UserRole.finance_team, UserRole.finance_leader, UserRole.super_admin}:
        raise HTTPException(status_code=403, detail="Manager or Finance Leader role required")

    try:
        payload = await approve_claim(
            session,
            tenant_id=user.tenant_id,
            claim_id=claim_id,
            approver_id=user.id,
            approver_role=user.role.value,
            action=body.action,
            comments=body.comments,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc

    claim = (
        await session.execute(
            select(ExpenseClaim).where(
                ExpenseClaim.id == claim_id,
                ExpenseClaim.tenant_id == user.tenant_id,
            )
        )
    ).scalar_one_or_none()
    if claim is not None:
        try:
            action_value = str(body.action).strip().lower()
            notification_type = (
                "expense_approved" if action_value == "approved" else "expense_rejected"
            )
            await send_notification(
                session,
                tenant_id=user.tenant_id,
                recipient_user_id=claim.submitted_by,
                notification_type=notification_type,
                title=f"Expense {action_value}: {claim.vendor_name}",
                body=f"Your expense claim has been {action_value}.",
                action_url=f"/expenses/{claim.id}",
                metadata={"claim_id": str(claim.id), "status": payload.get("status")},
            )
        except Exception:
            pass

    await session.flush()
    return payload

