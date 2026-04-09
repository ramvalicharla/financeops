from __future__ import annotations

import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from financeops.core.exceptions import AuthorizationError, ValidationError
from financeops.core.intent.context import MutationContext, governed_mutation_context
from financeops.db.models.accounting_jv import JVStatus
from financeops.db.models.users import UserRole
from financeops.modules.accounting_layer.application import governance_service, journal_service
from financeops.modules.closing_checklist.api import routes as close_routes


@pytest.mark.asyncio
async def test_maker_cannot_approve_own_journal(monkeypatch: pytest.MonkeyPatch) -> None:
    maker_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    journal_id = uuid.uuid4()

    jv = MagicMock()
    jv.id = journal_id
    jv.tenant_id = tenant_id
    jv.entity_id = uuid.uuid4()
    jv.fiscal_year = 2026
    jv.fiscal_period = 4
    jv.status = JVStatus.SUBMITTED
    jv.created_by = maker_id
    jv.first_reviewed_at = None

    monkeypatch.setattr(journal_service, "_get_journal_aggregate", AsyncMock(return_value=jv))
    monkeypatch.setattr(journal_service, "assert_period_allows_modification", AsyncMock(return_value=None))
    monkeypatch.setattr(
        journal_service,
        "get_approval_policy",
        AsyncMock(
            return_value=governance_service.ApprovalPolicyConfig(
                require_reviewer=False,
                require_distinct_approver=True,
                require_distinct_poster=False,
            )
        ),
    )

    with governed_mutation_context(
        MutationContext(
            intent_id=uuid.uuid4(),
            job_id=uuid.uuid4(),
            actor_user_id=maker_id,
            actor_role=UserRole.finance_leader.value,
            intent_type="APPROVE_JOURNAL",
        )
    ):
        with pytest.raises(ValidationError, match="maker cannot approve own journal"):
            await journal_service.approve_journal(
                AsyncMock(),
                tenant_id=tenant_id,
                journal_id=journal_id,
                acted_by=maker_id,
                actor_role=UserRole.finance_leader.value,
            )


@pytest.mark.asyncio
async def test_posting_blocked_in_locked_period(monkeypatch: pytest.MonkeyPatch) -> None:
    tenant_id = uuid.uuid4()
    poster_id = uuid.uuid4()
    journal_id = uuid.uuid4()

    jv = MagicMock()
    jv.id = journal_id
    jv.tenant_id = tenant_id
    jv.entity_id = uuid.uuid4()
    jv.fiscal_year = 2026
    jv.fiscal_period = 4
    jv.status = JVStatus.APPROVED

    monkeypatch.setattr(journal_service, "_get_journal_aggregate", AsyncMock(return_value=jv))
    monkeypatch.setattr(
        journal_service,
        "assert_period_allows_posting",
        AsyncMock(side_effect=ValidationError("Period is HARD_CLOSED. Posting is blocked.")),
    )

    with governed_mutation_context(
        MutationContext(
            intent_id=uuid.uuid4(),
            job_id=uuid.uuid4(),
            actor_user_id=poster_id,
            actor_role=UserRole.finance_leader.value,
            intent_type="POST_JOURNAL",
        )
    ):
        with pytest.raises(ValidationError, match="HARD_CLOSED"):
            await journal_service.post_journal(
                AsyncMock(),
                tenant_id=tenant_id,
                journal_id=journal_id,
                acted_by=poster_id,
                actor_role=UserRole.finance_leader.value,
            )


def test_unlock_requires_proper_role() -> None:
    with pytest.raises(AuthorizationError):
        governance_service.ensure_unlock_role(UserRole.finance_team)


@pytest.mark.asyncio
async def test_readiness_fails_with_draft_journal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        governance_service,
        "_readiness_data",
        AsyncMock(
            return_value={
                "pending_count": 1,
                "total_debit": 100,
                "total_credit": 100,
                "fx_entities_exist": False,
                "revaluation_done": True,
                "translation_done": True,
                "group_exists": False,
                "consolidation_done": True,
                "coa_present": True,
            }
        ),
    )
    payload = await governance_service.run_close_readiness(
        AsyncMock(),
        tenant_id=uuid.uuid4(),
        org_entity_id=uuid.uuid4(),
        fiscal_year=2026,
        period_number=4,
    )
    assert payload["pass"] is False
    assert payload["blockers"]


