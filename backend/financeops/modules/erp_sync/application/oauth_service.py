from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from base64 import urlsafe_b64encode
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import AuthenticationError, AuthorizationError, NotFoundError, ValidationError
from financeops.core.security import decrypt_field, encrypt_field
from financeops.db.models.erp_sync import ErpOAuthSession, ExternalConnection, ExternalConnectionVersion
from financeops.modules.erp_sync.application.connection_service import (
    get_latest_connection_version,
    merge_connection_runtime_snapshot,
)
from financeops.modules.erp_sync.infrastructure.secret_store import secret_store
from financeops.services.audit_writer import AuditWriter
from financeops.services.network_runtime import post_form_request

SESSION_TTL_MINUTES = 15

_PROVIDER_BY_CONNECTOR: dict[str, str] = {
    "zoho": "ZOHO",
    "quickbooks": "QBO",
}

OAUTH_CONFIG: dict[str, dict[str, str]] = {
    "ZOHO": {
        "auth_url": "https://accounts.zoho.in/oauth/v2/auth",
        "token_url": "https://accounts.zoho.in/oauth/v2/token",
        "default_scopes": (
            "ZohoBooks.fullaccess.all,ZohoBooks.contacts.READ,"
            "ZohoBooks.invoices.READ,ZohoBooks.expenses.READ"
        ),
    },
    "QBO": {
        "auth_url": "https://appcenter.intuit.com/connect/oauth2",
        "token_url": "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer",
        "default_scopes": "com.intuit.quickbooks.accounting",
    },
}


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _generate_pkce_pair() -> tuple[str, str]:
    verifier = urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


def _resolve_provider(connector_type: str) -> str:
    provider = _PROVIDER_BY_CONNECTOR.get(str(connector_type or "").strip().lower())
    if provider is None:
        raise ValidationError(
            f"connector_type '{connector_type}' does not support OAuth"
        )
    return provider


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    text_value = str(value).strip()
    if not text_value:
        return None
    try:
        parsed = datetime.fromisoformat(text_value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


async def _get_connection(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    connection_id: uuid.UUID,
) -> ExternalConnection:
    connection = (
        await session.execute(
            select(ExternalConnection).where(
                ExternalConnection.tenant_id == tenant_id,
                ExternalConnection.id == connection_id,
            )
        )
    ).scalar_one_or_none()
    if connection is None:
        raise NotFoundError("Connection not found")
    return connection


async def _latest_connection_version(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    connection_id: uuid.UUID,
) -> ExternalConnectionVersion | None:
    return await get_latest_connection_version(
        session,
        tenant_id=tenant_id,
        connection_id=connection_id,
    )


async def _resolve_active_secret_ref(
    session: AsyncSession,
    *,
    connection: ExternalConnection,
) -> tuple[str | None, ExternalConnectionVersion | None]:
    latest_version = await _latest_connection_version(
        session,
        tenant_id=connection.tenant_id,
        connection_id=connection.id,
    )
    snapshot = merge_connection_runtime_snapshot(connection, latest_version)
    resolved = str(
        snapshot.get("oauth_secret_ref")
        or snapshot.get("secret_ref")
        or connection.secret_ref
        or ""
    ).strip()
    return (resolved or None), latest_version


async def _resolve_credentials(
    session: AsyncSession,
    *,
    connection: ExternalConnection,
) -> tuple[dict[str, Any], str | None, ExternalConnectionVersion | None]:
    active_secret_ref, latest_version = await _resolve_active_secret_ref(
        session,
        connection=connection,
    )
    if not active_secret_ref:
        return {}, None, latest_version
    payload = await secret_store.get_secret(active_secret_ref)
    return payload, active_secret_ref, latest_version


async def _append_connection_secret_version(
    session: AsyncSession,
    *,
    connection: ExternalConnection,
    actor_user_id: uuid.UUID | None,
    secret_ref: str,
    scopes: str | None,
    token_expires_at: datetime | None,
) -> ExternalConnectionVersion:
    latest_version = await _latest_connection_version(
        session,
        tenant_id=connection.tenant_id,
        connection_id=connection.id,
    )
    max_version_no = (
        await session.execute(
            select(func.max(ExternalConnectionVersion.version_no)).where(
                ExternalConnectionVersion.tenant_id == connection.tenant_id,
                ExternalConnectionVersion.connection_id == connection.id,
            )
        )
    ).scalar_one_or_none()
    next_version_no = int(max_version_no or 0) + 1
    version_token = uuid.uuid4().hex

    snapshot = merge_connection_runtime_snapshot(connection, latest_version)
    snapshot["oauth_secret_ref"] = secret_ref
    snapshot["secret_ref"] = secret_ref
    if scopes is not None:
        snapshot["oauth_scopes"] = scopes
    if token_expires_at is not None:
        snapshot["token_expires_at"] = token_expires_at.isoformat()
        snapshot["token_refreshed_at"] = _utcnow().isoformat()

    return await AuditWriter.insert_financial_record(
        session,
        model_class=ExternalConnectionVersion,
        tenant_id=connection.tenant_id,
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
            "created_by": actor_user_id or connection.created_by,
        },
    )


