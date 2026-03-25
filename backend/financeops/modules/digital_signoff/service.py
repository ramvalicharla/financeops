from __future__ import annotations

import hmac
import hashlib
import uuid
from datetime import UTC, datetime

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import AuthenticationError, NotFoundError, ValidationError
from financeops.core.security import decrypt_field, verify_totp
from financeops.db.models.users import IamUser
from financeops.modules.digital_signoff.models import DirectorSignoff
from financeops.modules.notifications.service import send_notification

VALID_SIGNATORY_ROLES = {
    "Director",
    "CFO",
    "MD",
    "Company Secretary",
    "Finance Leader",
    "CEO",
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _content_bytes(document_content: bytes | str) -> bytes:
    if isinstance(document_content, bytes):
        return document_content
    return document_content.encode("utf-8")


def validate_signatory_role(role: str) -> str:
    normalized = str(role).strip()
    if normalized not in VALID_SIGNATORY_ROLES:
        raise ValueError(
            f"Invalid signatory role: {normalized}. Must be one of {sorted(VALID_SIGNATORY_ROLES)}"
        )
    return normalized


async def initiate_signoff(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    document_type: str,
    document_reference: str,
    period: str,
    signatory_user_id: uuid.UUID,
    signatory_role: str,
    document_content: bytes | str,
    declaration_text: str,
    document_id: uuid.UUID | None = None,
) -> DirectorSignoff:
    user = (
        await session.execute(
            select(IamUser).where(IamUser.id == signatory_user_id, IamUser.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if user is None:
        raise NotFoundError("Signatory not found")

    content_hash = _sha256(_content_bytes(document_content))
    normalized_role = validate_signatory_role(signatory_role)
    signature_seed = f"{signatory_user_id}:{content_hash}:pending".encode("utf-8")
    placeholder_signature = _sha256(signature_seed)

    row = DirectorSignoff(
        tenant_id=tenant_id,
        document_type=document_type,
        document_id=document_id,
        document_reference=document_reference,
        period=period,
        signatory_user_id=signatory_user_id,
        signatory_name=user.full_name,
        signatory_role=normalized_role,
        mfa_verified=False,
        declaration_text=declaration_text,
        content_hash=content_hash,
        signature_hash=placeholder_signature,
        status="pending",
        created_at=datetime.now(UTC),
    )
    session.add(row)
    await session.flush()

    await send_notification(
        session,
        tenant_id=tenant_id,
        recipient_user_id=signatory_user_id,
        notification_type="approval_required",
        title=f"Signoff requested: {document_reference}",
        body="A legally binding signoff is pending your MFA verification.",
        action_url="/signoff",
        metadata={"signoff_id": str(row.id)},
    )
    return row


async def complete_signoff(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    signoff_id: uuid.UUID,
    signatory_user_id: uuid.UUID,
    totp_code: str,
    ip_address: str,
    user_agent: str,
) -> DirectorSignoff:
    pending = (
        await session.execute(
            select(DirectorSignoff).where(
                DirectorSignoff.id == signoff_id,
                DirectorSignoff.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if pending is None:
        raise NotFoundError("Signoff request not found")
    if pending.signatory_user_id != signatory_user_id:
        raise AuthenticationError("Only designated signatory can sign")
    if pending.status != "pending":
        raise ValidationError("Signoff is not in pending state")

    user = (
        await session.execute(
            select(IamUser).where(IamUser.id == signatory_user_id, IamUser.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if user is None or not user.totp_secret_encrypted:
        raise AuthenticationError("MFA is not configured for this user")

    secret = decrypt_field(user.totp_secret_encrypted)
    if not verify_totp(secret, totp_code):
        raise AuthenticationError("Invalid TOTP code")

    now = datetime.now(UTC)
    signature_seed = f"{signatory_user_id}{pending.content_hash}{now.isoformat()}".encode("utf-8")
    signed_row = DirectorSignoff(
        tenant_id=tenant_id,
        document_type=pending.document_type,
        document_id=pending.document_id,
        document_reference=pending.document_reference,
        period=pending.period,
        signatory_user_id=signatory_user_id,
        signatory_name=pending.signatory_name,
        signatory_role=pending.signatory_role,
        mfa_verified=True,
        mfa_verified_at=now,
        ip_address=ip_address,
        user_agent=user_agent,
        declaration_text=pending.declaration_text,
        content_hash=pending.content_hash,
        signature_hash=_sha256(signature_seed),
        status="signed",
        signed_at=now,
        created_at=now,
    )
    session.add(signed_row)
    await session.flush()
    return signed_row


def verify_signoff(
    content_hash: str,
    signatory_user_id: uuid.UUID | str,
    signed_at: datetime | None,
    signoff: DirectorSignoff,
) -> bool:
    if signoff.status != "signed":
        return False
    if signed_at is None or signoff.signed_at is None:
        return False
    if content_hash != signoff.content_hash or signed_at != signoff.signed_at:
        return False
    if str(signatory_user_id) != str(signoff.signatory_user_id):
        return False
    if len(signoff.signature_hash) != 64:
        return False
    expected = _sha256(f"{signatory_user_id}{content_hash}{signed_at.isoformat()}".encode("utf-8"))
    return hmac.compare_digest(expected, signoff.signature_hash)


async def generate_certificate(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    signoff_id: uuid.UUID,
) -> dict:
    row = (
        await session.execute(
            select(DirectorSignoff).where(
                DirectorSignoff.id == signoff_id,
                DirectorSignoff.tenant_id == tenant_id,
                DirectorSignoff.status == "signed",
            )
        )
    ).scalar_one_or_none()
    if row is None:
        pending = (
            await session.execute(
                select(DirectorSignoff).where(
                    DirectorSignoff.id == signoff_id,
                    DirectorSignoff.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if pending is not None:
            row = (
                await session.execute(
                    select(DirectorSignoff)
                    .where(
                        DirectorSignoff.tenant_id == tenant_id,
                        DirectorSignoff.status == "signed",
                        DirectorSignoff.document_reference == pending.document_reference,
                        DirectorSignoff.period == pending.period,
                        DirectorSignoff.signatory_user_id == pending.signatory_user_id,
                    )
                    .order_by(desc(DirectorSignoff.created_at), desc(DirectorSignoff.id))
                    .limit(1)
                )
            ).scalar_one_or_none()
    if row is None:
        raise NotFoundError("Signed signoff not found")

    certificate_number = f"SIG-{row.created_at.year}-{str(row.id)[:8].upper()}"
    return {
        "certificate_number": certificate_number,
        "document_reference": row.document_reference,
        "period": row.period,
        "signatory_name": row.signatory_name,
        "signatory_role": row.signatory_role,
        "signed_at": row.signed_at,
        "content_hash": row.content_hash,
        "signature_hash": row.signature_hash,
        "is_valid": verify_signoff(row.content_hash, row.signatory_user_id, row.signed_at, row),
        "declaration_text": row.declaration_text,
    }


async def list_signoffs(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    rows = (
        await session.execute(
            select(DirectorSignoff)
            .where(DirectorSignoff.tenant_id == tenant_id)
            .order_by(desc(DirectorSignoff.created_at), desc(DirectorSignoff.id))
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    total = int(
        (
            await session.execute(
                select(func.count())
                .select_from(DirectorSignoff)
                .where(DirectorSignoff.tenant_id == tenant_id)
            )
        ).scalar_one()
    )
    return {"data": rows, "total": total, "limit": limit, "offset": offset}


__all__ = [
    "initiate_signoff",
    "complete_signoff",
    "validate_signatory_role",
    "verify_signoff",
    "generate_certificate",
    "list_signoffs",
]
