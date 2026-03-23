from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.security import create_access_token, hash_password
from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql
from financeops.db.models.tenants import IamTenant, TenantStatus, TenantType
from financeops.db.models.users import IamUser, UserRole
from financeops.modules.compliance.iso27001_controls import ISO27001_CONTROLS
from financeops.modules.compliance.iso27001_service import (
    ISO_AUTO_CHECKS,
    check_a10_1_1_encryption,
    check_a12_4_1_chain_hash,
    get_iso27001_dashboard,
    get_iso27001_evidence_package,
    run_auto_evaluation,
)
from financeops.modules.compliance.models import ComplianceControl, ComplianceEvent
from financeops.modules.compliance.soc2_service import check_cc6_6_mfa
from financeops.utils.chain_hash import GENESIS_HASH, compute_chain_hash


def _auth_headers(user: IamUser) -> dict[str, str]:
    token = create_access_token(user.id, user.tenant_id, user.role.value)
    return {"Authorization": f"Bearer {token}"}


async def _create_user(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    email: str,
    role: UserRole,
) -> IamUser:
    existing_tenant = await session.get(IamTenant, tenant_id)
    if existing_tenant is None:
        tenant = IamTenant(
            id=tenant_id,
            tenant_id=tenant_id,
            display_name=f"Tenant-{str(tenant_id)[:8]}",
            tenant_type=TenantType.direct,
            country="US",
            timezone="UTC",
            status=TenantStatus.active,
            chain_hash=compute_chain_hash(
                {
                    "display_name": f"Tenant-{str(tenant_id)[:8]}",
                    "tenant_type": TenantType.direct.value,
                    "country": "US",
                    "timezone": "UTC",
                },
                GENESIS_HASH,
            ),
            previous_hash=GENESIS_HASH,
        )
        session.add(tenant)
        await session.flush()

    user = IamUser(
        tenant_id=tenant_id,
        email=email,
        hashed_password=hash_password("TestPass123!"),
        full_name=email.split("@")[0],
        role=role,
        is_active=True,
        mfa_enabled=True,
    )
    session.add(user)
    await session.flush()
    return user


def test_iso27001_controls_count() -> None:
    assert len(ISO27001_CONTROLS) == 35


def test_all_iso27001_have_required_fields() -> None:
    for control in ISO27001_CONTROLS:
        assert control["control_id"]
        assert control["control_name"]
        assert control["category"]
        assert "auto_evaluable" in control


def test_iso27001_ids_unique() -> None:
    ids = [control["control_id"] for control in ISO27001_CONTROLS]
    assert len(ids) == len(set(ids))


def test_auto_evaluable_iso_have_check_function() -> None:
    for control in ISO27001_CONTROLS:
        if control["auto_evaluable"]:
            assert control["auto_check_function"] is not None


@pytest.mark.asyncio
async def test_run_iso_auto_evaluation(async_session: AsyncSession, test_user: IamUser) -> None:
    result = await run_auto_evaluation(async_session, test_user.tenant_id)
    assert result["total"] == 8
    assert result["passed"] + result["failed"] == 8


@pytest.mark.asyncio
async def test_a9_4_2_reuses_soc2_mfa_check(async_session: AsyncSession, test_user: IamUser) -> None:
    iso_fn = ISO_AUTO_CHECKS["check_cc6_6_mfa"]
    assert iso_fn is check_cc6_6_mfa

    iso_result = await iso_fn(async_session, test_user.tenant_id)
    soc_result = await check_cc6_6_mfa(async_session, test_user.tenant_id)
    assert iso_result == soc_result


@pytest.mark.asyncio
async def test_a10_1_1_encryption_check_passes(async_session: AsyncSession, test_user: IamUser) -> None:
    ok, _ = await check_a10_1_1_encryption(async_session, test_user.tenant_id)
    assert ok is True


@pytest.mark.asyncio
async def test_a12_4_1_chain_hash_check(async_session: AsyncSession, test_user: IamUser) -> None:
    ok, _ = await check_a12_4_1_chain_hash(async_session, test_user.tenant_id)
    assert ok is True