async def _expire_pending_sessions(session: AsyncSession, *, connection_id: uuid.UUID) -> None:
    await session.execute(
        update(ErpOAuthSession)
        .where(
            ErpOAuthSession.connection_id == connection_id,
            ErpOAuthSession.status == "PENDING",
        )
        .values(status="EXPIRED", consumed_at=_utcnow())
    )


async def start_oauth_session(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    connection_id: uuid.UUID,
    entity_id: uuid.UUID | None,
    redirect_uri: str,
    initiated_by_user_id: uuid.UUID | None,
    scopes: str | None = None,
) -> dict[str, str]:
    connection = await _get_connection(
        session,
        tenant_id=tenant_id,
        connection_id=connection_id,
    )
    provider = _resolve_provider(connection.connector_type)
    config = OAUTH_CONFIG[provider]

    credentials, _, _ = await _resolve_credentials(session, connection=connection)
    client_id = str(credentials.get("client_id") or "").strip()
    if not client_id:
        raise ValidationError("client_id missing in connection credentials")

    requested_scopes = scopes or config["default_scopes"]
    code_verifier, code_challenge = _generate_pkce_pair()
    state_token = secrets.token_urlsafe(48)
    expires_at = _utcnow() + timedelta(minutes=SESSION_TTL_MINUTES)

    await _expire_pending_sessions(session, connection_id=connection_id)

    oauth_session = ErpOAuthSession(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        entity_id=entity_id,
        connection_id=connection_id,
        provider=provider,
        state_token=state_token,
        code_verifier_enc=encrypt_field(code_verifier),
        redirect_uri=redirect_uri,
        scopes=requested_scopes,
        status="PENDING",
        expires_at=expires_at,
        consumed_at=None,
        initiated_by_user_id=initiated_by_user_id,
        encrypted_tokens=None,
        token_expires_at=None,
    )
    session.add(oauth_session)
    await session.flush()

    query_params: dict[str, str] = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": requested_scopes,
        "state": state_token,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    if provider == "ZOHO":
        query_params["access_type"] = "offline"

    authorization_url = f"{config['auth_url']}?{urlencode(query_params)}"
    return {
        "authorization_url": authorization_url,
        "state_token": state_token,
        "expires_at": expires_at.isoformat(),
    }


async def consume_oauth_callback(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    connection_id: uuid.UUID,
    state_token: str,
    code: str,
    initiated_by_user_id: uuid.UUID | None,
    realm_id: str | None = None,
    organization_id: str | None = None,
) -> dict[str, Any]:
    oauth_session = (
        await session.execute(
            select(ErpOAuthSession).where(
                ErpOAuthSession.state_token == state_token,
                ErpOAuthSession.connection_id == connection_id,
            )
        )
    ).scalar_one_or_none()
    if oauth_session is None:
        raise NotFoundError("OAuth session not found")

    if oauth_session.tenant_id != tenant_id:
        raise AuthorizationError("OAuth callback tenant mismatch")

    if oauth_session.status != "PENDING":
        raise AuthorizationError(f"OAuth session already {oauth_session.status}")

    now = _utcnow()
    if now >= oauth_session.expires_at:
        oauth_session.status = "EXPIRED"
        oauth_session.consumed_at = now
        await session.flush()
        raise AuthenticationError("OAuth session expired")

    oauth_session.status = "CONSUMED"
    oauth_session.consumed_at = now
    await session.flush()

    connection = await _get_connection(
        session,
        tenant_id=tenant_id,
        connection_id=connection_id,
    )
    provider = _resolve_provider(connection.connector_type)
    config = OAUTH_CONFIG[provider]

    credentials, active_secret_ref, _ = await _resolve_credentials(session, connection=connection)
    client_id = str(credentials.get("client_id") or "").strip()
    client_secret = str(credentials.get("client_secret") or "").strip()
    if not client_id or not client_secret:
        raise ValidationError("client_id/client_secret missing in connection credentials")

    code_verifier = decrypt_field(oauth_session.code_verifier_enc)
    token_payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": oauth_session.redirect_uri,
        "code_verifier": code_verifier,
        "client_id": client_id,
        "client_secret": client_secret,
    }

    response = await post_form_request(
        url=str(config["token_url"]),
        data=token_payload,
        timeout=30.0,
    )

    if response.status_code != 200:
        raise ValidationError(
            f"Token exchange failed: HTTP {response.status_code}"
        )

    token_data = response.json()
    refresh_token = token_data.get("refresh_token") or credentials.get("refresh_token")
    access_token = token_data.get("access_token")
    expires_in = int(token_data.get("expires_in") or 3600)
    token_expires_at = now + timedelta(seconds=expires_in)

    if not access_token:
        raise ValidationError("Token exchange response missing access_token")

    new_secret_ref = await secret_store.put_secret(
        active_secret_ref,
        {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_expires_at": token_expires_at.isoformat(),
            "realm_id": realm_id or credentials.get("realm_id"),
            "organization_id": (
                token_data.get("organization_id")
                or organization_id
                or credentials.get("organization_id")
            ),
            "use_sandbox": credentials.get("use_sandbox"),
        },
    )
    await _append_connection_secret_version(
        session,
        connection=connection,
        actor_user_id=initiated_by_user_id,
        secret_ref=new_secret_ref,
        scopes=oauth_session.scopes,
        token_expires_at=token_expires_at,
    )

    oauth_session.encrypted_tokens = encrypt_field(json.dumps(token_data))
    oauth_session.token_expires_at = token_expires_at
    await session.flush()

    return {
        "connection_id": str(connection.id),
        "provider": provider,
        "token_expires_at": token_expires_at.isoformat(),
        "scopes": oauth_session.scopes,
        "status": "connected",
    }


