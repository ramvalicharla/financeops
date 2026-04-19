from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.security import hash_password
from financeops.db.models.accounting_approvals import ApprovalSLATimer
from financeops.db.models.accounting_jv import AccountingJVAggregate, JVStatus
from financeops.db.models.accounting_notifications import (
    AccountingNotificationEvent,
    ApprovalReminderRun,
    ApprovalSLABreachRun,
    NotificationType,
)
from financeops.db.models.reconciliation_bridge import (
    ReconciliationException,
    ReconciliationLine,
    ReconciliationSession,
)
from financeops.db.models.tenants import IamTenant, TenantStatus, TenantType
from financeops.db.models.users import IamUser, UserRole
from financeops.modules.accounting_layer.application.beat_tasks import (
    _run_approval_reminders,
    _run_daily_digests,
    _run_sla_breach_checks,
)
from financeops.modules.notifications.models import NotificationEvent
from financeops.platform.db.models.entities import CpEntity
from financeops.platform.db.models.organisations import CpOrganisation
from financeops.tasks.celery_app import celery_app
from financeops.utils.chain_hash import GENESIS_HASH, compute_chain_hash


def _tenant_chain(payload: dict[str, str]) -> str:
    return compute_chain_hash(payload, GENESIS_HASH)


async def _seed_tenant_with_user(
    session: AsyncSession,
    *,
    display_name: str,
    email: str,
) -> tuple[IamTenant, IamUser, CpEntity]:
    tenant_id = uuid.uuid4()
    tenant = IamTenant(
        id=tenant_id,
        tenant_id=tenant_id,
        display_name=display_name,
        tenant_type=TenantType.direct,
        country="IN",
        timezone="Asia/Kolkata",
        status=TenantStatus.active,
        chain_hash=_tenant_chain({"display_name": display_name, "tenant_type": TenantType.direct.value}),
        previous_hash=GENESIS_HASH,
        org_setup_complete=True,
        org_setup_step=7,
    )
    session.add(tenant)
    await session.flush()

    user = IamUser(
        tenant_id=tenant.id,
        email=email,
        hashed_password=hash_password("BeatTaskPass123!"),
        full_name=f"{display_name} User",
        role=UserRole.finance_leader,
        is_active=True,
        mfa_enabled=False,
    )
    session.add(user)
    await session.flush()

    org = CpOrganisation(
        tenant_id=tenant.id,
        organisation_code=f"ORG_{uuid.uuid4().hex[:8]}",
        organisation_name=f"{display_name} Org",
        parent_organisation_id=None,
        supersedes_id=None,
        is_active=True,
        correlation_id=f"org-{tenant.id}",
        chain_hash=_tenant_chain({"tenant_id": str(tenant.id), "organisation_name": f"{display_name} Org"}),
        previous_hash=GENESIS_HASH,
    )
    session.add(org)
    await session.flush()

    entity = CpEntity(
        tenant_id=tenant.id,
        organisation_id=org.id,
        group_id=None,
        entity_code=f"ENT_{uuid.uuid4().hex[:8]}",
        entity_name=f"{display_name} Entity",
        base_currency="INR",
        country_code="IN",
        status="active",
        deactivated_at=None,
        correlation_id=f"entity-{tenant.id}",
        chain_hash=_tenant_chain({"tenant_id": str(tenant.id), "entity_name": f"{display_name} Entity"}),
        previous_hash=GENESIS_HASH,
    )
    session.add(entity)
    await session.flush()
    return tenant, user, entity


async def _create_jv(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    created_by: uuid.UUID,
    jv_number: str,
    status: str,
    submitted_at: datetime,
    total: Decimal = Decimal("1000.00"),
) -> AccountingJVAggregate:
    row = AccountingJVAggregate(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        chain_hash="",
        previous_hash="",
        entity_id=entity_id,
        location_id=None,
        cost_centre_id=None,
        jv_number=jv_number,
        status=status,
        version=1,
        period_date=date(2026, 4, 1),
        fiscal_year=2026,
        fiscal_period=4,
        description=f"{jv_number} description",
        reference=None,
        source="MANUAL",
        external_reference_id=None,
        total_debit=total,
        total_credit=total,
        currency="INR",
        workflow_instance_id=None,
        created_by=created_by,
        created_by_intent_id=None,
        recorded_by_job_id=None,
        resubmission_count=0,
        voided_by=None,
        void_reason=None,
        voided_at=None,
        submitted_at=submitted_at,
        first_reviewed_at=None,
        decided_at=None,
    )
    session.add(row)
    await session.flush()
    return row


