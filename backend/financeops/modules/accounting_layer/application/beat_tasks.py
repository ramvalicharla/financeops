from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from celery import Task
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.accounting_approvals import ApprovalSLATimer
from financeops.db.models.accounting_jv import AccountingJVAggregate, JVStatus
from financeops.db.models.accounting_notifications import (
    AccountingNotificationEvent,
    ApprovalSLABreachRun,
    NotificationChannel,
    NotificationType,
)
from financeops.db.models.reconciliation_bridge import ReconciliationException
from financeops.db.models.tenants import IamTenant, TenantStatus
from financeops.db.models.users import IamUser, UserRole
from financeops.db.session import AsyncSessionLocal, tenant_session
from financeops.modules.accounting_layer.application.notification_service import (
    send_approval_reminders,
)
from financeops.modules.notifications.service import send_notification
from financeops.tasks.base_task import FinanceOpsTask
from financeops.tasks.celery_app import celery_app

_PENDING_JV_STATUSES = frozenset(
    {
        JVStatus.PENDING_REVIEW,
        JVStatus.UNDER_REVIEW,
        JVStatus.RESUBMITTED,
        JVStatus.ESCALATED,
    }
)
_TERMINAL_JV_STATUSES = frozenset(
    {
        JVStatus.APPROVED,
        JVStatus.REJECTED,
        JVStatus.PUSHED,
        JVStatus.VOIDED,
    }
)
_DIGEST_ROLES = frozenset(
    {
        UserRole.finance_leader,
        UserRole.platform_owner,
        UserRole.platform_admin,
    }
)


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)


async def _list_active_tenant_ids() -> list[uuid.UUID]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(IamTenant.id).where(IamTenant.status == TenantStatus.active)
        )
        return list(result.scalars().all())


async def _iter_digest_recipients(session: AsyncSession, *, tenant_id: uuid.UUID) -> list[IamUser]:
    result = await session.execute(
        select(IamUser).where(
            IamUser.tenant_id == tenant_id,
            IamUser.is_active.is_(True),
            IamUser.role.in_(_DIGEST_ROLES),
        )
    )
    return list(result.scalars().all())


async def _create_accounting_notification_event(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    jv_id: uuid.UUID | None,
    recipient_user_id: uuid.UUID,
    notification_type: str,
    subject: str,
    body: str,
    metadata_json: dict[str, Any] | None = None,
) -> None:
    session.add(
        AccountingNotificationEvent(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            chain_hash="",
            previous_hash="",
            jv_id=jv_id,
            recipient_user_id=recipient_user_id,
            notification_type=notification_type,
            channel=NotificationChannel.IN_APP,
            subject=subject,
            body=body,
            metadata_json=metadata_json or {},
            sent_at=_utcnow(),
        )
    )
    await session.flush()


async def _run_approval_reminders() -> dict[str, Any]:
    tenant_ids = await _list_active_tenant_ids()
    totals = {"sent_24h": 0, "sent_48h": 0}

    for tenant_id in tenant_ids:
        async with tenant_session(tenant_id) as session:
            result = await send_approval_reminders(session, tenant_id=tenant_id)
            totals["sent_24h"] += int(result.get("sent_24h", 0))
            totals["sent_48h"] += int(result.get("sent_48h", 0))

    return {
        "status": "complete",
        "tenants_processed": len(tenant_ids),
        **totals,
    }


