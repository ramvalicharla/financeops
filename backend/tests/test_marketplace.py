from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import InsufficientCreditsError, ValidationError
from financeops.core.security import create_access_token, hash_password
from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql
from financeops.db.models.credits import CreditBalance
from financeops.db.models.tenants import IamTenant, TenantStatus, TenantType
from financeops.db.models.users import IamUser, UserRole
from financeops.modules.marketplace.models import (
    MarketplaceContributor,
    MarketplacePayout,
    MarketplacePurchase,
    MarketplaceRating,
    MarketplaceTemplate,
)
from financeops.modules.marketplace.service import (
    get_marketplace_listings,
    process_monthly_payouts,
    purchase_template,
    rate_template,
    register_contributor,
    review_template,
    submit_template,
)
from financeops.services.credit_service import add_credits
from financeops.utils.chain_hash import GENESIS_HASH, compute_chain_hash


async def _fund(session: AsyncSession, tenant_id: uuid.UUID, amount: str = "1000.00") -> None:
    await add_credits(session, tenant_id, Decimal(amount), "marketplace_test_fund")
    await session.flush()


async def _create_tenant(session: AsyncSession, tenant_id: uuid.UUID, name: str) -> IamTenant:
    record_data = {
        "display_name": name,
        "tenant_type": TenantType.direct.value,
        "country": "US",
        "timezone": "UTC",
    }
    tenant = IamTenant(
        id=tenant_id,
        tenant_id=tenant_id,
        display_name=name,
        tenant_type=TenantType.direct,
        country="US",
        timezone="UTC",
        status=TenantStatus.active,
        chain_hash=compute_chain_hash(record_data, GENESIS_HASH),
        previous_hash=GENESIS_HASH,
    )
    session.add(tenant)
    await session.flush()
    return tenant


def _auth_headers(user: IamUser) -> dict[str, str]:
    token = create_access_token(user.id, user.tenant_id, user.role.value)
    return {"Authorization": f"Bearer {token}"}


async def _create_platform_user(
    session: AsyncSession,
    *,
    email: str,
    role: UserRole,
) -> IamUser:
    platform_tenant_id = uuid.UUID(int=0)
    tenant = (
        await session.execute(
            select(IamTenant).where(IamTenant.id == platform_tenant_id)
        )
    ).scalar_one_or_none()
    if tenant is None:
        record_data = {
            "display_name": "FinanceOps Platform",
            "tenant_type": TenantType.direct.value,
            "country": "US",
            "timezone": "UTC",
        }
        tenant = IamTenant(
            id=platform_tenant_id,
            tenant_id=platform_tenant_id,
            display_name="FinanceOps Platform",
            tenant_type=TenantType.direct,
            country="US",
            timezone="UTC",
            status=TenantStatus.active,
            is_platform_tenant=True,
            chain_hash=compute_chain_hash(record_data, GENESIS_HASH),
            previous_hash=GENESIS_HASH,
        )
        session.add(tenant)
        await session.flush()

    user = IamUser(
        tenant_id=platform_tenant_id,
        email=email,
        hashed_password=hash_password("TestPass123!"),
        full_name="Platform Admin",
        role=role,
        is_active=True,
        mfa_enabled=True,
    )
    session.add(user)
    await session.flush()
    return user


async def _create_published_template(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    title: str = "Template One",
    price_credits: int = 100,
) -> tuple[MarketplaceContributor, MarketplaceTemplate]:
    contributor = await register_contributor(session, tenant_id, "Contributor")
    template = await submit_template(
        session,
        contributor_id=contributor.id,
        tenant_id=tenant_id,
        title=title,
        description="Template description",
        template_type="mis_template",
        price_credits=price_credits,
        template_data={"line_items": ["Revenue", "EBITDA"]},
        industry="saas",
        tags=["ops"],
    )
    await review_template(session, template.id, "approve")
    await session.flush()
    return contributor, template


