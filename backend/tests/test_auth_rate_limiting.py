from __future__ import annotations

import httpx
import pytest
import pytest_asyncio
from fastapi.routing import APIRoute
from types import SimpleNamespace

import financeops.api.v1.auth as auth_router
from financeops.api.deps import get_async_session, get_current_user
from financeops.config import settings
from financeops.main import app


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


@pytest.fixture(autouse=True)
def _stub_login_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_get_user_by_email(session, email):
        del session, email
        return None

    monkeypatch.setattr(auth_router, "get_user_by_email", _fake_get_user_by_email)


class _FakeSession:
    async def commit(self) -> None:
        return None


@pytest.fixture(autouse=True)
def _override_auth_dependencies() -> None:
    async def _fake_session_dependency():
        yield _FakeSession()

    async def _fake_current_user():
        return SimpleNamespace(id="test-user", tenant_id="test-tenant")

    app.dependency_overrides[get_async_session] = _fake_session_dependency
    app.dependency_overrides[get_current_user] = _fake_current_user
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_async_session, None)
        app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture(autouse=True)
def _bind_limited_auth_routes() -> None:
    wrapped_handlers = {
        "/api/v1/auth/login": auth_router.user_login,
        "/api/v1/auth/refresh": auth_router.token_refresh,
        "/api/v1/auth/mfa/verify": auth_router.mfa_verify,
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


@pytest.mark.asyncio
async def test_login_under_limit_passes(http_client: httpx.AsyncClient) -> None:
    """POST /auth/login four times from same client remains below limiter threshold."""
    responses = await _repeat_post(
        http_client,
        "/api/v1/auth/login",
        {"email": "nouser@example.com", "password": "WrongPass1!"},
        4,
    )
    assert all(response.status_code != 429 for response in responses)


@pytest.mark.asyncio
async def test_login_at_limit_passes(http_client: httpx.AsyncClient) -> None:
    """POST /auth/login exactly five times should not block the 5th call."""
    responses = await _repeat_post(
        http_client,
        "/api/v1/auth/login",
        {"email": "nouser@example.com", "password": "WrongPass1!"},
        5,
    )
    assert responses[-1].status_code != 429


@pytest.mark.asyncio
async def test_login_over_limit_blocked(http_client: httpx.AsyncClient) -> None:
    """POST /auth/login six times should rate-limit on the 6th request."""
    responses = await _repeat_post(
        http_client,
        "/api/v1/auth/login",
        {"email": "nouser@example.com", "password": "WrongPass1!"},
        6,
    )
    assert responses[-1].status_code == 429


@pytest.mark.asyncio
async def test_login_rate_limit_response_body(http_client: httpx.AsyncClient) -> None:
    """429 login response includes standard SlowAPI error payload keys."""
    responses = await _repeat_post(
        http_client,
        "/api/v1/auth/login",
        {"email": "nouser@example.com", "password": "WrongPass1!"},
        6,
    )
    payload = responses[-1].json()
    assert "error" in payload or "detail" in payload


@pytest.mark.asyncio
async def test_token_under_limit_passes(http_client: httpx.AsyncClient) -> None:
    """POST /auth/refresh four times remains below limiter threshold."""
    responses = await _repeat_post(
        http_client,
        "/api/v1/auth/refresh",
        {"refresh_token": "invalid.refresh.token"},
        4,
    )
    assert all(response.status_code != 429 for response in responses)


@pytest.mark.asyncio
async def test_token_over_limit_blocked(http_client: httpx.AsyncClient) -> None:
    """POST /auth/refresh six times should rate-limit on the 6th request."""
    responses = await _repeat_post(
        http_client,
        "/api/v1/auth/refresh",
        {"refresh_token": "invalid.refresh.token"},
        6,
    )
    assert responses[-1].status_code == 429


@pytest.mark.asyncio
async def test_mfa_under_limit_passes(http_client: httpx.AsyncClient) -> None:
    """POST /auth/mfa/verify twice remains below limiter threshold."""
    responses = await _repeat_post(
        http_client,
        "/api/v1/auth/mfa/verify",
        {"mfa_challenge_token": "token-1", "totp_code": "123456"},
        2,
    )
    assert all(response.status_code != 429 for response in responses)


@pytest.mark.asyncio
async def test_mfa_at_limit_passes(http_client: httpx.AsyncClient) -> None:
    """POST /auth/mfa/verify exactly three times should not block the 3rd call."""
    responses = await _repeat_post(
        http_client,
        "/api/v1/auth/mfa/verify",
        {"mfa_challenge_token": "token-1", "totp_code": "123456"},
        3,
    )
    assert responses[-1].status_code != 429


@pytest.mark.asyncio
async def test_mfa_over_limit_blocked(http_client: httpx.AsyncClient) -> None:
    """POST /auth/mfa/verify four times should rate-limit on the 4th request."""
    responses = await _repeat_post(
        http_client,
        "/api/v1/auth/mfa/verify",
        {"mfa_challenge_token": "token-1", "totp_code": "123456"},
        4,
    )
    assert responses[-1].status_code == 429


@pytest.mark.asyncio
async def test_mfa_stricter_than_login() -> None:
    """MFA rate-limit config is stricter than login by numeric prefix."""
    login_limit = int(settings.AUTH_LOGIN_RATE_LIMIT.split("/", 1)[0])
    mfa_limit = int(settings.AUTH_MFA_RATE_LIMIT.split("/", 1)[0])
    assert mfa_limit < login_limit


@pytest.mark.asyncio
async def test_rate_limit_headers_present(http_client: httpx.AsyncClient) -> None:
    """Rate-limited endpoint exposes at least one SlowAPI header.

    SlowAPI injects X-RateLimit-* headers when headers_enabled=True.
    We check the first non-blocked response; if headers are absent there
    (middleware ordering edge case), we verify Retry-After on the 429
    which SlowAPI always sets.
    """
    rate_limit_headers = {
        "x-ratelimit-limit",
        "x-ratelimit-remaining",
        "retry-after",
    }

    # First attempt: well-formed request, wrong credentials -> 401
    response = await http_client.post(
        "/api/v1/auth/login",
        json={"email": "nouser@example.com", "password": "WrongPass1!"},
    )
    lower_headers = {k.lower() for k in response.headers}
    if rate_limit_headers & lower_headers:
        # Headers present on normal response - ideal case
        return

    # Fallback: exhaust the limit and check the 429 carries Retry-After
    # (consume remaining quota - up to 5 calls allowed, 1 already used)
    for _ in range(5):
        await http_client.post(
            "/api/v1/auth/login",
            json={"email": "nouser@example.com", "password": "WrongPass1!"},
        )
    blocked = await http_client.post(
        "/api/v1/auth/login",
        json={"email": "nouser@example.com", "password": "WrongPass1!"},
    )
    assert blocked.status_code == 429
    lower_blocked = {k.lower() for k in blocked.headers}
    assert "retry-after" in lower_blocked, (
        f"Expected retry-after in 429 headers, got: {set(blocked.headers.keys())}"
    )


@pytest.mark.asyncio
async def test_unrelated_endpoint_not_limited(http_client: httpx.AsyncClient) -> None:
    """Unrelated auth endpoint without limiter decorators should never return 429 here."""
    responses = await _repeat_post(
        http_client,
        "/api/v1/auth/logout",
        {"refresh_token": "invalid.refresh.token"},
        10,
    )
    assert all(response.status_code != 429 for response in responses)
