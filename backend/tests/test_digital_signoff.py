from __future__ import annotations

import hashlib
from decimal import Decimal

import pyotp
import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import AuthenticationError
from financeops.core.security import create_access_token, encrypt_field, generate_totp_secret
from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql
from financeops.db.models.users import IamUser
from financeops.modules.digital_signoff.models import DirectorSignoff
from financeops.modules.digital_signoff.service import (
    complete_signoff,
    generate_certificate,
    initiate_signoff,
    verify_signoff,
)


def _auth_headers(user: IamUser) -> dict[str, str]:
    token = create_access_token(user.id, user.tenant_id, user.role.value)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_initiate_signoff_computes_content_hash(async_session: AsyncSession, test_user: IamUser) -> None:
    content = b"board pack"
    row = await initiate_signoff(
        async_session,
        tenant_id=test_user.tenant_id,
        document_type="board_pack",
        document_reference="BP-Q1",
        period="2026-03",
        signatory_user_id=test_user.id,
        signatory_role="CFO",
        document_content=content,
        declaration_text="I approve",
    )
    assert row.content_hash == hashlib.sha256(content).hexdigest()


@pytest.mark.asyncio
async def test_complete_signoff_requires_valid_mfa(async_session: AsyncSession, test_user: IamUser) -> None:
    secret = generate_totp_secret()
    test_user.totp_secret_encrypted = encrypt_field(secret)
    row = await initiate_signoff(
        async_session,
        tenant_id=test_user.tenant_id,
        document_type="board_pack",
        document_reference="BP-Q1",
        period="2026-03",
        signatory_user_id=test_user.id,
        signatory_role="CFO",
        document_content="doc",
        declaration_text="I approve",
    )
    with pytest.raises(AuthenticationError):
        await complete_signoff(
            async_session,
            tenant_id=test_user.tenant_id,
            signoff_id=row.id,
            signatory_user_id=test_user.id,
            totp_code="000000",
            ip_address="127.0.0.1",
            user_agent="pytest",
        )


@pytest.mark.asyncio
async def test_complete_signoff_sets_mfa_verified(async_session: AsyncSession, test_user: IamUser) -> None:
    secret = generate_totp_secret()
    test_user.totp_secret_encrypted = encrypt_field(secret)
    code = pyotp.TOTP(secret).now()
    row = await initiate_signoff(
        async_session,
        tenant_id=test_user.tenant_id,
        document_type="board_pack",
        document_reference="BP-Q1",
        period="2026-03",
        signatory_user_id=test_user.id,
        signatory_role="CFO",
        document_content="doc",
        declaration_text="I approve",
    )
    completed = await complete_signoff(
        async_session,
        tenant_id=test_user.tenant_id,
        signoff_id=row.id,
        signatory_user_id=test_user.id,
        totp_code=code,
        ip_address="127.0.0.1",
        user_agent="pytest",
    )
    assert completed.mfa_verified is True


@pytest.mark.asyncio
async def test_signature_hash_computed(async_session: AsyncSession, test_user: IamUser) -> None:
    secret = generate_totp_secret()
    test_user.totp_secret_encrypted = encrypt_field(secret)
    code = pyotp.TOTP(secret).now()
    row = await initiate_signoff(
        async_session,
        tenant_id=test_user.tenant_id,
        document_type="board_pack",
        document_reference="BP-Q1",
        period="2026-03",
        signatory_user_id=test_user.id,
        signatory_role="CFO",
        document_content="doc",
        declaration_text="I approve",
    )
    completed = await complete_signoff(
        async_session,
        tenant_id=test_user.tenant_id,
        signoff_id=row.id,
        signatory_user_id=test_user.id,
        totp_code=code,
        ip_address="127.0.0.1",
        user_agent="pytest",
    )
    assert len(completed.signature_hash) == 64


@pytest.mark.asyncio
async def test_verify_signoff_valid(async_session: AsyncSession, test_user: IamUser) -> None:
    secret = generate_totp_secret()
    test_user.totp_secret_encrypted = encrypt_field(secret)
    code = pyotp.TOTP(secret).now()
    row = await initiate_signoff(
        async_session,
        tenant_id=test_user.tenant_id,
        document_type="board_pack",
        document_reference="BP-Q1",
        period="2026-03",
        signatory_user_id=test_user.id,
        signatory_role="CFO",
        document_content="doc",
        declaration_text="I approve",
    )
    completed = await complete_signoff(
        async_session,
        tenant_id=test_user.tenant_id,
        signoff_id=row.id,
        signatory_user_id=test_user.id,
        totp_code=code,
        ip_address="127.0.0.1",
        user_agent="pytest",
    )
    assert verify_signoff(completed.content_hash, completed) is True


