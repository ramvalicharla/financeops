from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time
from decimal import Decimal
from unittest.mock import patch

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.security import create_access_token, hash_password
from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql
from financeops.db.models.users import IamUser, UserRole
from financeops.modules.expense_management.service import submit_claim
from financeops.modules.notifications.models import NotificationEvent, NotificationPreferences, NotificationReadState
from financeops.modules.notifications.service import (
    get_or_create_preferences,
    get_unread_notifications,
    list_notifications,
    mark_all_as_read,
    mark_as_read,
    send_notification,
    update_preferences,
)


def _auth_headers(user: IamUser) -> dict[str, str]:
    token = create_access_token(user.id, user.tenant_id, user.role.value)
    return {"Authorization": f"Bearer {token}"}


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
async def test_send_notification_creates_event(async_session: AsyncSession, test_user: IamUser) -> None:
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
async def test_send_notification_creates_read_state(async_session: AsyncSession, test_user: IamUser) -> None:
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
    async_session: AsyncSession,
    test_user: IamUser,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
    async_session: AsyncSession,
    test_user: IamUser,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
    async_session: AsyncSession,
    test_user: IamUser,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
    async_session: AsyncSession,
    test_user: IamUser,
) -> None:
    other = await _create_user(async_session, test_user.tenant_id, email="other.notifications@example.com")
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
async def test_get_unread_count(async_session: AsyncSession, test_user: IamUser) -> None:
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
async def test_mark_as_read_updates_state(async_session: AsyncSession, test_user: IamUser) -> None:
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
async def test_mark_all_as_read(async_client, async_session: AsyncSession, test_user: IamUser) -> None:
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
async def test_unread_count_decreases_after_read(async_session: AsyncSession, test_user: IamUser) -> None:
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
async def test_get_or_create_preferences_idempotent(async_session: AsyncSession, test_user: IamUser) -> None:
    first = await get_or_create_preferences(async_session, test_user.tenant_id, test_user.id)
    second = await get_or_create_preferences(async_session, test_user.tenant_id, test_user.id)
    assert first.id == second.id


@pytest.mark.asyncio
async def test_default_email_enabled_true(async_session: AsyncSession, test_user: IamUser) -> None:
    prefs = await get_or_create_preferences(async_session, test_user.tenant_id, test_user.id)
    assert prefs.email_enabled is True


@pytest.mark.asyncio
async def test_update_preferences(async_session: AsyncSession, test_user: IamUser) -> None:
    prefs = await update_preferences(
        async_session,
        test_user.tenant_id,
        test_user.id,
        {"email_enabled": False},
    )
    assert prefs.email_enabled is False


@pytest.mark.asyncio
async def test_type_preferences_stored_as_json(async_session: AsyncSession, test_user: IamUser) -> None:
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
async def test_anomaly_detection_triggers_notification(async_session: AsyncSession, test_user: IamUser) -> None:
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
    async_session: AsyncSession,
    test_user: IamUser,
) -> None:
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
async def test_task_assignment_triggers_notification(async_session: AsyncSession, test_user: IamUser) -> None:
    assignee = await _create_user(
        async_session,
        test_user.tenant_id,
        email="assignee.close@example.com",
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
async def test_board_pack_completion_triggers_notification(async_session: AsyncSession, test_user: IamUser) -> None:
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
async def test_notifications_list_endpoint_paginated(async_client, async_session: AsyncSession, test_user: IamUser) -> None:
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
async def test_preferences_endpoint(async_client, test_user: IamUser) -> None:
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
async def test_mark_all_service(async_session: AsyncSession, test_user: IamUser) -> None:
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
async def test_list_notifications_filter_by_type(async_session: AsyncSession, test_user: IamUser) -> None:
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
