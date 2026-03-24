from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import AuthenticationError, NotFoundError
from financeops.core.security import decrypt_field, verify_totp
from financeops.db.models.users import IamUser
from financeops.modules.digital_signoff.models import DirectorSignoff
from financeops.modules.notifications.service import send_notification


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _content_bytes(document_content: bytes | str) -> bytes:
    if isinstance(document_content, bytes):
        return document_content
    return document_content.encode("utf-8")


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
        signatory_role=signatory_role,
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
    row = (
        await session.execute(
            select(DirectorSignoff).where(
                DirectorSignoff.id == signoff_id,
                DirectorSignoff.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError("Signoff request not found")
    if row.signatory_user_id != signatory_user_id:
        raise AuthenticationError("Only designated signatory can sign")

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
    signature_seed = f"{signatory_user_id}{row.content_hash}{now.isoformat()}".encode("utf-8")
    row.mfa_verified = True
    row.mfa_verified_at = now
    row.signature_hash = _sha256(signature_seed)
    row.status = "signed"
    row.signed_at = now
    row.ip_address = ip_address
    row.user_agent = user_agent
    await session.flush()
    return row


def verify_signoff(content_hash: str, signoff: DirectorSignoff) -> bool:
    if signoff.status != "signed":
        return False
    if content_hash != signoff.content_hash:
        return False
    if len(signoff.signature_hash) != 64:
        return False
    try:
        int(signoff.signature_hash, 16)
    except ValueError:
        return False
    return True


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
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError("Signoff not found")

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
        "is_valid": verify_signoff(row.content_hash, row),
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
    "verify_signoff",
    "generate_certificate",
    "list_signoffs",
]
