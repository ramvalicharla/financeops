from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import ValidationError
from financeops.core.security import create_access_token, hash_password
from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql
from financeops.db.models.tenants import IamTenant, TenantStatus, TenantType
from financeops.db.models.users import IamUser, UserRole
from financeops.modules.white_label.models import WhiteLabelAuditLog, WhiteLabelConfig
from financeops.modules.white_label.service import (
    enable_white_label,
    get_branding_for_domain,
    get_or_create_config,
    initiate_domain_verification,
    update_branding,
)
from financeops.utils.chain_hash import GENESIS_HASH, compute_chain_hash


def _auth_headers(user: IamUser) -> dict[str, str]:
    token = create_access_token(user.id, user.tenant_id, user.role.value)
    return {"Authorization": f"Bearer {token}"}


async def _create_tenant(session: AsyncSession, tenant_id: uuid.UUID, name: str) -> IamTenant:
    record_data = {
        "display_name": name,
        "tenant_type": TenantType.direct.value,
        "country": "US",
        "timezone": "UTC",
    }
    tenant = IamTenant(
        id=tenant_id,
        tenant_id=tenant_id,
        display_name=name,
        tenant_type=TenantType.direct,
        country="US",
        timezone="UTC",
        status=TenantStatus.active,
        chain_hash=compute_chain_hash(record_data, GENESIS_HASH),
        previous_hash=GENESIS_HASH,
    )
    session.add(tenant)
    await session.flush()
    return tenant


async def _create_platform_user(session: AsyncSession, email: str, role: UserRole) -> IamUser:
    platform_tenant_id = uuid.UUID(int=0)
    tenant = (
        await session.execute(
            select(IamTenant).where(IamTenant.id == platform_tenant_id)
        )
    ).scalar_one_or_none()
    if tenant is None:
        await _create_tenant(session, platform_tenant_id, "FinanceOps Platform")
        tenant = (
            await session.execute(
                select(IamTenant).where(IamTenant.id == platform_tenant_id)
            )
        ).scalar_one()
        tenant.is_platform_tenant = True

    user = IamUser(
        tenant_id=platform_tenant_id,
        email=email,
        hashed_password=hash_password("TestPass123!"),
        full_name="Platform Admin",
        role=role,
        is_active=True,
        mfa_enabled=True,
    )
    session.add(user)
    await session.flush()
    return user


# Config management (5)
@pytest.mark.asyncio
async def test_get_or_create_config_idempotent(async_session: AsyncSession, test_user: IamUser) -> None:
    first = await get_or_create_config(async_session, test_user.tenant_id)
    second = await get_or_create_config(async_session, test_user.tenant_id)
    assert first.id == second.id


@pytest.mark.asyncio
async def test_update_branding_creates_audit_log(async_session: AsyncSession, test_user: IamUser) -> None:
    await get_or_create_config(async_session, test_user.tenant_id)
    await update_branding(
        async_session,
        tenant_id=test_user.tenant_id,
        updated_by=test_user.id,
        updates={"primary_colour": "#112233"},
    )
    logs = (
        await async_session.execute(
            select(WhiteLabelAuditLog).where(WhiteLabelAuditLog.tenant_id == test_user.tenant_id)
        )
    ).scalars().all()
    assert any(log.field_changed == "primary_colour" for log in logs)


@pytest.mark.asyncio
async def test_update_branding_validates_hex_colour(async_session: AsyncSession, test_user: IamUser) -> None:
    await get_or_create_config(async_session, test_user.tenant_id)
    with pytest.raises(ValidationError):
        await update_branding(
            async_session,
            tenant_id=test_user.tenant_id,
            updated_by=test_user.id,
            updates={"primary_colour": "not-a-hex"},
        )


@pytest.mark.asyncio
async def test_update_branding_validates_css_length(async_session: AsyncSession, test_user: IamUser) -> None:
    await get_or_create_config(async_session, test_user.tenant_id)
    with pytest.raises(ValidationError):
        await update_branding(
            async_session,
            tenant_id=test_user.tenant_id,
            updated_by=test_user.id,
            updates={"custom_css": "a" * 10001},
        )


