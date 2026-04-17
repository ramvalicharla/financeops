from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib
from urllib.parse import quote

import pyotp
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.security import create_access_token, decode_token
from financeops.db.models.auth_tokens import MfaRecoveryCode, PasswordResetToken
from financeops.db.models.users import IamSession
from financeops.db.models.users import IamUser, UserRole
from financeops.services.user_service import create_user


async def _set_mfa_setup_required(api_session_factory, user_id) -> None:
    async with api_session_factory() as db:
        user = await db.get(IamUser, user_id)
        assert user is not None
        user.force_mfa_setup = True
        user.mfa_enabled = False
        await db.commit()


async def _load_user(api_session_factory, user_id):
    async with api_session_factory() as db:
        return await db.get(IamUser, user_id)


async def _seed_password_reset_token(api_session_factory, *, user_id, plain: str, expires_at, used_at=None) -> None:
    async with api_session_factory() as db:
        db.add(
            PasswordResetToken(
                user_id=user_id,
                token_hash=hashlib.sha256(plain.encode("utf-8")).hexdigest(),
                expires_at=expires_at,
                used_at=used_at,
            )
        )
        await db.commit()


@pytest.mark.asyncio
async def test_user_created_with_force_mfa_setup_true(async_session: AsyncSession, test_tenant) -> None:
    user = await create_user(
        async_session,
        tenant_id=test_tenant.id,
        email=f"create-user-{datetime.now(UTC).timestamp()}@example.com",
        password="TestPass123!",
        full_name="New User",
        role=UserRole.finance_team,
    )
    assert user.force_mfa_setup is True


@pytest.mark.asyncio
async def test_login_returns_requires_mfa_setup_when_flag_set(async_client, api_session_factory, test_user: IamUser) -> None:
    await _set_mfa_setup_required(api_session_factory, test_user.id)
    response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": test_user.email, "password": "TestPass123!"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["requires_mfa_setup"] is True
    assert data["status"] == "requires_mfa_setup"


@pytest.mark.asyncio
async def test_mfa_setup_token_has_limited_scope(async_client, api_session_factory, test_user: IamUser) -> None:
    await _set_mfa_setup_required(api_session_factory, test_user.id)
    response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": test_user.email, "password": "TestPass123!"},
    )
    token = response.json()["data"]["setup_token"]
    payload = decode_token(token)
    assert payload.get("scope") == "mfa_setup_only"


@pytest.mark.asyncio
async def test_protected_route_blocks_mfa_setup_token(async_client, api_session_factory, test_user: IamUser) -> None:
    await _set_mfa_setup_required(api_session_factory, test_user.id)
    login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": test_user.email, "password": "TestPass123!"},
    )
    token = login.json()["data"]["setup_token"]
    me = await async_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 403


@pytest.mark.asyncio
async def test_verify_mfa_setup_enables_mfa(async_client, api_session_factory, test_user: IamUser) -> None:
    await _set_mfa_setup_required(api_session_factory, test_user.id)
    login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": test_user.email, "password": "TestPass123!"},
    )
    setup_token = login.json()["data"]["setup_token"]
    setup = await async_client.post("/api/v1/auth/mfa/setup", headers={"Authorization": f"Bearer {setup_token}"})
    secret = setup.json()["data"]["secret"]
    code = pyotp.TOTP(secret).now()
    verify = await async_client.post(
        "/api/v1/auth/mfa/verify-setup",
        headers={"Authorization": f"Bearer {setup_token}"},
        json={"code": code},
    )
    assert verify.status_code == 200
    refreshed = await _load_user(api_session_factory, test_user.id)
    assert refreshed is not None
    assert refreshed.mfa_enabled is True
    assert refreshed.force_mfa_setup is False


