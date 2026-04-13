from __future__ import annotations

import logging
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import AuthenticationError
from financeops.core.security import get_totp_uri, hash_password, verify_password, verify_totp
from financeops.services.audit_writer import AuditWriter
from financeops.services.auth_service import (
    build_billing_token_claims,
    login,
    logout,
    refresh_tokens,
    setup_totp,
    verify_totp_setup,
)


@pytest.mark.asyncio
async def test_setup_totp_returns_secret_and_uri(
    async_session: AsyncSession, test_user
):
    result = await setup_totp(test_user, async_session)
    assert "totp_secret" in result
    assert "qr_code_url" in result
    assert result["qr_code_url"].startswith("otpauth://")
    assert len(result["totp_secret"]) >= 16


@pytest.mark.asyncio
async def test_setup_totp_debug_logs_do_not_expose_secret_or_uri(
    async_session: AsyncSession,
    test_user,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.DEBUG, logger="financeops.services.auth_service"):
        result = await setup_totp(test_user, async_session)

    assert result["totp_secret"] not in caplog.text
    assert result["qr_code_url"] not in caplog.text
    assert "otpauth://" not in caplog.text


def test_get_totp_uri_uses_canonical_google_authenticator_format() -> None:
    secret = "JBSWY3DPEHPK3PXP"
    uri = get_totp_uri(secret, "Mfa.User+Ops@example.com")
    assert (
        uri
        == "otpauth://totp/FinanceOps:mfa.user%2Bops%40example.com"
        "?secret=JBSWY3DPEHPK3PXP&issuer=FinanceOps"
    )


def test_verify_totp_normalizes_secret_and_code() -> None:
    import pyotp

    secret = "JBSWY3DPEHPK3PXP"
    code = pyotp.TOTP(secret).now()
    assert verify_totp(f" {secret.lower()} ", f" {code} ") is True


@pytest.mark.asyncio
async def test_verify_totp_setup_activates_mfa(
    async_session: AsyncSession, test_user
):
    import pyotp
    result = await setup_totp(test_user, async_session)
    secret = result["totp_secret"]
    valid_code = pyotp.TOTP(secret).now()
    confirmed = await verify_totp_setup(test_user, valid_code, async_session)
    assert confirmed is True
    assert test_user.mfa_enabled is True


@pytest.mark.asyncio
async def test_verify_totp_setup_rejects_wrong_code(
    async_session: AsyncSession, test_user
):
    await setup_totp(test_user, async_session)
    with pytest.raises(AuthenticationError):
        await verify_totp_setup(test_user, "000000", async_session)


@pytest.mark.asyncio
async def test_logout_revokes_session(
    async_session: AsyncSession, test_user
):
    tokens = await login(
        async_session,
        user=test_user,
        totp_code=None,
        ip_address="127.0.0.1",
    )
    refresh = tokens["refresh_token"]
    await logout(async_session, refresh)

    # Attempting to use the revoked token should fail
    with pytest.raises(AuthenticationError):
        await refresh_tokens(async_session, refresh)


@pytest.mark.asyncio
async def test_login_uses_audit_writer(async_session: AsyncSession, test_user):
    with patch(
        "financeops.services.auth_service.AuditWriter.insert_record",
        wraps=AuditWriter.insert_record,
    ) as insert_spy:
        with patch(
            "financeops.services.auth_service.AuditWriter.flush_with_audit",
            wraps=AuditWriter.flush_with_audit,
        ) as flush_spy:
            await login(
                async_session,
                user=test_user,
                totp_code=None,
                ip_address="127.0.0.1",
                device_info="pytest",
            )
    assert insert_spy.await_count >= 1
    assert flush_spy.await_count >= 1


@pytest.mark.asyncio
async def test_refresh_tokens_uses_audited_session_revocation(
    async_session: AsyncSession, test_user
):
    tokens = await login(
        async_session,
        user=test_user,
        totp_code=None,
        ip_address="127.0.0.1",
        device_info="pytest",
    )
    with patch(
        "financeops.services.auth_service.AuditWriter.insert_record",
        wraps=AuditWriter.insert_record,
    ) as insert_spy:
        with patch(
            "financeops.services.auth_service.AuditWriter.flush_with_audit",
            wraps=AuditWriter.flush_with_audit,
        ) as flush_spy:
            await refresh_tokens(async_session, tokens["refresh_token"])
    assert insert_spy.await_count >= 1
    assert flush_spy.await_count >= 1


def test_password_hashing_and_verification():
    password = "SuperSecret123!"
    hashed = hash_password(password)
    assert verify_password(password, hashed) is True
    assert verify_password("wrong_password", hashed) is False


@pytest.mark.asyncio
async def test_build_billing_token_claims_populates_entity_roles(
    async_session: AsyncSession,
) -> None:
    fake_entity_1 = MagicMock()
    fake_entity_1.id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    fake_entity_1.entity_name = "Acme Corp"
    fake_entity_1.base_currency = "INR"

    fake_entity_2 = MagicMock()
    fake_entity_2.id = uuid.UUID("00000000-0000-0000-0000-000000000002")
    fake_entity_2.entity_name = "Beta Ltd"
    fake_entity_2.base_currency = "USD"

    with patch(
        "financeops.platform.services.tenancy.entity_access.get_entities_for_user",
        new_callable=AsyncMock,
        return_value=[fake_entity_1, fake_entity_2],
    ):
        claims = await build_billing_token_claims(
            async_session,
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            user_role="finance_leader",
        )

    assert "entity_roles" in claims
    assert len(claims["entity_roles"]) == 2
    for item in claims["entity_roles"]:
        assert "entity_id" in item
        assert "entity_name" in item
        assert "role" in item
        assert "currency" in item
