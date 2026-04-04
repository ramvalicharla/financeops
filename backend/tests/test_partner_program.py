from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import NotFoundError
from financeops.core.security import create_access_token, hash_password
from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql
from financeops.db.models.tenants import IamTenant, TenantStatus, TenantType
from financeops.db.models.users import IamUser, UserRole
from financeops.modules.partner_program.models import PartnerCommission, PartnerProfile, ReferralTracking
from financeops.modules.partner_program.service import (
    _generate_partner_code,
    approve_partner,
    convert_referral,
    get_partner_dashboard,
    record_commission,
    register_partner,
    track_referral_click,
)
from financeops.utils.chain_hash import GENESIS_HASH, compute_chain_hash


def _auth_headers(user: IamUser) -> dict[str, str]:
    token = create_access_token(user.id, user.tenant_id, user.role.value)
    return {"Authorization": f"Bearer {token}"}


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


async def _create_platform_user(session: AsyncSession, email: str, role: UserRole) -> IamUser:
    platform_tenant_id = uuid.UUID(int=0)
    tenant = (
        await session.execute(select(IamTenant).where(IamTenant.id == platform_tenant_id))
    ).scalar_one_or_none()
    if tenant is None:
        await _create_tenant(session, platform_tenant_id, "FinanceOps Platform")
        tenant = (
            await session.execute(select(IamTenant).where(IamTenant.id == platform_tenant_id))
        ).scalar_one()
        tenant.is_platform_tenant = True

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


async def _register_and_convert_referral(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    tier: str = "referral",
) -> tuple[PartnerProfile, ReferralTracking, uuid.UUID]:
    partner = await register_partner(
        session,
        tenant_id=tenant_id,
        partner_tier=tier,
        company_name=f"Partner {tier}",
        contact_email=f"{tier}@example.com",
    )
    click = await track_referral_click(session, partner.partner_code, "lead@example.com")
    referred_tenant_id = uuid.uuid4()
    await _create_tenant(session, referred_tenant_id, "Referred Tenant")
    converted = await convert_referral(session, click.referral_code, referred_tenant_id)
    return partner, converted, referred_tenant_id


# Partner registration (5)
@pytest.mark.asyncio
async def test_register_partner_referral_tier(async_session: AsyncSession, test_user: IamUser) -> None:
    partner = await register_partner(
        async_session,
        tenant_id=test_user.tenant_id,
        partner_tier="referral",
        company_name="Acme Advisors",
        contact_email="acme@example.com",
    )
    assert partner.commission_rate_pct == Decimal("0.1500")


@pytest.mark.asyncio
async def test_register_partner_reseller_tier(async_session: AsyncSession, test_user: IamUser) -> None:
    tenant_b = uuid.uuid4()
    await _create_tenant(async_session, tenant_b, "Tenant B")
    partner = await register_partner(
        async_session,
        tenant_id=tenant_b,
        partner_tier="reseller",
        company_name="Reseller Co",
        contact_email="reseller@example.com",
    )
    assert partner.commission_rate_pct == Decimal("0.3000")


@pytest.mark.asyncio
async def test_partner_code_unique(async_session: AsyncSession, test_user: IamUser) -> None:
    partner_a = await register_partner(
        async_session,
        tenant_id=test_user.tenant_id,
        partner_tier="referral",
        company_name="Smith CPA",
        contact_email="smith@example.com",
    )
    tenant_b = uuid.uuid4()
    await _create_tenant(async_session, tenant_b, "Tenant B")
    partner_b = await register_partner(
        async_session,
        tenant_id=tenant_b,
        partner_tier="referral",
        company_name="Smith CPA LLP",
        contact_email="smith2@example.com",
    )
    assert partner_a.partner_code != partner_b.partner_code


@pytest.mark.asyncio
async def test_partner_pending_until_approved(async_session: AsyncSession, test_user: IamUser) -> None:
    partner = await register_partner(
        async_session,
        tenant_id=test_user.tenant_id,
        partner_tier="technology",
        company_name="Tech Partner",
        contact_email="tech@example.com",
    )
    assert partner.approved_at is None


