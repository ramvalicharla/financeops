from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP
from typing import Any

from sqlalchemy import Select, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import NotFoundError, ValidationError
from financeops.modules.marketplace.models import (
    MarketplaceContributor,
    MarketplacePayout,
    MarketplacePurchase,
    MarketplaceRating,
    MarketplaceTemplate,
)
from financeops.services.credit_service import confirm_credits, reserve_credits


def _q2(value: Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _q4(value: Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.0000"), rounding=ROUND_HALF_UP)


def _to_decimal(value: Any, default: str = "0") -> Decimal:
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal(default)


def _revenue_share_for_tier(tier: str) -> Decimal:
    if tier == "verified_partner":
        return Decimal("0.7000")
    if tier == "platform_official":
        return Decimal("1.0000")
    return Decimal("0.6000")


def _month_bounds(today: date) -> tuple[date, date]:
    start = date(today.year, today.month, 1)
    if today.month == 12:
        next_month = date(today.year + 1, 1, 1)
    else:
        next_month = date(today.year, today.month + 1, 1)
    return start, (next_month - timedelta(days=1))


async def register_contributor(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    display_name: str,
    bio: str | None = None,
) -> MarketplaceContributor:
    """
    Register a tenant as a marketplace contributor.
    """
    existing = (
        await session.execute(
            select(MarketplaceContributor).where(
                MarketplaceContributor.tenant_id == tenant_id
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    contributor = MarketplaceContributor(
        tenant_id=tenant_id,
        display_name=display_name,
        bio=bio,
        contributor_tier="community",
        revenue_share_pct=Decimal("0.6000"),
    )
    session.add(contributor)
    await session.flush()
    return contributor


def _validate_template_data(template_type: str, template_data: dict) -> None:
    if not isinstance(template_data, dict):
        raise ValidationError("template_data must be an object")
    if template_type == "mis_template" and "line_items" in template_data:
        if not isinstance(template_data["line_items"], list):
            raise ValidationError("mis_template line_items must be a list")
    if template_type == "report_template" and "sections" in template_data:
        if not isinstance(template_data["sections"], list):
            raise ValidationError("report_template sections must be a list")


async def submit_template(
    session: AsyncSession,
    contributor_id: uuid.UUID,
    tenant_id: uuid.UUID,
    title: str,
    description: str,
    template_type: str,
    price_credits: int,
    template_data: dict,
    industry: str | None = None,
    tags: list[str] | None = None,
) -> MarketplaceTemplate:
    """
    Submit a template for review.
    """
    contributor = (
        await session.execute(
            select(MarketplaceContributor).where(
                MarketplaceContributor.id == contributor_id,
                MarketplaceContributor.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if contributor is None:
        raise NotFoundError("Contributor not found")
    if price_credits < 0:
        raise ValidationError("price_credits must be >= 0")

    _validate_template_data(template_type, template_data)

    template = MarketplaceTemplate(
        contributor_id=contributor_id,
        tenant_id=tenant_id,
        title=title,
        description=description,
        template_type=template_type,
        industry=industry,
        price_credits=price_credits,
        is_free=price_credits == 0,
        template_data=template_data,
        tags=list(tags or []),
        status="pending_review",
    )
    session.add(template)
    await session.flush()
    return template


async def review_template(
    session: AsyncSession,
    template_id: uuid.UUID,
    action: str,
    review_notes: str | None = None,
) -> MarketplaceTemplate:
    """
    Platform admin template review flow.
    """
    template = (
        await session.execute(
            select(MarketplaceTemplate).where(MarketplaceTemplate.id == template_id)
        )
    ).scalar_one_or_none()
    if template is None:
        raise NotFoundError("Template not found")
    contributor = (
        await session.execute(
            select(MarketplaceContributor).where(
                MarketplaceContributor.id == template.contributor_id
            )
        )
    ).scalar_one()

    if action == "approve":
        was_published = template.status == "published"
        template.status = "published"
        template.review_notes = None
        if not was_published:
            contributor.total_templates = int(contributor.total_templates or 0) + 1
    elif action == "reject":
        template.status = "rejected"
        template.review_notes = review_notes
    else:
        raise ValidationError("action must be approve or reject")

    template.updated_at = datetime.now(UTC)
    await session.flush()
    return template


async def _require_published_template(
    session: AsyncSession,
    template_id: uuid.UUID,
) -> tuple[MarketplaceTemplate, MarketplaceContributor]:
    template = (
        await session.execute(
            select(MarketplaceTemplate).where(
                MarketplaceTemplate.id == template_id
            )
        )
    ).scalar_one_or_none()
    if template is None:
        raise NotFoundError("Template not found")
    if template.status != "published":
        raise ValidationError("Template is not published")

    contributor = (
        await session.execute(
            select(MarketplaceContributor).where(
                MarketplaceContributor.id == template.contributor_id
            )
        )
    ).scalar_one_or_none()
    if contributor is None:
        raise NotFoundError("Contributor not found")
    return template, contributor


async def purchase_template(
    session: AsyncSession,
    buyer_tenant_id: uuid.UUID,
    template_id: uuid.UUID,
) -> MarketplacePurchase:
    """
    Purchase a marketplace template.
    """
    template, contributor = await _require_published_template(session, template_id)
    existing_purchase = (
        await session.execute(
            select(MarketplacePurchase).where(
                MarketplacePurchase.template_id == template.id,
                MarketplacePurchase.buyer_tenant_id == buyer_tenant_id,
            )
        )
    ).scalar_one_or_none()
    if existing_purchase is not None:
        return existing_purchase

    price = int(template.price_credits or 0)
    is_free = bool(template.is_free) or price == 0
    contributor_share_pct = _q4(
        _to_decimal(contributor.revenue_share_pct or _revenue_share_for_tier(contributor.contributor_tier))
    )
    platform_share_pct = _q4(Decimal("1.0000") - contributor_share_pct)

    if is_free:
        contributor_share_credits = 0
        platform_share_credits = 0
        paid_credits = 0
    else:
        reservation_id = await reserve_credits(
            session,
            tenant_id=buyer_tenant_id,
            task_type=f"marketplace_purchase:{template.id}:{uuid.uuid4()}",
            amount=Decimal(str(price)),
        )
        await confirm_credits(
            session,
            tenant_id=buyer_tenant_id,
            reservation_id=reservation_id,
            user_id=None,
        )
        paid_credits = price
        contributor_share_credits = int(
            (
                Decimal(str(price)) * contributor_share_pct
            ).to_integral_value(rounding=ROUND_FLOOR)
        )
        platform_share_credits = price - contributor_share_credits

    purchase = MarketplacePurchase(
        template_id=template.id,
        buyer_tenant_id=buyer_tenant_id,
        contributor_id=contributor.id,
        price_credits_paid=paid_credits,
        platform_share_credits=platform_share_credits,
        contributor_share_credits=contributor_share_credits,
        platform_share_pct=platform_share_pct,
        contributor_share_pct=contributor_share_pct,
        status="completed",
    )
    session.add(purchase)

    template.download_count = int(template.download_count or 0) + 1
    contributor.total_downloads = int(contributor.total_downloads or 0) + 1
    contributor.total_earnings = _q2(
        _to_decimal(contributor.total_earnings) + Decimal(str(contributor_share_credits))
    )
    template.updated_at = datetime.now(UTC)
    contributor.updated_at = datetime.now(UTC)

    await session.flush()
    return purchase


async def _refresh_contributor_rating(
    session: AsyncSession,
    contributor_id: uuid.UUID,
) -> None:
    avg_value = (
        await session.execute(
            select(func.avg(MarketplaceRating.rating))
            .join(
                MarketplaceTemplate,
                MarketplaceTemplate.id == MarketplaceRating.template_id,
            )
            .where(MarketplaceTemplate.contributor_id == contributor_id)
        )
    ).scalar_one_or_none()
    contributor = (
        await session.execute(
            select(MarketplaceContributor).where(MarketplaceContributor.id == contributor_id)
        )
    ).scalar_one_or_none()
    if contributor is None:
        return
    contributor.rating_average = _q2(_to_decimal(avg_value, "0"))


async def rate_template(
    session: AsyncSession,
    buyer_tenant_id: uuid.UUID,
    template_id: uuid.UUID,
    rating: int,
    review_text: str | None = None,
) -> MarketplaceRating:
    """
    Rate a purchased template.
    """
    if rating < 1 or rating > 5:
        raise ValidationError("rating must be between 1 and 5")

    template, contributor = await _require_published_template(session, template_id)
    purchase = (
        await session.execute(
            select(MarketplacePurchase).where(
                MarketplacePurchase.template_id == template.id,
                MarketplacePurchase.buyer_tenant_id == buyer_tenant_id,
            )
        )
    ).scalar_one_or_none()
    if purchase is None:
        raise ValidationError("Template must be purchased before rating")

    existing_rating = (
        await session.execute(
            select(MarketplaceRating).where(
                MarketplaceRating.template_id == template.id,
                MarketplaceRating.buyer_tenant_id == buyer_tenant_id,
            )
        )
    ).scalar_one_or_none()
    if existing_rating is not None:
        raise ValidationError("Template already rated by this tenant")

    row = MarketplaceRating(
        template_id=template.id,
        buyer_tenant_id=buyer_tenant_id,
        rating=rating,
        review_text=review_text,
    )
    session.add(row)

    template.rating_count = int(template.rating_count or 0) + 1
    template.rating_sum = int(template.rating_sum or 0) + int(rating)
    template.rating_average = _q2(
        Decimal(str(template.rating_sum))
        / Decimal(str(template.rating_count))
    )
    template.updated_at = datetime.now(UTC)

    await _refresh_contributor_rating(session, contributor.id)
    await session.flush()
    return row


def _apply_listing_filters(
    stmt: Select[tuple[MarketplaceTemplate]],
    *,
    template_type: str | None,
    industry: str | None,
    is_free: bool | None,
) -> Select[tuple[MarketplaceTemplate]]:
    filtered = stmt.where(MarketplaceTemplate.status == "published")
    if template_type:
        filtered = filtered.where(MarketplaceTemplate.template_type == template_type)
    if industry:
        filtered = filtered.where(MarketplaceTemplate.industry == industry)
    if is_free is not None:
        filtered = filtered.where(MarketplaceTemplate.is_free.is_(is_free))
    return filtered


async def get_marketplace_listings(
    session: AsyncSession,
    template_type: str | None = None,
    industry: str | None = None,
    is_free: bool | None = None,
    sort_by: str = "featured",
    limit: int = 20,
    offset: int = 0,
) -> dict:
    """
    Public marketplace listing.
    """
    stmt = _apply_listing_filters(
        select(MarketplaceTemplate),
        template_type=template_type,
        industry=industry,
        is_free=is_free,
    )
    total = int(
        (
            await session.execute(
                select(func.count()).select_from(stmt.subquery())
            )
        ).scalar_one()
    )

    if sort_by == "newest":
        stmt = stmt.order_by(desc(MarketplaceTemplate.created_at), desc(MarketplaceTemplate.id))
    elif sort_by == "popular":
        stmt = stmt.order_by(desc(MarketplaceTemplate.download_count), desc(MarketplaceTemplate.created_at))
    elif sort_by == "price_asc":
        stmt = stmt.order_by(MarketplaceTemplate.price_credits.asc(), desc(MarketplaceTemplate.created_at))
    elif sort_by == "rating":
        stmt = stmt.order_by(desc(MarketplaceTemplate.rating_average), desc(MarketplaceTemplate.rating_count))
    else:
        stmt = stmt.order_by(
            desc(MarketplaceTemplate.is_featured),
            desc(MarketplaceTemplate.rating_average),
            desc(MarketplaceTemplate.created_at),
        )

    rows = (
        await session.execute(
            stmt.limit(limit).offset(offset)
        )
    ).scalars().all()

    return {
        "data": rows,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


async def get_contributor_dashboard(
    session: AsyncSession,
    contributor_id: uuid.UUID,
) -> dict:
    """
    Returns contributor analytics.
    """
    contributor = (
        await session.execute(
            select(MarketplaceContributor).where(MarketplaceContributor.id == contributor_id)
        )
    ).scalar_one_or_none()
    if contributor is None:
        raise NotFoundError("Contributor not found")

    templates = (
        await session.execute(
            select(MarketplaceTemplate)
            .where(MarketplaceTemplate.contributor_id == contributor.id)
            .order_by(desc(MarketplaceTemplate.updated_at), desc(MarketplaceTemplate.id))
        )
    ).scalars().all()
    purchases = (
        await session.execute(
            select(MarketplacePurchase)
            .where(MarketplacePurchase.contributor_id == contributor.id)
            .order_by(desc(MarketplacePurchase.purchased_at), desc(MarketplacePurchase.id))
            .limit(10)
        )
    ).scalars().all()
    payouts = (
        await session.execute(
            select(MarketplacePayout)
            .where(MarketplacePayout.contributor_id == contributor.id)
            .order_by(desc(MarketplacePayout.created_at), desc(MarketplacePayout.id))
            .limit(5)
        )
    ).scalars().all()

    month_start, month_end = _month_bounds(datetime.now(UTC).date())
    earnings_this_month_credits = (
        await session.execute(
            select(func.coalesce(func.sum(MarketplacePurchase.contributor_share_credits), 0))
            .where(
                MarketplacePurchase.contributor_id == contributor.id,
                MarketplacePurchase.purchased_at >= datetime.combine(month_start, datetime.min.time(), tzinfo=UTC),
                MarketplacePurchase.purchased_at <= datetime.combine(month_end, datetime.max.time(), tzinfo=UTC),
            )
        )
    ).scalar_one()

    top_template = (
        await session.execute(
            select(MarketplaceTemplate)
            .where(MarketplaceTemplate.contributor_id == contributor.id)
            .order_by(desc(MarketplaceTemplate.download_count), desc(MarketplaceTemplate.id))
            .limit(1)
        )
    ).scalar_one_or_none()

    return {
        "contributor": contributor,
        "templates": templates,
        "earnings_this_month": _q2(_to_decimal(earnings_this_month_credits)),
        "earnings_total": _q2(_to_decimal(contributor.total_earnings)),
        "top_template": top_template,
        "recent_purchases": purchases,
        "payout_history": payouts,
    }


async def process_monthly_payouts(
    session: AsyncSession,
) -> list[MarketplacePayout]:
    """
    Monthly payout processing.
    """
    month_start, month_end = _month_bounds(datetime.now(UTC).date())
    created: list[MarketplacePayout] = []

    contributors = (
        await session.execute(
            select(MarketplaceContributor).where(MarketplaceContributor.is_active.is_(True))
        )
    ).scalars().all()

    for contributor in contributors:
        existing = (
            await session.execute(
                select(MarketplacePayout).where(
                    MarketplacePayout.contributor_id == contributor.id,
                    MarketplacePayout.period_start == month_start,
                    MarketplacePayout.period_end == month_end,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            continue

        credits_earned = (
            await session.execute(
                select(func.coalesce(func.sum(MarketplacePurchase.contributor_share_credits), 0))
                .where(
                    MarketplacePurchase.contributor_id == contributor.id,
                    MarketplacePurchase.purchased_at >= datetime.combine(month_start, datetime.min.time(), tzinfo=UTC),
                    MarketplacePurchase.purchased_at <= datetime.combine(month_end, datetime.max.time(), tzinfo=UTC),
                )
            )
        ).scalar_one()
        credits_int = int(credits_earned or 0)
        if credits_int <= 0:
            continue

        usd_amount = _q2(Decimal(str(credits_int)) * Decimal("0.01"))
        payout = MarketplacePayout(
            contributor_id=contributor.id,
            period_start=month_start,
            period_end=month_end,
            total_credits_earned=credits_int,
            total_usd_amount=usd_amount,
            status="pending",
        )
        session.add(payout)
        created.append(payout)

    await session.flush()
    return created


__all__ = [
    "get_contributor_dashboard",
    "get_marketplace_listings",
    "process_monthly_payouts",
    "purchase_template",
    "rate_template",
    "register_contributor",
    "review_template",
    "submit_template",
]