@pytest.mark.asyncio
@pytest.mark.integration
async def test_approval_reminder_task_sends_notification_for_pending_approval(
    api_db_session: AsyncSession,
) -> None:
    tenant, user, entity = await _seed_tenant_with_user(
        api_db_session,
        display_name="Reminder Tenant",
        email=f"reminder-{uuid.uuid4().hex[:8]}@example.com",
    )
    jv = await _create_jv(
        api_db_session,
        tenant_id=tenant.id,
        entity_id=entity.id,
        created_by=user.id,
        jv_number="JV-REM-001",
        status=JVStatus.PENDING_REVIEW,
        submitted_at=datetime.now(UTC) - timedelta(hours=30),
    )
    api_db_session.add(
        ApprovalSLATimer(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            jv_id=jv.id,
            review_sla_hours=24,
            approval_sla_hours=48,
            review_breached=False,
            approval_breached=False,
            nudge_24h_sent=False,
            nudge_48h_sent=False,
            updated_at=datetime.now(UTC),
        )
    )
    await api_db_session.flush()

    result = await _run_approval_reminders()

    reminder_runs = list(
        (
            await api_db_session.execute(
                select(ApprovalReminderRun).where(ApprovalReminderRun.tenant_id == tenant.id)
            )
        ).scalars().all()
    )
    notification_events = list(
        (
            await api_db_session.execute(
                select(NotificationEvent).where(
                    NotificationEvent.tenant_id == tenant.id,
                    NotificationEvent.notification_type == NotificationType.REMINDER_24H,
                )
            )
        ).scalars().all()
    )

    assert result["status"] == "complete"
    assert result["sent_24h"] >= 1
    assert len(reminder_runs) == 1
    assert len(notification_events) == 1
    assert notification_events[0].recipient_user_id == user.id


@pytest.mark.asyncio
@pytest.mark.integration
async def test_sla_breach_task_inserts_breached_row_not_updates(
    api_db_session: AsyncSession,
) -> None:
    tenant, user, entity = await _seed_tenant_with_user(
        api_db_session,
        display_name="SLA Tenant",
        email=f"sla-{uuid.uuid4().hex[:8]}@example.com",
    )
    jv = await _create_jv(
        api_db_session,
        tenant_id=tenant.id,
        entity_id=entity.id,
        created_by=user.id,
        jv_number="JV-SLA-001",
        status=JVStatus.PENDING_REVIEW,
        submitted_at=datetime.now(UTC) - timedelta(hours=5),
    )
    timer = ApprovalSLATimer(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        jv_id=jv.id,
        review_sla_hours=1,
        approval_sla_hours=999,
        review_breached=False,
        approval_breached=False,
        nudge_24h_sent=False,
        nudge_48h_sent=False,
        updated_at=datetime.now(UTC),
    )
    api_db_session.add(timer)
    await api_db_session.flush()

    first = await _run_sla_breach_checks()
    second = await _run_sla_breach_checks()

    refreshed_timer = (
        await api_db_session.execute(select(ApprovalSLATimer).where(ApprovalSLATimer.id == timer.id))
    ).scalar_one()
    breach_rows = list(
        (
            await api_db_session.execute(
                select(ApprovalSLABreachRun).where(ApprovalSLABreachRun.tenant_id == tenant.id)
            )
        ).scalars().all()
    )
    accounting_events = list(
        (
            await api_db_session.execute(
                select(AccountingNotificationEvent).where(
                    AccountingNotificationEvent.tenant_id == tenant.id,
                    AccountingNotificationEvent.notification_type == NotificationType.SLA_BREACH,
                )
            )
        ).scalars().all()
    )

    assert first["status"] == "complete"
    assert second["status"] == "complete"
    assert first["breaches_inserted"] >= 1
    assert len(breach_rows) == 1
    assert refreshed_timer.review_breached is False
    assert refreshed_timer.approval_breached is False
    assert len(accounting_events) == 1