@pytest.mark.asyncio
async def test_verify_mfa_setup_creates_persisted_session(
    async_client,
    api_session_factory,
    test_user: IamUser,
) -> None:
    await _set_mfa_setup_required(api_session_factory, test_user.id)

    login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": test_user.email, "password": "TestPass123!"},
    )
    setup_token = login.json()["data"]["setup_token"]
    setup = await async_client.post(
        "/api/v1/auth/mfa/setup",
        headers={"Authorization": f"Bearer {setup_token}"},
    )
    secret = setup.json()["data"]["secret"]
    code = pyotp.TOTP(secret).now()

    async with api_session_factory() as db:
        before = (
            await db.execute(
                select(func.count()).select_from(IamSession).where(IamSession.user_id == test_user.id)
            )
        ).scalar_one()

    verify = await async_client.post(
        "/api/v1/auth/mfa/verify-setup",
        headers={"Authorization": f"Bearer {setup_token}"},
        json={"code": code},
    )

    assert verify.status_code == 200
    payload = verify.json()["data"]
    assert isinstance(payload["access_token"], str)
    assert isinstance(payload["refresh_token"], str)

    async with api_session_factory() as db:
        after = (
            await db.execute(
                select(func.count()).select_from(IamSession).where(IamSession.user_id == test_user.id)
            )
        ).scalar_one()
    assert int(after) == int(before) + 1


@pytest.mark.asyncio
async def test_mfa_setup_returns_canonical_otpauth_uri(
    async_client,
    api_session_factory,
    test_user: IamUser,
) -> None:
    await _set_mfa_setup_required(api_session_factory, test_user.id)
    login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": test_user.email, "password": "TestPass123!"},
    )
    setup_token = login.json()["data"]["setup_token"]

    setup = await async_client.post(
        "/api/v1/auth/mfa/setup",
        headers={"Authorization": f"Bearer {setup_token}"},
    )

    assert setup.status_code == 200
    payload = setup.json()["data"]
    secret = payload["secret"]
    expected_qr = (
        f"otpauth://totp/FinanceOps:{quote(test_user.email.strip().lower(), safe='')}"
        f"?secret={secret}&issuer=FinanceOps"
    )
    assert payload["qr_url"] == expected_qr


@pytest.mark.asyncio
async def test_verify_mfa_setup_invalid_code_rejected(async_client, api_session_factory, test_user: IamUser) -> None:
    await _set_mfa_setup_required(api_session_factory, test_user.id)
    login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": test_user.email, "password": "TestPass123!"},
    )
    setup_token = login.json()["data"]["setup_token"]
    setup = await async_client.post("/api/v1/auth/mfa/setup", headers={"Authorization": f"Bearer {setup_token}"})
    secret = setup.json()["data"]["secret"]
    verify = await async_client.post(
        "/api/v1/auth/mfa/verify-setup",
        headers={"Authorization": f"Bearer {setup_token}"},
        json={"secret": secret, "code": "000000"},
    )
    assert verify.status_code == 400


@pytest.mark.asyncio
async def test_verify_mfa_setup_rejects_cross_user_totp(
    async_client,
    api_session_factory,
    test_user: IamUser,
    test_tenant,
) -> None:
    async with api_session_factory() as db:
        user_b = await create_user(
            db,
            tenant_id=test_tenant.id,
            email=f"mfa-user-b-{datetime.now(UTC).timestamp()}@example.com",
            password="TestPass123!",
            full_name="User B",
            role=UserRole.finance_team,
        )
        await db.commit()
        user_b_id = user_b.id
        user_b_email = user_b.email

    await _set_mfa_setup_required(api_session_factory, test_user.id)
    await _set_mfa_setup_required(api_session_factory, user_b_id)

    login_a = await async_client.post(
        "/api/v1/auth/login",
        json={"email": test_user.email, "password": "TestPass123!"},
    )
    setup_token_a = login_a.json()["data"]["setup_token"]
    setup_a = await async_client.post(
        "/api/v1/auth/mfa/setup",
        headers={"Authorization": f"Bearer {setup_token_a}"},
    )
    secret_a = setup_a.json()["data"]["secret"]
    code_a = pyotp.TOTP(secret_a).now()

    login_b = await async_client.post(
        "/api/v1/auth/login",
        json={"email": user_b_email, "password": "TestPass123!"},
    )
    setup_token_b = login_b.json()["data"]["setup_token"]
    setup_b = await async_client.post(
        "/api/v1/auth/mfa/setup",
        headers={"Authorization": f"Bearer {setup_token_b}"},
    )
    assert setup_b.status_code == 200

    verify_b = await async_client.post(
        "/api/v1/auth/mfa/verify-setup",
        headers={"Authorization": f"Bearer {setup_token_b}"},
        json={"secret": secret_a, "code": code_a},
    )
    assert verify_b.status_code in {400, 401}
    refreshed_b = await _load_user(api_session_factory, user_b_id)
    assert refreshed_b is not None
    assert refreshed_b.mfa_enabled is False


