from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import ValidationError
from financeops.core.intent.enums import IntentEventType, IntentSourceChannel, IntentType
from financeops.core.intent.service import IntentActor, IntentService
from financeops.core.security import hash_password
from financeops.db.models.accounting_jv import AccountingJVAggregate
from financeops.db.models.intent_pipeline import CanonicalIntent, CanonicalIntentEvent
from financeops.db.models.users import IamUser, UserRole
from financeops.modules.accounting_layer.application.journal_service import create_journal_draft
from financeops.modules.accounting_layer.domain.schemas import JournalCreate
from financeops.modules.coa.models import TenantCoaAccount
from financeops.platform.db.models.entities import CpEntity


async def _seed_accounts(async_session: AsyncSession, tenant_id: uuid.UUID) -> None:
    async_session.add_all(
        [
            TenantCoaAccount(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                account_code="1000",
                display_name="Cash",
                is_active=True,
            ),
            TenantCoaAccount(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                account_code="2000",
                display_name="Revenue",
                is_active=True,
            ),
        ]
    )
    await async_session.flush()


async def _default_entity(async_session: AsyncSession, tenant_id: uuid.UUID) -> CpEntity:
    return (
        await async_session.execute(select(CpEntity).where(CpEntity.tenant_id == tenant_id))
    ).scalar_one()


def _payload(entity_id: uuid.UUID) -> dict[str, object]:
    return {
        "org_entity_id": str(entity_id),
        "journal_date": "2026-04-01",
        "reference": "INTENT-001",
        "narration": "Intent pipeline test",
        "lines": [
            {"account_code": "1000", "debit": "100.00", "credit": "0.00", "memo": "Debit"},
            {"account_code": "2000", "debit": "0.00", "credit": "100.00", "memo": "Credit"},
        ],
    }


@pytest.mark.asyncio
async def test_intent_lifecycle_emits_events_and_reuses_idempotency(
    async_session: AsyncSession,
    test_user,
) -> None:
    await _seed_accounts(async_session, test_user.tenant_id)
    entity = await _default_entity(async_session, test_user.tenant_id)
    actor = IntentActor(
        user_id=test_user.id,
        tenant_id=test_user.tenant_id,
        role=test_user.role.value,
        source_channel=IntentSourceChannel.API.value,
        request_id="unit-lifecycle",
    )

    service = IntentService(async_session)
    result = await service.submit_intent(
        intent_type=IntentType.CREATE_JOURNAL,
        actor=actor,
        payload=_payload(entity.id),
        idempotency_key="lifecycle-key",
    )

    assert result.status == "RECORDED"
    assert result.job_id is not None
    journal_id = uuid.UUID(result.record_refs["journal_id"])

    journal = (
        await async_session.execute(
            select(AccountingJVAggregate).where(AccountingJVAggregate.id == journal_id)
        )
    ).scalar_one()
    assert journal.created_by_intent_id == result.intent_id
    assert journal.recorded_by_job_id == result.job_id

    events = (
        await async_session.execute(
            select(CanonicalIntentEvent)
            .where(CanonicalIntentEvent.intent_id == result.intent_id)
            .order_by(CanonicalIntentEvent.event_at.asc())
        )
    ).scalars().all()
    assert [event.event_type for event in events] == [
        IntentEventType.AUTH_CONTEXT_CAPTURED.value,
        IntentEventType.INTENT_CREATED.value,
        IntentEventType.INTENT_SUBMITTED.value,
        IntentEventType.INTENT_VALIDATED.value,
        IntentEventType.INTENT_APPROVED.value,
        IntentEventType.JOB_DISPATCHED.value,
        IntentEventType.JOB_EXECUTED.value,
        IntentEventType.RECORD_RECORDED.value,
    ]

    duplicate = await service.submit_intent(
        intent_type=IntentType.CREATE_JOURNAL,
        actor=actor,
        payload=_payload(entity.id),
        idempotency_key="lifecycle-key",
    )
    assert duplicate.intent_id == result.intent_id
    assert duplicate.job_id == result.job_id


@pytest.mark.asyncio
async def test_guards_reject_invalid_post_and_unauthorized_approve(
    async_session: AsyncSession,
    test_user,
) -> None:
    await _seed_accounts(async_session, test_user.tenant_id)
    entity = await _default_entity(async_session, test_user.tenant_id)
    leader_actor = IntentActor(
        user_id=test_user.id,
        tenant_id=test_user.tenant_id,
        role=test_user.role.value,
        source_channel=IntentSourceChannel.API.value,
    )
    service = IntentService(async_session)
    created = await service.submit_intent(
        intent_type=IntentType.CREATE_JOURNAL,
        actor=leader_actor,
        payload=_payload(entity.id),
        idempotency_key="guard-create",
    )
    journal_id = uuid.UUID(created.record_refs["journal_id"])

    with pytest.raises(ValidationError):
        await service.submit_intent(
            intent_type=IntentType.POST_JOURNAL,
            actor=leader_actor,
            payload={},
            target_id=journal_id,
            idempotency_key="guard-post-draft",
        )

    await service.submit_intent(
        intent_type=IntentType.SUBMIT_JOURNAL,
        actor=leader_actor,
        payload={},
        target_id=journal_id,
        idempotency_key="guard-submit",
    )
    await service.submit_intent(
        intent_type=IntentType.REVIEW_JOURNAL,
        actor=leader_actor,
        payload={},
        target_id=journal_id,
        idempotency_key="guard-review",
    )

    low_role_user = IamUser(
        tenant_id=test_user.tenant_id,
        email="finance-team@example.com",
        hashed_password=hash_password("TestPass123!"),
        full_name="Finance Team",
        role=UserRole.finance_team,
        is_active=True,
        mfa_enabled=False,
    )
    async_session.add(low_role_user)
    await async_session.flush()

    low_role_actor = IntentActor(
        user_id=low_role_user.id,
        tenant_id=low_role_user.tenant_id,
        role=low_role_user.role.value,
        source_channel=IntentSourceChannel.API.value,
    )
    with pytest.raises(ValidationError):
        await service.submit_intent(
            intent_type=IntentType.APPROVE_JOURNAL,
            actor=low_role_actor,
            payload={},
            target_id=journal_id,
            idempotency_key="guard-unauthorized-approve",
        )

    rejected_intent = (
        await async_session.execute(
            select(CanonicalIntent).where(
                CanonicalIntent.idempotency_key == "guard-unauthorized-approve"
            )
        )
    ).scalar_one()
    assert rejected_intent.status == "REJECTED"


@pytest.mark.asyncio
async def test_direct_domain_mutation_is_blocked_without_intent_context(
    async_session: AsyncSession,
    test_user,
) -> None:
    await _seed_accounts(async_session, test_user.tenant_id)
    entity = await _default_entity(async_session, test_user.tenant_id)

    with pytest.raises(ValidationError):
        await create_journal_draft(
            async_session,
            tenant_id=test_user.tenant_id,
            created_by=test_user.id,
            payload=JournalCreate.model_validate(_payload(entity.id)),
        )
