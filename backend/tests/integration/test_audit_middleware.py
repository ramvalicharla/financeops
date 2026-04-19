from __future__ import annotations

from collections.abc import Mapping

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request
from starlette.responses import Response

from financeops.core.security import create_access_token
from financeops.db.models.audit import AuditTrail
from financeops.db.models.users import IamUser
from financeops.middleware.audit_middleware import AuditMiddleware


def _auth_headers(user: IamUser) -> dict[str, str]:
    token = create_access_token(user.id, user.tenant_id, user.role.value)
    return {"Authorization": f"Bearer {token}"}


def _build_request(
    *,
    method: str,
    path: str,
    headers: Mapping[str, str] | None = None,
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


async def _dispatch(
    middleware: AuditMiddleware,
    request: Request,
    *,
    status_code: int = 200,
) -> Response:
    async def _call_next(_: Request) -> Response:
        return Response(status_code=status_code)

    return await middleware.dispatch(request, _call_next)


async def _tenant_audit_rows(session: AsyncSession, *, tenant_id) -> list[AuditTrail]:
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
async def test_audit_middleware_writes_row_on_post_200(
    api_db_session: AsyncSession,
    api_test_user: IamUser,
) -> None:
    before_rows = await _tenant_audit_rows(api_db_session, tenant_id=api_test_user.tenant_id)
    request = _build_request(
        method="POST",
        path="/api/v1/notifications/read-all",
        headers=_auth_headers(api_test_user),
    )

    response = await _dispatch(_middleware(), request)
    rows = await _tenant_audit_rows(api_db_session, tenant_id=api_test_user.tenant_id)
    created_row = rows[-1]

    assert response.status_code == 200
    assert len(rows) == len(before_rows) + 1
    assert created_row.user_id == api_test_user.id
    assert created_row.action == "http.post"
    assert created_row.resource_type == "notifications"
    assert created_row.resource_name == "/api/v1/notifications/read-all"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_audit_middleware_skips_on_get_request(
    api_db_session: AsyncSession,
    api_test_user: IamUser,
) -> None:
    before = int(
        (
            await api_db_session.execute(
                select(func.count()).select_from(AuditTrail).where(
                    AuditTrail.tenant_id == api_test_user.tenant_id
                )
            )
        ).scalar_one()
        or 0
    )
    request = _build_request(
        method="GET",
        path="/api/v1/notifications/preferences",
        headers=_auth_headers(api_test_user),
    )

    response = await _dispatch(_middleware(), request)
    total = int(
        (
            await api_db_session.execute(
                select(func.count()).select_from(AuditTrail).where(
                    AuditTrail.tenant_id == api_test_user.tenant_id
                )
            )
        ).scalar_one()
        or 0
    )

    assert response.status_code == 200
    assert total == before


@pytest.mark.asyncio
@pytest.mark.integration
async def test_audit_middleware_skips_on_4xx_response(
    api_db_session: AsyncSession,
    api_test_user: IamUser,
) -> None:
    before = int(
        (
            await api_db_session.execute(
                select(func.count()).select_from(AuditTrail).where(
                    AuditTrail.tenant_id == api_test_user.tenant_id
                )
            )
        ).scalar_one()
        or 0
    )
    request = _build_request(
        method="PATCH",
        path="/api/v1/notifications/preferences",
        headers=_auth_headers(api_test_user),
    )

    response = await _dispatch(_middleware(), request, status_code=422)
    total = int(
        (
            await api_db_session.execute(
                select(func.count()).select_from(AuditTrail).where(
                    AuditTrail.tenant_id == api_test_user.tenant_id
                )
            )
        ).scalar_one()
        or 0
    )

    assert response.status_code == 422
    assert total == before


@pytest.mark.asyncio
@pytest.mark.integration
async def test_audit_middleware_skips_exempt_paths(
    api_db_session: AsyncSession,
) -> None:
    before = int(
        (
            await api_db_session.execute(select(func.count()).select_from(AuditTrail))
        ).scalar_one()
        or 0
    )
    request = _build_request(
        method="POST",
        path="/api/v1/auth/forgot-password",
    )

    response = await _dispatch(_middleware(), request)
    after = int(
        (
            await api_db_session.execute(select(func.count()).select_from(AuditTrail))
        ).scalar_one()
        or 0
    )

    assert response.status_code == 200
    assert after == before


@pytest.mark.asyncio
@pytest.mark.integration
async def test_audit_chain_hash_links_to_previous_row(
    api_db_session: AsyncSession,
    api_test_user: IamUser,
) -> None:
    headers = _auth_headers(api_test_user)
    middleware = _middleware()
    before_rows = await _tenant_audit_rows(api_db_session, tenant_id=api_test_user.tenant_id)

    first = await _dispatch(
        middleware,
        _build_request(method="POST", path="/api/v1/notifications/read-all", headers=headers),
    )
    second = await _dispatch(
        middleware,
        _build_request(method="POST", path="/api/v1/notifications/read-all", headers=headers),
    )
    rows = await _tenant_audit_rows(api_db_session, tenant_id=api_test_user.tenant_id)
    new_rows = rows[len(before_rows):]

    assert first.status_code == 200
    assert second.status_code == 200
    assert len(new_rows) == 2
    assert new_rows[1].previous_hash == new_rows[0].chain_hash


@pytest.mark.asyncio
@pytest.mark.integration
async def test_audit_write_failure_does_not_break_response(
    api_db_session: AsyncSession,
    api_test_user: IamUser,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fail_log_action(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("audit write unavailable")

    monkeypatch.setattr("financeops.middleware.audit_middleware.log_action", _fail_log_action)
    before_rows = await _tenant_audit_rows(api_db_session, tenant_id=api_test_user.tenant_id)
    request = _build_request(
        method="POST",
        path="/api/v1/notifications/read-all",
        headers=_auth_headers(api_test_user),
    )

    response = await _dispatch(_middleware(), request)
    rows = await _tenant_audit_rows(api_db_session, tenant_id=api_test_user.tenant_id)

    assert response.status_code == 200
    assert len(rows) == len(before_rows)