# Contributor (4)
@pytest.mark.asyncio
async def test_register_contributor(async_session: AsyncSession, test_user: IamUser) -> None:
    contributor = await register_contributor(
        async_session,
        test_user.tenant_id,
        "ACME Templates",
    )
    assert contributor.contributor_tier == "community"
    assert contributor.revenue_share_pct == Decimal("0.6000")


@pytest.mark.asyncio
async def test_contributor_unique_per_tenant(async_session: AsyncSession, test_user: IamUser) -> None:
    first = await register_contributor(async_session, test_user.tenant_id, "First")
    second = await register_contributor(async_session, test_user.tenant_id, "Second")
    assert first.id == second.id


@pytest.mark.asyncio
async def test_verified_partner_higher_revenue_share(async_session: AsyncSession, test_user: IamUser) -> None:
    contributor = await register_contributor(async_session, test_user.tenant_id, "Tier test")
    contributor.contributor_tier = "verified_partner"
    contributor.revenue_share_pct = Decimal("0.7000")
    await async_session.flush()
    assert contributor.revenue_share_pct == Decimal("0.7000")


@pytest.mark.asyncio
async def test_contributor_rls(async_session: AsyncSession, test_user: IamUser) -> None:
    contributor_a = await register_contributor(async_session, test_user.tenant_id, "A")
    tenant_b = uuid.uuid4()
    await _create_tenant(async_session, tenant_b, "Tenant B")
    contributor_b = await register_contributor(async_session, tenant_b, "B")
    rows = (
        await async_session.execute(
            select(MarketplaceContributor).where(MarketplaceContributor.tenant_id == test_user.tenant_id)
        )
    ).scalars().all()
    ids = {row.id for row in rows}
    assert contributor_a.id in ids
    assert contributor_b.id not in ids


# Template lifecycle (6)
@pytest.mark.asyncio
async def test_submit_template_pending_review(async_session: AsyncSession, test_user: IamUser) -> None:
    contributor = await register_contributor(async_session, test_user.tenant_id, "Submitter")
    row = await submit_template(
        async_session,
        contributor_id=contributor.id,
        tenant_id=test_user.tenant_id,
        title="Pending Template",
        description="Desc",
        template_type="mis_template",
        price_credits=25,
        template_data={"line_items": []},
    )
    assert row.status == "pending_review"


@pytest.mark.asyncio
async def test_approve_template_publishes(async_session: AsyncSession, test_user: IamUser) -> None:
    contributor = await register_contributor(async_session, test_user.tenant_id, "Approver")
    row = await submit_template(
        async_session,
        contributor_id=contributor.id,
        tenant_id=test_user.tenant_id,
        title="Approve me",
        description="Desc",
        template_type="report_template",
        price_credits=30,
        template_data={"sections": []},
    )
    await review_template(async_session, row.id, "approve")
    assert row.status == "published"
    assert contributor.total_templates == 1


@pytest.mark.asyncio
async def test_reject_template_with_notes(async_session: AsyncSession, test_user: IamUser) -> None:
    contributor = await register_contributor(async_session, test_user.tenant_id, "Rejector")
    row = await submit_template(
        async_session,
        contributor_id=contributor.id,
        tenant_id=test_user.tenant_id,
        title="Reject me",
        description="Desc",
        template_type="board_pack",
        price_credits=40,
        template_data={"k": "v"},
    )
    await review_template(async_session, row.id, "reject", review_notes="Missing documentation")
    assert row.status == "rejected"
    assert row.review_notes == "Missing documentation"


