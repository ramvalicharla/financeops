from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.security import create_access_token, hash_password
from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql
from financeops.db.models.tenants import IamTenant, TenantStatus, TenantType
from financeops.db.models.users import IamSession, IamUser, UserRole
from financeops.modules.compliance.gdpr_models import GDPRBreachRecord, GDPRConsentRecord, GDPRDataRequest
from financeops.modules.compliance.gdpr_service import (
    export_user_data,
    get_consent_summary,
    record_breach,
    record_consent,
    run_retention_check,
)
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


# Portability (4)
@pytest.mark.asyncio
async def test_export_user_data_structure(async_session: AsyncSession, test_user: IamUser) -> None:
    payload = await export_user_data(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        requested_by=test_user.id,
    )
    for key in ["requested_at", "user", "expense_claims", "checklist_tasks", "compliance_events", "consent_records", "erasure_log", "request_id"]:
        assert key in payload


@pytest.mark.asyncio
async def test_export_excludes_passwords(async_session: AsyncSession, test_user: IamUser) -> None:
    payload = await export_user_data(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        requested_by=test_user.id,
    )
    dumped = str(payload)
    assert "hashed_password" not in dumped
    assert "totp_secret" not in dumped


@pytest.mark.asyncio
async def test_export_creates_data_request_record(async_session: AsyncSession, test_user: IamUser) -> None:
    await export_user_data(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        requested_by=test_user.id,
    )
    count = (
        await async_session.execute(
            select(func.count()).select_from(GDPRDataRequest).where(
                GDPRDataRequest.tenant_id == test_user.tenant_id,
                GDPRDataRequest.user_id == test_user.id,
                GDPRDataRequest.request_type == "portability",
            )
        )
    ).scalar_one()
    assert int(count) >= 1


@pytest.mark.asyncio
async def test_export_tenant_isolation(async_session: AsyncSession, test_user: IamUser) -> None:
    other_tenant = uuid.uuid4()
    other_user = await _create_user(
        async_session,
        tenant_id=other_tenant,
        email="other-export@example.com",
        role=UserRole.employee,
    )
    with pytest.raises(ValueError):
        await export_user_data(
            async_session,
            tenant_id=test_user.tenant_id,
            user_id=other_user.id,
            requested_by=test_user.id,
        )


# Consent (5)
@pytest.mark.asyncio
async def test_record_consent_granted(async_session: AsyncSession, test_user: IamUser) -> None:
    row = await record_consent(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        consent_type="analytics",
        granted=True,
    )
    assert row.granted is True
    assert row.granted_at is not None


@pytest.mark.asyncio
async def test_record_consent_withdrawn(async_session: AsyncSession, test_user: IamUser) -> None:
    await record_consent(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        consent_type="analytics",
        granted=True,
    )
    row = await record_consent(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        consent_type="analytics",
        granted=False,
    )
    assert row.granted is False
    assert row.withdrawn_at is not None


@pytest.mark.asyncio
async def test_consent_upsert_not_duplicate(async_session: AsyncSession, test_user: IamUser) -> None:
    await record_consent(async_session, test_user.tenant_id, test_user.id, "marketing", True)
    await record_consent(async_session, test_user.tenant_id, test_user.id, "marketing", False)
    rows = (
        await async_session.execute(
            select(GDPRConsentRecord).where(
                GDPRConsentRecord.tenant_id == test_user.tenant_id,
                GDPRConsentRecord.user_id == test_user.id,
                GDPRConsentRecord.consent_type == "marketing",
            )
        )
    ).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_consent_summary_coverage_pct_is_decimal(async_session: AsyncSession, test_user: IamUser) -> None:
    await record_consent(async_session, test_user.tenant_id, test_user.id, "analytics", True)
    summary = await get_consent_summary(async_session, test_user.tenant_id)
    analytics_row = next(row for row in summary["consent"] if row["consent_type"] == "analytics")
    assert isinstance(analytics_row["coverage_pct"], Decimal)


@pytest.mark.asyncio
async def test_data_request_is_append_only(async_session: AsyncSession, test_user: IamUser) -> None:
    payload = await export_user_data(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        requested_by=test_user.id,
    )
    request_id = payload["request_id"]

    await async_session.execute(text(append_only_function_sql()))
    await async_session.execute(text(drop_trigger_sql("gdpr_data_requests")))
    await async_session.execute(text(create_trigger_sql("gdpr_data_requests")))
    await async_session.flush()

    with pytest.raises(Exception):
        await async_session.execute(
            text("UPDATE gdpr_data_requests SET status = 'rejected' WHERE id = :id"),
            {"id": request_id},
        )


# Breach (4)
@pytest.mark.asyncio
async def test_record_breach_creates_record(async_session: AsyncSession, test_user: IamUser) -> None:
    row = await record_breach(
        async_session,
        tenant_id=test_user.tenant_id,
        breach_data={
            "breach_type": "data_loss",
            "description": "Disk corruption",
            "affected_user_count": 0,
            "affected_data_types": ["logs"],
            "discovered_at": datetime.now(UTC),
            "severity": "low",
        },
        created_by=test_user.id,
    )
    assert row.id is not None


