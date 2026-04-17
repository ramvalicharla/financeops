from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.security import create_access_token, hash_password
from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql
from financeops.db.models.users import IamUser, UserRole
from financeops.modules.compliance.models import ComplianceControl, ComplianceEvent
from financeops.modules.compliance.soc2_controls import SOC2_CONTROLS
from financeops.modules.compliance.soc2_service import (
    check_cc6_1_rls,
    check_cc6_6_mfa,
    check_cc7_1_clamav,
    get_soc2_dashboard,
    get_soc2_evidence_package,
    run_auto_evaluation,
    set_control_status,
)


def _auth_headers(user: IamUser) -> dict[str, str]:
    token = create_access_token(user.id, user.tenant_id, user.role.value)
    return {"Authorization": f"Bearer {token}"}


async def _create_user(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    email: str,
    role: UserRole,
    mfa_enabled: bool,
) -> IamUser:
    user = IamUser(
        tenant_id=tenant_id,
        email=email,
        hashed_password=hash_password("TestPass123!"),
        full_name=email.split("@")[0],
        role=role,
        is_active=True,
        mfa_enabled=mfa_enabled,
    )
    session.add(user)
    await session.flush()
    return user


# Control definitions (4)
def test_soc2_controls_count() -> None:
    assert len(SOC2_CONTROLS) == 47


def test_all_soc2_have_required_fields() -> None:
    for control in SOC2_CONTROLS:
        assert control["control_id"]
        assert control["control_name"]
        assert control["category"]
        assert "auto_evaluable" in control


def test_auto_evaluable_have_check_function() -> None:
    for control in SOC2_CONTROLS:
        if control["auto_evaluable"]:
            assert control["auto_check_function"] is not None


def test_soc2_control_ids_unique() -> None:
    ids = [control["control_id"] for control in SOC2_CONTROLS]
    assert len(ids) == len(set(ids))


# Auto-evaluation (8)
@pytest.mark.asyncio
async def test_run_auto_evaluation_returns_counts(api_session_factory, test_user: IamUser) -> None:
    async with api_session_factory() as db:
        payload = await run_auto_evaluation(db, test_user.tenant_id)
    assert payload["total"] == 7
    assert payload["passed"] + payload["failed"] == payload["total"]


