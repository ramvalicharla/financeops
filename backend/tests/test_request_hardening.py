from __future__ import annotations

import asyncio

import httpx
import pytest
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.requests import Request

from financeops.config import get_real_ip, settings
from financeops.core.middleware import RequestTimeoutMiddleware
from financeops.main import create_app


def _build_request(
    *,
    headers: list[tuple[bytes, bytes]] | None = None,
    client_host: str = "9.9.9.9",
) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": headers or [],
            "client": (client_host, 1234),
            "scheme": "https",
            "server": ("testserver", 443),
        }
    )


def test_get_real_ip_prefers_cloudflare_header() -> None:
    request = _build_request(
        headers=[
            (b"cf-connecting-ip", b"1.1.1.1"),
            (b"x-forwarded-for", b"2.2.2.2, 3.3.3.3"),
        ],
        client_host="4.4.4.4",
    )
    assert get_real_ip(request) == "1.1.1.1"


def test_get_real_ip_falls_back_to_forwarded_for_then_client() -> None:
    forwarded_request = _build_request(
        headers=[(b"x-forwarded-for", b"2.2.2.2, 3.3.3.3")],
        client_host="4.4.4.4",
    )
    client_request = _build_request(client_host="4.4.4.4")

    assert get_real_ip(forwarded_request) == "2.2.2.2"
    assert get_real_ip(client_request) == "4.4.4.4"


@pytest.mark.asyncio
async def test_request_timeout_middleware_returns_504_for_slow_requests() -> None:
    app = FastAPI()
    app.add_middleware(RequestTimeoutMiddleware, timeout_seconds=0.01)

    @app.get("/slow")
    async def slow_endpoint() -> dict[str, str]:
        await asyncio.sleep(0.05)
        return {"status": "ok"}

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/slow")

    assert response.status_code == 504
    assert response.json()["error"] == "request_timeout"


@pytest.mark.asyncio
async def test_request_timeout_middleware_skips_streaming_routes() -> None:
    app = FastAPI()
    app.add_middleware(RequestTimeoutMiddleware, timeout_seconds=0.01)

    @app.get("/api/v1/ai/stream")
    async def stream_endpoint() -> StreamingResponse:
        await asyncio.sleep(0.05)

        async def _events():
            yield "data: ok\n\n"

        return StreamingResponse(_events(), media_type="text/event-stream")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/ai/stream")

    assert response.status_code == 200


def test_create_app_adds_production_host_and_https_middlewares(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "APP_ENV", "production")
    app = create_app()
    middleware_classes = [middleware.cls for middleware in app.user_middleware]

    assert TrustedHostMiddleware in middleware_classes
    assert HTTPSRedirectMiddleware in middleware_classes