@pytest.mark.asyncio
async def test_checklist_progression_marks_autocomplete_items(monkeypatch: pytest.MonkeyPatch) -> None:
    period_id = uuid.uuid4()
    org_entity_id = uuid.uuid4()

    period = MagicMock()
    period.id = period_id
    monkeypatch.setattr(
        governance_service,
        "get_or_create_accounting_period",
        AsyncMock(return_value=period),
    )
    monkeypatch.setattr(
        governance_service,
        "run_close_readiness",
        AsyncMock(
            return_value={
                "pass": True,
                "blockers": [],
                "warnings": [],
                "metrics": {
                    "pending_journals": 0,
                    "trial_balance_total_debit": "100.00",
                    "trial_balance_total_credit": "100.00",
                    "fx_entities_exist": False,
                    "revaluation_done": True,
                    "translation_done": True,
                    "group_exists": False,
                    "consolidation_done": True,
                    "coa_present": True,
                },
            }
        ),
    )

    exec_result = MagicMock()
    exec_result.scalars.return_value.all.return_value = []
    db = AsyncMock()
    db.execute = AsyncMock(return_value=exec_result)

    payload = await governance_service.get_close_checklist(
        db,
        tenant_id=uuid.uuid4(),
        org_entity_id=org_entity_id,
        fiscal_year=2026,
        period_number=4,
    )
    assert payload["items"]
    assert all(
        row["checklist_status"] == governance_service.CloseChecklistStatus.COMPLETED
        for row in payload["items"]
    )


@pytest.mark.asyncio
async def test_submit_journal_emits_governance_audit_event(monkeypatch: pytest.MonkeyPatch) -> None:
    tenant_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    journal_id = uuid.uuid4()

    jv = MagicMock()
    jv.id = journal_id
    jv.tenant_id = tenant_id
    jv.entity_id = uuid.uuid4()
    jv.fiscal_year = 2026
    jv.fiscal_period = 4
    jv.status = JVStatus.DRAFT
    jv.jv_number = "JV-0001"

    record_event_mock = AsyncMock(return_value=None)
    monkeypatch.setattr(journal_service, "_get_journal_aggregate", AsyncMock(return_value=jv))
    monkeypatch.setattr(journal_service, "assert_period_allows_modification", AsyncMock(return_value=None))
    monkeypatch.setattr(journal_service, "_append_state_event", AsyncMock(return_value=None))
    monkeypatch.setattr(journal_service, "_emit_journal_governance_event", record_event_mock)

    with governed_mutation_context(
        MutationContext(
            intent_id=uuid.uuid4(),
            job_id=uuid.uuid4(),
            actor_user_id=actor_id,
            actor_role=UserRole.finance_team.value,
            intent_type="SUBMIT_JOURNAL",
        )
    ):
        response = await journal_service.submit_journal(
            AsyncMock(),
            tenant_id=tenant_id,
            journal_id=journal_id,
            acted_by=actor_id,
            actor_role=UserRole.finance_team.value,
        )

    assert response.status == "SUBMITTED"
    assert record_event_mock.await_count == 1


