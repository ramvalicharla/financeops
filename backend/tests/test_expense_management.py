from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.security import hash_password
from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql
from financeops.db.models.tenants import IamTenant, TenantStatus, TenantType
from financeops.db.models.users import IamUser, UserRole
from financeops.modules.expense_management.models import ExpenseApproval, ExpenseClaim, ExpensePolicy
from financeops.modules.expense_management.policy_engine import ExpensePolicyEngine
from financeops.modules.expense_management.service import (
    JustificationRequiredError,
    PolicyViolationError,
    _get_or_create_policy,
    approve_claim,
    get_expense_analytics,
    submit_claim,
)
from financeops.utils.chain_hash import GENESIS_HASH, compute_chain_hash


def _make_engine(policy: ExpensePolicy) -> ExpensePolicyEngine:
    return ExpensePolicyEngine(policy)


async def _ensure_policy(async_session: AsyncSession, tenant_id: uuid.UUID) -> ExpensePolicy:
    policy = await _get_or_create_policy(async_session, tenant_id)
    await async_session.flush()
    return policy


async def _create_tenant_user(
    async_session: AsyncSession,
    *,
    tenant_name: str,
    email: str,
    role: UserRole,
) -> tuple[IamTenant, IamUser]:
    tenant_id = uuid.uuid4()
    tenant_hash = compute_chain_hash(
        {
            "display_name": tenant_name,
            "tenant_type": TenantType.direct.value,
            "country": "US",
            "timezone": "UTC",
        },
        GENESIS_HASH,
    )
    tenant = IamTenant(
        id=tenant_id,
        tenant_id=tenant_id,
        display_name=tenant_name,
        tenant_type=TenantType.direct,
        country="US",
        timezone="UTC",
        status=TenantStatus.active,
        chain_hash=tenant_hash,
        previous_hash=GENESIS_HASH,
    )
    user = IamUser(
        tenant_id=tenant_id,
        email=email,
        hashed_password=hash_password("TestPass123!"),
        full_name=tenant_name,
        role=role,
        is_active=True,
        mfa_enabled=False,
    )
    async_session.add(tenant)
    async_session.add(user)
    await async_session.flush()
    return tenant, user


async def _submit_claim_for_user(
    async_session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    vendor_name: str,
    category: str,
    amount: Decimal,
    claim_date: date,
    has_receipt: bool = True,
    justification: str | None = None,
) -> ExpenseClaim:
    return await submit_claim(
        async_session,
        tenant_id=tenant_id,
        submitted_by=user_id,
        vendor_name=vendor_name,
        description="Test expense",
        category=category,
        amount=amount,
        currency="INR",
        claim_date=claim_date,
        has_receipt=has_receipt,
        receipt_url="https://example.com/receipt.png" if has_receipt else None,
        justification=justification,
    )


# Policy engine (8)
@pytest.mark.asyncio
async def test_personal_merchant_hard_block(async_session: AsyncSession, test_user: IamUser) -> None:
    policy = await _ensure_policy(async_session, test_user.tenant_id)
    result = _make_engine(policy).check(
        "meals", Decimal("500"), "INR", date(2025, 3, 17), "swiggy order", True
    )
    assert result.is_hard_block is True
    assert result.violation_type == "personal_merchant"


@pytest.mark.asyncio
async def test_personal_merchant_case_insensitive(async_session: AsyncSession, test_user: IamUser) -> None:
    policy = await _ensure_policy(async_session, test_user.tenant_id)
    result = _make_engine(policy).check(
        "meals", Decimal("500"), "INR", date(2025, 3, 17), "Swiggy Restaurant", True
    )
    assert result.is_hard_block is True
    assert result.violation_type == "personal_merchant"