@pytest.mark.asyncio
async def test_recovery_codes_generated_on_mfa_setup(async_client, api_session_factory, test_user: IamUser) -> None:
    await _set_mfa_setup_required(api_session_factory, test_user.id)
    login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": test_user.email, "password": "TestPass123!"},
    )
    setup_token = login.json()["data"]["setup_token"]
    setup = await async_client.post("/api/v1/auth/mfa/setup", headers={"Authorization": f"Bearer {setup_token}"})
    secret = setup.json()["data"]["secret"]
    code = pyotp.TOTP(secret).now()
    verify = await async_client.post(
        "/api/v1/auth/mfa/verify-setup",
        headers={"Authorization": f"Bearer {setup_token}"},
        json={"secret": secret, "code": code},
    )
    codes = verify.json()["data"]["recovery_codes"]
    assert len(codes) == 8
    async with api_session_factory() as db:
        count = (
            await db.execute(
                select(func.count()).select_from(MfaRecoveryCode).where(MfaRecoveryCode.user_id == test_user.id)
            )
        ).scalar_one()
    assert int(count) == 8


@pytest.mark.asyncio
async def test_recovery_code_login_succeeds(async_client, api_session_factory, test_user: IamUser) -> None:
    await _set_mfa_setup_required(api_session_factory, test_user.id)
    login = await async_client.post("/api/v1/auth/login", json={"email": test_user.email, "password": "TestPass123!"})
    setup_token = login.json()["data"]["setup_token"]
    setup = await async_client.post("/api/v1/auth/mfa/setup", headers={"Authorization": f"Bearer {setup_token}"})
    secret = setup.json()["data"]["secret"]
    code = pyotp.TOTP(secret).now()
    verify_setup = await async_client.post(
        "/api/v1/auth/mfa/verify-setup",
        headers={"Authorization": f"Bearer {setup_token}"},
        json={"secret": secret, "code": code},
    )
    recovery_code = verify_setup.json()["data"]["recovery_codes"][0]

    login2 = await async_client.post("/api/v1/auth/login", json={"email": test_user.email, "password": "TestPass123!"})
    challenge = login2.json()["data"]["mfa_challenge_token"]
    verify = await async_client.post(
        "/api/v1/auth/mfa/verify",
        json={"mfa_challenge_token": challenge, "recovery_code": recovery_code},
    )
    assert verify.status_code == 200
    assert isinstance(verify.json()["data"]["access_token"], str)


@pytest.mark.asyncio
async def test_recovery_code_cannot_be_reused(async_client, api_session_factory, test_user: IamUser) -> None:
    await _set_mfa_setup_required(api_session_factory, test_user.id)
    login = await async_client.post("/api/v1/auth/login", json={"email": test_user.email, "password": "TestPass123!"})
    setup_token = login.json()["data"]["setup_token"]
    setup = await async_client.post("/api/v1/auth/mfa/setup", headers={"Authorization": f"Bearer {setup_token}"})
    secret = setup.json()["data"]["secret"]
    verify_setup = await async_client.post(
        "/api/v1/auth/mfa/verify-setup",
        headers={"Authorization": f"Bearer {setup_token}"},
        json={"secret": secret, "code": pyotp.TOTP(secret).now()},
    )
    recovery_code = verify_setup.json()["data"]["recovery_codes"][0]

    challenge1 = (await async_client.post("/api/v1/auth/login", json={"email": test_user.email, "password": "TestPass123!"})).json()["data"]["mfa_challenge_token"]
    ok = await async_client.post("/api/v1/auth/mfa/verify", json={"mfa_challenge_token": challenge1, "recovery_code": recovery_code})
    assert ok.status_code == 200

    challenge2 = (await async_client.post("/api/v1/auth/login", json={"email": test_user.email, "password": "TestPass123!"})).json()["data"]["mfa_challenge_token"]
    bad = await async_client.post("/api/v1/auth/mfa/verify", json={"mfa_challenge_token": challenge2, "recovery_code": recovery_code})
    assert bad.status_code == 401


