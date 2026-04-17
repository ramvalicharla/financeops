from __future__ import annotations

from contextlib import asynccontextmanager
import uuid
from datetime import UTC, date, datetime, time
from decimal import Decimal
from unittest.mock import patch

import pytest
import pytest_asyncio
from fastapi import Request
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from financeops.core.intent.context import MutationContext, governed_mutation_context
from financeops.core.security import create_access_token, hash_password
from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql
from financeops.db.models.tenants import IamTenant, TenantStatus, TenantType
from financeops.db.models.users import IamUser, UserRole
from financeops.db.rls import clear_tenant_context, set_tenant_context
from financeops.modules.expense_management.service import submit_claim as _submit_claim
from financeops.modules.notifications.models import NotificationEvent, NotificationPreferences, NotificationReadState
from financeops.platform.db.models import CpEntity, CpOrganisation
from financeops.modules.notifications.service import (
    get_or_create_preferences,
    get_unread_notifications,
    list_notifications,
    mark_all_as_read,
    mark_as_read,
    send_notification,
    update_preferences,
)
from financeops.utils.chain_hash import GENESIS_HASH, compute_chain_hash


@pytest_asyncio.fixture(scope="session")
async def engine(test_database_url: str):
    test_engine = create_async_engine(test_database_url, echo=False, poolclass=NullPool)
    yield test_engine
    await test_engine.dispose()


@pytest.fixture
def notification_session_factory(engine):
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


@pytest.fixture
def notification_session(notification_session_factory):
    @asynccontextmanager
    async def _session():
        async with notification_session_factory() as session:
            original_flush = session.flush

            async def _flush_and_commit(*args, **kwargs):
                await original_flush(*args, **kwargs)
                await session.commit()

            session.flush = _flush_and_commit  # type: ignore[method-assign]
            try:
                yield session
            finally:
                session.flush = original_flush  # type: ignore[method-assign]
                if session.in_transaction():
                    await session.rollback()

    return _session


async def _create_test_tenant(session: AsyncSession) -> IamTenant:
    tenant_id = uuid.uuid4()
    record_data = {
        "display_name": "Notifications Tenant",
        "tenant_type": TenantType.direct.value,
        "country": "US",
        "timezone": "UTC",
    }
    tenant = IamTenant(
        id=tenant_id,
        tenant_id=tenant_id,
        display_name="Notifications Tenant",
        tenant_type=TenantType.direct,
        country="US",
        timezone="UTC",
        status=TenantStatus.active,
        chain_hash=compute_chain_hash(record_data, GENESIS_HASH),
        previous_hash=GENESIS_HASH,
        org_setup_complete=True,
        org_setup_step=7,
    )
    session.add(tenant)
    await session.flush()
    return tenant


async def _create_test_user(session: AsyncSession, test_tenant: IamTenant) -> IamUser:
    org_code = f"ORG_{uuid.uuid4().hex[:8].upper()}"
    entity_code = f"ENT_{uuid.uuid4().hex[:8].upper()}"
    org_payload = {
        "tenant_id": str(test_tenant.id),
        "organisation_code": org_code,
        "organisation_name": "Notifications Org",
    }
    org = CpOrganisation(
        tenant_id=test_tenant.id,
        organisation_code=org_code,
        organisation_name="Notifications Org",
        parent_organisation_id=None,
        supersedes_id=None,
        is_active=True,
        correlation_id=f"notifications-org-{uuid.uuid4().hex[:8]}",
        chain_hash=compute_chain_hash(org_payload, GENESIS_HASH),
        previous_hash=GENESIS_HASH,
    )
    session.add(org)
    await session.flush()

    entity_payload = {
        "tenant_id": str(test_tenant.id),
        "entity_code": entity_code,
        "entity_name": "Notifications Entity",
        "organisation_id": str(org.id),
    }
    entity = CpEntity(
        tenant_id=test_tenant.id,
        organisation_id=org.id,
        group_id=None,
        entity_code=entity_code,
        entity_name="Notifications Entity",
        base_currency="INR",
        country_code="IN",
        status="active",
        deactivated_at=None,
        correlation_id=f"notifications-entity-{uuid.uuid4().hex[:8]}",
        chain_hash=compute_chain_hash(entity_payload, GENESIS_HASH),
        previous_hash=GENESIS_HASH,
    )
    session.add(entity)
    await session.flush()

    row = IamUser(
        tenant_id=test_tenant.id,
        email=f"notifications-{uuid.uuid4().hex[:12]}@example.com",
        hashed_password=hash_password("TestPass123!"),
        full_name="Notification User",
        role=UserRole.finance_leader,
        is_active=True,
        mfa_enabled=False,
    )
    session.add(row)
    await session.flush()
    return row