@pytest.mark.asyncio
async def test_receipt_missing_soft_violation(async_session: AsyncSession, test_user: IamUser) -> None:
    policy = await _ensure_policy(async_session, test_user.tenant_id)
    result = _make_engine(policy).check(
        "meals", Decimal("600"), "INR", date(2025, 3, 17), "Hotel Restaurant", False
    )
    assert result.passed is False
    assert result.requires_justification is True
    assert result.is_hard_block is False
    assert result.violation_type == "receipt_missing"


@pytest.mark.asyncio
async def test_meal_limit_soft_violation(async_session: AsyncSession, test_user: IamUser) -> None:
    policy = await _ensure_policy(async_session, test_user.tenant_id)
    result = _make_engine(policy).check(
        "meals", Decimal("2001"), "INR", date(2025, 3, 17), "Some Restaurant", True
    )
    assert result.violation_type == "soft_limit"
    assert result.requires_justification is True


@pytest.mark.asyncio
async def test_meal_hard_block_at_150_pct(async_session: AsyncSession, test_user: IamUser) -> None:
    policy = await _ensure_policy(async_session, test_user.tenant_id)
    result = _make_engine(policy).check(
        "meals", Decimal("3200"), "INR", date(2025, 3, 17), "Some Restaurant", True
    )
    assert result.is_hard_block is True
    assert result.violation_type == "hard_limit"


@pytest.mark.asyncio
async def test_round_number_flagged(async_session: AsyncSession, test_user: IamUser) -> None:
    policy = await _ensure_policy(async_session, test_user.tenant_id)
    result = _make_engine(policy).check(
        "other", Decimal("5000"), "INR", date(2025, 3, 17), "Some Restaurant", True
    )
    assert result.violation_type == "round_number"
    assert result.is_hard_block is False


@pytest.mark.asyncio
async def test_weekend_claim_flagged(async_session: AsyncSession, test_user: IamUser) -> None:
    policy = await _ensure_policy(async_session, test_user.tenant_id)
    result = _make_engine(policy).check(
        "meals", Decimal("500"), "INR", date(2025, 3, 22), "Some Restaurant", True
    )
    assert result.violation_type == "weekend"
    assert result.requires_justification is True


@pytest.mark.asyncio
async def test_clean_claim_passes_all_checks(async_session: AsyncSession, test_user: IamUser) -> None:
    policy = await _ensure_policy(async_session, test_user.tenant_id)
    result = _make_engine(policy).check(
        "meals", Decimal("499"), "INR", date(2025, 3, 17), "Hotel Restaurant", True
    )
    assert result.passed is True
    assert result.violation_type is None


# Claim lifecycle (9)
@pytest.mark.asyncio
async def test_submit_claim_creates_append_only_record(async_session: AsyncSession, test_user: IamUser) -> None:
    await _ensure_policy(async_session, test_user.tenant_id)
    claim = await _submit_claim_for_user(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        vendor_name="Office Store",
        category="office_supplies",
        amount=Decimal("1200.00"),
        claim_date=date(2025, 3, 17),
    )
    row = await async_session.get(ExpenseClaim, claim.id)
    assert row is not None


@pytest.mark.asyncio
async def test_hard_violation_blocks_submission(async_session: AsyncSession, test_user: IamUser) -> None:
    await _ensure_policy(async_session, test_user.tenant_id)
    with pytest.raises(PolicyViolationError):
        await _submit_claim_for_user(
            async_session,
            tenant_id=test_user.tenant_id,
            user_id=test_user.id,
            vendor_name="Swiggy Delivery",
            category="meals",
            amount=Decimal("500.00"),
            claim_date=date(2025, 3, 17),
        )

    count = (
        await async_session.execute(
            select(func.count()).select_from(ExpenseClaim).where(
                ExpenseClaim.tenant_id == test_user.tenant_id,
            )
        )
    ).scalar_one()
    assert count == 0


