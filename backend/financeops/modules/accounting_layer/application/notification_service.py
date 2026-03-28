from __future__ import annotations

import html
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.accounting_approvals import ApprovalSLATimer
from financeops.db.models.accounting_jv import AccountingJVAggregate, JVStatus
from financeops.db.models.accounting_notifications import (
    AccountingNotificationEvent,
    ApprovalReminderRun,
    NotificationChannel,
    NotificationType,
)

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


async def send_approval_reminders(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
) -> dict[str, int]:
    now = _utcnow()
    sent_24h = 0
    sent_48h = 0

    stmt = (
        select(ApprovalSLATimer, AccountingJVAggregate)
        .join(
            AccountingJVAggregate,
            AccountingJVAggregate.id == ApprovalSLATimer.jv_id,
        )
        .where(
            ApprovalSLATimer.tenant_id == tenant_id,
            AccountingJVAggregate.tenant_id == tenant_id,
            AccountingJVAggregate.status.in_(
                [
                    JVStatus.PENDING_REVIEW,
                    JVStatus.UNDER_REVIEW,
                    JVStatus.RESUBMITTED,
                    JVStatus.ESCALATED,
                ]
            ),
        )
    )
    rows = (await db.execute(stmt)).all()

    for timer, jv in rows:
        if jv.submitted_at is None:
            continue

        hours_pending = (now - jv.submitted_at).total_seconds() / 3600

        if hours_pending >= timer.review_sla_hours and not timer.nudge_24h_sent:
            await _send_reminder(
                db=db,
                tenant_id=tenant_id,
                jv=jv,
                reminder_type=NotificationType.REMINDER_24H,
            )
            timer.nudge_24h_sent = True
            timer.updated_at = now
            sent_24h += 1

        if hours_pending >= timer.approval_sla_hours and not timer.nudge_48h_sent:
            await _send_reminder(
                db=db,
                tenant_id=tenant_id,
                jv=jv,
                reminder_type=NotificationType.REMINDER_48H,
            )
            timer.nudge_48h_sent = True
            timer.updated_at = now
            sent_48h += 1

    await db.flush()
    return {"sent_24h": sent_24h, "sent_48h": sent_48h}


async def _send_reminder(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    jv: AccountingJVAggregate,
    reminder_type: str,
) -> None:
    run = ApprovalReminderRun(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        chain_hash="",
        previous_hash="",
        jv_id=jv.id,
        reminder_type=reminder_type,
        sent_to_user_id=jv.created_by,
        sent_at=_utcnow(),
    )
    db.add(run)

    title = f"JV Approval Reminder - {jv.jv_number}"
    body = (
        f"JV {jv.jv_number} has been pending approval. "
        "Please follow up with the assigned reviewer."
    )

    try:
        from financeops.modules.notifications.service import send_notification

        await send_notification(
            db,
            tenant_id=tenant_id,
            recipient_user_id=jv.created_by,
            notification_type=reminder_type,
            title=title,
            body=body,
            metadata={"jv_id": str(jv.id), "jv_number": jv.jv_number},
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Failed to dispatch reminder notification",
            extra={"tenant_id": str(tenant_id), "jv_id": str(jv.id), "error": str(exc)},
        )

    event = AccountingNotificationEvent(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        chain_hash="",
        previous_hash="",
        jv_id=jv.id,
        recipient_user_id=jv.created_by,
        notification_type=reminder_type,
        channel=NotificationChannel.IN_APP,
        subject=title,
        body=body,
        metadata_json={"jv_id": str(jv.id), "jv_number": jv.jv_number},
        sent_at=_utcnow(),
    )
    db.add(event)
    await db.flush()


async def send_sla_breach_alerts(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
) -> int:
    from financeops.modules.accounting_layer.application.approval_service import (
        check_and_update_sla_breaches,
    )
    from financeops.modules.notifications.service import send_notification

    breached_timers = await check_and_update_sla_breaches(db, tenant_id=tenant_id)
    alerts_sent = 0

    for timer in breached_timers:
        jv = (
            await db.execute(
                select(AccountingJVAggregate).where(
                    AccountingJVAggregate.id == timer.jv_id,
                    AccountingJVAggregate.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if jv is None:
            continue

        title = f"SLA Breach - JV {jv.jv_number}"
        body = f"JV {jv.jv_number} has breached its approval SLA and requires immediate action."

        try:
            await send_notification(
                db,
                tenant_id=tenant_id,
                recipient_user_id=jv.created_by,
                notification_type=NotificationType.SLA_BREACH,
                title=title,
                body=body,
                metadata={"jv_id": str(jv.id), "jv_number": jv.jv_number},
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to dispatch SLA breach notification",
                extra={"tenant_id": str(tenant_id), "jv_id": str(jv.id), "error": str(exc)},
            )

        event = AccountingNotificationEvent(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            chain_hash="",
            previous_hash="",
            jv_id=jv.id,
            recipient_user_id=jv.created_by,
            notification_type=NotificationType.SLA_BREACH,
            channel=NotificationChannel.IN_APP,
            subject=title,
            body=body,
            metadata_json={"jv_id": str(jv.id), "jv_number": jv.jv_number},
            sent_at=_utcnow(),
        )
        db.add(event)
        alerts_sent += 1

    await db.flush()
    return alerts_sent


async def send_daily_digest(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    recipient_user_id: uuid.UUID,
    recipient_email: str,
) -> bool:
    stmt = select(AccountingJVAggregate).where(
        AccountingJVAggregate.tenant_id == tenant_id,
        AccountingJVAggregate.status.in_(
            [
                JVStatus.PENDING_REVIEW,
                JVStatus.UNDER_REVIEW,
                JVStatus.ESCALATED,
            ]
        ),
    )
    pending_jvs = list((await db.execute(stmt)).scalars().all())
    if not pending_jvs:
        return False

    subject = f"FinanceOps Daily Digest - {len(pending_jvs)} JV(s) pending approval"
    lines = [
        f"- {jv.jv_number} | {jv.status} | INR {jv.total_debit}"
        for jv in pending_jvs[:20]
    ]
    if len(pending_jvs) > 20:
        lines.append(f"...and {len(pending_jvs) - 20} more.")
    body = "You have pending Journal Vouchers awaiting approval.\n\n" + "\n".join(lines)
    html_body = "<br/>".join(html.escape(body).splitlines())

    from financeops.modules.notifications.channels.email_channel import send_direct

    sent = await send_direct(
        to=recipient_email,
        subject=subject,
        html_body=f"<html><body><p>{html_body}</p></body></html>",
        text_body=body,
    )
    if not sent:
        return False

    event = AccountingNotificationEvent(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        chain_hash="",
        previous_hash="",
        jv_id=None,
        recipient_user_id=recipient_user_id,
        notification_type=NotificationType.DAILY_DIGEST,
        channel=NotificationChannel.EMAIL,
        subject=subject,
        body=f"{len(pending_jvs)} JVs pending",
        metadata_json={"pending_jv_count": len(pending_jvs)},
        sent_at=_utcnow(),
    )
    db.add(event)
    await db.flush()
    return True