async def _insert_sla_breach_run_if_missing(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    jv: AccountingJVAggregate,
    breach_type: str,
    breached_at: datetime,
) -> bool:
    existing = (
        await session.execute(
            select(ApprovalSLABreachRun).where(
                ApprovalSLABreachRun.tenant_id == tenant_id,
                ApprovalSLABreachRun.jv_id == jv.id,
                ApprovalSLABreachRun.breach_type == breach_type,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return False

    session.add(
        ApprovalSLABreachRun(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            chain_hash="",
            previous_hash="",
            jv_id=jv.id,
            breach_type=breach_type,
            sent_to_user_id=jv.created_by,
            breached_at=breached_at,
        )
    )
    await session.flush()
    return True


async def _run_sla_breach_checks() -> dict[str, Any]:
    tenant_ids = await _list_active_tenant_ids()
    inserted = 0
    alerts_sent = 0
    now = _utcnow()

    for tenant_id in tenant_ids:
        async with tenant_session(tenant_id) as session:
            result = await session.execute(
                select(ApprovalSLATimer, AccountingJVAggregate)
                .join(AccountingJVAggregate, AccountingJVAggregate.id == ApprovalSLATimer.jv_id)
                .where(
                    ApprovalSLATimer.tenant_id == tenant_id,
                    AccountingJVAggregate.tenant_id == tenant_id,
                    AccountingJVAggregate.status.not_in(_TERMINAL_JV_STATUSES),
                )
            )

            for timer, jv in result.all():
                if jv.submitted_at is None:
                    continue

                candidates: list[tuple[str, datetime]] = []
                review_deadline = jv.submitted_at + timedelta(hours=timer.review_sla_hours)
                if now > review_deadline and jv.status in _PENDING_JV_STATUSES:
                    candidates.append(("review", now))

                approval_deadline = jv.submitted_at + timedelta(hours=timer.approval_sla_hours)
                if now > approval_deadline:
                    candidates.append(("approval", now))

                for breach_type, breached_at in candidates:
                    created = await _insert_sla_breach_run_if_missing(
                        session,
                        tenant_id=tenant_id,
                        jv=jv,
                        breach_type=breach_type,
                        breached_at=breached_at,
                    )
                    if not created:
                        continue

                    subject = f"SLA Breach - JV {jv.jv_number}"
                    body = (
                        f"JV {jv.jv_number} breached its {breach_type} approval SLA and requires immediate action."
                    )
                    metadata = {
                        "jv_id": str(jv.id),
                        "jv_number": jv.jv_number,
                        "breach_type": breach_type,
                    }
                    await send_notification(
                        session,
                        tenant_id=tenant_id,
                        recipient_user_id=jv.created_by,
                        notification_type=NotificationType.SLA_BREACH,
                        title=subject,
                        body=body,
                        metadata=metadata,
                    )
                    await _create_accounting_notification_event(
                        session,
                        tenant_id=tenant_id,
                        jv_id=jv.id,
                        recipient_user_id=jv.created_by,
                        notification_type=NotificationType.SLA_BREACH,
                        subject=subject,
                        body=body,
                        metadata_json=metadata,
                    )
                    inserted += 1
                    alerts_sent += 1

    return {
        "status": "complete",
        "tenants_processed": len(tenant_ids),
        "breaches_inserted": inserted,
        "alerts_sent": alerts_sent,
    }


async def _run_daily_digests() -> dict[str, Any]:
    tenant_ids = await _list_active_tenant_ids()
    notifications_sent = 0
    summaries: dict[str, dict[str, int]] = {}
    start_of_day = _utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    for tenant_id in tenant_ids:
        async with tenant_session(tenant_id) as session:
            recipients = await _iter_digest_recipients(session, tenant_id=tenant_id)
            if not recipients:
                continue

            pending_jvs = int(
                (
                    await session.execute(
                        select(func.count()).select_from(AccountingJVAggregate).where(
                            AccountingJVAggregate.tenant_id == tenant_id,
                            AccountingJVAggregate.status.in_(_PENDING_JV_STATUSES),
                        )
                    )
                ).scalar_one()
                or 0
            )
            sla_breaches = int(
                (
                    await session.execute(
                        select(func.count()).select_from(ApprovalSLABreachRun).where(
                            ApprovalSLABreachRun.tenant_id == tenant_id,
                            ApprovalSLABreachRun.breached_at >= start_of_day,
                        )
                    )
                ).scalar_one()
                or 0
            )
            recon_exceptions = int(
                (
                    await session.execute(
                        select(func.count()).select_from(ReconciliationException).where(
                            ReconciliationException.tenant_id == tenant_id,
                            ReconciliationException.resolution_status == "open",
                        )
                    )
                ).scalar_one()
                or 0
            )

            summary = {
                "pending_jvs": pending_jvs,
                "sla_breaches": sla_breaches,
                "recon_exceptions": recon_exceptions,
            }
            summaries[str(tenant_id)] = summary

            subject = "FinanceOps Daily Digest"
            body = (
                f"Pending JVs: {pending_jvs} | "
                f"SLA breaches today: {sla_breaches} | "
                f"Open recon exceptions: {recon_exceptions}"
            )
            for recipient in recipients:
                await send_notification(
                    session,
                    tenant_id=tenant_id,
                    recipient_user_id=recipient.id,
                    notification_type=NotificationType.DAILY_DIGEST,
                    title=subject,
                    body=body,
                    metadata=summary,
                )
                await _create_accounting_notification_event(
                    session,
                    tenant_id=tenant_id,
                    jv_id=None,
                    recipient_user_id=recipient.id,
                    notification_type=NotificationType.DAILY_DIGEST,
                    subject=subject,
                    body=body,
                    metadata_json=summary,
                )
                notifications_sent += 1

    return {
        "status": "complete",
        "tenants_processed": len(tenant_ids),
        "notifications_sent": notifications_sent,
        "tenant_summaries": summaries,
    }


@celery_app.task(
    bind=True,
    base=FinanceOpsTask,
    name="accounting_layer.approval_reminder",
    queue="normal_q",
)
def approval_reminder_task(self: Task) -> dict[str, Any]:
    del self
    return asyncio.run(_run_approval_reminders())


@celery_app.task(
    bind=True,
    base=FinanceOpsTask,
    name="accounting_layer.sla_breach_check",
    queue="normal_q",
)
def sla_breach_check_task(self: Task) -> dict[str, Any]:
    del self
    return asyncio.run(_run_sla_breach_checks())


@celery_app.task(
    bind=True,
    base=FinanceOpsTask,
    name="accounting_layer.daily_digest",
    queue="low_q",
)
def daily_digest_task(self: Task) -> dict[str, Any]:
    del self
    return asyncio.run(_run_daily_digests())
