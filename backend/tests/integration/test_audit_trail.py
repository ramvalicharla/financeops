from __future__ import annotations

import uuid

import pytest
from fastapi import Request, Response
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.security import create_access_token
from financeops.db.models.audit import AuditTrail
from financeops.db.models.users import IamUser
from financeops.db.rls import set_tenant_context
from financeops.middleware.audit_middleware import AuditMiddleware
from financeops.services.audit_service import log_action, verify_tenant_chain


@pytest.mark.asyncio
@pytest.mark.integration
async def test_audit_chain_hash_tamper_detection(async_session: AsyncSession) -> None:
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()

    await set_tenant_context(async_session, tenant_id)
    await log_action(
        async_session,
        tenant_id=tenant_id,
        user_id=user_id,
        action="http.post",
        resource_type="audit",
        resource_id="row-1",
        resource_name="/api/v1/audit/row-1",
        ip_address="127.0.0.1",
    )
    await log_action(
        async_session,
        tenant_id=tenant_id,
        user_id=user_id,
        action="http.post",
        resource_type="audit",
        resource_id="row-2",
        resource_name="/api/v1/audit/row-2",
        ip_address="127.0.0.1",
    )

    first_row = (
        await async_session.execute(
            select(AuditTrail)
            .where(AuditTrail.tenant_id == tenant_id)
            .order_by(AuditTrail.created_at.asc(), AuditTrail.id.asc())
            .limit(1)
        )
    ).scalar_one()

    await async_session.execute(text("ALTER TABLE audit_trail DISABLE TRIGGER ALL"))
    try:
        await async_session.execute(
            text("UPDATE audit_trail SET chain_hash = :tampered_hash WHERE id = :row_id"),
            {
                "tampered_hash": "deadbeef" * 8,
                "row_id": first_row.id,
            },
        )
    finally:
        await async_session.execute(text("ALTER TABLE audit_trail ENABLE TRIGGER ALL"))

    async_session.expire_all()
    verification = await verify_tenant_chain(async_session, tenant_id)

    assert verification.is_valid is False
    assert verification.total_records == 2
    assert verification.first_broken_at == 1


@pytest.mark.asyncio
@pytest.mark.integration
async def test_audit_trail_rls_tenant_isolation(async_session: AsyncSession) -> None:
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()

    await set_tenant_context(async_session, tenant_a)
    await log_action(
        async_session,
        tenant_id=tenant_a,
        user_id=None,
        action="http.post",
        resource_type="audit",
        resource_id="tenant-a",
        resource_name="tenant-a-row",
        ip_address="127.0.0.1",
    )

    await set_tenant_context(async_session, tenant_b)
    await log_action(
        async_session,
        tenant_id=tenant_b,
        user_id=None,
        action="http.post",
        resource_type="audit",
        resource_id="tenant-b",
        resource_name="tenant-b-row",
        ip_address="127.0.0.1",
    )

    await async_session.execute(
        text(
            """
            DO $$
            BEGIN
              CREATE ROLE rls_audit_probe_user NOLOGIN NOSUPERUSER NOBYPASSRLS;
            EXCEPTION
              WHEN duplicate_object THEN NULL;
            END $$;
            """
        )
    )
    await async_session.execute(text("GRANT USAGE ON SCHEMA public TO rls_audit_probe_user"))
    await async_session.execute(text("GRANT SELECT ON audit_trail TO rls_audit_probe_user"))
    await async_session.execute(text("SET ROLE rls_audit_probe_user"))

    await set_tenant_context(async_session, tenant_a)
    visible_rows = (
        await async_session.execute(
            text("SELECT resource_name FROM audit_trail ORDER BY resource_name")
        )
    ).scalars().all()

    await async_session.execute(text("RESET ROLE"))

    assert visible_rows == ["tenant-a-row"]


def _auth_headers(user: IamUser) -> dict[str, str]:
    token = create_access_token(user.id, user.tenant_id, user.role.value)
    return {"Authorization": f"Bearer {token}"}


def _build_request(
    *,
    method: str,
    path: str,
    headers: dict[str, str] | None = None,
) -> Request:
    raw_headers = [
        (key.lower().encode("latin-1"), value.encode("latin-1"))
        for key, value in (headers or {}).items()
    ]

    async def _receive() -> dict[str, object]:
        return {"type": "http.request", "body": b"", "more_body": False}

    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": method,
        "path": path,
        "raw_path": path.encode("ascii"),
        "query_string": b"",
        "headers": raw_headers,
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
        "scheme": "http",
        "state": {},
        "path_params": {},
    }
    return Request(scope, _receive)


async def _dispatch(middleware: AuditMiddleware, request: Request) -> Response:
    async def _call_next(_: Request) -> Response:
        return Response(status_code=200)

    return await middleware.dispatch(request, _call_next)


async def _tenant_audit_rows(session: AsyncSession, *, tenant_id: uuid.UUID) -> list[AuditTrail]:
    result = await session.execute(
        select(AuditTrail)
        .where(AuditTrail.tenant_id == tenant_id)
        .order_by(AuditTrail.created_at.asc(), AuditTrail.id.asc())
    )
    return list(result.scalars().all())


def _middleware() -> AuditMiddleware:
    async def _dummy_app(scope, receive, send):  # type: ignore[no-untyped-def]
        return None

    return AuditMiddleware(_dummy_app)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_audit_chain_hash_links_across_different_modules(
    api_db_session: AsyncSession,
    api_test_user: IamUser,
) -> None:
    headers = _auth_headers(api_test_user)
    middleware = _middleware()
    before_rows = await _tenant_audit_rows(api_db_session, tenant_id=api_test_user.tenant_id)

    first = await _dispatch(
        middleware,
        _build_request(
            method="POST",
            path="/api/v1/bank-recon/runs",
            headers=headers,
        ),
    )
    second = await _dispatch(
        middleware,
        _build_request(
            method="POST",
            path="/api/v1/gst/returns",
            headers=headers,
        ),
    )

    rows = await _tenant_audit_rows(api_db_session, tenant_id=api_test_user.tenant_id)
    new_rows = rows[len(before_rows):]

    assert first.status_code == 200
    assert second.status_code == 200
    assert len(new_rows) == 2
    assert new_rows[0].resource_type == "bank-recon"
    assert new_rows[1].resource_type == "gst"
    assert new_rows[1].previous_hash == new_rows[0].chain_hash
    assert new_rows[0].resource_type != new_rows[1].resource_type
