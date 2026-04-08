from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.governance.airlock import AirlockActor, AirlockAdmissionService
from financeops.core.governance.approvals import ApprovalPolicyResolver, ApprovalRequest
from financeops.core.governance.guards import GuardEngine, MutationGuardContext
from financeops.db.models.governance_control import (
    AirlockEvent,
    AirlockItem,
    CanonicalGovernanceEvent,
    GovernanceApprovalPolicy,
)
from financeops.db.models.users import UserRole


@pytest.mark.asyncio
async def test_airlock_submission_quarantines_then_admits_clean_payload(
    async_session: AsyncSession,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_id = test_user.tenant_id
    actor = AirlockActor(user_id=test_user.id, tenant_id=tenant_id, role=test_user.role.value)
    service = AirlockAdmissionService()

    fake_scan = SimpleNamespace(
        mime_type="text/csv",
        size_bytes=12,
        sha256="abc123",
        quarantine_ref="quarantine://abc123",
        status="APPROVED",
        rejection_reason=None,
        scan_result="clean",
    )
    monkeypatch.setattr(
        "financeops.core.governance.guards.scan_and_seal",
        AsyncMock(return_value=fake_scan),
    )
    monkeypatch.setattr(
        "financeops.core.governance.airlock.scan_and_seal",
        AsyncMock(return_value=fake_scan),
    )

    submitted = await service.submit_external_input(
        async_session,
        source_type="erp_sync_upload",
        actor=actor,
        metadata={"connection_id": "conn-1"},
        content=b"id,value\n1,2",
        file_name="sample.csv",
        source_reference="conn-1",
    )
    admitted = await service.admit_airlock_item(async_session, item_id=submitted.item_id, actor=actor)

    item = (
        await async_session.execute(
            select(AirlockItem).where(AirlockItem.id == submitted.item_id)
        )
    ).scalar_one()
    assert submitted.status == "QUARANTINED"
    assert admitted.status == "ADMITTED"
    assert item.status == "ADMITTED"
    assert item.source_type == "erp_sync_upload"
    assert item.checksum_sha256 == "abc123"

    airlock_events = (
        await async_session.execute(
            select(AirlockEvent).where(AirlockEvent.airlock_item_id == item.id)
        )
    ).scalars().all()
    governance_events = (
        await async_session.execute(
            select(CanonicalGovernanceEvent).where(
                CanonicalGovernanceEvent.subject_id == str(item.id)
            )
        )
    ).scalars().all()
    assert {row.event_type for row in airlock_events} >= {
        "AIRLOCK_RECEIVED",
        "AIRLOCK_SCANNED",
        "AIRLOCK_QUARANTINED",
        "AIRLOCK_ADMITTED",
    }
    assert {row.event_type for row in governance_events} >= {
        "GUARD_EVALUATED",
        "AIRLOCK_RECEIVED",
        "AIRLOCK_QUARANTINED",
        "AIRLOCK_ADMITTED",
    }


@pytest.mark.asyncio
async def test_guard_engine_blocks_missing_airlock_admission(async_session: AsyncSession, test_user) -> None:
    evaluation = await GuardEngine().evaluate_mutation(
        async_session,
        context=MutationGuardContext(
            tenant_id=test_user.tenant_id,
            module_key="erp_sync",
            mutation_type="ERP_SYNC_TRIGGER",
            actor_user_id=test_user.id,
            actor_role=test_user.role.value,
            entity_id=None,
            requires_airlock_admission=True,
            subject_id="sync-run",
        ),
    )

    assert evaluation.overall_passed is False
    assert any(row.guard_code == "airlock.admission" and row.result == "FAIL" for row in evaluation.results)


@pytest.mark.asyncio
async def test_airlock_submission_hashes_long_caller_idempotency_key(
    async_session: AsyncSession,
    test_user,
) -> None:
    tenant_id = test_user.tenant_id
    actor = AirlockActor(user_id=test_user.id, tenant_id=tenant_id, role=test_user.role.value)
    service = AirlockAdmissionService()
    long_key = ":".join(str(uuid.uuid4()) for _ in range(8))

    submitted = await service.submit_external_input(
        async_session,
        source_type="normalization_upload",
        actor=actor,
        metadata={"source_id": "source-1"},
        source_reference="source-1",
        idempotency_key=long_key,
    )

    item = (
        await async_session.execute(
            select(AirlockItem).where(AirlockItem.id == submitted.item_id)
        )
    ).scalar_one()
    assert len(long_key) > 128
    assert len(item.idempotency_key) == 64
    assert item.idempotency_key != long_key


@pytest.mark.asyncio
async def test_airlock_duplicate_detection_allows_same_file_for_distinct_metadata(
    async_session: AsyncSession,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actor = AirlockActor(user_id=test_user.id, tenant_id=test_user.tenant_id, role=test_user.role.value)
    service = AirlockAdmissionService()
    fake_scan = SimpleNamespace(
        mime_type="text/csv",
        size_bytes=12,
        sha256="same-checksum",
        quarantine_ref="quarantine://same-checksum",
        status="APPROVED",
        rejection_reason=None,
        scan_result="clean",
    )
    monkeypatch.setattr(
        "financeops.core.governance.guards.scan_and_seal",
        AsyncMock(return_value=fake_scan),
    )
    monkeypatch.setattr(
        "financeops.core.governance.airlock.scan_and_seal",
        AsyncMock(return_value=fake_scan),
    )

    first = await service.submit_external_input(
        async_session,
        source_type="normalization_upload",
        actor=actor,
        metadata={"source_id": "source-1", "reporting_period": "2026-01-31"},
        content=b"id,value\n1,2",
        file_name="sample.csv",
        source_reference="source-1",
    )
    second = await service.submit_external_input(
        async_session,
        source_type="normalization_upload",
        actor=actor,
        metadata={"source_id": "source-1", "reporting_period": "2026-02-28"},
        content=b"id,value\n1,2",
        file_name="sample.csv",
        source_reference="source-1",
    )

    assert first.item_id != second.item_id


@pytest.mark.asyncio
async def test_approval_policy_resolver_uses_default_and_tenant_specific_rules(
    async_session: AsyncSession,
    test_user,
) -> None:
    resolver = ApprovalPolicyResolver()
    denied = await resolver.resolve_mutation(
        async_session,
        request=ApprovalRequest(
            tenant_id=test_user.tenant_id,
            module_key="period_close",
            mutation_type="PERIOD_UNLOCK",
            entity_id=None,
            actor_user_id=test_user.id,
            actor_role=UserRole.finance_team.value,
            subject_id="unlock",
        ),
    )
    assert denied.approval_required is True
    assert denied.is_granted is False
    assert denied.required_role == UserRole.finance_leader.value

    async_session.add(
        GovernanceApprovalPolicy(
            tenant_id=test_user.tenant_id,
            entity_id=None,
            policy_name="GST low threshold",
            module_key="gst",
            mutation_type="GST_RETURN_SUBMIT",
            source_type=None,
            threshold_amount="1000.0000",
            required_approver_role=UserRole.finance_leader.value,
            approval_mode="single",
            active_flag=True,
            priority=5,
            policy_payload_json={"reason": "low threshold"},
            created_by=test_user.id,
        )
    )
    await async_session.flush()

    granted = await resolver.resolve_mutation(
            async_session,
            request=ApprovalRequest(
                tenant_id=test_user.tenant_id,
                module_key="gst",
                mutation_type="GST_RETURN_SUBMIT",
                entity_id=None,
                actor_user_id=test_user.id,
                actor_role=UserRole.finance_leader.value,
                amount="5000.00",
            subject_id="gst-return",
        ),
    )
    assert granted.approval_required is True
    assert granted.is_granted is True
    assert granted.required_role == UserRole.finance_leader.value


@pytest.mark.asyncio
async def test_approval_policy_resolver_blocks_finance_team_for_approve_journal_default(
    async_session: AsyncSession,
    test_user,
) -> None:
    evaluation = await ApprovalPolicyResolver().resolve_mutation(
        async_session,
        request=ApprovalRequest(
            tenant_id=test_user.tenant_id,
            module_key="accounting_layer",
            mutation_type="APPROVE_JOURNAL",
            entity_id=None,
            actor_user_id=test_user.id,
            actor_role=UserRole.finance_team.value,
            subject_id="approve-journal",
        ),
    )

    assert evaluation.approval_required is True
    assert evaluation.is_granted is False
    assert evaluation.required_role == UserRole.finance_leader.value