@pytest.mark.asyncio
async def test_iso_compliance_events_append_only(async_session: AsyncSession, test_user: IamUser) -> None:
    await run_auto_evaluation(async_session, test_user.tenant_id)
    event = (
        await async_session.execute(
            select(ComplianceEvent)
            .where(
                ComplianceEvent.tenant_id == test_user.tenant_id,
                ComplianceEvent.framework == "ISO27001",
            )
            .order_by(ComplianceEvent.created_at.desc())
            .limit(1)
        )
    ).scalar_one()

    await async_session.execute(text(append_only_function_sql()))
    await async_session.execute(text(drop_trigger_sql("compliance_events")))
    await async_session.execute(text(create_trigger_sql("compliance_events")))
    await async_session.flush()

    with pytest.raises(Exception):
        await async_session.execute(
            text("UPDATE compliance_events SET notes = 'mutated' WHERE id = :id"),
            {"id": event.id},
        )


@pytest.mark.asyncio
async def test_iso_dashboard_structure(async_session: AsyncSession, test_user: IamUser) -> None:
    payload = await get_iso27001_dashboard(async_session, test_user.tenant_id)
    for key in ["overall_rag", "last_evaluated", "summary", "controls_by_category", "recently_failed", "upcoming_evaluations"]:
        assert key in payload


@pytest.mark.asyncio
async def test_iso_evidence_package_structure(async_session: AsyncSession, test_user: IamUser) -> None:
    payload = await get_iso27001_evidence_package(async_session, test_user.tenant_id)
    assert payload["framework"] == "ISO27001"
    assert "generated_at" in payload
    assert isinstance(payload["controls"], list)


@pytest.mark.asyncio
async def test_iso_controls_seeded_for_tenant(async_session: AsyncSession, test_user: IamUser) -> None:
    await get_iso27001_dashboard(async_session, test_user.tenant_id)
    count = (
        await async_session.execute(
            select(func.count()).select_from(ComplianceControl).where(
                ComplianceControl.tenant_id == test_user.tenant_id,
                ComplianceControl.framework == "ISO27001",
            )
        )
    ).scalar_one()
    assert int(count) == 35


@pytest.mark.asyncio
async def test_iso_manual_status_update_requires_platform_admin(async_client, test_user: IamUser) -> None:
    denied = await async_client.patch(
        "/api/v1/compliance/iso27001/controls/A.5.1.1/status",
        headers=_auth_headers(test_user),
        json={"status": "pass", "notes": "manual"},
    )
    assert denied.status_code == 403


@pytest.mark.asyncio
async def test_iso_status_update_creates_event(async_session: AsyncSession, async_client, test_user: IamUser) -> None:
    await get_iso27001_dashboard(async_session, test_user.tenant_id)
    admin = await _create_user(
        async_session,
        tenant_id=test_user.tenant_id,
        email="iso-admin@example.com",
        role=UserRole.super_admin,
    )
    response = await async_client.patch(
        "/api/v1/compliance/iso27001/controls/A.5.1.1/status",
        headers=_auth_headers(admin),
        json={"status": "pass", "notes": "manual update"},
    )
    assert response.status_code == 200
    events = (
        await async_session.execute(
            select(ComplianceEvent).where(
                ComplianceEvent.tenant_id == test_user.tenant_id,
                ComplianceEvent.framework == "ISO27001",
                ComplianceEvent.control_id == "A.5.1.1",
            )
        )
    ).scalars().all()
    assert events


@pytest.mark.asyncio
async def test_tenant_isolation_iso_controls(async_session: AsyncSession, test_user: IamUser) -> None:
    await get_iso27001_dashboard(async_session, test_user.tenant_id)
    other_tenant = uuid.uuid4()
    user_other = await _create_user(
        async_session,
        tenant_id=other_tenant,
        email="iso-other@example.com",
        role=UserRole.finance_leader,
    )
    await get_iso27001_dashboard(async_session, user_other.tenant_id)

    controls = (
        await async_session.execute(
            select(ComplianceControl).where(
                ComplianceControl.tenant_id == test_user.tenant_id,
                ComplianceControl.framework == "ISO27001",
            )
        )
    ).scalars().all()
    assert controls
    assert all(control.tenant_id == test_user.tenant_id for control in controls)
