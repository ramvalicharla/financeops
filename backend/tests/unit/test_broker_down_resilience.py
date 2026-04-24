from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch


async def test_tenants_invite_user_resilience() -> None:
    """tenants.py invite_user → send_notification → schedule_notification_delivery: broker down must not 500."""
    from financeops.modules.notifications.tasks import schedule_notification_delivery

    with patch(
        "financeops.modules.notifications.tasks.send_notification_task"
    ) as mock_task:
        mock_task.delay.side_effect = ConnectionError("Redis broker unreachable")
        mock_task.name = "notifications.send_notification"

        # Must return without raising
        result = schedule_notification_delivery(
            notification_event_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
        )

    assert result is None


async def test_users_invite_user_resilience() -> None:
    """users.py invite_user → send_notification → schedule_notification_delivery: broker down must not 500."""
    from financeops.modules.notifications.tasks import schedule_notification_delivery

    with patch(
        "financeops.modules.notifications.tasks.send_notification_task"
    ) as mock_task:
        mock_task.delay.side_effect = OSError("connection refused")
        mock_task.name = "notifications.send_notification"

        result = schedule_notification_delivery(
            notification_event_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
        )

    assert result is None


async def test_platform_users_create_resilience() -> None:
    """platform_users.py create_platform_user → send_notification → schedule_notification_delivery: broker down must not 500."""
    from financeops.modules.notifications.tasks import schedule_notification_delivery

    with patch(
        "financeops.modules.notifications.tasks.send_notification_task"
    ) as mock_task:
        mock_task.delay.side_effect = Exception("broker unavailable during deploy restart")
        mock_task.name = "notifications.send_notification"

        result = schedule_notification_delivery(
            notification_event_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
        )

    assert result is None