@pytest.mark.asyncio
async def test_soft_violation_without_justification_raises(async_session: AsyncSession, test_user: IamUser) -> None:
    await _ensure_policy(async_session, test_user.tenant_id)
    with pytest.raises(JustificationRequiredError):
        await _submit_claim_for_user(
            async_session,
            tenant_id=test_user.tenant_id,
            user_id=test_user.id,
            vendor_name="Some Restaurant",
            category="meals",
            amount=Decimal("2001"),
            claim_date=date(2025, 3, 17),
            has_receipt=True,
        )


@pytest.mark.asyncio
async def test_soft_violation_with_justification_succeeds(async_session: AsyncSession, test_user: IamUser) -> None:
    await _ensure_policy(async_session, test_user.tenant_id)
    claim = await _submit_claim_for_user(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        vendor_name="Some Restaurant",
        category="other",
        amount=Decimal("5000"),
        claim_date=date(2025, 3, 17),
        has_receipt=True,
        justification="Client dinner reimbursement",
    )
    assert claim.policy_violation_type == "round_number"


@pytest.mark.asyncio
async def test_auto_approve_below_threshold(async_session: AsyncSession, test_user: IamUser) -> None:
    policy = await _ensure_policy(async_session, test_user.tenant_id)
    policy.auto_approve_below = Decimal("100.00")
    await async_session.flush()

    claim = await _submit_claim_for_user(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        vendor_name="Tea Stall",
        category="other",
        amount=Decimal("50.00"),
        claim_date=date(2025, 3, 17),
    )
    assert claim.status == "approved"


@pytest.mark.asyncio
async def test_approval_creates_audit_record(async_session: AsyncSession, test_user: IamUser) -> None:
    await _ensure_policy(async_session, test_user.tenant_id)
    claim = await _submit_claim_for_user(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        vendor_name="Office Store",
        category="office_supplies",
        amount=Decimal("1200.00"),
        claim_date=date(2025, 3, 17),
    )
    await approve_claim(
        async_session,
        tenant_id=test_user.tenant_id,
        claim_id=claim.id,
        approver_id=test_user.id,
        approver_role=UserRole.finance_leader.value,
        action="approved",
    )

    approvals = (
        await async_session.execute(
            select(ExpenseApproval).where(ExpenseApproval.claim_id == claim.id)
        )
    ).scalars().all()
    assert len(approvals) == 1
    assert approvals[0].action == "approved"


@pytest.mark.asyncio
async def test_rejection_creates_audit_record(async_session: AsyncSession, test_user: IamUser) -> None:
    await _ensure_policy(async_session, test_user.tenant_id)
    claim = await _submit_claim_for_user(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        vendor_name="Office Store",
        category="office_supplies",
        amount=Decimal("1200.00"),
        claim_date=date(2025, 3, 17),
    )
    await approve_claim(
        async_session,
        tenant_id=test_user.tenant_id,
        claim_id=claim.id,
        approver_id=test_user.id,
        approver_role=UserRole.finance_leader.value,
        action="rejected",
    )

    approvals = (
        await async_session.execute(
            select(ExpenseApproval).where(ExpenseApproval.claim_id == claim.id)
        )
    ).scalars().all()
    assert approvals[0].action == "rejected"


@pytest.mark.asyncio
async def test_claim_amount_stored_as_decimal(async_session: AsyncSession, test_user: IamUser) -> None:
    await _ensure_policy(async_session, test_user.tenant_id)
    claim = await _submit_claim_for_user(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        vendor_name="Office Store",
        category="office_supplies",
        amount=Decimal("1500.50"),
        claim_date=date(2025, 3, 17),
    )
    row = await async_session.get(ExpenseClaim, claim.id)
    assert isinstance(row.amount, Decimal)
    assert row.amount == Decimal("1500.50")