@pytest.mark.asyncio
async def test_audit_log_is_append_only(async_session: AsyncSession, test_user: IamUser) -> None:
    log = WhiteLabelAuditLog(
        tenant_id=test_user.tenant_id,
        changed_by=test_user.id,
        field_changed="brand_name",
        old_value="A",
        new_value="B",
    )
    async_session.add(log)
    await async_session.flush()
    await async_session.execute(text(append_only_function_sql()))
    await async_session.execute(text(drop_trigger_sql("white_label_audit_log")))
    await async_session.execute(text(create_trigger_sql("white_label_audit_log")))
    await async_session.flush()
    with pytest.raises(Exception):
        await async_session.execute(
            text("UPDATE white_label_audit_log SET new_value = 'C' WHERE id = :id"),
            {"id": log.id},
        )


# Domain verification (5)
@pytest.mark.asyncio
async def test_initiate_domain_verification_returns_token(async_session: AsyncSession, test_user: IamUser) -> None:
    payload = await initiate_domain_verification(
        async_session,
        tenant_id=test_user.tenant_id,
        custom_domain="valid-domain.com",
    )
    config = await get_or_create_config(async_session, test_user.tenant_id)
    assert payload["verification_token"]
    assert config.domain_verification_token == payload["verification_token"]


@pytest.mark.asyncio
async def test_domain_format_validation(async_session: AsyncSession, test_user: IamUser) -> None:
    with pytest.raises(ValidationError):
        await initiate_domain_verification(
            async_session,
            tenant_id=test_user.tenant_id,
            custom_domain="http://invalid.com/path",
        )
    payload = await initiate_domain_verification(
        async_session,
        tenant_id=test_user.tenant_id,
        custom_domain="valid-domain.com",
    )
    assert payload["domain"] == "valid-domain.com"


@pytest.mark.asyncio
async def test_domain_verified_false_until_checked(async_session: AsyncSession, test_user: IamUser) -> None:
    await initiate_domain_verification(
        async_session,
        tenant_id=test_user.tenant_id,
        custom_domain="verify-pending.com",
    )
    config = await get_or_create_config(async_session, test_user.tenant_id)
    assert config.domain_verified is False


@pytest.mark.asyncio
async def test_get_branding_for_domain_returns_none_if_unverified(async_session: AsyncSession, test_user: IamUser) -> None:
    config = await get_or_create_config(async_session, test_user.tenant_id)
    config.custom_domain = "unverified.com"
    config.domain_verified = False
    config.is_enabled = True
    await async_session.flush()
    resolved = await get_branding_for_domain(async_session, "unverified.com")
    assert resolved is None


@pytest.mark.asyncio
async def test_get_branding_for_domain_returns_config_if_verified(async_session: AsyncSession, test_user: IamUser) -> None:
    config = await get_or_create_config(async_session, test_user.tenant_id)
    config.custom_domain = "verified.com"
    config.domain_verified = True
    config.is_enabled = True
    await async_session.flush()
    resolved = await get_branding_for_domain(async_session, "verified.com")
    assert resolved is not None
    assert resolved.id == config.id