@pytest.mark.asyncio
async def test_mfa_enforcement_blocks_dashboard_without_setup(async_client, api_session_factory, test_user: IamUser) -> None:
    await _set_mfa_setup_required(api_session_factory, test_user.id)
    token = create_access_token(test_user.id, test_user.tenant_id, test_user.role.value)
    response = await async_client.get("/api/v1/tenants/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_mfa_enforcement_allows_setup_page(async_client, api_session_factory, test_user: IamUser) -> None:
    await _set_mfa_setup_required(api_session_factory, test_user.id)
    login = await async_client.post("/api/v1/auth/login", json={"email": test_user.email, "password": "TestPass123!"})
    setup_token = login.json()["data"]["setup_token"]
    response = await async_client.post("/api/v1/auth/mfa/setup", headers={"Authorization": f"Bearer {setup_token}"})
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_forgot_password_returns_200_for_unknown_email(async_client) -> None:
    response = await async_client.post("/api/v1/auth/forgot-password", json={"email": "unknown@example.com"})
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_forgot_password_sends_email_for_known_user(async_client, api_session_factory, test_user: IamUser) -> None:
    async with api_session_factory() as db:
        before = (
            await db.execute(
                select(func.count()).select_from(PasswordResetToken).where(PasswordResetToken.user_id == test_user.id)
            )
        ).scalar_one()
    response = await async_client.post("/api/v1/auth/forgot-password", json={"email": test_user.email})
    assert response.status_code == 200
    async with api_session_factory() as db:
        after = (
            await db.execute(
                select(func.count()).select_from(PasswordResetToken).where(PasswordResetToken.user_id == test_user.id)
            )
        ).scalar_one()
    assert int(after) == int(before) + 1


@pytest.mark.asyncio
async def test_reset_password_valid_token_succeeds(async_client, api_session_factory, test_user: IamUser) -> None:
    plain = "valid-token"
    old_hash = test_user.hashed_password
    await _seed_password_reset_token(
        api_session_factory,
        user_id=test_user.id,
        plain=plain,
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
    )
    response = await async_client.post("/api/v1/auth/reset-password", json={"token": plain, "new_password": "NewPass123!"})
    assert response.status_code == 200
    refreshed = await _load_user(api_session_factory, test_user.id)
    assert refreshed is not None
    assert refreshed.hashed_password != old_hash


@pytest.mark.asyncio
async def test_reset_password_expired_token_fails(async_client, api_session_factory, test_user: IamUser) -> None:
    plain = "expired-token"
    await _seed_password_reset_token(
        api_session_factory,
        user_id=test_user.id,
        plain=plain,
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    response = await async_client.post("/api/v1/auth/reset-password", json={"token": plain, "new_password": "NewPass123!"})
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_reset_password_used_token_fails(async_client, api_session_factory, test_user: IamUser) -> None:
    plain = "used-token"
    await _seed_password_reset_token(
        api_session_factory,
        user_id=test_user.id,
        plain=plain,
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
        used_at=datetime.now(UTC),
    )
    response = await async_client.post("/api/v1/auth/reset-password", json={"token": plain, "new_password": "NewPass123!"})
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_reset_password_invalid_token_fails(async_client) -> None:
    response = await async_client.post("/api/v1/auth/reset-password", json={"token": "missing", "new_password": "NewPass123!"})
    assert response.status_code == 400