@pytest.mark.asyncio
async def test_soft_close_blocks_posting_without_override_and_allows_admin_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lock_state = governance_service.EffectivePeriodLock(
        status=governance_service.AccountingPeriodStatus.SOFT_CLOSED,
        period_id=uuid.uuid4(),
        reason="soft close",
        locked_at=None,
        locked_by=None,
        org_entity_id=uuid.uuid4(),
    )
    monkeypatch.setattr(
        governance_service,
        "resolve_effective_period_lock",
        AsyncMock(return_value=lock_state),
    )

    with pytest.raises(ValidationError, match="SOFT_CLOSED"):
        await governance_service.assert_period_allows_posting(
            AsyncMock(),
            tenant_id=uuid.uuid4(),
            org_entity_id=uuid.uuid4(),
            fiscal_year=2026,
            period_number=4,
            actor_role=UserRole.finance_team.value,
        )

    await governance_service.assert_period_allows_posting(
        AsyncMock(),
        tenant_id=uuid.uuid4(),
        org_entity_id=uuid.uuid4(),
        fiscal_year=2026,
        period_number=4,
        actor_role=UserRole.finance_leader.value,
    )


@pytest.mark.asyncio
async def test_hard_close_blocks_posting_for_all_roles(monkeypatch: pytest.MonkeyPatch) -> None:
    lock_state = governance_service.EffectivePeriodLock(
        status=governance_service.AccountingPeriodStatus.HARD_CLOSED,
        period_id=uuid.uuid4(),
        reason="hard close",
        locked_at=None,
        locked_by=None,
        org_entity_id=uuid.uuid4(),
    )
    monkeypatch.setattr(
        governance_service,
        "resolve_effective_period_lock",
        AsyncMock(return_value=lock_state),
    )

    with pytest.raises(ValidationError, match="HARD_CLOSED"):
        await governance_service.assert_period_allows_posting(
            AsyncMock(),
            tenant_id=uuid.uuid4(),
            org_entity_id=uuid.uuid4(),
            fiscal_year=2026,
            period_number=4,
            actor_role=UserRole.finance_leader.value,
        )


@pytest.mark.asyncio
async def test_hard_close_blocks_journal_modification(monkeypatch: pytest.MonkeyPatch) -> None:
    lock_state = governance_service.EffectivePeriodLock(
        status=governance_service.AccountingPeriodStatus.HARD_CLOSED,
        period_id=uuid.uuid4(),
        reason="hard close",
        locked_at=None,
        locked_by=None,
        org_entity_id=uuid.uuid4(),
    )
    monkeypatch.setattr(
        governance_service,
        "resolve_effective_period_lock",
        AsyncMock(return_value=lock_state),
    )

    with pytest.raises(ValidationError, match="HARD_CLOSED"):
        await governance_service.assert_period_allows_modification(
            AsyncMock(),
            tenant_id=uuid.uuid4(),
            org_entity_id=uuid.uuid4(),
            fiscal_year=2026,
            period_number=4,
        )


@pytest.mark.asyncio
async def test_revaluation_blocked_when_period_hard_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    lock_state = governance_service.EffectivePeriodLock(
        status=governance_service.AccountingPeriodStatus.HARD_CLOSED,
        period_id=uuid.uuid4(),
        reason="hard close",
        locked_at=None,
        locked_by=None,
        org_entity_id=uuid.uuid4(),
    )
    monkeypatch.setattr(
        governance_service,
        "resolve_effective_period_lock",
        AsyncMock(return_value=lock_state),
    )

    with pytest.raises(ValidationError, match="HARD_CLOSED"):
        await governance_service.assert_period_allows_revaluation(
            AsyncMock(),
            tenant_id=uuid.uuid4(),
            org_entity_id=uuid.uuid4(),
            as_of_date=date(2026, 4, 1),
            actor_role=UserRole.finance_leader.value,
        )


@pytest.mark.asyncio
async def test_consolidation_blocked_when_period_hard_closed() -> None:
    entities_result = MagicMock()
    entities_result.scalars.return_value.all.return_value = [uuid.uuid4()]

    lock_result = MagicMock()
    lock_result.scalar_one_or_none.return_value = uuid.uuid4()

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[entities_result, lock_result])

    with pytest.raises(ValidationError, match="HARD_CLOSED"):
        await governance_service.assert_group_period_not_hard_closed(
            db,
            tenant_id=uuid.uuid4(),
            org_group_id=uuid.uuid4(),
            as_of_date=date(2026, 4, 1),
        )