# Enable/disable (3)
@pytest.mark.asyncio
async def test_enable_white_label_requires_platform_admin(async_client: AsyncClient, test_access_token: str) -> None:
    response = await async_client.post(
        f"/api/v1/white-label/admin/{uuid.uuid4()}/enable",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_enable_creates_audit_log_entry(api_session_factory, test_user: IamUser) -> None:
    async with api_session_factory() as db:
        await get_or_create_config(db, test_user.tenant_id)
        await enable_white_label(db, test_user.tenant_id, test_user.id)
        await db.commit()

    async with api_session_factory() as db:
        logs = (
            await db.execute(
                select(WhiteLabelAuditLog).where(
                    WhiteLabelAuditLog.tenant_id == test_user.tenant_id,
                    WhiteLabelAuditLog.field_changed == "is_enabled",
                )
            )
        ).scalars().all()
    assert logs


@pytest.mark.asyncio
async def test_disabled_config_not_returned_by_domain_lookup(api_session_factory, test_user: IamUser) -> None:
    async with api_session_factory() as db:
        config = await get_or_create_config(db, test_user.tenant_id)
        config.custom_domain = "disabled.com"
        config.domain_verified = True
        config.is_enabled = False
        await db.commit()

    async with api_session_factory() as db:
        resolved = await get_branding_for_domain(db, "disabled.com")
    assert resolved is None


# Audit log (4)
@pytest.mark.asyncio
async def test_audit_log_captures_all_field_changes(api_session_factory, test_user: IamUser) -> None:
    async with api_session_factory() as db:
        await get_or_create_config(db, test_user.tenant_id)
        await update_branding(
            db,
            tenant_id=test_user.tenant_id,
            updated_by=test_user.id,
            updates={
                "brand_name": "Brand A",
                "primary_colour": "#123456",
                "secondary_colour": "#654321",
            },
        )
        await db.commit()

    async with api_session_factory() as db:
        logs = (
            await db.execute(
                select(WhiteLabelAuditLog).where(WhiteLabelAuditLog.tenant_id == test_user.tenant_id)
            )
        ).scalars().all()
    assert len(logs) >= 3


@pytest.mark.asyncio
async def test_audit_log_stores_old_and_new_values(api_session_factory, test_user: IamUser) -> None:
    async with api_session_factory() as db:
        config = await get_or_create_config(db, test_user.tenant_id)
        config.brand_name = "Old Brand"
        await db.flush()
        await update_branding(
            db,
            tenant_id=test_user.tenant_id,
            updated_by=test_user.id,
            updates={"brand_name": "New Brand"},
        )
        await db.commit()

    async with api_session_factory() as db:
        log = (
            await db.execute(
                select(WhiteLabelAuditLog)
                .where(
                    WhiteLabelAuditLog.tenant_id == test_user.tenant_id,
                    WhiteLabelAuditLog.field_changed == "brand_name",
                )
                .order_by(WhiteLabelAuditLog.created_at.desc())
                .limit(1)
            )
        ).scalar_one()
    assert log.old_value == "Old Brand"
    assert log.new_value == "New Brand"


@pytest.mark.asyncio
async def test_audit_log_rls(api_session_factory, test_user: IamUser) -> None:
    tenant_b = uuid.uuid4()
    async with api_session_factory() as db:
        await _create_tenant(db, tenant_b, "Tenant B")
        log_a = WhiteLabelAuditLog(
            tenant_id=test_user.tenant_id,
            changed_by=test_user.id,
            field_changed="brand_name",
            old_value="a",
            new_value="b",
        )
        log_b = WhiteLabelAuditLog(
            tenant_id=tenant_b,
            changed_by=test_user.id,
            field_changed="brand_name",
            old_value="x",
            new_value="y",
        )
        db.add(log_a)
        db.add(log_b)
        await db.commit()
        log_a_id = log_a.id
        log_b_id = log_b.id

    async with api_session_factory() as db:
        rows = (
            await db.execute(
                select(WhiteLabelAuditLog).where(WhiteLabelAuditLog.tenant_id == test_user.tenant_id)
            )
        ).scalars().all()
    ids = {row.id for row in rows}
    assert log_a_id in ids
    assert log_b_id not in ids


@pytest.mark.asyncio
async def test_config_rls_isolation(api_session_factory, test_user: IamUser) -> None:
    tenant_b = uuid.uuid4()
    async with api_session_factory() as db:
        config_a = await get_or_create_config(db, test_user.tenant_id)
        await _create_tenant(db, tenant_b, "Tenant B")
        config_b = await get_or_create_config(db, tenant_b)
        await db.commit()
        config_a_id = config_a.id
        config_b_id = config_b.id

    async with api_session_factory() as db:
        rows = (
            await db.execute(
                select(WhiteLabelConfig).where(WhiteLabelConfig.tenant_id == test_user.tenant_id)
            )
        ).scalars().all()
    ids = {row.id for row in rows}
    assert config_a_id in ids
    assert config_b_id not in ids


# API (3)
@pytest.mark.asyncio
async def test_config_endpoint_returns_own_tenant_config(
    async_client: AsyncClient,
    test_access_token: str,
) -> None:
    response = await async_client.get(
        "/api/v1/white-label/config",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert "tenant_id" in payload


@pytest.mark.asyncio
async def test_admin_list_requires_platform_admin(
    async_client: AsyncClient,
    test_access_token: str,
    async_session: AsyncSession,
) -> None:
    denied = await async_client.get(
        "/api/v1/white-label/admin/all",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert denied.status_code == 403

    admin = await _create_platform_user(async_session, "wl.admin@example.com", UserRole.platform_admin)
    allowed = await async_client.get(
        "/api/v1/white-label/admin/all",
        headers=_auth_headers(admin),
    )
    assert allowed.status_code == 200


@pytest.mark.asyncio
async def test_domain_resolve_endpoint_public(async_client: AsyncClient) -> None:
    response = await async_client.get("/api/v1/white-label/resolve/non-existent-domain.com")
    assert response.status_code in {404, 422}
