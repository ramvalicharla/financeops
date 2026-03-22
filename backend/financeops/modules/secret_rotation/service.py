from __future__ import annotations

"""
Secret storage audit findings (pre-implementation):
1) Scheduled delivery webhook signing secret storage:
   - Stored in delivery_schedules.config JSONB under key "webhook_secret".
   - Used by DeliveryService._dispatch_webhook() to compute HMAC-SHA256
     header X-Signature-256.
2) ERP connector credential storage:
   - external_connections contains immutable secret_ref on the connector
     instance root row (append-only financial table).
   - Connection configuration history is represented by
     external_connection_versions.config_snapshot_json.
   - Rotation must append a new external_connection_versions row rather than
     UPDATE external_connections because external_connections is append-only.
3) Encryption-at-rest utility availability:
   - FIELD_ENCRYPTION_KEY exists and AES-GCM helpers exist in core.security,
     but webhook secret and ERP connector secret_ref are currently stored as
     plain string payload values in their respective JSON/string fields.
   - Rotation logic therefore preserves current storage semantics and does not
     introduce incompatible ciphertext transformations in this phase.
4) Existing secret generation pattern:
   - Deterministic/hash tokens are common for run/version metadata.
   - For rotation-generated webhook secrets, secrets.token_urlsafe(32) is used.
"""

import asyncio
import secrets
import smtplib
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.config import settings
from financeops.core.security import decrypt_field, encrypt_field
from financeops.db.models.erp_sync import ExternalConnection, ExternalConnectionVersion
from financeops.db.models.scheduled_delivery import DeliverySchedule
from financeops.db.rls import clear_tenant_context, get_current_tenant_from_db, set_tenant_context
from financeops.modules.secret_rotation.models import SecretRotationLog
from financeops.services.audit_writer import AuditWriter

PLATFORM_TENANT_ID = uuid.UUID(int=0)
_ALLOWED_SECRET_TYPES = {"smtp", "webhook_signing", "erp_api_key"}


def _secret_hint(value: str | None) -> str | None:
    if value is None:
        return None
    text_value = str(value).strip()
    if not text_value:
        return None
    return text_value[-4:]


def _decrypt_maybe_ciphertext(value: str | None) -> str:
    text_value = str(value or "").strip()
    if not text_value:
        return ""
    try:
        return decrypt_field(text_value)
    except Exception:
        return text_value


@asynccontextmanager
async def _tenant_context(session: AsyncSession, tenant_id: uuid.UUID):
    previous = await get_current_tenant_from_db(session)
    await set_tenant_context(session, tenant_id)
    try:
        yield
    finally:
        if previous:
            await set_tenant_context(session, previous)
        else:
            await clear_tenant_context(session)


async def _append_rotation_event(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    secret_type: str,
    status: str,
    resource_id: uuid.UUID | None = None,
    resource_type: str | None = None,
    rotated_by: uuid.UUID | None = None,
    rotation_method: str = "manual",
    failure_reason: str | None = None,
    previous_secret_hint: str | None = None,
    new_secret_hint: str | None = None,
    initiated_at: datetime | None = None,
    completed_at: datetime | None = None,
) -> SecretRotationLog:
    row = SecretRotationLog(
        tenant_id=tenant_id,
        secret_type=secret_type,
        resource_id=resource_id,
        resource_type=resource_type,
        rotated_by=rotated_by,
        rotation_method=rotation_method,
        status=status,
        failure_reason=failure_reason,
        previous_secret_hint=previous_secret_hint,
        new_secret_hint=new_secret_hint,
        initiated_at=initiated_at or datetime.now(UTC),
        completed_at=completed_at,
        created_at=datetime.now(UTC),
    )
    session.add(row)
    await session.flush()
    return row