async def _seed_notification_user(session: AsyncSession) -> tuple[IamTenant, IamUser]:
    tenant = await _create_test_tenant(session)
    user = await _create_test_user(session, tenant)
    return tenant, user


@pytest_asyncio.fixture
async def async_client(engine) -> AsyncClient:
    from financeops.api.deps import get_async_session
    from financeops.main import app

    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    original_startup_errors = getattr(app.state, "startup_errors", [])
    original_migration_state = getattr(app.state, "migration_state", None)
    app.state.startup_errors = []
    app.state.migration_state = {
        "status": "ok",
        "current_revision": "test",
        "head_revision": "test",
        "detail": None,
    }

    async def override_session(request: Request):
        tenant_id = str(getattr(request.state, "tenant_id", "") or "")
        if not tenant_id:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                from financeops.core.security import decode_token

                token = auth_header[7:]
                try:
                    payload = decode_token(token)
                except Exception:
                    payload = {}
                tenant_id = str(payload.get("tenant_id", "") or "")

        async with session_factory() as session:
            if tenant_id:
                await set_tenant_context(session, tenant_id)
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                if tenant_id:
                    try:
                        await clear_tenant_context(session)
                    except Exception:
                        await session.rollback()

    app.dependency_overrides[get_async_session] = override_session
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        yield client
    app.dependency_overrides.clear()
    app.state.startup_errors = original_startup_errors
    app.state.migration_state = original_migration_state


def _auth_headers(user: IamUser) -> dict[str, str]:
    token = create_access_token(user.id, user.tenant_id, user.role.value)
    return {"Authorization": f"Bearer {token}"}


def _expense_context() -> MutationContext:
    return MutationContext(
        intent_id=uuid.uuid4(),
        job_id=uuid.uuid4(),
        actor_user_id=None,
        actor_role="finance_leader",
        intent_type="SUBMIT_EXPENSE_CLAIM",
    )


async def submit_claim(*args, **kwargs):
    with governed_mutation_context(_expense_context()):
        return await _submit_claim(*args, **kwargs)


async def _create_user(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    email: str,
    role: UserRole = UserRole.employee,
) -> IamUser:
    row = IamUser(
        tenant_id=tenant_id,
        email=email,
        hashed_password=hash_password("TestPass123!"),
        full_name="Notification User",
        role=role,
        is_active=True,
        mfa_enabled=False,
    )
    session.add(row)
    await session.flush()
    return row


@pytest.mark.asyncio
async def test_send_notification_creates_event(notification_session) -> None:
    async with notification_session() as async_session:
        _, test_user = await _seed_notification_user(async_session)
        event = await send_notification(
            async_session,
            tenant_id=test_user.tenant_id,
            recipient_user_id=test_user.id,
            notification_type="system_alert",
            title="System alert",
            body="Test body",
        )
        assert event.id is not None
        await async_session.execute(text(append_only_function_sql()))
        await async_session.execute(text(drop_trigger_sql("notification_events")))
        await async_session.execute(text(create_trigger_sql("notification_events")))
        await async_session.flush()
        with pytest.raises(Exception):
            await async_session.execute(
                text("UPDATE notification_events SET title = 'mutated' WHERE id = :id"),
                {"id": event.id},
            )


@pytest.mark.asyncio
async def test_send_notification_creates_read_state(notification_session) -> None:
    async with notification_session() as async_session:
        _, test_user = await _seed_notification_user(async_session)
        event = await send_notification(
            async_session,
            tenant_id=test_user.tenant_id,
            recipient_user_id=test_user.id,
            notification_type="system_alert",
            title="Hello",
            body="World",
        )
        state = (
            await async_session.execute(
                select(NotificationReadState).where(
                    NotificationReadState.notification_event_id == event.id
                )
            )
        ).scalar_one()
        assert state.is_read is False