@pytest.mark.asyncio
@pytest.mark.integration
async def test_daily_digest_task_aggregates_correctly_per_tenant(
    api_db_session: AsyncSession,
) -> None:
    tenant_a, user_a, entity_a = await _seed_tenant_with_user(
        api_db_session,
        display_name="Digest Tenant A",
        email=f"digest-a-{uuid.uuid4().hex[:8]}@example.com",
    )
    tenant_b, user_b, entity_b = await _seed_tenant_with_user(
        api_db_session,
        display_name="Digest Tenant B",
        email=f"digest-b-{uuid.uuid4().hex[:8]}@example.com",
    )

    await _create_jv(
        api_db_session,
        tenant_id=tenant_a.id,
        entity_id=entity_a.id,
        created_by=user_a.id,
        jv_number="JV-DIG-001",
        status=JVStatus.PENDING_REVIEW,
        submitted_at=datetime.now(UTC) - timedelta(hours=10),
    )
    await _create_jv(
        api_db_session,
        tenant_id=tenant_a.id,
        entity_id=entity_a.id,
        created_by=user_a.id,
        jv_number="JV-DIG-002",
        status=JVStatus.UNDER_REVIEW,
        submitted_at=datetime.now(UTC) - timedelta(hours=4),
    )
    await _create_jv(
        api_db_session,
        tenant_id=tenant_b.id,
        entity_id=entity_b.id,
        created_by=user_b.id,
        jv_number="JV-DIG-101",
        status=JVStatus.PENDING_REVIEW,
        submitted_at=datetime.now(UTC) - timedelta(hours=2),
    )

    api_db_session.add(
        ApprovalSLABreachRun(
            id=uuid.uuid4(),
            tenant_id=tenant_a.id,
            chain_hash="",
            previous_hash="",
            jv_id=(
                await api_db_session.execute(
                    select(AccountingJVAggregate.id).where(
                        AccountingJVAggregate.tenant_id == tenant_a.id,
                        AccountingJVAggregate.jv_number == "JV-DIG-001",
                    )
                )
            ).scalar_one(),
            breach_type="review",
            sent_to_user_id=user_a.id,
            breached_at=datetime.now(UTC),
        )
    )

    recon_session = ReconciliationSession(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        chain_hash="",
        previous_hash="",
        organisation_id=entity_a.organisation_id,
        reconciliation_type="gl_tb",
        source_a_type="gl",
        source_a_ref="gl://seed",
        source_b_type="tb",
        source_b_ref="tb://seed",
        period_start=date(2026, 4, 1),
        period_end=date(2026, 4, 30),
        matching_rule_version="v1",
        tolerance_rule_version="v1",
        session_token=f"token-{uuid.uuid4().hex}",
        materiality_config_json={},
        status="completed",
        created_by=user_a.id,
    )
    api_db_session.add(recon_session)
    await api_db_session.flush()

    recon_line = ReconciliationLine(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        chain_hash="",
        previous_hash="",
        entity_id=entity_a.id,
        session_id=recon_session.id,
        scope_id=None,
        line_key=f"line-{uuid.uuid4().hex[:8]}",
        comparison_dimension_json={},
        source_a_value=Decimal("100"),
        source_b_value=Decimal("90"),
        variance_value=Decimal("10"),
        variance_abs=Decimal("10"),
        variance_pct=Decimal("11.11"),
        currency_code="INR",
        reconciliation_status="exception",
        difference_type="value_mismatch",
        materiality_flag=True,
        explanation_hint=None,
        created_by=user_a.id,
    )
    api_db_session.add(recon_line)
    await api_db_session.flush()

    api_db_session.add(
        ReconciliationException(
            id=uuid.uuid4(),
            tenant_id=tenant_a.id,
            chain_hash="",
            previous_hash="",
            entity_id=entity_a.id,
            session_id=recon_session.id,
            line_id=recon_line.id,
            exception_code="VALUE_MISMATCH",
            severity="warning",
            message="Seed exception",
            owner_role="finance_leader",
            resolution_status="open",
            created_by=user_a.id,
        )
    )
    await api_db_session.flush()

    result = await _run_daily_digests()

    digest_events = list(
        (
            await api_db_session.execute(
                select(NotificationEvent).where(
                    NotificationEvent.notification_type == NotificationType.DAILY_DIGEST
                )
            )
        ).scalars().all()
    )
    tenant_a_event = next(row for row in digest_events if row.tenant_id == tenant_a.id)
    tenant_b_event = next(row for row in digest_events if row.tenant_id == tenant_b.id)

    assert result["status"] == "complete"
    assert result["tenant_summaries"][str(tenant_a.id)] == {
        "pending_jvs": 2,
        "sla_breaches": 1,
        "recon_exceptions": 1,
    }
    assert result["tenant_summaries"][str(tenant_b.id)] == {
        "pending_jvs": 1,
        "sla_breaches": 0,
        "recon_exceptions": 0,
    }
    assert tenant_a_event.metadata_json == {
        "pending_jvs": 2,
        "sla_breaches": 1,
        "recon_exceptions": 1,
    }
    assert tenant_b_event.metadata_json == {
        "pending_jvs": 1,
        "sla_breaches": 0,
        "recon_exceptions": 0,
    }


def test_accounting_beat_tasks_registered_in_celery() -> None:
    assert "accounting_layer.approval_reminder" in celery_app.tasks
    assert "accounting_layer.sla_breach_check" in celery_app.tasks
    assert "accounting_layer.daily_digest" in celery_app.tasks
