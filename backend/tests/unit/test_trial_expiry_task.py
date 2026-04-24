from __future__ import annotations

import uuid
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch, call


def _make_sub(
    *,
    tenant_id: uuid.UUID | None = None,
    trial_end_date: date | None = None,
    status: str = "trialing",
    provider_subscription_id: str = "trial_abc",
) -> MagicMock:
    sub = MagicMock()
    sub.tenant_id = tenant_id or uuid.uuid4()
    sub.id = uuid.uuid4()
    sub.plan_id = uuid.uuid4()
    sub.provider = "internal"
    sub.provider_subscription_id = provider_subscription_id
    sub.provider_customer_id = str(sub.tenant_id)
    sub.status = status
    sub.billing_cycle = "monthly"
    sub.current_period_start = date(2026, 1, 1)
    sub.current_period_end = trial_end_date or date(2026, 1, 15)
    sub.trial_start = date(2026, 1, 1)
    sub.trial_end = trial_end_date or date(2026, 1, 15)
    sub.trial_end_date = trial_end_date or date(2026, 1, 15)
    sub.start_date = date(2026, 1, 1)
    sub.end_date = trial_end_date or date(2026, 1, 15)
    sub.auto_renew = True
    sub.cancelled_at = None
    sub.cancel_at_period_end = False
    sub.onboarding_mode = "self_serve"
    sub.billing_country = "US"
    sub.billing_currency = "USD"
    sub.metadata_json = {}
    return sub


async def test_trial_expiry_task_marks_expired_subscriptions() -> None:
    """
    check_trial_expirations: expired trialing subscriptions without payment method
    are revised to 'incomplete' and a notification is enqueued.
    """
    from financeops.tasks.payment_tasks import check_trial_expirations

    tenant_id = uuid.uuid4()
    yesterday = date.today() - timedelta(days=1)
    sub = _make_sub(tenant_id=tenant_id, trial_end_date=yesterday)

    mock_recipient = MagicMock()
    mock_recipient.id = uuid.uuid4()

    revised_sub = MagicMock()
    revised_sub.id = uuid.uuid4()
    revised_sub.status = "incomplete"
    revised_sub.tenant_id = tenant_id
    revised_sub.provider_subscription_id = sub.provider_subscription_id

    # session.execute returns: expired subs → no payment method → no recipient (finance_leader) → recipient (fallback) → send_notification flush
    exec_results = [
        MagicMock(scalars=MagicMock(return_value=iter([sub]))),          # expired sub query
        MagicMock(scalar_one_or_none=MagicMock(return_value=None)),      # payment method query → None
        MagicMock(scalar_one_or_none=MagicMock(return_value=None)),      # finance_leader query → None
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_recipient)),  # fallback user query
    ]
    exec_iter = iter(exec_results)

    mock_session = MagicMock()
    mock_session.execute = AsyncMock(side_effect=lambda *a, **kw: next(exec_iter))
    mock_session.commit = AsyncMock()
    mock_session.flush = AsyncMock()

    mock_nested_ctx = MagicMock()
    mock_nested_ctx.__aenter__ = AsyncMock(return_value=None)
    mock_nested_ctx.__aexit__ = AsyncMock(return_value=False)
    mock_session.begin_nested = MagicMock(return_value=mock_nested_ctx)

    mock_session_ctx = MagicMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

    mock_send_notification = AsyncMock(return_value=MagicMock())
    mock_revised = MagicMock()
    mock_revised.id = uuid.uuid4()
    mock_revised.status = "incomplete"

    with (
        patch("financeops.tasks.payment_tasks.AsyncSessionLocal", return_value=mock_session_ctx),
        patch("financeops.tasks.payment_tasks._append_subscription_revision", AsyncMock(return_value=mock_revised)),
        patch("financeops.tasks.payment_tasks._emit_subscription_event", AsyncMock()),
        patch("financeops.tasks.payment_tasks.send_notification", mock_send_notification),
    ):
        result = check_trial_expirations()

    assert result["incomplete"] == 1
    assert result["converted"] == 0
    mock_send_notification.assert_awaited_once()
    notif_kwargs = mock_send_notification.call_args.kwargs
    assert notif_kwargs["notification_type"] == "trial_expiry"
    assert notif_kwargs["tenant_id"] == tenant_id
    assert notif_kwargs["recipient_user_id"] == mock_recipient.id


async def test_trial_expiry_task_is_idempotent() -> None:
    """
    check_trial_expirations: running twice with no remaining trialing subscriptions
    (because the first run revised them to 'incomplete') processes 0 records both times.
    """
    from financeops.tasks.payment_tasks import check_trial_expirations

    # First run: one expired sub
    tenant_id = uuid.uuid4()
    yesterday = date.today() - timedelta(days=1)
    sub = _make_sub(tenant_id=tenant_id, trial_end_date=yesterday)

    mock_recipient = MagicMock()
    mock_recipient.id = uuid.uuid4()

    mock_revised = MagicMock()
    mock_revised.id = uuid.uuid4()
    mock_revised.status = "incomplete"

    def _make_session_ctx(exec_side_effects):
        session = MagicMock()
        exec_iter = iter(exec_side_effects)
        session.execute = AsyncMock(side_effect=lambda *a, **kw: next(exec_iter))
        session.commit = AsyncMock()
        session.flush = AsyncMock()
        nested = MagicMock()
        nested.__aenter__ = AsyncMock(return_value=None)
        nested.__aexit__ = AsyncMock(return_value=False)
        session.begin_nested = MagicMock(return_value=nested)
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=session)
        ctx.__aexit__ = AsyncMock(return_value=False)
        return ctx

    first_run_exec = [
        MagicMock(scalars=MagicMock(return_value=iter([sub]))),
        MagicMock(scalar_one_or_none=MagicMock(return_value=None)),  # no payment method
        MagicMock(scalar_one_or_none=MagicMock(return_value=None)),  # no finance_leader
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_recipient)),  # fallback
    ]

    # Second run: DB now returns 0 trialing subs (already revised)
    second_run_exec = [
        MagicMock(scalars=MagicMock(return_value=iter([]))),
    ]

    first_ctx = _make_session_ctx(first_run_exec)
    second_ctx = _make_session_ctx(second_run_exec)
    session_ctx_iter = iter([first_ctx, second_ctx])

    with (
        patch("financeops.tasks.payment_tasks.AsyncSessionLocal", side_effect=lambda: next(session_ctx_iter)),
        patch("financeops.tasks.payment_tasks._append_subscription_revision", AsyncMock(return_value=mock_revised)),
        patch("financeops.tasks.payment_tasks._emit_subscription_event", AsyncMock()),
        patch("financeops.tasks.payment_tasks.send_notification", AsyncMock()),
    ):
        first_result = check_trial_expirations()
        second_result = check_trial_expirations()

    # First run processes 1 expired subscription
    assert first_result["incomplete"] == 1

    # Second run processes 0 (already handled — idempotent)
    assert second_result["incomplete"] == 0
    assert second_result["converted"] == 0
