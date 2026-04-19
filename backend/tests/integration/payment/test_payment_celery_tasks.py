from __future__ import annotations

from financeops.tasks.celery_app import celery_app


def test_payment_tasks_registered_and_scheduled() -> None:
    task_names = set(celery_app.tasks.keys())
    assert "payment.check_trial_conversions" in task_names
    assert "payment.check_grace_periods" in task_names
    assert "payment.retry_failed_payments" in task_names
    assert "payment.expire_credits" in task_names
    assert "ops.check_dead_letter_queue" in task_names
    assert "ops.check_payment_dead_letter_queue" in task_names

    schedule = celery_app.conf.beat_schedule or {}
    assert "payment-check-trial-conversions-daily-0000-utc" in schedule
    assert "payment-check-grace-periods-every-6h" in schedule
    assert "payment-retry-failed-payments-daily-0600-utc" in schedule
    assert "payment-expire-credits-daily-2300-utc" in schedule
    assert "ops-check-dead-letter-queue-hourly" in schedule
    assert "ops-check-payment-dead-letter-queue-hourly" in schedule