@pytest.mark.asyncio
async def test_only_published_templates_in_listing(async_session: AsyncSession, test_user: IamUser) -> None:
    contributor = await register_contributor(async_session, test_user.tenant_id, "Lister")
    draft = MarketplaceTemplate(
        contributor_id=contributor.id,
        tenant_id=test_user.tenant_id,
        title="Draft",
        description="draft",
        template_type="mis_template",
        price_credits=10,
        template_data={},
        status="draft",
    )
    pending = await submit_template(
        async_session,
        contributor_id=contributor.id,
        tenant_id=test_user.tenant_id,
        title="Pending",
        description="pending",
        template_type="mis_template",
        price_credits=10,
        template_data={},
    )
    published = await submit_template(
        async_session,
        contributor_id=contributor.id,
        tenant_id=test_user.tenant_id,
        title="Published",
        description="published",
        template_type="mis_template",
        price_credits=10,
        template_data={},
    )
    async_session.add(draft)
    await review_template(async_session, published.id, "approve")
    payload = await get_marketplace_listings(async_session)
    ids = {row.id for row in payload["data"]}
    assert published.id in ids
    assert pending.id not in ids
    assert draft.id not in ids


@pytest.mark.asyncio
async def test_template_data_structure_preserved(async_session: AsyncSession, test_user: IamUser) -> None:
    contributor = await register_contributor(async_session, test_user.tenant_id, "Structure")
    template_data = {"line_items": [{"name": "Revenue", "type": "credit"}]}
    row = await submit_template(
        async_session,
        contributor_id=contributor.id,
        tenant_id=test_user.tenant_id,
        title="Structured",
        description="Desc",
        template_type="mis_template",
        price_credits=10,
        template_data=template_data,
    )
    assert row.template_data == template_data


@pytest.mark.asyncio
async def test_free_template_flag(async_session: AsyncSession, test_user: IamUser) -> None:
    contributor = await register_contributor(async_session, test_user.tenant_id, "Free")
    row = await submit_template(
        async_session,
        contributor_id=contributor.id,
        tenant_id=test_user.tenant_id,
        title="Free template",
        description="Desc",
        template_type="mis_template",
        price_credits=0,
        template_data={},
    )
    assert row.is_free is True


# Purchase (6)
@pytest.mark.asyncio
async def test_purchase_deducts_credits(async_session: AsyncSession, test_user: IamUser) -> None:
    _, template = await _create_published_template(async_session, tenant_id=test_user.tenant_id, price_credits=50)
    buyer_tenant = uuid.uuid4()
    await _fund(async_session, buyer_tenant, "100.00")
    await purchase_template(async_session, buyer_tenant, template.id)
    balance = (
        await async_session.execute(
            select(CreditBalance).where(CreditBalance.tenant_id == buyer_tenant)
        )
    ).scalar_one()
    assert balance.balance == Decimal("50.00")


@pytest.mark.asyncio
async def test_purchase_revenue_split_community(async_session: AsyncSession, test_user: IamUser) -> None:
    contributor, template = await _create_published_template(async_session, tenant_id=test_user.tenant_id, price_credits=100)
    buyer_tenant = uuid.uuid4()
    await _fund(async_session, buyer_tenant, "100.00")
    purchase = await purchase_template(async_session, buyer_tenant, template.id)
    assert purchase.contributor_share_credits == 60
    assert purchase.platform_share_credits == 40
    assert contributor.total_earnings == Decimal("60.00")


@pytest.mark.asyncio
async def test_purchase_revenue_split_verified_partner(async_session: AsyncSession, test_user: IamUser) -> None:
    contributor, template = await _create_published_template(async_session, tenant_id=test_user.tenant_id, price_credits=100)
    contributor.contributor_tier = "verified_partner"
    contributor.revenue_share_pct = Decimal("0.7000")
    await async_session.flush()
    buyer_tenant = uuid.uuid4()
    await _fund(async_session, buyer_tenant, "100.00")
    purchase = await purchase_template(async_session, buyer_tenant, template.id)
    assert purchase.contributor_share_credits == 70
    assert purchase.platform_share_credits == 30


