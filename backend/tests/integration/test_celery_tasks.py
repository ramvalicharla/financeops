from __future__ import annotations

from contextlib import asynccontextmanager
import os
import uuid

import pytest
import pytest_asyncio
from fastapi import Request
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from financeops.core.security import create_access_token, hash_password
from financeops.db.models.tenants import IamTenant, TenantStatus, TenantType
from financeops.db.models.users import IamUser, UserRole
from financeops.db.rls import clear_tenant_context, set_tenant_context
from financeops.modules.notifications.models import NotificationReadState
from financeops.modules.notifications.service import send_notification
from financeops.modules.notifications.tasks import run_notification_delivery, send_notification_task
from financeops.tasks.celery_app import celery_app
from financeops.utils.chain_hash import GENESIS_HASH, compute_chain_hash


def _auth_headers(user) -> dict[str, str]:
    token = create_access_token(user.id, user.tenant_id, user.role.value)
    return {"Authorization": f"Bearer {token}"}


def _disable_pytest_inline(monkeypatch: pytest.MonkeyPatch) -> None:
    original_getenv = os.getenv

    def _fake_getenv(key: str, default: str | None = None) -> str | None:
        if key == "PYTEST_CURRENT_TEST":
            return ""
        return original_getenv(key, default)

    monkeypatch.setattr("financeops.modules.notifications.service.os.getenv", _fake_getenv)


@pytest_asyncio.fixture(scope="session", loop_scope="session")
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


async def _create_api_test_tenant(api_db_session: AsyncSession) -> IamTenant:
    tenant_id = uuid.uuid4()
    record_data = {
        "display_name": "Notifications Queue Tenant",
        "tenant_type": TenantType.direct.value,
        "country": "US",
        "timezone": "UTC",
    }
    tenant = IamTenant(
        id=tenant_id,
        tenant_id=tenant_id,
        display_name="Notifications Queue Tenant",
        tenant_type=TenantType.direct,
        country="US",
        timezone="UTC",
        status=TenantStatus.active,
        chain_hash=compute_chain_hash(record_data, GENESIS_HASH),
        previous_hash=GENESIS_HASH,
        org_setup_complete=True,
        org_setup_step=7,
    )
    api_db_session.add(tenant)
    await api_db_session.flush()
    return tenant


async def _create_api_test_user(api_db_session: AsyncSession, api_test_tenant: IamTenant) -> IamUser:
    row = IamUser(
        tenant_id=api_test_tenant.id,
        email=f"celery-notification-{uuid.uuid4().hex[:12]}@example.com",
        hashed_password=hash_password("TestPass123!"),
        full_name="Queued Notification User",
        role=UserRole.finance_leader,
        is_active=True,
        mfa_enabled=False,
    )
    api_db_session.add(row)
    await api_db_session.flush()
    return row


async def _seed_api_test_user(api_db_session: AsyncSession) -> tuple[IamTenant, IamUser]:
    tenant = await _create_api_test_tenant(api_db_session)
    user = await _create_api_test_user(api_db_session, tenant)
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


@pytest.mark.asyncio
@pytest.mark.integration
async def test_notifications_task_completes_and_updates_delivery_status(
    notification_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with notification_session() as api_db_session:
        _, api_test_user = await _seed_api_test_user(api_db_session)
        _disable_pytest_inline(monkeypatch)
        monkeypatch.setattr(
            "financeops.modules.notifications.tasks.schedule_notification_delivery",
            lambda **kwargs: None,
        )

        sent: list[str] = []

        async def _fake_send_email(*args, **kwargs):  # type: ignore[no-untyped-def]
            sent.append("email")
            return True

        monkeypatch.setattr("financeops.modules.notifications.service.send_email", _fake_send_email)

        event = await send_notification(
            api_db_session,
            tenant_id=api_test_user.tenant_id,
            recipient_user_id=api_test_user.id,
            notification_type="system_alert",
            title="Queued notification",
            body="Body",
        )

        result = await run_notification_delivery(
            notification_event_id=str(event.id),
            tenant_id=str(api_test_user.tenant_id),
        )
        read_state = (
            await api_db_session.execute(
                select(NotificationReadState).where(
                    NotificationReadState.notification_event_id == event.id
                )
            )
        ).scalar_one()

        assert result["status"] == "complete"
        assert "email" in result["channels_sent"]
        assert read_state.channels_sent == ["inapp", "email"]
        assert sent == ["email"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_notifications_task_idempotent_called_twice(
    notification_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with notification_session() as api_db_session:
        _, api_test_user = await _seed_api_test_user(api_db_session)
        _disable_pytest_inline(monkeypatch)
        monkeypatch.setattr(
            "financeops.modules.notifications.tasks.schedule_notification_delivery",
            lambda **kwargs: None,
        )

        calls: list[str] = []

        async def _fake_send_email(*args, **kwargs):  # type: ignore[no-untyped-def]
            calls.append("email")
            return True

        monkeypatch.setattr("financeops.modules.notifications.service.send_email", _fake_send_email)

        event = await send_notification(
            api_db_session,
            tenant_id=api_test_user.tenant_id,
            recipient_user_id=api_test_user.id,
            notification_type="system_alert",
            title="Idempotent notification",
            body="Body",
        )

        first = await run_notification_delivery(
            notification_event_id=str(event.id),
            tenant_id=str(api_test_user.tenant_id),
        )
        second = await run_notification_delivery(
            notification_event_id=str(event.id),
            tenant_id=str(api_test_user.tenant_id),
        )
        read_state = (
            await api_db_session.execute(
                select(NotificationReadState).where(
                    NotificationReadState.notification_event_id == event.id
                )
            )
        ).scalar_one()

        assert first["status"] == "complete"
        assert second["status"] == "complete"
        assert calls == ["email"]
        assert read_state.channels_sent == ["inapp", "email"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_notification_status_endpoint_reflects_delivery_state(
    async_client,
    notification_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with notification_session() as api_db_session:
        _, api_test_user = await _seed_api_test_user(api_db_session)
        _disable_pytest_inline(monkeypatch)
        monkeypatch.setattr(
            "financeops.modules.notifications.tasks.schedule_notification_delivery",
            lambda **kwargs: None,
        )

        async def _fake_send_email(*args, **kwargs):  # type: ignore[no-untyped-def]
            return True

        monkeypatch.setattr("financeops.modules.notifications.service.send_email", _fake_send_email)

        event = await send_notification(
            api_db_session,
            tenant_id=api_test_user.tenant_id,
            recipient_user_id=api_test_user.id,
            notification_type="system_alert",
            title="Status notification",
            body="Body",
        )
        await run_notification_delivery(
            notification_event_id=str(event.id),
            tenant_id=str(api_test_user.tenant_id),
        )

        response = await async_client.get(
            f"/api/v1/notifications/{event.id}/status",
            headers=_auth_headers(api_test_user),
        )

        assert response.status_code == 200
        payload = response.json()["data"]
        assert payload["status"] == "delivered"
        assert "email" in payload["channels_sent"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_notification_task_missing_event_returns_missing(notification_session) -> None:
    async with notification_session() as api_db_session:
        _, api_test_user = await _seed_api_test_user(api_db_session)
        result = await run_notification_delivery(
            notification_event_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            tenant_id=str(api_test_user.tenant_id),
        )
        assert result["status"] == "missing"


def test_all_new_tasks_appear_in_celery_registered_tasks() -> None:
    assert "notifications.send_notification" in celery_app.tasks