@pytest.mark.asyncio
async def test_quiet_hours_suppresses_email(
    notification_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with notification_session() as async_session:
        _, test_user = await _seed_notification_user(async_session)
        now_time = datetime.now(UTC).time().replace(second=0, microsecond=0, tzinfo=None)
        start_hour = (now_time.hour - 1) % 24
        end_hour = (now_time.hour + 1) % 24
        prefs = await get_or_create_preferences(async_session, test_user.tenant_id, test_user.id)
        prefs.quiet_hours_start = time(start_hour, now_time.minute)
        prefs.quiet_hours_end = time(end_hour, now_time.minute)
        prefs.timezone = "UTC"
        await async_session.flush()

        calls: list[str] = []

        async def _fake_send_email(*args, **kwargs):  # type: ignore[no-untyped-def]
            calls.append("email")
            return True

        monkeypatch.setattr("financeops.modules.notifications.service.send_email", _fake_send_email)
        await send_notification(
            async_session,
            tenant_id=test_user.tenant_id,
            recipient_user_id=test_user.id,
            notification_type="system_alert",
            title="Quiet Hours",
            body="Body",
        )
        assert calls == []


@pytest.mark.asyncio
async def test_type_preference_disables_channel(
    notification_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with notification_session() as async_session:
        _, test_user = await _seed_notification_user(async_session)
        prefs = await get_or_create_preferences(async_session, test_user.tenant_id, test_user.id)
        prefs.type_preferences = {"anomaly_detected": {"email": False}}
        await async_session.flush()

        calls: list[str] = []

        async def _fake_send_email(*args, **kwargs):  # type: ignore[no-untyped-def]
            calls.append("email")
            return True

        monkeypatch.setattr("financeops.modules.notifications.service.send_email", _fake_send_email)
        await send_notification(
            async_session,
            tenant_id=test_user.tenant_id,
            recipient_user_id=test_user.id,
            notification_type="anomaly_detected",
            title="Anomaly",
            body="Detected",
        )
        assert calls == []


@pytest.mark.asyncio
async def test_send_notification_never_raises(
    notification_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with notification_session() as async_session:
        _, test_user = await _seed_notification_user(async_session)

        async def _boom(*args, **kwargs):  # type: ignore[no-untyped-def]
            raise RuntimeError("smtp unavailable")

        monkeypatch.setattr("financeops.modules.notifications.service.send_email", _boom)
        await send_notification(
            async_session,
            tenant_id=test_user.tenant_id,
            recipient_user_id=test_user.id,
            notification_type="system_alert",
            title="No Raise",
            body="Body",
        )
        states = (
            await async_session.execute(
                select(NotificationReadState).where(NotificationReadState.user_id == test_user.id)
            )
        ).scalars().all()
        assert len(states) >= 1


@pytest.mark.asyncio
async def test_notification_rls(
    async_client,
    notification_session,
) -> None:
    async with notification_session() as async_session:
        _, test_user = await _seed_notification_user(async_session)
        other = await _create_user(
            async_session,
            test_user.tenant_id,
            email=f"other.notifications.{uuid.uuid4().hex[:8]}@example.com",
        )
        await send_notification(
            async_session,
            tenant_id=test_user.tenant_id,
            recipient_user_id=other.id,
            notification_type="system_alert",
            title="For other user",
            body="Hidden",
        )
        response = await async_client.get("/api/v1/notifications", headers=_auth_headers(test_user))
        assert response.status_code == 200
        rows = response.json()["data"]["notifications"]
        assert all(row["id"] for row in rows)
        assert all(row["read_state"]["is_read"] in {True, False} for row in rows)


@pytest.mark.asyncio
async def test_get_unread_count(notification_session) -> None:
    async with notification_session() as async_session:
        _, test_user = await _seed_notification_user(async_session)
        for idx in range(3):
            await send_notification(
                async_session,
                tenant_id=test_user.tenant_id,
                recipient_user_id=test_user.id,
                notification_type="system_alert",
                title=f"N{idx}",
                body="Body",
            )
        payload = await get_unread_notifications(async_session, test_user.tenant_id, test_user.id)
        assert payload["unread_count"] >= 3


@pytest.mark.asyncio
async def test_mark_as_read_updates_state(notification_session) -> None:
    async with notification_session() as async_session:
        _, test_user = await _seed_notification_user(async_session)
        first = await send_notification(
            async_session,
            tenant_id=test_user.tenant_id,
            recipient_user_id=test_user.id,
            notification_type="system_alert",
            title="First",
            body="Body",
        )
        second = await send_notification(
            async_session,
            tenant_id=test_user.tenant_id,
            recipient_user_id=test_user.id,
            notification_type="system_alert",
            title="Second",
            body="Body",
        )
        updated = await mark_as_read(
            async_session,
            tenant_id=test_user.tenant_id,
            user_id=test_user.id,
            notification_ids=[first.id, second.id],
        )
        assert updated == 2


@pytest.mark.asyncio
async def test_mark_all_as_read(async_client, notification_session) -> None:
    async with notification_session() as async_session:
        _, test_user = await _seed_notification_user(async_session)
        for idx in range(5):
            await send_notification(
                async_session,
                tenant_id=test_user.tenant_id,
                recipient_user_id=test_user.id,
                notification_type="system_alert",
                title=f"Read all {idx}",
                body="Body",
            )
        response = await async_client.post("/api/v1/notifications/read-all", headers=_auth_headers(test_user))
        assert response.status_code == 200
        assert response.json()["data"]["updated"] >= 5


@pytest.mark.asyncio
async def test_unread_count_decreases_after_read(notification_session) -> None:
    async with notification_session() as async_session:
        _, test_user = await _seed_notification_user(async_session)
        events: list[NotificationEvent] = []
        for idx in range(3):
            events.append(
                await send_notification(
                    async_session,
                    tenant_id=test_user.tenant_id,
                    recipient_user_id=test_user.id,
                    notification_type="system_alert",
                    title=f"Dec {idx}",
                    body="Body",
                )
            )
        before = await get_unread_notifications(async_session, test_user.tenant_id, test_user.id)
        await mark_as_read(
            async_session,
            tenant_id=test_user.tenant_id,
            user_id=test_user.id,
            notification_ids=[events[0].id, events[1].id],
        )
        after = await get_unread_notifications(async_session, test_user.tenant_id, test_user.id)
        assert before["unread_count"] - after["unread_count"] >= 2


@pytest.mark.asyncio
async def test_get_or_create_preferences_idempotent(notification_session) -> None:
    async with notification_session() as async_session:
        _, test_user = await _seed_notification_user(async_session)
        first = await get_or_create_preferences(async_session, test_user.tenant_id, test_user.id)
        second = await get_or_create_preferences(async_session, test_user.tenant_id, test_user.id)
        assert first.id == second.id


@pytest.mark.asyncio
async def test_default_email_enabled_true(notification_session) -> None:
    async with notification_session() as async_session:
        _, test_user = await _seed_notification_user(async_session)
        prefs = await get_or_create_preferences(async_session, test_user.tenant_id, test_user.id)
        assert prefs.email_enabled is True


@pytest.mark.asyncio
async def test_update_preferences(notification_session) -> None:
    async with notification_session() as async_session:
        _, test_user = await _seed_notification_user(async_session)
        prefs = await update_preferences(
            async_session,
            test_user.tenant_id,
            test_user.id,
            {"email_enabled": False},
        )
        assert prefs.email_enabled is False


@pytest.mark.asyncio
async def test_type_preferences_stored_as_json(notification_session) -> None:
    async with notification_session() as async_session:
        _, test_user = await _seed_notification_user(async_session)
        prefs = await update_preferences(
            async_session,
            test_user.tenant_id,
            test_user.id,
            {
                "type_preferences": {
                    "anomaly_detected": {"email": False},
                    "task_assigned": {"push": True},
                    "expense_approved": {"email": True},
                }
            },
        )
        assert len(prefs.type_preferences.keys()) == 3


@pytest.mark.asyncio
async def test_anomaly_detection_triggers_notification(notification_session) -> None:
    async with notification_session() as async_session:
        _, test_user = await _seed_notification_user(async_session)
        await send_notification(
            async_session,
            tenant_id=test_user.tenant_id,
            recipient_user_id=test_user.id,
            notification_type="anomaly_detected",
            title="Variance anomaly detected",
            body="A material variance anomaly was detected.",
        )
        row = (
            await async_session.execute(
                select(NotificationEvent).where(
                    NotificationEvent.tenant_id == test_user.tenant_id,
                    NotificationEvent.notification_type == "anomaly_detected",
                )
            )
        ).scalar_one_or_none()
        assert row is not None


@pytest.mark.asyncio
async def test_expense_approval_triggers_notification(
    async_client,
    notification_session,
) -> None:
    async with notification_session() as async_session:
        _, test_user = await _seed_notification_user(async_session)

        class _FixedWeekdayDate(date):
            @classmethod
            def today(cls) -> _FixedWeekdayDate:
                return cls(2025, 3, 17)

        with patch(f"{__name__}.date", _FixedWeekdayDate):
            claim = await submit_claim(
                async_session,
                tenant_id=test_user.tenant_id,
                submitted_by=test_user.id,
                vendor_name="Vendor A",
                description="Meal",
                category="meals",
                amount=Decimal("100.00"),
                currency="INR",
                claim_date=date.today(),
                has_receipt=True,
            )
        response = await async_client.post(
            f"/api/v1/expenses/{claim.id}/approve",
            headers=_auth_headers(test_user),
            json={"action": "approved"},
        )
        assert response.status_code == 200
        row = (
            await async_session.execute(
                select(NotificationEvent).where(
                    NotificationEvent.notification_type == "expense_approved",
                    NotificationEvent.recipient_user_id == test_user.id,
                )
            )
        ).scalar_one_or_none()
        assert row is not None


@pytest.mark.asyncio
async def test_task_assignment_triggers_notification(notification_session) -> None:
    async with notification_session() as async_session:
        _, test_user = await _seed_notification_user(async_session)
        assignee = await _create_user(
            async_session,
            test_user.tenant_id,
            email=f"assignee.close.{uuid.uuid4().hex[:8]}@example.com",
            role=UserRole.finance_team,
        )
        await send_notification(
            async_session,
            tenant_id=test_user.tenant_id,
            recipient_user_id=assignee.id,
            notification_type="task_assigned",
            title="Task assigned: Close books",
            body="You have been assigned a closing task.",
        )
        row = (
            await async_session.execute(
                select(NotificationEvent).where(
                    NotificationEvent.notification_type == "task_assigned",
                    NotificationEvent.recipient_user_id == assignee.id,
                )
            )
        ).scalar_one_or_none()
        assert row is not None


@pytest.mark.asyncio
async def test_board_pack_completion_triggers_notification(notification_session) -> None:
    async with notification_session() as async_session:
        _, test_user = await _seed_notification_user(async_session)
        await send_notification(
            async_session,
            tenant_id=test_user.tenant_id,
            recipient_user_id=test_user.id,
            notification_type="board_pack_ready",
            title="Board pack ready",
            body="Your board pack has been generated.",
        )
        row = (
            await async_session.execute(
                select(NotificationEvent).where(
                    NotificationEvent.notification_type == "board_pack_ready",
                    NotificationEvent.recipient_user_id == test_user.id,
                )
            )
        ).scalar_one_or_none()
        assert row is not None


@pytest.mark.asyncio
async def test_notifications_list_endpoint_paginated(async_client, notification_session) -> None:
    async with notification_session() as async_session:
        _, test_user = await _seed_notification_user(async_session)
        for idx in range(3):
            await send_notification(
                async_session,
                tenant_id=test_user.tenant_id,
                recipient_user_id=test_user.id,
                notification_type="system_alert",
                title=f"Page {idx}",
                body="Body",
            )
        response = await async_client.get("/api/v1/notifications?limit=2&offset=0", headers=_auth_headers(test_user))
        assert response.status_code == 200
        payload = response.json()["data"]
        assert payload["limit"] == 2
        assert payload["total"] >= 3


@pytest.mark.asyncio
async def test_preferences_endpoint(async_client, notification_session) -> None:
    async with notification_session() as async_session:
        _, test_user = await _seed_notification_user(async_session)
        get_response = await async_client.get("/api/v1/notifications/preferences", headers=_auth_headers(test_user))
        assert get_response.status_code == 200

        patch_response = await async_client.patch(
            "/api/v1/notifications/preferences",
            headers=_auth_headers(test_user),
            json={"email_enabled": False, "timezone": "UTC"},
        )
        assert patch_response.status_code == 200
        assert patch_response.json()["data"]["email_enabled"] is False


@pytest.mark.asyncio
async def test_mark_all_service(notification_session) -> None:
    async with notification_session() as async_session:
        _, test_user = await _seed_notification_user(async_session)
        for idx in range(2):
            await send_notification(
                async_session,
                tenant_id=test_user.tenant_id,
                recipient_user_id=test_user.id,
                notification_type="system_alert",
                title=f"All {idx}",
                body="Body",
            )
        updated = await mark_all_as_read(async_session, test_user.tenant_id, test_user.id)
        assert updated >= 2


@pytest.mark.asyncio
async def test_list_notifications_filter_by_type(notification_session) -> None:
    async with notification_session() as async_session:
        _, test_user = await _seed_notification_user(async_session)
        await send_notification(
            async_session,
            tenant_id=test_user.tenant_id,
            recipient_user_id=test_user.id,
            notification_type="system_alert",
            title="A",
            body="Body",
        )
        await send_notification(
            async_session,
            tenant_id=test_user.tenant_id,
            recipient_user_id=test_user.id,
            notification_type="task_assigned",
            title="B",
            body="Body",
        )
        payload = await list_notifications(
            async_session,
            tenant_id=test_user.tenant_id,
            user_id=test_user.id,
            notification_type="task_assigned",
        )
        assert payload["total"] >= 1
        assert all(event.notification_type == "task_assigned" for event, _ in payload["rows"])