@pytest.mark.asyncio
async def test_approve_partner(async_session: AsyncSession, test_user: IamUser) -> None:
    partner = await register_partner(
        async_session,
        tenant_id=test_user.tenant_id,
        partner_tier="referral",
        company_name="Approver",
        contact_email="approve@example.com",
    )
    approved = await approve_partner(async_session, partner.id, test_user.id)
    assert approved.approved_at is not None
    assert approved.is_active is True


# Referral tracking (7)
@pytest.mark.asyncio
async def test_track_referral_click_creates_record(async_session: AsyncSession, test_user: IamUser) -> None:
    partner = await register_partner(
        async_session,
        tenant_id=test_user.tenant_id,
        partner_tier="referral",
        company_name="Tracker",
        contact_email="track@example.com",
    )
    row = await track_referral_click(async_session, partner.partner_code, "lead@example.com")
    assert row.status == "clicked"
    assert row.id is not None
    assert row.expires_at.date() == (row.clicked_at + timedelta(days=90)).date()


@pytest.mark.asyncio
async def test_track_invalid_partner_code(async_session: AsyncSession) -> None:
    with pytest.raises(NotFoundError):
        await track_referral_click(async_session, "NOPE-CODE")


@pytest.mark.asyncio
async def test_convert_referral_updates_status(async_session: AsyncSession, test_user: IamUser) -> None:
    partner = await register_partner(
        async_session,
        tenant_id=test_user.tenant_id,
        partner_tier="referral",
        company_name="Converter",
        contact_email="convert@example.com",
    )
    click = await track_referral_click(async_session, partner.partner_code)
    referred_tenant_id = uuid.uuid4()
    await _create_tenant(async_session, referred_tenant_id, "Converted Tenant")
    converted = await convert_referral(async_session, click.referral_code, referred_tenant_id)
    assert converted.status == "signed_up"
    assert converted.referred_tenant_id == referred_tenant_id


@pytest.mark.asyncio
async def test_referral_expiry_set_correctly(async_session: AsyncSession, test_user: IamUser) -> None:
    partner = await register_partner(
        async_session,
        tenant_id=test_user.tenant_id,
        partner_tier="referral",
        company_name="Expiry",
        contact_email="expiry@example.com",
    )
    row = await track_referral_click(async_session, partner.partner_code)
    assert row.expires_at.date() == (row.clicked_at + timedelta(days=90)).date()


@pytest.mark.asyncio
async def test_expired_referral_not_eligible_for_commission(async_session: AsyncSession, test_user: IamUser) -> None:
    partner, referral, referred_tenant_id = await _register_and_convert_referral(async_session, test_user.tenant_id)
    now = datetime.now(UTC)
    # Keep row valid for ck_referral_tracking_expiry_gt_created while ensuring
    # referral is already expired at commission-evaluation time.
    referral.created_at = now - timedelta(days=2)
    referral.expires_at = now - timedelta(days=1)
    await async_session.flush()
    row = await record_commission(
        async_session,
        referred_tenant_id=referred_tenant_id,
        payment_amount=Decimal("1000.00"),
        commission_type="first_payment",
    )
    assert row is None


@pytest.mark.asyncio
async def test_referral_tracking_rls(async_session: AsyncSession, test_user: IamUser) -> None:
    partner_a = await register_partner(
        async_session,
        tenant_id=test_user.tenant_id,
        partner_tier="referral",
        company_name="RLS A",
        contact_email="rlsa@example.com",
    )
    row_a = await track_referral_click(async_session, partner_a.partner_code)
    tenant_b = uuid.uuid4()
    await _create_tenant(async_session, tenant_b, "Tenant B")
    partner_b = await register_partner(
        async_session,
        tenant_id=tenant_b,
        partner_tier="referral",
        company_name="RLS B",
        contact_email="rlsb@example.com",
    )
    row_b = await track_referral_click(async_session, partner_b.partner_code)
    rows = (
        await async_session.execute(
            select(ReferralTracking).where(ReferralTracking.tenant_id == test_user.tenant_id)
        )
    ).scalars().all()
    ids = {row.id for row in rows}
    assert row_a.id in ids
    assert row_b.id not in ids