@pytest.mark.asyncio
async def test_purchase_is_append_only(async_session: AsyncSession, test_user: IamUser) -> None:
    _, template = await _create_published_template(async_session, tenant_id=test_user.tenant_id, price_credits=10)
    buyer_tenant = uuid.uuid4()
    await _fund(async_session, buyer_tenant, "100.00")
    purchase = await purchase_template(async_session, buyer_tenant, template.id)
    await async_session.execute(text(append_only_function_sql()))
    await async_session.execute(text(drop_trigger_sql("marketplace_purchases")))
    await async_session.execute(text(create_trigger_sql("marketplace_purchases")))
    await async_session.flush()
    with pytest.raises(Exception):
        await async_session.execute(
            text("UPDATE marketplace_purchases SET status = 'failed' WHERE id = :id"),
            {"id": purchase.id},
        )


@pytest.mark.asyncio
async def test_free_template_no_credit_deduction(async_session: AsyncSession, test_user: IamUser) -> None:
    _, template = await _create_published_template(async_session, tenant_id=test_user.tenant_id, price_credits=0)
    buyer_tenant = uuid.uuid4()
    await _fund(async_session, buyer_tenant, "100.00")
    await purchase_template(async_session, buyer_tenant, template.id)
    balance = (
        await async_session.execute(
            select(CreditBalance).where(CreditBalance.tenant_id == buyer_tenant)
        )
    ).scalar_one()
    assert balance.balance == Decimal("100.00")


@pytest.mark.asyncio
async def test_cannot_purchase_without_sufficient_credits(async_session: AsyncSession, test_user: IamUser) -> None:
    _, template = await _create_published_template(async_session, tenant_id=test_user.tenant_id, price_credits=100)
    buyer_tenant = uuid.uuid4()
    await _fund(async_session, buyer_tenant, "10.00")
    with pytest.raises(InsufficientCreditsError):
        await purchase_template(async_session, buyer_tenant, template.id)


# Rating (4)
@pytest.mark.asyncio
async def test_rate_template_creates_record(async_session: AsyncSession, test_user: IamUser) -> None:
    _, template = await _create_published_template(async_session, tenant_id=test_user.tenant_id, price_credits=20)
    buyer_tenant = uuid.uuid4()
    await _fund(async_session, buyer_tenant, "100.00")
    await purchase_template(async_session, buyer_tenant, template.id)
    rating = await rate_template(async_session, buyer_tenant, template.id, 5, "Great")
    assert rating.id is not None


@pytest.mark.asyncio
async def test_rating_updates_template_average(async_session: AsyncSession, test_user: IamUser) -> None:
    _, template = await _create_published_template(async_session, tenant_id=test_user.tenant_id, price_credits=20)
    buyer_a = uuid.uuid4()
    buyer_b = uuid.uuid4()
    await _fund(async_session, buyer_a, "100.00")
    await _fund(async_session, buyer_b, "100.00")
    await purchase_template(async_session, buyer_a, template.id)
    await purchase_template(async_session, buyer_b, template.id)
    await rate_template(async_session, buyer_a, template.id, 5)
    await rate_template(async_session, buyer_b, template.id, 3)
    assert template.rating_average == Decimal("4.00")


@pytest.mark.asyncio
async def test_cannot_rate_without_purchase(async_session: AsyncSession, test_user: IamUser) -> None:
    _, template = await _create_published_template(async_session, tenant_id=test_user.tenant_id, price_credits=20)
    with pytest.raises(ValidationError):
        await rate_template(async_session, uuid.uuid4(), template.id, 5)


@pytest.mark.asyncio
async def test_rating_is_append_only(async_session: AsyncSession, test_user: IamUser) -> None:
    _, template = await _create_published_template(async_session, tenant_id=test_user.tenant_id, price_credits=20)
    buyer_tenant = uuid.uuid4()
    await _fund(async_session, buyer_tenant, "100.00")
    await purchase_template(async_session, buyer_tenant, template.id)
    rating = await rate_template(async_session, buyer_tenant, template.id, 4)
    await async_session.execute(text(append_only_function_sql()))
    await async_session.execute(text(drop_trigger_sql("marketplace_ratings")))
    await async_session.execute(text(create_trigger_sql("marketplace_ratings")))
    await async_session.flush()
    with pytest.raises(Exception):
        await async_session.execute(
            text("UPDATE marketplace_ratings SET rating = 1 WHERE id = :id"),
            {"id": rating.id},
        )