@pytest.mark.asyncio
async def test_breach_is_append_only(async_session: AsyncSession, test_user: IamUser) -> None:
    row = await record_breach(
        async_session,
        tenant_id=test_user.tenant_id,
        breach_data={
            "breach_type": "other",
            "description": "Incident",
            "affected_user_count": 1,
            "affected_data_types": ["pii"],
            "discovered_at": datetime.now(UTC),
            "severity": "medium",
        },
        created_by=test_user.id,
    )

    await async_session.execute(text(append_only_function_sql()))
    await async_session.execute(text(drop_trigger_sql("gdpr_breach_records")))
    await async_session.execute(text(create_trigger_sql("gdpr_breach_records")))
    await async_session.flush()

    with pytest.raises(Exception):
        await async_session.execute(
            text("UPDATE gdpr_breach_records SET status = 'closed' WHERE id = :id"),
            {"id": row.id},
        )


@pytest.mark.asyncio
async def test_critical_breach_creates_notification_task(async_session: AsyncSession, test_user: IamUser, monkeypatch) -> None:
    sent: list[tuple[str, dict[str, str], int]] = []

    def _fake_send_task(name: str, kwargs: dict[str, str], countdown: int) -> None:
        sent.append((name, kwargs, countdown))

    monkeypatch.setattr("financeops.modules.compliance.gdpr_service.celery_app.send_task", _fake_send_task)

    await record_breach(
        async_session,
        tenant_id=test_user.tenant_id,
        breach_data={
            "breach_type": "unauthorized_access",
            "description": "Critical incident",
            "affected_user_count": 5,
            "affected_data_types": ["pii"],
            "discovered_at": datetime.now(UTC),
            "severity": "critical",
        },
        created_by=test_user.id,
    )
    assert sent
    assert sent[0][0] == "gdpr.notify_dpa_reminder"


@pytest.mark.asyncio
async def test_low_severity_no_notification(async_session: AsyncSession, test_user: IamUser, monkeypatch) -> None:
    sent: list[str] = []

    def _fake_send_task(name: str, kwargs: dict[str, str], countdown: int) -> None:
        del kwargs, countdown
        sent.append(name)

    monkeypatch.setattr("financeops.modules.compliance.gdpr_service.celery_app.send_task", _fake_send_task)

    await record_breach(
        async_session,
        tenant_id=test_user.tenant_id,
        breach_data={
            "breach_type": "accidental_disclosure",
            "description": "Low incident",
            "affected_user_count": 1,
            "affected_data_types": ["metadata"],
            "discovered_at": datetime.now(UTC),
            "severity": "low",
        },
        created_by=test_user.id,
    )
    assert sent == []


# Retention (4)
@pytest.mark.asyncio
async def test_retention_check_structure(async_session: AsyncSession, test_user: IamUser) -> None:
    payload = await run_retention_check(async_session, test_user.tenant_id)
    assert "sessions_purged" in payload
    assert "audit_records_approaching_retention_limit" in payload


@pytest.mark.asyncio
async def test_expired_sessions_purged(async_session: AsyncSession, test_user: IamUser) -> None:
    old_session = IamSession(
        user_id=test_user.id,
        tenant_id=test_user.tenant_id,
        refresh_token_hash="old-token",
        expires_at=datetime.now(UTC) + timedelta(days=2),
        created_at=datetime.now(UTC) - timedelta(days=120),
    )
    async_session.add(old_session)
    await async_session.flush()

    payload = await run_retention_check(async_session, test_user.tenant_id)
    assert payload["sessions_purged"] >= 1


@pytest.mark.asyncio
async def test_recent_sessions_not_purged(async_session: AsyncSession, test_user: IamUser) -> None:
    recent_session = IamSession(
        user_id=test_user.id,
        tenant_id=test_user.tenant_id,
        refresh_token_hash="recent-token",
        expires_at=datetime.now(UTC) + timedelta(days=2),
        created_at=datetime.now(UTC) - timedelta(days=5),
    )
    async_session.add(recent_session)
    await async_session.flush()

    payload = await run_retention_check(async_session, test_user.tenant_id)
    assert payload["sessions_purged"] == 0


@pytest.mark.asyncio
async def test_retention_counts_are_integers(async_session: AsyncSession, test_user: IamUser) -> None:
    payload = await run_retention_check(async_session, test_user.tenant_id)
    assert isinstance(payload["sessions_purged"], int)
    assert isinstance(payload["audit_records_approaching_retention_limit"], int)


# API (3)
@pytest.mark.asyncio
async def test_export_endpoint_own_data(async_client, test_user: IamUser) -> None:
    response = await async_client.post(
        "/api/v1/compliance/gdpr/export",
        headers=_auth_headers(test_user),
        json={},
    )
    assert response.status_code == 200
    assert "request_id" in response.json()["data"]


@pytest.mark.asyncio
async def test_consent_endpoint(async_client, test_user: IamUser) -> None:
    response = await async_client.post(
        "/api/v1/compliance/gdpr/consent",
        headers=_auth_headers(test_user),
        json={"consent_type": "analytics", "granted": True, "lawful_basis": "consent"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["consent_type"] == "analytics"


@pytest.mark.asyncio
async def test_breach_requires_finance_leader(async_session: AsyncSession, async_client, test_user: IamUser) -> None:
    team_user = await _create_user(
        async_session,
        tenant_id=test_user.tenant_id,
        email="team-breach@example.com",
        role=UserRole.finance_team,
    )
    response = await async_client.post(
        "/api/v1/compliance/gdpr/breach",
        headers=_auth_headers(team_user),
        json={
            "breach_type": "other",
            "description": "Denied attempt",
            "affected_user_count": 0,
            "affected_data_types": [],
            "discovered_at": datetime.now(UTC).isoformat(),
            "severity": "low",
        },
    )
    assert response.status_code == 403
