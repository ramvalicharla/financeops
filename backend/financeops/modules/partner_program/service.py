from __future__ import annotations

import logging
import re
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import NotFoundError, ValidationError
from financeops.db.session import AsyncSessionLocal
from financeops.modules.partner_program.models import PartnerCommission, PartnerProfile, ReferralTracking

_CODE_SANITIZE_RE = re.compile(r"[^A-Z0-9]+")
logger = logging.getLogger(__name__)
MAX_PARTNER_CODE_ATTEMPTS = 100


def _q2(value: Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _q4(value: Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.0000"), rounding=ROUND_HALF_UP)


def _to_decimal(value: Decimal | str | int) -> Decimal:
    return Decimal(str(value))


def _rate_for_tier(partner_tier: str) -> Decimal:
    if partner_tier == "reseller":
        return Decimal("0.3000")
    if partner_tier == "technology":
        return Decimal("0.1000")
    return Decimal("0.1500")


def _sanitize_company_prefix(company_name: str) -> str:
    base = _CODE_SANITIZE_RE.sub("-", company_name.strip().upper()).strip("-")
    if not base:
        base = "PARTNER"
    base = base[:8]
    return base


def _suffix_for_name(company_name: str) -> str:
    digest = uuid.uuid5(uuid.NAMESPACE_DNS, company_name).hex[:4]
    return digest.upper()


def _generate_partner_code(company_name: str) -> str:
    """
    Generate deterministic base partner code.
    """
    prefix = _sanitize_company_prefix(company_name)
    suffix = _suffix_for_name(company_name)
    return f"{prefix}-{suffix}"


def _generate_referral_code(partner_code: str) -> str:
    # Keep referral code deterministic length (<=20) and unique per click.
    suffix = uuid.uuid4().hex[:8].upper()
    prefix = re.sub(r"[^A-Z0-9]", "", partner_code.upper())[:12]
    if not prefix:
        prefix = "REF"
    return f"{prefix}{suffix}"[:20]


async def _unique_partner_code(session: AsyncSession, company_name: str) -> str:
    base_code = _generate_partner_code(company_name)
    candidate = base_code
    attempt = 1
    while attempt <= MAX_PARTNER_CODE_ATTEMPTS:
        existing = (
            await session.execute(
                select(PartnerProfile.id).where(PartnerProfile.partner_code == candidate)
            )
        ).scalar_one_or_none()
        if existing is None:
            return candidate
        candidate = f"{base_code[:15]}{attempt:04d}"[:20]
        attempt += 1
    logger.error(
        "partner_code_generation_exhausted company_name=%s max_attempts=%d",
        company_name,
        MAX_PARTNER_CODE_ATTEMPTS,
    )
    raise ValidationError("Unable to allocate a unique partner code after bounded attempts.")


async def register_partner(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    partner_tier: str,
    company_name: str,
    contact_email: str,
    website_url: str | None = None,
) -> PartnerProfile:
    """
    Register as a partner.
    """
    if partner_tier not in {"referral", "reseller", "technology"}:
        raise ValidationError("partner_tier must be referral, reseller, or technology")

    existing = (
        await session.execute(
            select(PartnerProfile).where(PartnerProfile.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    partner = PartnerProfile(
        tenant_id=tenant_id,
        partner_tier=partner_tier,
        company_name=company_name,
        contact_email=contact_email,
        website_url=website_url,
        partner_code=await _unique_partner_code(session, company_name),
        commission_rate_pct=_rate_for_tier(partner_tier),
        total_referrals=0,
        total_commissions_earned=Decimal("0"),
        is_active=False,
        approved_at=None,
    )
    session.add(partner)
    await session.flush()
    return partner


async def track_referral_click(
    session: AsyncSession,
    partner_code: str,
    referral_email: str | None = None,
) -> ReferralTracking:
    """
    Create referral click tracking record.
    """
    partner = (
        await session.execute(
            select(PartnerProfile).where(PartnerProfile.partner_code == partner_code)
        )
    ).scalar_one_or_none()
    if partner is None:
        raise NotFoundError("Partner code not found")

    now = datetime.now(UTC)
    row = ReferralTracking(
        partner_id=partner.id,
        referred_tenant_id=None,
        tenant_id=partner.tenant_id,
        referral_code=_generate_referral_code(partner.partner_code),
        referral_email=referral_email,
        status="clicked",
        clicked_at=now,
        expires_at=now + timedelta(days=90),
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    partner.total_referrals = int(partner.total_referrals or 0) + 1
    partner.updated_at = now
    await session.flush()
    return row


async def track_referral_click_public(
    partner_code: str,
    referral_email: str | None = None,
) -> ReferralTracking:
    async with AsyncSessionLocal() as session:
        row = await track_referral_click(
            session,
            partner_code=partner_code,
            referral_email=referral_email,
        )
        await session.commit()
        return row


async def convert_referral(
    session: AsyncSession,
    referral_code: str,
    new_tenant_id: uuid.UUID,
) -> ReferralTracking:
    """
    Mark clicked referral as signed up.
    """
    row = (
        await session.execute(
            select(ReferralTracking)
            .where(ReferralTracking.referral_code == referral_code)
            .order_by(desc(ReferralTracking.clicked_at), desc(ReferralTracking.id))
            .limit(1)
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError("Referral not found")
    if row.status in {"signed_up", "converted"} and row.referred_tenant_id == new_tenant_id:
        return row

    row.status = "signed_up"
    row.signed_up_at = datetime.now(UTC)
    row.referred_tenant_id = new_tenant_id
    row.updated_at = datetime.now(UTC)
    await session.flush()
    return row


async def record_commission(
    session: AsyncSession,
    referred_tenant_id: uuid.UUID,
    payment_amount: Decimal,
    commission_type: str,
    period: str | None = None,
) -> PartnerCommission | None:
    """
    Create immutable commission record for converted referral payments.
    """
    if commission_type not in {"first_payment", "recurring", "technology_rev_share"}:
        raise ValidationError("invalid commission_type")

    now = datetime.now(UTC)
    referral = (
        await session.execute(
            select(ReferralTracking)
            .where(
                ReferralTracking.referred_tenant_id == referred_tenant_id,
                ReferralTracking.status.in_(["signed_up", "converted"]),
                ReferralTracking.expires_at > now,
            )
            .order_by(desc(ReferralTracking.clicked_at), desc(ReferralTracking.id))
            .limit(1)
        )
    ).scalar_one_or_none()
    if referral is None:
        return None

    partner = (
        await session.execute(
            select(PartnerProfile).where(PartnerProfile.id == referral.partner_id)
        )
    ).scalar_one_or_none()
    if partner is None:
        return None

    payment = _q2(_to_decimal(payment_amount))
    rate = _q4(_to_decimal(partner.commission_rate_pct))
    commission_amount = _q2(payment * rate)

    row = PartnerCommission(
        partner_id=partner.id,
        referral_id=referral.id,
        referred_tenant_id=referred_tenant_id,
        commission_type=commission_type,
        payment_amount=payment,
        commission_rate=rate,
        commission_amount=commission_amount,
        status="pending",
        period=period,
    )
    session.add(row)

    partner.total_commissions_earned = _q2(
        _to_decimal(partner.total_commissions_earned) + commission_amount
    )
    partner.updated_at = now

    if commission_type == "first_payment":
        referral.status = "converted"
        referral.converted_at = now
        referral.first_payment_amount = payment
        referral.updated_at = now

    await session.flush()
    return row


async def get_partner_dashboard(
    session: AsyncSession,
    partner_id: uuid.UUID,
) -> dict:
    """
    Build partner dashboard summary.
    """
    partner = (
        await session.execute(
            select(PartnerProfile).where(PartnerProfile.id == partner_id)
        )
    ).scalar_one_or_none()
    if partner is None:
        raise NotFoundError("Partner not found")

    referrals = (
        await session.execute(
            select(ReferralTracking)
            .where(ReferralTracking.partner_id == partner.id)
            .order_by(desc(ReferralTracking.clicked_at), desc(ReferralTracking.id))
            .limit(10)
        )
    ).scalars().all()
    commissions = (
        await session.execute(
            select(PartnerCommission)
            .where(PartnerCommission.partner_id == partner.id)
            .order_by(desc(PartnerCommission.created_at), desc(PartnerCommission.id))
            .limit(10)
        )
    ).scalars().all()

    total_clicks = int(
        (
            await session.execute(
                select(func.count()).select_from(ReferralTracking).where(
                    ReferralTracking.partner_id == partner.id
                )
            )
        ).scalar_one()
    )
    total_signups = int(
        (
            await session.execute(
                select(func.count()).select_from(ReferralTracking).where(
                    ReferralTracking.partner_id == partner.id,
                    ReferralTracking.status.in_(["signed_up", "converted"]),
                )
            )
        ).scalar_one()
    )
    total_conversions = int(
        (
            await session.execute(
                select(func.count()).select_from(ReferralTracking).where(
                    ReferralTracking.partner_id == partner.id,
                    ReferralTracking.status == "converted",
                )
            )
        ).scalar_one()
    )
    conversion_rate = Decimal("0.0000")
    if total_signups > 0:
        conversion_rate = _q4(
            Decimal(str(total_conversions)) / Decimal(str(total_signups))
        )

    pending_commissions = _q2(
        _to_decimal(
            (
                await session.execute(
                    select(func.coalesce(func.sum(PartnerCommission.commission_amount), 0))
                    .where(
                        PartnerCommission.partner_id == partner.id,
                        PartnerCommission.status == "pending",
                    )
                )
            ).scalar_one()
        )
    )

    return {
        "partner": partner,
        "referral_link": f"https://app.finqor.ai?ref={partner.partner_code}",
        "stats": {
            "total_clicks": total_clicks,
            "total_signups": total_signups,
            "total_conversions": total_conversions,
            "conversion_rate": conversion_rate,
            "total_commissions_earned": _q2(_to_decimal(partner.total_commissions_earned)),
            "pending_commissions": pending_commissions,
        },
        "recent_referrals": referrals,
        "commission_history": commissions,
    }


async def approve_partner(
    session: AsyncSession,
    partner_id: uuid.UUID,
    approved_by: uuid.UUID,
) -> PartnerProfile:
    """
    Approve pending partner application.
    """
    del approved_by
    row = (
        await session.execute(
            select(PartnerProfile).where(PartnerProfile.id == partner_id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError("Partner not found")
    row.approved_at = datetime.now(UTC)
    row.is_active = True
    row.updated_at = datetime.now(UTC)
    await session.flush()
    return row


__all__ = [
    "_generate_partner_code",
    "approve_partner",
    "convert_referral",
    "get_partner_dashboard",
    "record_commission",
    "register_partner",
    "track_referral_click",
    "track_referral_click_public",
]