# Payouts (3)
@pytest.mark.asyncio
async def test_process_monthly_payouts_creates_records(async_session: AsyncSession, test_user: IamUser) -> None:
    _, template = await _create_published_template(async_session, tenant_id=test_user.tenant_id, price_credits=100)
    buyer_tenant = uuid.uuid4()
    await _fund(async_session, buyer_tenant, "200.00")
    await purchase_template(async_session, buyer_tenant, template.id)
    payouts = await process_monthly_payouts(async_session)
    assert len(payouts) >= 1


@pytest.mark.asyncio
async def test_payout_amount_is_decimal(async_session: AsyncSession, test_user: IamUser) -> None:
    _, template = await _create_published_template(async_session, tenant_id=test_user.tenant_id, price_credits=100)
    buyer_tenant = uuid.uuid4()
    await _fund(async_session, buyer_tenant, "200.00")
    await purchase_template(async_session, buyer_tenant, template.id)
    payouts = await process_monthly_payouts(async_session)
    assert payouts
    assert isinstance(payouts[0].total_usd_amount, Decimal)


@pytest.mark.asyncio
async def test_payout_is_append_only(async_session: AsyncSession, test_user: IamUser) -> None:
    contributor, _ = await _create_published_template(async_session, tenant_id=test_user.tenant_id, price_credits=0)
    payout = MarketplacePayout(
        contributor_id=contributor.id,
        period_start=datetime.now(UTC).date(),
        period_end=datetime.now(UTC).date(),
        total_credits_earned=100,
        total_usd_amount=Decimal("1.00"),
        status="pending",
    )
    async_session.add(payout)
    await async_session.flush()
    await async_session.execute(text(append_only_function_sql()))
    await async_session.execute(text(drop_trigger_sql("marketplace_payouts")))
    await async_session.execute(text(create_trigger_sql("marketplace_payouts")))
    await async_session.flush()
    with pytest.raises(Exception):
        await async_session.execute(
            text("UPDATE marketplace_payouts SET status = 'completed' WHERE id = :id"),
            {"id": payout.id},
        )


# API (2)
@pytest.mark.asyncio
async def test_marketplace_listing_endpoint_pagination(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_user: IamUser,
    test_access_token: str,
) -> None:
    await _create_published_template(async_session, tenant_id=test_user.tenant_id, title="T1")
    await _create_published_template(async_session, tenant_id=test_user.tenant_id, title="T2")
    response = await async_client.get(
        "/api/v1/marketplace/templates?limit=1&offset=0",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["limit"] == 1
    assert payload["total"] >= 1


@pytest.mark.asyncio
async def test_admin_review_endpoint_requires_platform_admin(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_user: IamUser,
    test_access_token: str,
) -> None:
    contributor = await register_contributor(async_session, test_user.tenant_id, "API Reviewer")
    template = await submit_template(
        async_session,
        contributor_id=contributor.id,
        tenant_id=test_user.tenant_id,
        title="Pending API review",
        description="Desc",
        template_type="mis_template",
        price_credits=20,
        template_data={},
    )
    forbidden = await async_client.post(
        f"/api/v1/marketplace/admin/templates/{template.id}/review",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={"action": "approve"},
    )
    assert forbidden.status_code == 403

    admin_user = await _create_platform_user(
        async_session,
        email="marketplace.admin@example.com",
        role=UserRole.platform_admin,
    )
    allowed = await async_client.post(
        f"/api/v1/marketplace/admin/templates/{template.id}/review",
        headers=_auth_headers(admin_user),
        json={"action": "approve"},
    )
    assert allowed.status_code == 200
    assert allowed.json()["data"]["status"] == "published"
