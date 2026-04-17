from __future__ import annotations

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager

import pyotp
import pytest
import pytest_asyncio
from httpx import AsyncClient
from unittest.mock import AsyncMock

from financeops.core.security import encrypt_field, generate_totp_secret
from financeops.services.auth_service import create_mfa_challenge

TEST_REDIS_URL = os.getenv("TEST_REDIS_URL", "redis://localhost:6380/0")


@asynccontextmanager
async def _redis_client():
    import redis.asyncio as aioredis

    client = aioredis.from_url(TEST_REDIS_URL, encoding="utf-8", decode_responses=True)
    try:
        yield client
    finally:
        await client.flushdb()
        await client.aclose()


@pytest_asyncio.fixture
async def mfa_user(api_session_factory, test_user):
    """Create an MFA-enabled user fixture with a valid encrypted TOTP secret."""
    secret = generate_totp_secret()
    async with api_session_factory() as db:
        user = await db.get(type(test_user), test_user.id)
        assert user is not None
        user.totp_secret_encrypted = encrypt_field(secret)
        user.mfa_enabled = True
        await db.flush()
        await db.commit()
        return user, secret


@pytest.mark.asyncio
async def test_login_with_mfa_user_returns_challenge_token(
    async_client: AsyncClient,
    mfa_user,
) -> None:
    """MFA login returns challenge token, not access token."""
    user, _ = mfa_user
    async with _redis_client() as redis_client:
        response = await async_client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": "TestPass123!"},
        )

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["requires_mfa"] is True
        assert isinstance(data.get("mfa_challenge_token"), str)
        assert data["mfa_challenge_token"]
        assert "access_token" not in data
        assert "refresh_token" not in data

        key = f"mfa_challenge:{data['mfa_challenge_token']}"
        cached = await redis_client.get(key)
        ttl = await redis_client.ttl(key)
        assert cached is not None
        assert 0 < ttl <= 90


@pytest.mark.asyncio
async def test_mfa_verify_with_valid_challenge_issues_tokens(
    async_client: AsyncClient,
    mfa_user,
) -> None:
    """Valid challenge + valid TOTP issues full token pair."""
    user, secret = mfa_user
    async with _redis_client() as redis_client:
        challenge_token = await create_mfa_challenge(redis_client, user=user)
        code = pyotp.TOTP(secret).now()

        response = await async_client.post(
            "/api/v1/auth/mfa/verify",
            json={"mfa_challenge_token": challenge_token, "totp_code": code},
        )

        assert response.status_code == 200
        data = response.json()["data"]
        assert "access_token" in data
        assert "refresh_token" in data
        assert await redis_client.get(f"mfa_challenge:{challenge_token}") is None


@pytest.mark.asyncio
async def test_mfa_verify_logs_do_not_expose_secret_or_code(
    async_client: AsyncClient,
    mfa_user,
    caplog: pytest.LogCaptureFixture,
) -> None:
    user, secret = mfa_user
    async with _redis_client() as redis_client:
        challenge_token = await create_mfa_challenge(redis_client, user=user)
        code = pyotp.TOTP(secret).now()

        with caplog.at_level(logging.DEBUG, logger="financeops.services.auth_service"):
            response = await async_client.post(
                "/api/v1/auth/mfa/verify",
                json={"mfa_challenge_token": challenge_token, "totp_code": code},
            )

        assert response.status_code == 200
        assert secret not in caplog.text
        assert code not in caplog.text
        assert "otpauth://" not in caplog.text


@pytest.mark.asyncio
async def test_mfa_verify_commits_session_when_tokens_issued(
    async_client: AsyncClient,
    mfa_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user, secret = mfa_user
    async with _redis_client() as redis_client:
        challenge_token = await create_mfa_challenge(redis_client, user=user)
        code = pyotp.TOTP(secret).now()
        commit_spy = AsyncMock()
        monkeypatch.setattr("financeops.api.v1.auth.commit_session", commit_spy)

        response = await async_client.post(
            "/api/v1/auth/mfa/verify",
            json={"mfa_challenge_token": challenge_token, "totp_code": code},
        )

        assert response.status_code == 200
        assert commit_spy.await_count == 1


@pytest.mark.asyncio
async def test_mfa_challenge_token_is_single_use(
    async_client: AsyncClient,
    mfa_user,
) -> None:
    """Challenge token cannot be reused after successful verify."""
    user, secret = mfa_user
    async with _redis_client() as redis_client:
        challenge_token = await create_mfa_challenge(redis_client, user=user)
        code = pyotp.TOTP(secret).now()

        first = await async_client.post(
            "/api/v1/auth/mfa/verify",
            json={"mfa_challenge_token": challenge_token, "totp_code": code},
        )
        assert first.status_code == 200

        second = await async_client.post(
            "/api/v1/auth/mfa/verify",
            json={"mfa_challenge_token": challenge_token, "totp_code": code},
        )
        assert second.status_code == 401


@pytest.mark.asyncio
async def test_mfa_challenge_token_expired_returns_401(
    async_client: AsyncClient,
    mfa_user,
) -> None:
    """Expired challenge token is rejected."""
    user, secret = mfa_user
    async with _redis_client() as redis_client:
        challenge_token = "expired-token"
        key = f"mfa_challenge:{challenge_token}"
        await redis_client.setex(
            key,
            1,
            json.dumps({"user_id": str(user.id), "tenant_id": str(user.tenant_id)}),
        )
        await asyncio.sleep(2.1)

        response = await async_client.post(
            "/api/v1/auth/mfa/verify",
            json={
                "mfa_challenge_token": challenge_token,
                "totp_code": pyotp.TOTP(secret).now(),
            },
        )
        assert response.status_code == 401