async def refresh_connection_token(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    connection_id: uuid.UUID,
    initiated_by_user_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    connection = await _get_connection(
        session,
        tenant_id=tenant_id,
        connection_id=connection_id,
    )
    provider = _resolve_provider(connection.connector_type)
    config = OAUTH_CONFIG[provider]

    credentials, active_secret_ref, _ = await _resolve_credentials(session, connection=connection)
    client_id = str(credentials.get("client_id") or "").strip()
    client_secret = str(credentials.get("client_secret") or "").strip()
    refresh_token = str(credentials.get("refresh_token") or "").strip()

    if not client_id or not client_secret:
        raise ValidationError("client_id/client_secret missing in connection credentials")
    if not refresh_token:
        raise AuthenticationError("refresh_token missing in connection credentials")

    refresh_payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
        "client_secret": client_secret,
    }

    response = await post_form_request(
        url=str(config["token_url"]),
        data=refresh_payload,
        timeout=30.0,
    )

    if response.status_code != 200:
        raise AuthenticationError(f"Token refresh failed: HTTP {response.status_code}")

    token_data = response.json()
    access_token = token_data.get("access_token")
    if not access_token:
        raise ValidationError("Token refresh response missing access_token")

    new_refresh = token_data.get("refresh_token") or refresh_token
    expires_in = int(token_data.get("expires_in") or 3600)
    token_expires_at = _utcnow() + timedelta(seconds=expires_in)

    new_secret_ref = await secret_store.put_secret(
        active_secret_ref,
        {
            "access_token": access_token,
            "refresh_token": new_refresh,
            "token_expires_at": token_expires_at.isoformat(),
            "realm_id": credentials.get("realm_id"),
            "organization_id": credentials.get("organization_id"),
            "use_sandbox": credentials.get("use_sandbox"),
        },
    )
    await _append_connection_secret_version(
        session,
        connection=connection,
        actor_user_id=initiated_by_user_id,
        secret_ref=new_secret_ref,
        scopes=str(credentials.get("oauth_scopes") or "").strip() or None,
        token_expires_at=token_expires_at,
    )
    await session.flush()

    return {
        "connection_id": str(connection_id),
        "token_expires_at": token_expires_at.isoformat(),
        "status": "refreshed",
    }


async def get_decrypted_access_token(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    connection_id: uuid.UUID,
    auto_refresh: bool = True,
) -> str:
    connection = await _get_connection(
        session,
        tenant_id=tenant_id,
        connection_id=connection_id,
    )
    credentials, _, _ = await _resolve_credentials(session, connection=connection)

    access_token = str(credentials.get("access_token") or "").strip()
    token_expires_at = _parse_datetime(credentials.get("token_expires_at"))

    if auto_refresh and token_expires_at is not None:
        if _utcnow() >= (token_expires_at - timedelta(minutes=5)):
            await refresh_connection_token(
                session,
                tenant_id=tenant_id,
                connection_id=connection_id,
            )
            credentials, _, _ = await _resolve_credentials(session, connection=connection)
            access_token = str(credentials.get("access_token") or "").strip()

    if not access_token:
        raise AuthenticationError("OAuth access_token unavailable")

    return access_token