@pytest.mark.asyncio
async def test_referral_no_duplicate_conversion(async_session: AsyncSession, test_user: IamUser) -> None:
    partner = await register_partner(
        async_session,
        tenant_id=test_user.tenant_id,
        partner_tier="referral",
        company_name="No Duplicate",
        contact_email="nodupe@example.com",
    )
    click = await track_referral_click(async_session, partner.partner_code)
    referred_tenant_id = uuid.uuid4()
    await _create_tenant(async_session, referred_tenant_id, "Referred")
    first = await convert_referral(async_session, click.referral_code, referred_tenant_id)
    second = await convert_referral(async_session, click.referral_code, referred_tenant_id)
    assert first.id == second.id
    assert second.status in {"signed_up", "converted"}


# Commission (8)
@pytest.mark.asyncio
async def test_record_commission_referral_tier(async_session: AsyncSession, test_user: IamUser) -> None:
    _, _, referred_tenant_id = await _register_and_convert_referral(async_session, test_user.tenant_id, "referral")
    commission = await record_commission(
        async_session,
        referred_tenant_id=referred_tenant_id,
        payment_amount=Decimal("1000.00"),
        commission_type="first_payment",
    )
    assert commission is not None
    assert commission.commission_amount == Decimal("150.00")


@pytest.mark.asyncio
async def test_record_commission_reseller_tier(async_session: AsyncSession) -> None:
    tenant_id = uuid.uuid4()
    await _create_tenant(async_session, tenant_id, "Reseller Partner Tenant")
    _, _, referred_tenant_id = await _register_and_convert_referral(async_session, tenant_id, "reseller")
    commission = await record_commission(
        async_session,
        referred_tenant_id=referred_tenant_id,
        payment_amount=Decimal("1000.00"),
        commission_type="first_payment",
    )
    assert commission is not None
    assert commission.commission_amount == Decimal("300.00")


@pytest.mark.asyncio
async def test_commission_amount_is_decimal(async_session: AsyncSession, test_user: IamUser) -> None:
    _, _, referred_tenant_id = await _register_and_convert_referral(async_session, test_user.tenant_id)
    commission = await record_commission(
        async_session,
        referred_tenant_id=referred_tenant_id,
        payment_amount=Decimal("1234.56"),
        commission_type="first_payment",
    )
    assert commission is not None
    assert isinstance(commission.commission_amount, Decimal)


@pytest.mark.asyncio
async def test_commission_is_append_only(async_session: AsyncSession, test_user: IamUser) -> None:
    _, _, referred_tenant_id = await _register_and_convert_referral(async_session, test_user.tenant_id)
    commission = await record_commission(
        async_session,
        referred_tenant_id=referred_tenant_id,
        payment_amount=Decimal("1000.00"),
        commission_type="first_payment",
    )
    assert commission is not None
    await async_session.execute(text(append_only_function_sql()))
    await async_session.execute(text(drop_trigger_sql("partner_commissions")))
    await async_session.execute(text(create_trigger_sql("partner_commissions")))
    await async_session.flush()
    with pytest.raises(Exception):
        await async_session.execute(
            text("UPDATE partner_commissions SET status = 'paid' WHERE id = :id"),
            {"id": commission.id},
        )


@pytest.mark.asyncio
async def test_no_commission_without_referral(async_session: AsyncSession, test_user: IamUser) -> None:
    tenant_id = uuid.uuid4()
    await _create_tenant(async_session, tenant_id, "No Referral")
    row = await record_commission(
        async_session,
        referred_tenant_id=tenant_id,
        payment_amount=Decimal("100.00"),
        commission_type="first_payment",
    )
    assert row is None


@pytest.mark.asyncio
async def test_first_payment_sets_converted_status(async_session: AsyncSession, test_user: IamUser) -> None:
    _, referral, referred_tenant_id = await _register_and_convert_referral(async_session, test_user.tenant_id)
    commission = await record_commission(
        async_session,
        referred_tenant_id=referred_tenant_id,
        payment_amount=Decimal("500.00"),
        commission_type="first_payment",
    )
    assert commission is not None
    assert referral.status == "converted"