@pytest.mark.asyncio
async def test_expense_claim_is_append_only(async_session: AsyncSession, test_user: IamUser) -> None:
    await _ensure_policy(async_session, test_user.tenant_id)
    claim = await _submit_claim_for_user(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        vendor_name="Office Store",
        category="office_supplies",
        amount=Decimal("1500.50"),
        claim_date=date(2025, 3, 17),
    )

    await async_session.execute(text(append_only_function_sql()))
    await async_session.execute(text(drop_trigger_sql("expense_claims")))
    await async_session.execute(text(create_trigger_sql("expense_claims")))
    await async_session.flush()

    with pytest.raises(Exception):
        await async_session.execute(
            text("UPDATE expense_claims SET amount = :amount WHERE id = :id"),
            {"amount": Decimal("1.00"), "id": claim.id},
        )


# API (5)
@pytest.mark.asyncio
async def test_submit_expense_via_api(async_client: AsyncClient, test_access_token: str) -> None:
    response = await async_client.post(
        "/api/v1/expenses",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "vendor_name": "Office Store",
            "description": "Stationery",
            "category": "office_supplies",
            "amount": "1250.00",
            "currency": "INR",
            "claim_date": "2025-03-17",
            "has_receipt": True,
        },
    )
    assert response.status_code == 201
    payload = response.json()["data"]
    assert payload["vendor_name"] == "Office Store"