@pytest.mark.asyncio
async def test_cc6_1_rls_check_passes(api_session_factory, test_user: IamUser) -> None:
    async with api_session_factory() as db:
        await db.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS _soc2_rls_probe (
                  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                  tenant_id uuid NOT NULL
                )
                """
            )
        )
        await db.execute(text("ALTER TABLE _soc2_rls_probe ENABLE ROW LEVEL SECURITY"))
        await db.execute(
            text(
                """
                DO $$
                BEGIN
                  IF NOT EXISTS (
                    SELECT 1 FROM pg_policies
                    WHERE schemaname = 'public'
                      AND tablename = '_soc2_rls_probe'
                      AND policyname = 'tenant_isolation'
                  ) THEN
                    CREATE POLICY tenant_isolation ON _soc2_rls_probe USING (true);
                  END IF;
                END $$;
                """
            )
        )
        ok, _ = await check_cc6_1_rls(db, test_user.tenant_id)
    assert ok is True


@pytest.mark.asyncio
async def test_cc6_6_mfa_fails_when_finance_leader_no_mfa(api_session_factory, test_user: IamUser) -> None:
    async with api_session_factory() as db:
        user = await db.get(IamUser, test_user.id)
        assert user is not None
        user.mfa_enabled = False
        await db.flush()
        ok, _ = await check_cc6_6_mfa(db, test_user.tenant_id)
    assert ok is False


@pytest.mark.asyncio
async def test_cc6_6_mfa_passes_when_all_have_mfa(api_session_factory, test_user: IamUser) -> None:
    async with api_session_factory() as db:
        user = await db.get(IamUser, test_user.id)
        assert user is not None
        user.mfa_enabled = True
        await db.flush()
        ok, _ = await check_cc6_6_mfa(db, test_user.tenant_id)
    assert ok is True


@pytest.mark.asyncio
async def test_cc7_1_clamav_check_passes_when_required_true(
    async_session: AsyncSession,
    test_user: IamUser,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("financeops.modules.compliance.soc2_service.settings.CLAMAV_REQUIRED", True)
    ok, _ = await check_cc7_1_clamav(async_session, test_user.tenant_id)
    assert ok is True


@pytest.mark.asyncio
async def test_auto_evaluation_creates_compliance_events(api_session_factory, test_user: IamUser) -> None:
    async with api_session_factory() as db:
        await run_auto_evaluation(db, test_user.tenant_id)
        count = (
            await db.execute(
                select(func.count()).select_from(ComplianceEvent).where(
                    ComplianceEvent.tenant_id == test_user.tenant_id,
                    ComplianceEvent.framework == "SOC2",
                )
            )
        ).scalar_one()
    assert int(count) >= 8


@pytest.mark.asyncio
async def test_compliance_event_is_append_only(api_session_factory, test_user: IamUser) -> None:
    async with api_session_factory() as db:
        await run_auto_evaluation(db, test_user.tenant_id)
        event = (
            await db.execute(
                select(ComplianceEvent)
                .where(ComplianceEvent.tenant_id == test_user.tenant_id)
                .order_by(ComplianceEvent.created_at.desc())
                .limit(1)
            )
        ).scalar_one()
        await db.execute(text(append_only_function_sql()))
        await db.execute(text(drop_trigger_sql("compliance_events")))
        await db.execute(text(create_trigger_sql("compliance_events")))
        await db.flush()

        with pytest.raises(Exception):
            await db.execute(
                text("UPDATE compliance_events SET notes = 'mutated' WHERE id = :id"),
                {"id": event.id},
            )


@pytest.mark.asyncio
async def test_auto_evaluation_updates_rag_status(api_session_factory, test_user: IamUser) -> None:
    async with api_session_factory() as db:
        await run_auto_evaluation(db, test_user.tenant_id)
        control = (
            await db.execute(
                select(ComplianceControl).where(
                    ComplianceControl.tenant_id == test_user.tenant_id,
                    ComplianceControl.framework == "SOC2",
                    ComplianceControl.control_id == "CC6.6",
                )
            )
        ).scalar_one()
    assert control.rag_status in {"green", "red"}


# Dashboard and evidence (5)
@pytest.mark.asyncio
async def test_soc2_dashboard_structure(api_session_factory, test_user: IamUser) -> None:
    async with api_session_factory() as db:
        payload = await get_soc2_dashboard(db, test_user.tenant_id)
    for key in ["overall_rag", "last_evaluated", "summary", "controls_by_category", "recently_failed", "upcoming_evaluations"]:
        assert key in payload


@pytest.mark.asyncio
async def test_soc2_dashboard_summary_counts(api_session_factory, test_user: IamUser) -> None:
    async with api_session_factory() as db:
        await get_soc2_dashboard(db, test_user.tenant_id)
        rows = (
            await db.execute(
                select(ComplianceControl).where(
                    ComplianceControl.tenant_id == test_user.tenant_id,
                    ComplianceControl.framework == "SOC2",
                )
            )
        ).scalars().all()
        for idx, row in enumerate(rows):
            row.status = "pass" if idx < 10 else "fail" if idx < 15 else "not_evaluated"
            row.rag_status = "green" if idx < 10 else "red" if idx < 15 else "grey"
        await db.flush()
        payload = await get_soc2_dashboard(db, test_user.tenant_id)
    assert payload["summary"]["green"] == 10
    assert payload["summary"]["red"] == 5


@pytest.mark.asyncio
async def test_evidence_package_structure(api_session_factory, test_user: IamUser) -> None:
    async with api_session_factory() as db:
        payload = await get_soc2_evidence_package(db, test_user.tenant_id)
    assert payload["framework"] == "SOC2"
    assert "generated_at" in payload
    assert isinstance(payload["controls"], list)
    assert "summary" in payload


@pytest.mark.asyncio
async def test_evidence_package_no_pii(api_session_factory, test_user: IamUser) -> None:
    async with api_session_factory() as db:
        payload = await get_soc2_evidence_package(db, test_user.tenant_id)
    dumped = str(payload).lower()
    assert test_user.email.lower() not in dumped
    assert "@" not in dumped


@pytest.mark.asyncio
async def test_overall_rag_green_when_all_pass(api_session_factory, test_user: IamUser) -> None:
    async with api_session_factory() as db:
        await get_soc2_dashboard(db, test_user.tenant_id)
        rows = (
            await db.execute(
                select(ComplianceControl).where(
                    ComplianceControl.tenant_id == test_user.tenant_id,
                    ComplianceControl.framework == "SOC2",
                )
            )
        ).scalars().all()
        for row in rows:
            row.status = "pass"
            row.rag_status = "green"
        await db.flush()
        payload = await get_soc2_dashboard(db, test_user.tenant_id)
    assert payload["overall_rag"] == "green"


# API role gates (3)
@pytest.mark.asyncio
async def test_evaluate_requires_platform_admin_or_finance_leader(
    async_session: AsyncSession,
    async_client,
    test_user: IamUser,
) -> None:
    allowed = await async_client.post(
        "/api/v1/compliance/soc2/evaluate",
        headers=_auth_headers(test_user),
    )
    assert allowed.status_code == 200

    finance_team = await _create_user(
        async_session,
        tenant_id=test_user.tenant_id,
        email="team-user@example.com",
        role=UserRole.finance_team,
        mfa_enabled=True,
    )
    denied = await async_client.post(
        "/api/v1/compliance/soc2/evaluate",
        headers=_auth_headers(finance_team),
    )
    assert denied.status_code == 403


@pytest.mark.asyncio
async def test_manual_status_update_requires_platform_admin(
    async_session: AsyncSession,
    async_client,
    test_user: IamUser,
) -> None:
    await get_soc2_dashboard(async_session, test_user.tenant_id)
    denied = await async_client.patch(
        "/api/v1/compliance/soc2/controls/CC1.1/status",
        headers=_auth_headers(test_user),
        json={"status": "pass", "notes": "manual"},
    )
    assert denied.status_code == 403

    admin = await _create_user(
        async_session,
        tenant_id=test_user.tenant_id,
        email="admin-user@example.com",
        role=UserRole.super_admin,
        mfa_enabled=True,
    )
    allowed = await async_client.patch(
        "/api/v1/compliance/soc2/controls/CC1.1/status",
        headers=_auth_headers(admin),
        json={"status": "pass", "notes": "manual"},
    )
    assert allowed.status_code == 200


@pytest.mark.asyncio
async def test_controls_list_paginated(async_client, test_user: IamUser) -> None:
    response = await async_client.get(
        "/api/v1/compliance/soc2/controls?limit=5&offset=0",
        headers=_auth_headers(test_user),
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["limit"] == 5
    assert payload["offset"] == 0
    assert isinstance(payload["data"], list)
