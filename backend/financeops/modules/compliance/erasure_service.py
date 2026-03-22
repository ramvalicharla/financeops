from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import NotFoundError, ValidationError
from financeops.db.models.users import IamSession, IamUser
from financeops.modules.compliance.models import ErasureLog, UserPiiKey

log = logging.getLogger(__name__)


async def erase_user_pii(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    requested_by: uuid.UUID | None = None,
    request_method: str = "self",
) -> dict:
    """
    Cryptographic erasure of a user's PII.
    """
    if request_method not in {"self", "admin", "regulatory"}:
        raise ValidationError("request_method must be self, admin, or regulatory")

    user = (
        await session.execute(
            select(IamUser).where(
                IamUser.id == user_id,
                IamUser.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if user is None:
        raise NotFoundError("User not found for tenant")

    user_id_hash = hashlib.sha256(str(user_id).encode()).hexdigest()
    initiated = ErasureLog(
        tenant_id=tenant_id,
        user_id=user_id,
        user_id_hash=user_id_hash,
        requested_by=requested_by,
        request_method=request_method,
        status="initiated",
        pii_fields_erased=[],
    )
    session.add(initiated)
    await session.flush()

    try:
        await session.execute(delete(IamSession).where(IamSession.user_id == user_id))
        await session.execute(
            update(IamUser)
            .where(IamUser.id == user_id, IamUser.tenant_id == tenant_id)
            .values(
                email=f"erased_{user_id_hash[:12]}@erased.invalid",
                full_name="[Erased]",
                hashed_password="[ERASED]",
                totp_secret_encrypted=None,
                mfa_enabled=False,
                is_active=False,
            )
        )
        await session.execute(
            update(UserPiiKey)
            .where(
                UserPiiKey.user_id == user_id,
                UserPiiKey.tenant_id == tenant_id,
            )
            .values(
                encrypted_key=None,
                erased_at=datetime.now(UTC),
            )
        )

        completed_at = datetime.now(UTC)
        completed = ErasureLog(
            tenant_id=tenant_id,
            user_id=None,
            user_id_hash=user_id_hash,
            requested_by=requested_by,
            request_method=request_method,
            status="completed",
            pii_fields_erased=[
                "email",
                "full_name",
                "hashed_password",
                "totp_secret_encrypted",
                "pii_key",
            ],
            completed_at=completed_at,
        )
        session.add(completed)
        await session.commit()
        return {
            "status": "completed",
            "user_id_hash": user_id_hash,
            "fields_erased": completed.pii_fields_erased,
            "completed_at": completed_at.isoformat(),
        }
    except Exception as exc:
        await session.rollback()
        log.exception("erasure_failed user_id_hash=%s", user_id_hash)
        failed = ErasureLog(
            tenant_id=tenant_id,
            user_id=user_id,
            user_id_hash=user_id_hash,
            requested_by=requested_by,
            request_method=request_method,
            status="failed",
            pii_fields_erased=[],
        )
        session.add(failed)
        await session.commit()
        raise exc


async def list_erasure_logs(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[ErasureLog], int]:
    clamped_limit = max(1, min(100, int(limit)))
    clamped_offset = max(0, int(offset))

    total = len(
        (
            await session.execute(
                select(ErasureLog.id).where(ErasureLog.tenant_id == tenant_id)
            )
        ).scalars().all()
    )
    rows = (
        await session.execute(
            select(ErasureLog)
            .where(ErasureLog.tenant_id == tenant_id)
            .order_by(ErasureLog.created_at.desc(), ErasureLog.id.desc())
            .limit(clamped_limit)
            .offset(clamped_offset)
        )
    ).scalars().all()
    return list(rows), total