@pytest.mark.asyncio
async def test_employee_sees_only_own_claims(async_client: AsyncClient, async_session: AsyncSession, test_user: IamUser) -> None:
    user_a = IamUser(
        tenant_id=test_user.tenant_id,
        email=f"emp-a-{uuid.uuid4().hex[:6]}@example.com",
        hashed_password=hash_password("TestPass123!"),
        full_name="Emp A",
        role=UserRole.employee,
        is_active=True,
        mfa_enabled=False,
    )
    user_b = IamUser(
        tenant_id=test_user.tenant_id,
        email=f"emp-b-{uuid.uuid4().hex[:6]}@example.com",
        hashed_password=hash_password("TestPass123!"),
        full_name="Emp B",
        role=UserRole.employee,
        is_active=True,
        mfa_enabled=False,
    )
    async_session.add_all([user_a, user_b])
    await async_session.flush()

    await _ensure_policy(async_session, test_user.tenant_id)
    await _submit_claim_for_user(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=user_a.id,
        vendor_name="Store A",
        category="other",
        amount=Decimal("300.00"),
        claim_date=date(2025, 3, 17),
    )
    await _submit_claim_for_user(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=user_b.id,
        vendor_name="Store B",
        category="other",
        amount=Decimal("350.00"),
        claim_date=date(2025, 3, 17),
    )

    from financeops.core.security import create_access_token

    token_a = create_access_token(user_a.id, user_a.tenant_id, user_a.role.value)
    response = await async_client.get(
        "/api/v1/expenses",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert response.status_code == 200
    rows = response.json()["data"]["data"]
    assert rows
    assert all(row["submitted_by"] == str(user_a.id) for row in rows)


@pytest.mark.asyncio
async def test_finance_leader_sees_all_claims(async_client: AsyncClient, async_session: AsyncSession, test_user: IamUser, test_access_token: str) -> None:
    await _ensure_policy(async_session, test_user.tenant_id)

    user_b = IamUser(
        tenant_id=test_user.tenant_id,
        email=f"emp-c-{uuid.uuid4().hex[:6]}@example.com",
        hashed_password=hash_password("TestPass123!"),
        full_name="Emp C",
        role=UserRole.employee,
        is_active=True,
        mfa_enabled=False,
    )
    async_session.add(user_b)
    await async_session.flush()

    await _submit_claim_for_user(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        vendor_name="Store A",
        category="other",
        amount=Decimal("300.00"),
        claim_date=date(2025, 3, 17),
    )
    await _submit_claim_for_user(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=user_b.id,
        vendor_name="Store B",
        category="other",
        amount=Decimal("350.00"),
        claim_date=date(2025, 3, 17),
    )

    response = await async_client.get(
        "/api/v1/expenses",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 200
    rows = response.json()["data"]["data"]
    submitters = {row["submitted_by"] for row in rows}
    assert str(test_user.id) in submitters
    assert str(user_b.id) in submitters


@pytest.mark.asyncio
async def test_approve_requires_manager_role(async_client: AsyncClient, async_session: AsyncSession, test_user: IamUser) -> None:
    await _ensure_policy(async_session, test_user.tenant_id)
    claim = await _submit_claim_for_user(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        vendor_name="Store A",
        category="other",
        amount=Decimal("300.00"),
        claim_date=date(2025, 3, 17),
    )

    employee = IamUser(
        tenant_id=test_user.tenant_id,
        email=f"emp-d-{uuid.uuid4().hex[:6]}@example.com",
        hashed_password=hash_password("TestPass123!"),
        full_name="Emp D",
        role=UserRole.employee,
        is_active=True,
        mfa_enabled=False,
    )
    async_session.add(employee)
    await async_session.flush()

    from financeops.core.security import create_access_token

    employee_token = create_access_token(employee.id, employee.tenant_id, employee.role.value)
    response = await async_client.post(
        f"/api/v1/expenses/{claim.id}/approve",
        headers={"Authorization": f"Bearer {employee_token}"},
        json={"action": "approved"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_policy_endpoint_returns_defaults(async_client: AsyncClient, test_access_token: str) -> None:
    response = await async_client.get(
        "/api/v1/expenses/policy",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["meal_limit_per_day"] == "2000.00"


# Analytics (3)
@pytest.mark.asyncio
async def test_analytics_spend_by_category(async_session: AsyncSession, test_user: IamUser) -> None:
    await _ensure_policy(async_session, test_user.tenant_id)

    await _submit_claim_for_user(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        vendor_name="Meals",
        category="meals",
        amount=Decimal("100.00"),
        claim_date=date(2025, 3, 17),
    )
    await _submit_claim_for_user(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        vendor_name="Travel",
        category="travel",
        amount=Decimal("200.00"),
        claim_date=date(2025, 3, 18),
    )

    payload = await get_expense_analytics(async_session, test_user.tenant_id, "2025-03")
    assert payload["spend_by_category"]["meals"] == Decimal("100.00")
    assert payload["spend_by_category"]["travel"] == Decimal("200.00")


@pytest.mark.asyncio
async def test_analytics_violation_rate(async_session: AsyncSession, test_user: IamUser) -> None:
    await _ensure_policy(async_session, test_user.tenant_id)

    for i in range(7):
        await _submit_claim_for_user(
            async_session,
            tenant_id=test_user.tenant_id,
            user_id=test_user.id,
            vendor_name=f"Store {i}",
            category="other",
            amount=Decimal("100.00"),
            claim_date=date(2025, 3, 17),
        )
    for i in range(3):
        await _submit_claim_for_user(
            async_session,
            tenant_id=test_user.tenant_id,
            user_id=test_user.id,
            vendor_name=f"Rounded {i}",
            category="other",
            amount=Decimal("1000.00"),
            claim_date=date(2025, 3, 17),
            justification="Business purchase",
        )

    payload = await get_expense_analytics(async_session, test_user.tenant_id, "2025-03")
    assert payload["policy_violation_rate"] == Decimal("0.3000")


@pytest.mark.asyncio
async def test_analytics_itc_recovered(async_session: AsyncSession, test_user: IamUser) -> None:
    await _ensure_policy(async_session, test_user.tenant_id)

    claims: list[ExpenseClaim] = []
    for i in range(5):
        claim = await _submit_claim_for_user(
            async_session,
            tenant_id=test_user.tenant_id,
            user_id=test_user.id,
            vendor_name=f"GST {i}",
            category="other",
            amount=Decimal("100.00"),
            claim_date=date(2025, 3, 17),
        )
        claims.append(claim)

    for claim in claims[:3]:
        claim.itc_eligible = True
        claim.gst_amount = Decimal("180.00")
    await async_session.flush()

    payload = await get_expense_analytics(async_session, test_user.tenant_id, "2025-03")
    assert payload["itc_recovered"] == Decimal("540.00")
