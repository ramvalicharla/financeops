from __future__ import annotations

import re
import secrets
import uuid
from datetime import UTC, datetime
from typing import Any

import redis.asyncio as aioredis
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.config import settings
from financeops.core.exceptions import ValidationError
from financeops.modules.white_label.models import WhiteLabelAuditLog, WhiteLabelConfig

_HEX_COLOUR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
_DOMAIN_RE = re.compile(
    r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$"
)
_ALLOWED_FONTS = {"inter", "plus_jakarta", "geist", "dm_sans"}
_CACHE_TTL_SECONDS = 300

_redis_pool: aioredis.Redis | None = None


def _to_text(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _normalize_domain(domain: str) -> str:
    return domain.strip().lower().rstrip(".")


def _validate_domain(domain: str) -> str:
    cleaned = _normalize_domain(domain)
    if not cleaned:
        raise ValidationError("custom_domain is required")
    if "://" in cleaned or "/" in cleaned or "?" in cleaned:
        raise ValidationError("custom_domain must not include protocol, path, or query")
    if not _DOMAIN_RE.match(cleaned):
        raise ValidationError("custom_domain is invalid")
    return cleaned


def _validate_colour(value: str | None, field_name: str) -> None:
    if value is None:
        return
    if not _HEX_COLOUR_RE.match(value):
        raise ValidationError(f"{field_name} must be a valid #RRGGBB value")


def _validate_font_family(value: str | None) -> None:
    if value is None:
        return
    if value not in _ALLOWED_FONTS:
        raise ValidationError("font_family is invalid")


def _validate_custom_css(value: str | None) -> None:
    if value is None:
        return
    if len(value) > 10000:
        raise ValidationError("custom_css exceeds 10,000 characters")


async def _get_redis_pool() -> aioredis.Redis | None:
    global _redis_pool
    try:
        if _redis_pool is None:
            _redis_pool = aioredis.from_url(
                str(settings.REDIS_URL),
                encoding="utf-8",
                decode_responses=True,
            )
        return _redis_pool
    except Exception:
        return None


async def _cache_domain_hit(domain: str, config_id: uuid.UUID | None) -> None:
    redis_pool = await _get_redis_pool()
    if redis_pool is None:
        return
    try:
        value = str(config_id) if config_id is not None else "none"
        await redis_pool.setex(f"white_label:domain:{domain}", _CACHE_TTL_SECONDS, value)
    except Exception:
        return


async def _get_cached_domain(domain: str) -> str | None:
    redis_pool = await _get_redis_pool()
    if redis_pool is None:
        return None
    try:
        value = await redis_pool.get(f"white_label:domain:{domain}")
        return value if isinstance(value, str) else None
    except Exception:
        return None


async def get_or_create_config(
    session: AsyncSession,
    tenant_id: uuid.UUID,
) -> WhiteLabelConfig:
    row = (
        await session.execute(
            select(WhiteLabelConfig).where(WhiteLabelConfig.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if row is not None:
        return row

    row = WhiteLabelConfig(tenant_id=tenant_id, is_enabled=False, domain_verified=False)
    session.add(row)
    await session.flush()
    return row


async def update_branding(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    updated_by: uuid.UUID,
    updates: dict,
) -> WhiteLabelConfig:
    """
    Update white label branding fields and log all changes.
    """
    row = await get_or_create_config(session, tenant_id)
    allowed_fields = {
        "custom_domain",
        "brand_name",
        "logo_url",
        "favicon_url",
        "primary_colour",
        "secondary_colour",
        "font_family",
        "hide_powered_by",
        "custom_css",
        "support_email",
        "support_url",
    }
    unknown_fields = [key for key in updates if key not in allowed_fields]
    if unknown_fields:
        raise ValidationError(f"Unsupported fields: {', '.join(sorted(unknown_fields))}")

    if "custom_domain" in updates and updates["custom_domain"] is not None:
        updates["custom_domain"] = _validate_domain(str(updates["custom_domain"]))
    _validate_colour(updates.get("primary_colour"), "primary_colour")
    _validate_colour(updates.get("secondary_colour"), "secondary_colour")
    _validate_font_family(updates.get("font_family"))
    _validate_custom_css(updates.get("custom_css"))

    for field_name, new_value in updates.items():
        old_value = getattr(row, field_name)
        if old_value == new_value:
            continue
        setattr(row, field_name, new_value)
        if field_name == "custom_domain":
            row.domain_verified = False
        session.add(
            WhiteLabelAuditLog(
                tenant_id=tenant_id,
                changed_by=updated_by,
                field_changed=field_name,
                old_value=_to_text(old_value),
                new_value=_to_text(new_value),
            )
        )

    row.updated_at = datetime.now(UTC)
    await session.flush()
    if row.custom_domain:
        await _cache_domain_hit(_normalize_domain(row.custom_domain), None)
    return row


async def initiate_domain_verification(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    custom_domain: str,
) -> dict:
    """
    Start DNS TXT verification flow for custom domains.
    """
    row = await get_or_create_config(session, tenant_id)
    domain = _validate_domain(custom_domain)
    token = secrets.token_urlsafe(24)

    row.custom_domain = domain
    row.domain_verification_token = token
    row.domain_verified = False
    row.updated_at = datetime.now(UTC)
    await session.flush()
    await _cache_domain_hit(domain, None)

    txt_record_name = f"_financeops-verify.{domain}"
    return {
        "domain": domain,
        "verification_token": token,
        "txt_record_name": txt_record_name,
        "txt_record_value": token,
        "instructions": (
            "Create a DNS TXT record with the values above. "
            "Then run verification check to confirm domain ownership."
        ),
    }


async def verify_domain(
    session: AsyncSession,
    tenant_id: uuid.UUID,
) -> bool:
    """
    Validate domain verification token via DNS TXT lookup.
    """
    row = await get_or_create_config(session, tenant_id)
    if not row.custom_domain or not row.domain_verification_token:
        return False

    txt_record_name = f"_financeops-verify.{_normalize_domain(row.custom_domain)}"
    found_values: list[str] = []
    try:
        import dns.resolver  # type: ignore[import-not-found]

        answers = dns.resolver.resolve(txt_record_name, "TXT")
        for answer in answers:
            joined = "".join(part.decode("utf-8") if isinstance(part, bytes) else str(part) for part in answer.strings)
            found_values.append(joined.strip())
    except Exception:
        return False

    if row.domain_verification_token in found_values:
        row.domain_verified = True
        row.updated_at = datetime.now(UTC)
        await session.flush()
        await _cache_domain_hit(_normalize_domain(row.custom_domain), row.id)
        return True
    return False


async def get_branding_for_domain(
    session: AsyncSession,
    domain: str,
) -> WhiteLabelConfig | None:
    """
    Resolve a verified and enabled white-label configuration by domain.
    """
    clean_domain = _validate_domain(domain)
    cached = await _get_cached_domain(clean_domain)
    if cached == "none":
        return None
    if cached:
        try:
            cached_id = uuid.UUID(cached)
        except ValueError:
            cached_id = None
        if cached_id is not None:
            row = (
                await session.execute(
                    select(WhiteLabelConfig).where(WhiteLabelConfig.id == cached_id)
                )
            ).scalar_one_or_none()
            if row is not None and row.domain_verified and row.is_enabled:
                return row

    row = (
        await session.execute(
            select(WhiteLabelConfig).where(
                WhiteLabelConfig.custom_domain == clean_domain,
                WhiteLabelConfig.domain_verified.is_(True),
                WhiteLabelConfig.is_enabled.is_(True),
            )
        )
    ).scalar_one_or_none()
    await _cache_domain_hit(clean_domain, row.id if row is not None else None)
    return row


async def enable_white_label(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    enabled_by: uuid.UUID,
) -> WhiteLabelConfig:
    row = await get_or_create_config(session, tenant_id)
    old_value = row.is_enabled
    row.is_enabled = True
    row.updated_at = datetime.now(UTC)
    session.add(
        WhiteLabelAuditLog(
            tenant_id=tenant_id,
            changed_by=enabled_by,
            field_changed="is_enabled",
            old_value=_to_text(old_value),
            new_value="True",
        )
    )
    await session.flush()
    if row.custom_domain and row.domain_verified:
        await _cache_domain_hit(_normalize_domain(row.custom_domain), row.id)
    return row


async def list_audit_log(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    limit: int,
    offset: int,
) -> tuple[list[WhiteLabelAuditLog], int]:
    stmt = select(WhiteLabelAuditLog).where(WhiteLabelAuditLog.tenant_id == tenant_id)
    total = int((await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one())
    rows = (
        await session.execute(
            stmt.order_by(desc(WhiteLabelAuditLog.created_at), desc(WhiteLabelAuditLog.id))
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    return rows, total


__all__ = [
    "enable_white_label",
    "get_branding_for_domain",
    "get_or_create_config",
    "initiate_domain_verification",
    "list_audit_log",
    "update_branding",
    "verify_domain",
]
