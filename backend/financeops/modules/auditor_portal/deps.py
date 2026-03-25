from __future__ import annotations

import logging
import uuid

import redis.asyncio as aioredis
from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_redis
from financeops.modules.auditor_portal.models import AuditorPortalAccess
from financeops.modules.auditor_portal.service import authenticate_auditor

log = logging.getLogger(__name__)


async def _check_token_brute_force(redis_client: aioredis.Redis | None, token_prefix: str) -> None:
    if redis_client is None:
        return
    key = f"auditor_token_fails:{token_prefix}"
    count = await redis_client.get(key)
    if count and int(count) >= 5:
        raise HTTPException(status_code=429, detail="Too many failed attempts. Try again later.")


async def _record_token_failure(redis_client: aioredis.Redis | None, token_prefix: str) -> None:
    if redis_client is None:
        return
    key = f"auditor_token_fails:{token_prefix}"
    await redis_client.incr(key)
    await redis_client.expire(key, 900)


async def _clear_token_failures(redis_client: aioredis.Redis | None, token_prefix: str) -> None:
    if redis_client is None:
        return
    await redis_client.delete(f"auditor_token_fails:{token_prefix}")


async def get_auditor_access(
    x_auditor_token: str = Header(..., alias="X-Auditor-Token"),
    session: AsyncSession = Depends(get_async_session),
    redis_client: aioredis.Redis = Depends(get_redis),
) -> AuditorPortalAccess:
    """
    Authenticate auditor access from token only (no JWT required).
    """
    token_value = x_auditor_token.strip()
    token_prefix = token_value[:8] if token_value else "unknown"
    try:
        await _check_token_brute_force(redis_client, token_prefix)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        log.warning("auditor_token_bruteforce_check_failed error=%s", exc)

    try:
        tenant_str = token_value.split(".", 1)[0]
        tenant_id = uuid.UUID(tenant_str)
    except Exception:
        try:
            await _record_token_failure(redis_client, token_prefix)
        except Exception as exc:  # noqa: BLE001
            log.warning("auditor_token_failure_record_failed error=%s", exc)
        raise HTTPException(status_code=401, detail="Invalid auditor token format")

    access = await authenticate_auditor(
        session,
        access_token=token_value,
        expected_tenant_id=tenant_id,
    )
    if access is None:
        try:
            await _record_token_failure(redis_client, token_prefix)
        except Exception as exc:  # noqa: BLE001
            log.warning("auditor_token_failure_record_failed error=%s", exc)
        raise HTTPException(status_code=401, detail="Invalid or expired auditor token")
    if not access.is_active:
        raise HTTPException(status_code=403, detail="Auditor access has been revoked")
    try:
        await _clear_token_failures(redis_client, token_prefix)
    except Exception as exc:  # noqa: BLE001
        log.warning("auditor_token_failure_clear_failed error=%s", exc)
    return access


__all__ = ["get_auditor_access"]