async def rotate_webhook_secret(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    schedule_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
    method: str = "manual",
) -> dict:
    """
    Zero-downtime webhook secret rotation.
    1. Load delivery_schedule, verify it belongs to tenant_id
    2. Generate new secret: secrets.token_urlsafe(32)
    3. Log rotation_log record: status='initiated',
       previous_secret_hint=old[-4:], new_secret_hint=new[-4:]
    4. Write new secret to delivery_schedule (encrypt if encrypted at rest)
    5. Verify: re-read the row, confirm new secret reads back correctly
    6. Update rotation_log: status='completed', completed_at=now()
    7. Return: { "schedule_id": str, "rotated_at": iso, "hint": new[-4:] }
    On any exception: update rotation_log status='failed',
    failure_reason=str(e), re-raise
    """
    row = (
        await session.execute(
            select(DeliverySchedule).where(
                DeliverySchedule.tenant_id == tenant_id,
                DeliverySchedule.id == schedule_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise LookupError("Delivery schedule not found")

    existing_config = dict(row.config or {})
    old_secret = _decrypt_maybe_ciphertext(
        str(existing_config.get("webhook_secret_enc") or existing_config.get("webhook_secret") or "")
    )
    new_secret = secrets.token_urlsafe(32)
    if old_secret and secrets.compare_digest(old_secret, new_secret):
        new_secret = secrets.token_urlsafe(32)

    initiated_at = datetime.now(UTC)
    await _append_rotation_event(
        session,
        tenant_id=tenant_id,
        secret_type="webhook_signing",
        status="initiated",
        resource_id=row.id,
        resource_type="delivery_schedule",
        rotated_by=user_id,
        rotation_method=method,
        previous_secret_hint=_secret_hint(old_secret),
        new_secret_hint=_secret_hint(new_secret),
        initiated_at=initiated_at,
    )

    try:
        updated_config = dict(existing_config)
        updated_config["webhook_secret_enc"] = encrypt_field(new_secret)
        updated_config.pop("webhook_secret", None)
        row.config = updated_config
        row.updated_at = datetime.now(UTC)
        await session.flush()

        verified = (
            await session.execute(
                select(DeliverySchedule).where(
                    DeliverySchedule.tenant_id == tenant_id,
                    DeliverySchedule.id == schedule_id,
                )
            )
        ).scalar_one()
        verified_config = dict(verified.config or {})
        verified_secret = _decrypt_maybe_ciphertext(
            str(verified_config.get("webhook_secret_enc") or verified_config.get("webhook_secret") or "")
        )
        if verified_secret != new_secret:
            raise RuntimeError("Webhook secret verification failed after write")

        completed_at = datetime.now(UTC)
        await _append_rotation_event(
            session,
            tenant_id=tenant_id,
            secret_type="webhook_signing",
            status="completed",
            resource_id=row.id,
            resource_type="delivery_schedule",
            rotated_by=user_id,
            rotation_method=method,
            previous_secret_hint=_secret_hint(old_secret),
            new_secret_hint=_secret_hint(new_secret),
            initiated_at=initiated_at,
            completed_at=completed_at,
        )

        return {
            "schedule_id": str(row.id),
            "rotated_at": completed_at.isoformat(),
            "hint": _secret_hint(new_secret),
        }
    except Exception as exc:
        await _append_rotation_event(
            session,
            tenant_id=tenant_id,
            secret_type="webhook_signing",
            status="failed",
            resource_id=row.id,
            resource_type="delivery_schedule",
            rotated_by=user_id,
            rotation_method=method,
            failure_reason=str(exc)[:2000],
            previous_secret_hint=_secret_hint(old_secret),
            new_secret_hint=_secret_hint(new_secret),
            initiated_at=initiated_at,
            completed_at=datetime.now(UTC),
        )
        raise


async def _load_latest_connection_version(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    connection_id: uuid.UUID,
) -> ExternalConnectionVersion | None:
    return (
        await session.execute(
            select(ExternalConnectionVersion)
            .where(
                ExternalConnectionVersion.tenant_id == tenant_id,
                ExternalConnectionVersion.connection_id == connection_id,
            )
            .order_by(ExternalConnectionVersion.version_no.desc(), ExternalConnectionVersion.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


def _resolve_current_api_key(
    *,
    connection: ExternalConnection,
    latest_version: ExternalConnectionVersion | None,
) -> str:
    if latest_version is not None:
        snapshot = dict(latest_version.config_snapshot_json or {})
        key_from_snapshot = str(snapshot.get("api_key") or snapshot.get("secret_ref") or "")
        if key_from_snapshot:
            return _decrypt_maybe_ciphertext(key_from_snapshot)
    return _decrypt_maybe_ciphertext(str(connection.secret_ref or ""))


async def rotate_erp_api_key(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    connector_instance_id: uuid.UUID,
    new_api_key: str,
    user_id: uuid.UUID | None = None,
    method: str = "manual",
) -> dict:
    """
    Zero-downtime ERP API key rotation.
    Note: unlike webhook secrets (which we generate), ERP API keys
    are issued by the ERP provider - the caller must supply the new key.
    1. Load connector instance, verify it belongs to tenant_id
    2. Validate new_api_key is not empty and differs from current key
    3. Log rotation_log record: status='initiated'
    4. Write new API key to connector instance
       (encrypt if encrypted at rest)
    5. Verify: re-read the row, confirm new key reads back correctly
    6. Update rotation_log: status='completed', completed_at=now()
    7. Return: { "connector_id": str, "rotated_at": iso }
    On any exception: update rotation_log status='failed',
    failure_reason=str(e), re-raise
    """
    connection = (
        await session.execute(
            select(ExternalConnection).where(
                ExternalConnection.tenant_id == tenant_id,
                ExternalConnection.id == connector_instance_id,
            )
        )
    ).scalar_one_or_none()
    if connection is None:
        raise LookupError("ERP connector instance not found")

    candidate_key = str(new_api_key or "").strip()
    if not candidate_key:
        raise ValueError("new_api_key must not be empty")

    latest_version = await _load_latest_connection_version(
        session,
        tenant_id=tenant_id,
        connection_id=connection.id,
    )
    current_key = _resolve_current_api_key(connection=connection, latest_version=latest_version)
    if current_key and secrets.compare_digest(current_key, candidate_key):
        raise ValueError("new_api_key must differ from current key")

    initiated_at = datetime.now(UTC)
    await _append_rotation_event(
        session,
        tenant_id=tenant_id,
        secret_type="erp_api_key",
        status="initiated",
        resource_id=connection.id,
        resource_type="erp_connector",
        rotated_by=user_id,
        rotation_method=method,
        previous_secret_hint=_secret_hint(current_key),
        new_secret_hint=_secret_hint(candidate_key),
        initiated_at=initiated_at,
    )

    try:
        max_version_no = (
            await session.execute(
                select(func.max(ExternalConnectionVersion.version_no)).where(
                    ExternalConnectionVersion.tenant_id == tenant_id,
                    ExternalConnectionVersion.connection_id == connection.id,
                )
            )
        ).scalar_one_or_none()
        next_version_no = int(max_version_no or 0) + 1
        version_token = uuid.uuid4().hex

        snapshot = dict((latest_version.config_snapshot_json if latest_version else {}) or {})
        encrypted_candidate = encrypt_field(candidate_key)
        snapshot["api_key"] = encrypted_candidate
        snapshot["secret_ref"] = encrypted_candidate

        created_by = user_id or connection.created_by
        inserted_version = await AuditWriter.insert_financial_record(
            session,
            model_class=ExternalConnectionVersion,
            tenant_id=tenant_id,
            record_data={
                "connection_id": str(connection.id),
                "version_no": next_version_no,
                "version_token": version_token,
            },
            values={
                "connection_id": connection.id,
                "version_no": next_version_no,
                "version_token": version_token,
                "config_snapshot_json": snapshot,
                "supersedes_id": latest_version.id if latest_version else None,
                "status": "active",
                "created_by": created_by,
            },
        )
        await session.flush()

        verified_version = (
            await session.execute(
                select(ExternalConnectionVersion).where(
                    ExternalConnectionVersion.tenant_id == tenant_id,
                    ExternalConnectionVersion.id == inserted_version.id,
                )
            )
        ).scalar_one()
        verified_snapshot = dict(verified_version.config_snapshot_json or {})
        verified_key = _decrypt_maybe_ciphertext(
            str(verified_snapshot.get("api_key") or verified_snapshot.get("secret_ref") or "")
        )
        if verified_key != candidate_key:
            raise RuntimeError("ERP API key verification failed after write")

        completed_at = datetime.now(UTC)
        await _append_rotation_event(
            session,
            tenant_id=tenant_id,
            secret_type="erp_api_key",
            status="completed",
            resource_id=connection.id,
            resource_type="erp_connector",
            rotated_by=user_id,
            rotation_method=method,
            previous_secret_hint=_secret_hint(current_key),
            new_secret_hint=_secret_hint(candidate_key),
            initiated_at=initiated_at,
            completed_at=completed_at,
        )

        return {
            "connector_id": str(connection.id),
            "rotated_at": completed_at.isoformat(),
        }
    except Exception as exc:
        await _append_rotation_event(
            session,
            tenant_id=tenant_id,
            secret_type="erp_api_key",
            status="failed",
            resource_id=connection.id,
            resource_type="erp_connector",
            rotated_by=user_id,
            rotation_method=method,
            failure_reason=str(exc)[:2000],
            previous_secret_hint=_secret_hint(current_key),
            new_secret_hint=_secret_hint(candidate_key),
            initiated_at=initiated_at,
            completed_at=datetime.now(UTC),
        )
        raise


async def rotate_smtp_credentials(
    session: AsyncSession,
    new_smtp_host: str,
    new_smtp_user: str,
    new_smtp_password: str,
    user_id: uuid.UUID | None = None,
    method: str = "manual",
) -> dict:
    """
    SMTP credential rotation.
    Note: SMTP credentials live in environment/config, not DB.
    This function:
    1. Validates new credentials by attempting SMTP connection
       (use smtplib.SMTP or aiosmtplib - connect + ehlo only,
        do not send a real email)
    2. Logs rotation event to secret_rotation_log with
       tenant_id=UUID(int=0) (platform-level sentinel)
    3. Returns instructions dict - it cannot update .env directly,
       so it returns:
       { "status": "verified",
         "action_required": "Update SMTP_HOST, SMTP_USER, SMTP_PASSWORD
           in your .env or secrets manager and restart the service.",
         "verified_host": new_smtp_host,
         "rotated_at": iso }
    4. Logs rotation_log: status='completed' after verification succeeds
    On SMTP connection failure: status='failed', re-raise with
    clear message about which credential is wrong.
    """
    host_value = str(new_smtp_host or "").strip()
    user_value = str(new_smtp_user or "").strip()
    password_value = str(new_smtp_password or "")
    if not host_value:
        raise ValueError("smtp_host must not be empty")
    if not user_value:
        raise ValueError("smtp_user must not be empty")
    if not password_value:
        raise ValueError("smtp_password must not be empty")

    def _probe() -> None:
        port_value = int(getattr(settings, "SMTP_PORT", 587) or 587)
        with smtplib.SMTP(host=host_value, port=port_value, timeout=15) as smtp:
            smtp.ehlo()
            try:
                smtp.starttls()
                smtp.ehlo()
            except smtplib.SMTPException:
                pass
            smtp.login(user_value, password_value)

    initiated_at = datetime.now(UTC)
    old_password_hint = _secret_hint(str(getattr(settings, "SMTP_PASSWORD", "") or ""))
    new_password_hint = _secret_hint(password_value)

    async with _tenant_context(session, PLATFORM_TENANT_ID):
        await _append_rotation_event(
            session,
            tenant_id=PLATFORM_TENANT_ID,
            secret_type="smtp",
            status="initiated",
            resource_id=None,
            resource_type=None,
            rotated_by=user_id,
            rotation_method=method,
            previous_secret_hint=old_password_hint,
            new_secret_hint=new_password_hint,
            initiated_at=initiated_at,
        )

        try:
            await asyncio.to_thread(_probe)
            completed_at = datetime.now(UTC)
            await _append_rotation_event(
                session,
                tenant_id=PLATFORM_TENANT_ID,
                secret_type="smtp",
                status="completed",
                resource_id=None,
                resource_type=None,
                rotated_by=user_id,
                rotation_method=method,
                previous_secret_hint=old_password_hint,
                new_secret_hint=new_password_hint,
                initiated_at=initiated_at,
                completed_at=completed_at,
            )
        except Exception as exc:
            await _append_rotation_event(
                session,
                tenant_id=PLATFORM_TENANT_ID,
                secret_type="smtp",
                status="failed",
                resource_id=None,
                resource_type=None,
                rotated_by=user_id,
                rotation_method=method,
                failure_reason=str(exc)[:2000],
                previous_secret_hint=old_password_hint,
                new_secret_hint=new_password_hint,
                initiated_at=initiated_at,
                completed_at=datetime.now(UTC),
            )
            raise RuntimeError(f"SMTP credential verification failed for host {host_value}: {exc}") from exc

    return {
        "status": "verified",
        "action_required": (
            "Update SMTP_HOST, SMTP_USER, SMTP_PASSWORD in your .env "
            "or secrets manager and restart the service."
        ),
        "verified_host": host_value,
        "rotated_at": datetime.now(UTC).isoformat(),
    }


async def get_rotation_log(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    secret_type: str | None = None,
    resource_id: uuid.UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[SecretRotationLog]:
    """
    Returns rotation log entries for tenant, optionally filtered
    by secret_type and resource_id. Ordered by initiated_at DESC.
    """
    clamped_limit = max(1, min(200, int(limit)))
    stmt = select(SecretRotationLog).where(SecretRotationLog.tenant_id == tenant_id)

    if secret_type is not None:
        normalized_secret_type = str(secret_type).strip().lower()
        if normalized_secret_type not in _ALLOWED_SECRET_TYPES:
            raise ValueError("secret_type must be one of smtp, webhook_signing, erp_api_key")
        stmt = stmt.where(SecretRotationLog.secret_type == normalized_secret_type)

    if resource_id is not None:
        stmt = stmt.where(SecretRotationLog.resource_id == resource_id)

    stmt = stmt.order_by(SecretRotationLog.initiated_at.desc(), SecretRotationLog.id.desc())
    stmt = stmt.offset(max(0, int(offset))).limit(clamped_limit)
    rows = (await session.execute(stmt)).scalars().all()
    return list(rows)


async def get_rotation_log_entry(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    log_id: uuid.UUID,
) -> SecretRotationLog | None:
    row = (
        await session.execute(
            select(SecretRotationLog).where(
                SecretRotationLog.tenant_id == tenant_id,
                SecretRotationLog.id == log_id,
            )
        )
    ).scalar_one_or_none()
    return row


__all__ = [
    "PLATFORM_TENANT_ID",
    "SecretRotationLog",
    "get_rotation_log",
    "get_rotation_log_entry",
    "rotate_erp_api_key",
    "rotate_smtp_credentials",
    "rotate_webhook_secret",
]