@pytest.mark.asyncio
async def test_unlock_records_reason_actor_and_timestamp(monkeypatch: pytest.MonkeyPatch) -> None:
    tenant_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    period = MagicMock()
    period.id = uuid.uuid4()
    period.org_entity_id = uuid.uuid4()
    period.fiscal_year = 2026
    period.period_number = 4
    period.status = governance_service.AccountingPeriodStatus.HARD_CLOSED
    period.reopened_by = None
    period.reopened_at = None
    period.notes = None
    period.updated_at = None

    audit_event_mock = AsyncMock(return_value=None)
    monkeypatch.setattr(
        governance_service,
        "get_or_create_accounting_period",
        AsyncMock(return_value=period),
    )
    monkeypatch.setattr(governance_service, "_append_audit_event", audit_event_mock)

    payload = await governance_service.unlock_period(
        AsyncMock(),
        tenant_id=tenant_id,
        org_entity_id=period.org_entity_id,
        fiscal_year=2026,
        period_number=4,
        reason="Reopen after correction",
        actor_user_id=actor_id,
    )

    assert payload["reason"] == "Reopen after correction"
    assert payload["reopened_by"] == str(actor_id)
    assert payload["reopened_at"] is not None
    assert period.reopened_by == actor_id
    assert period.reopened_at is not None

    called_kwargs = audit_event_mock.await_args.kwargs
    assert called_kwargs["action"] == "period_unlock"
    assert called_kwargs["actor_user_id"] == actor_id
    assert called_kwargs["payload"]["reason"] == "Reopen after correction"


@pytest.mark.asyncio
async def test_readiness_fails_for_draft_and_imbalance(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        governance_service,
        "_readiness_data",
        AsyncMock(
            return_value={
                "pending_count": 2,
                "total_debit": 100,
                "total_credit": 95,
                "fx_entities_exist": False,
                "revaluation_done": True,
                "translation_done": True,
                "group_exists": False,
                "consolidation_done": True,
                "coa_present": True,
            }
        ),
    )
    payload = await governance_service.run_close_readiness(
        AsyncMock(),
        tenant_id=uuid.uuid4(),
        org_entity_id=uuid.uuid4(),
        fiscal_year=2026,
        period_number=4,
    )
    assert payload["pass"] is False
    assert any("Unposted or unapproved journals" in item for item in payload["blockers"])
    assert any("Trial balance is not balanced" in item for item in payload["blockers"])


@pytest.mark.asyncio
async def test_hard_close_blocked_when_readiness_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    user = MagicMock()
    user.id = uuid.uuid4()
    user.tenant_id = uuid.uuid4()
    user.role = UserRole.finance_leader
    session = AsyncMock()
    org_entity_id = uuid.uuid4()
    body = close_routes.LockPeriodRequest(
        org_entity_id=org_entity_id,
        fiscal_year=2026,
        period_number=4,
        lock_type="HARD_CLOSED",
        reason="Month close",
    )

    monkeypatch.setattr(
        close_routes,
        "run_close_readiness",
        AsyncMock(return_value={"pass": False, "blockers": ["Draft journals pending"], "warnings": []}),
    )
    monkeypatch.setattr(close_routes, "emit_governance_event", AsyncMock(return_value=None))
    monkeypatch.setattr(
        close_routes,
        "GuardEngine",
        lambda: MagicMock(
            evaluate_mutation=AsyncMock(return_value=MagicMock(overall_passed=True, blocking_failures=[]))
        ),
    )
    monkeypatch.setattr(
        close_routes,
        "ApprovalPolicyResolver",
        lambda: MagicMock(
            resolve_mutation=AsyncMock(
                return_value=MagicMock(approval_required=True, is_granted=True, reason="approved")
            )
        ),
    )

    with pytest.raises(HTTPException) as exc_info:
        await close_routes.lock_period_endpoint(
            body=body,
            session=session,
            user=user,
        )

    assert exc_info.value.status_code == 422
    assert isinstance(exc_info.value.detail, dict)
    assert exc_info.value.detail.get("code") == "READINESS_FAILED"