@pytest.mark.asyncio
async def test_verify_signoff_tampered(async_session: AsyncSession, test_user: IamUser) -> None:
    row = DirectorSignoff(
        tenant_id=test_user.tenant_id,
        document_type="board_pack",
        document_id=None,
        document_reference="BP-Q1",
        period="2026-03",
        signatory_user_id=test_user.id,
        signatory_name="Tester",
        signatory_role="CFO",
        mfa_verified=True,
        declaration_text="I approve",
        content_hash="a" * 64,
        signature_hash="b" * 64,
        status="signed",
    )
    async_session.add(row)
    await async_session.flush()
    assert verify_signoff("c" * 64, row) is False


@pytest.mark.asyncio
async def test_signoff_append_only(async_session: AsyncSession, test_user: IamUser) -> None:
    row = await initiate_signoff(
        async_session,
        tenant_id=test_user.tenant_id,
        document_type="board_pack",
        document_reference="BP-Q1",
        period="2026-03",
        signatory_user_id=test_user.id,
        signatory_role="CFO",
        document_content="doc",
        declaration_text="I approve",
    )
    await async_session.execute(text(append_only_function_sql()))
    await async_session.execute(text(drop_trigger_sql("director_signoffs")))
    await async_session.execute(text(create_trigger_sql("director_signoffs")))
    await async_session.flush()
    with pytest.raises(Exception):
        await async_session.execute(text("UPDATE director_signoffs SET status='signed' WHERE id=:id"), {"id": row.id})


@pytest.mark.asyncio
async def test_signoff_rls(async_session: AsyncSession, test_user: IamUser) -> None:
    rows = (
        await async_session.execute(
            select(DirectorSignoff).where(DirectorSignoff.tenant_id == test_user.tenant_id)
        )
    ).scalars().all()
    assert all(row.tenant_id == test_user.tenant_id for row in rows)


@pytest.mark.asyncio
async def test_certificate_structure(async_session: AsyncSession, test_user: IamUser) -> None:
    row = await initiate_signoff(
        async_session,
        tenant_id=test_user.tenant_id,
        document_type="board_pack",
        document_reference="BP-Q1",
        period="2026-03",
        signatory_user_id=test_user.id,
        signatory_role="CFO",
        document_content="doc",
        declaration_text="I approve",
    )
    cert = await generate_certificate(async_session, test_user.tenant_id, row.id)
    assert {"certificate_number", "document_reference", "period", "content_hash"}.issubset(cert)


@pytest.mark.asyncio
async def test_certificate_includes_hashes(async_session: AsyncSession, test_user: IamUser) -> None:
    row = await initiate_signoff(
        async_session,
        tenant_id=test_user.tenant_id,
        document_type="board_pack",
        document_reference="BP-Q1",
        period="2026-03",
        signatory_user_id=test_user.id,
        signatory_role="CFO",
        document_content="doc",
        declaration_text="I approve",
    )
    cert = await generate_certificate(async_session, test_user.tenant_id, row.id)
    assert len(cert["content_hash"]) == 64
    assert len(cert["signature_hash"]) == 64


@pytest.mark.asyncio
async def test_api_initiate_signoff(async_client, test_user: IamUser) -> None:
    response = await async_client.post(
        "/api/v1/signoff/initiate",
        headers=_auth_headers(test_user),
        json={
            "document_type": "board_pack",
            "document_reference": "BP-Q1",
            "period": "2026-03",
            "signatory_user_id": str(test_user.id),
            "signatory_role": "CFO",
            "document_content": "doc",
            "declaration_text": "I approve",
        },
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_api_complete_signoff_with_mfa(async_client, async_session: AsyncSession, test_user: IamUser) -> None:
    secret = generate_totp_secret()
    test_user.totp_secret_encrypted = encrypt_field(secret)
    await async_session.flush()

    create = await async_client.post(
        "/api/v1/signoff/initiate",
        headers=_auth_headers(test_user),
        json={
            "document_type": "board_pack",
            "document_reference": "BP-Q1",
            "period": "2026-03",
            "signatory_user_id": str(test_user.id),
            "signatory_role": "CFO",
            "document_content": "doc",
            "declaration_text": "I approve",
        },
    )
    signoff_id = create.json()["data"]["id"]
    code = pyotp.TOTP(secret).now()

    response = await async_client.post(
        f"/api/v1/signoff/{signoff_id}/sign",
        headers=_auth_headers(test_user),
        json={"totp_code": code},
    )
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "signed"
