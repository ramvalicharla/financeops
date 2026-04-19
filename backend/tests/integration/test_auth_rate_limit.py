from __future__ import annotations

from types import SimpleNamespace
import uuid
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import pytest_asyncio
from fastapi.routing import APIRoute

import financeops.api.v1.auth as auth_router
from financeops.api.deps import get_async_session
from financeops.db.models.auth_tokens import PasswordResetToken
from financeops.main import app

_FORGOT_PASSWORD_MESSAGE = "If that email exists, a reset link has been sent."


class _FakeSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.flush_count = 0

    def add(self, instance: object) -> None:
        self.added.append(instance)

    async def flush(self) -> None:
        self.flush_count += 1


@pytest_asyncio.fixture
async def http_client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        yield client


@pytest_asyncio.fixture(scope="module", autouse=True)
async def _close_app_redis_client():
    yield
    redis_client = getattr(app.state, "redis", None)
    if redis_client is None:
        return
    if hasattr(redis_client, "aclose"):
        await redis_client.aclose()
    elif hasattr(redis_client, "close"):
        maybe_awaitable = redis_client.close()
        if hasattr(maybe_awaitable, "__await__"):
            await maybe_awaitable


@pytest.fixture
def fake_session() -> _FakeSession:
    return _FakeSession()


@pytest.fixture(autouse=True)
def _override_dependencies(fake_session: _FakeSession):
    async def _fake_session_dependency():
        yield fake_session

    app.dependency_overrides[get_async_session] = _fake_session_dependency
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_async_session, None)


@pytest.fixture(autouse=True)
def _bind_limited_auth_routes() -> None:
    wrapped_handlers = {
        "/api/v1/auth/forgot-password": auth_router.forgot_password,
    }
    originals: list[tuple[APIRoute, object, object]] = []
    for route in app.router.routes:
        if isinstance(route, APIRoute) and route.path in wrapped_handlers:
            originals.append((route, route.endpoint, route.dependant.call))
            wrapped = wrapped_handlers[route.path]
            route.endpoint = wrapped
            route.dependant.call = wrapped
    try:
        yield
    finally:
        for route, endpoint, call in originals:
            route.endpoint = endpoint
            route.dependant.call = call


async def _repeat_post(
    http_client: httpx.AsyncClient,
    path: str,
    payload: dict,
    calls: int,
) -> list[httpx.Response]:
    responses = []
    for _ in range(calls):
        responses.append(await http_client.post(path, json=payload))
    return responses


def _response_message(response: httpx.Response) -> str | None:
    payload = response.json()
    data = payload.get("data")
    if isinstance(data, dict):
        return data.get("message")
    return payload.get("message")


@pytest.mark.asyncio
async def test_forgot_password_rate_limited_after_3_requests(
    http_client: httpx.AsyncClient,
    fake_session: _FakeSession,
) -> None:
    known_user = SimpleNamespace(
        id=uuid.uuid4(),
        email="forgot-password-user@example.com",
    )
    with patch.object(auth_router, "get_user_by_email", AsyncMock(return_value=known_user)):
        with patch.object(auth_router, "commit_session", AsyncMock()) as commit_mock:
            with patch.object(auth_router.send_password_reset_email_task, "delay") as delay_mock:
                responses = await _repeat_post(
                    http_client,
                    "/api/v1/auth/forgot-password",
                    {"email": known_user.email},
                    4,
                )

    assert [response.status_code for response in responses[:3]] == [200, 200, 200]
    assert responses[3].status_code == 429
    assert commit_mock.await_count == 3
    assert delay_mock.call_count == 3
    assert len(fake_session.added) == 3
    assert all(isinstance(instance, PasswordResetToken) for instance in fake_session.added)


@pytest.mark.asyncio
async def test_forgot_password_returns_same_response_for_valid_email(
    http_client: httpx.AsyncClient,
    fake_session: _FakeSession,
) -> None:
    known_user = SimpleNamespace(
        id=uuid.uuid4(),
        email="forgot-password-user@example.com",
    )
    with patch.object(auth_router, "get_user_by_email", AsyncMock(return_value=known_user)):
        with patch.object(auth_router, "commit_session", AsyncMock()) as commit_mock:
            with patch.object(auth_router.send_password_reset_email_task, "delay") as delay_mock:
                response = await http_client.post(
                    "/api/v1/auth/forgot-password",
                    json={"email": known_user.email},
                )

    assert response.status_code == 200
    assert _response_message(response) == _FORGOT_PASSWORD_MESSAGE
    assert commit_mock.await_count == 1
    assert delay_mock.call_count == 1
    assert len(fake_session.added) == 1
    token_record = fake_session.added[0]
    assert isinstance(token_record, PasswordResetToken)
    assert token_record.user_id == known_user.id
    assert token_record.reset_attempt_count == 0


@pytest.mark.asyncio
async def test_forgot_password_returns_same_response_for_invalid_email(
    http_client: httpx.AsyncClient,
    fake_session: _FakeSession,
) -> None:
    with patch.object(auth_router, "get_user_by_email", AsyncMock(return_value=None)):
        with patch.object(auth_router, "commit_session", AsyncMock()) as commit_mock:
            with patch.object(auth_router.send_password_reset_email_task, "delay") as delay_mock:
                response = await http_client.post(
                    "/api/v1/auth/forgot-password",
                    json={"email": "missing-user@example.com"},
                )

    assert response.status_code == 200
    assert _response_message(response) == _FORGOT_PASSWORD_MESSAGE
    assert commit_mock.await_count == 0
    assert delay_mock.call_count == 0
    assert fake_session.added == []