@pytest.mark.asyncio
async def test_total_commissions_updated(async_session: AsyncSession, test_user: IamUser) -> None:
    partner, _, referred_tenant_id = await _register_and_convert_referral(async_session, test_user.tenant_id)
    before = partner.total_commissions_earned
    commission = await record_commission(
        async_session,
        referred_tenant_id=referred_tenant_id,
        payment_amount=Decimal("500.00"),
        commission_type="first_payment",
    )
    assert commission is not None
    assert partner.total_commissions_earned > before


@pytest.mark.asyncio
async def test_commission_decimal_not_float(async_session: AsyncSession, test_user: IamUser) -> None:
    _, _, referred_tenant_id = await _register_and_convert_referral(async_session, test_user.tenant_id)
    commission = await record_commission(
        async_session,
        referred_tenant_id=referred_tenant_id,
        payment_amount=Decimal("999.99"),
        commission_type="first_payment",
    )
    assert commission is not None
    assert isinstance(commission.commission_amount, Decimal)


# Dashboard (3)
@pytest.mark.asyncio
async def test_partner_dashboard_structure(async_session: AsyncSession, test_user: IamUser) -> None:
    partner, _, referred_tenant_id = await _register_and_convert_referral(async_session, test_user.tenant_id)
    await record_commission(
        async_session,
        referred_tenant_id=referred_tenant_id,
        payment_amount=Decimal("1000.00"),
        commission_type="first_payment",
    )
    payload = await get_partner_dashboard(async_session, partner.id)
    assert {"partner", "referral_link", "stats", "recent_referrals", "commission_history"}.issubset(payload.keys())


@pytest.mark.asyncio
async def test_conversion_rate_decimal(async_session: AsyncSession, test_user: IamUser) -> None:
    partner = await register_partner(
        async_session,
        tenant_id=test_user.tenant_id,
        partner_tier="referral",
        company_name="Rate",
        contact_email="rate@example.com",
    )
    for idx in range(3):
        click = await track_referral_click(async_session, partner.partner_code, f"user{idx}@example.com")
        referred_tenant_id = uuid.uuid4()
        await _create_tenant(async_session, referred_tenant_id, f"Rate Tenant {idx}")
        await convert_referral(async_session, click.referral_code, referred_tenant_id)
        if idx == 0:
            await record_commission(
                async_session,
                referred_tenant_id=referred_tenant_id,
                payment_amount=Decimal("100.00"),
                commission_type="first_payment",
            )
    payload = await get_partner_dashboard(async_session, partner.id)
    assert payload["stats"]["conversion_rate"] == Decimal("0.3333")


@pytest.mark.asyncio
async def test_referral_link_contains_partner_code(async_session: AsyncSession, test_user: IamUser) -> None:
    partner = await register_partner(
        async_session,
        tenant_id=test_user.tenant_id,
        partner_tier="referral",
        company_name="Link Co",
        contact_email="link@example.com",
    )
    payload = await get_partner_dashboard(async_session, partner.id)
    assert partner.partner_code in payload["referral_link"]


# API (2)
@pytest.mark.asyncio
async def test_track_endpoint_no_auth_required(async_client: AsyncClient) -> None:
    response = await async_client.post(
        "/api/v1/partner/track",
        json={"partner_code": "UNKNOWN-CODE"},
    )
    assert response.status_code != 401


@pytest.mark.asyncio
async def test_admin_approve_requires_platform_admin(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_user: IamUser,
    test_access_token: str,
) -> None:
    partner = await register_partner(
        async_session,
        tenant_id=test_user.tenant_id,
        partner_tier="referral",
        company_name="Admin Approval",
        contact_email="adminapprove@example.com",
    )
    denied = await async_client.post(
        f"/api/v1/partner/admin/{partner.id}/approve",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert denied.status_code == 403

    admin = await _create_platform_user(async_session, "partner.admin@example.com", UserRole.platform_admin)
    allowed = await async_client.post(
        f"/api/v1/partner/admin/{partner.id}/approve",
        headers=_auth_headers(admin),
    )
    assert allowed.status_code == 200


def test_generate_partner_code_uniqueness_small_sample() -> None:
    codes = {_generate_partner_code(f"Test Company {idx}") for idx in range(25)}
    assert len(codes) == 25
