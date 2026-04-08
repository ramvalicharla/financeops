from __future__ import annotations

import base64
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from financeops.api.v1 import gst as gst_routes
from financeops.core.governance.approvals import ApprovalEvaluation
from financeops.core.intent.service import IntentSubmissionResult
from financeops.db.models.users import UserRole
from financeops.modules.closing_checklist.api import routes as close_routes
from financeops.modules.erp_sync.api import sync_runs as erp_sync_routes
from financeops.modules.payroll_gl_normalization.api import routes as normalization_routes


def _scalar_result(value):
    return SimpleNamespace(scalar_one_or_none=lambda: value)


@pytest.mark.asyncio
async def test_erp_sync_route_requires_airlock_before_trigger(monkeypatch: pytest.MonkeyPatch) -> None:
    airlock_item_id = uuid.uuid4()
    submit_mock = AsyncMock(
        return_value=SimpleNamespace(
            item_id=airlock_item_id,
            status="QUARANTINED",
            quarantine_ref="quarantine://item",
            checksum_sha256="abc",
            admitted=False,
        )
    )
    admit_mock = AsyncMock(
        return_value=SimpleNamespace(
            item_id=airlock_item_id,
            status="ADMITTED",
            quarantine_ref="quarantine://item",
            checksum_sha256="abc",
            admitted=True,
        )
    )
    submit_intent_mock = AsyncMock(
        return_value=IntentSubmissionResult(
            intent_id=uuid.uuid4(),
            status="RECORDED",
            job_id=uuid.uuid4(),
            next_action="NONE",
            record_refs={"sync_run_id": str(uuid.uuid4()), "sync_run_status": "created"},
        )
    )
    monkeypatch.setattr(erp_sync_routes.AirlockAdmissionService, "submit_external_input", submit_mock)
    monkeypatch.setattr(erp_sync_routes.AirlockAdmissionService, "admit_airlock_item", admit_mock)
    monkeypatch.setattr(erp_sync_routes.IntentService, "submit_intent", submit_intent_mock)
    monkeypatch.setattr(erp_sync_routes, "start_workflow", lambda **_kwargs: object())
    monkeypatch.setattr(erp_sync_routes, "complete_workflow", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(erp_sync_routes, "fail_workflow", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(erp_sync_routes, "observe_erp_sync", lambda **_kwargs: None)

    request = SimpleNamespace(state=SimpleNamespace(correlation_id="corr-1", request_id="req-1"))
    session = AsyncMock()
    user = SimpleNamespace(id=uuid.uuid4(), tenant_id=uuid.uuid4(), role=UserRole.finance_leader)

    payload = await erp_sync_routes.create_sync_run.__wrapped__(
        request=request,
        body={
            "connection_id": str(uuid.uuid4()),
            "sync_definition_id": str(uuid.uuid4()),
            "sync_definition_version_id": str(uuid.uuid4()),
            "dataset_type": "trial_balance",
            "entity_id": str(uuid.uuid4()),
            "file_name": "sample.csv",
            "file_content_base64": base64.b64encode(b"id,value\n1,2").decode("ascii"),
        },
        session=session,
        user=user,
        idempotency_key="idem-1",
    )

    assert submit_mock.await_count == 1
    assert admit_mock.await_count == 1
    submit_kwargs = submit_intent_mock.await_args.kwargs
    assert submit_kwargs["payload"]["admitted_airlock_item_id"] == str(airlock_item_id)
    assert submit_kwargs["payload"]["source_type"] == "erp_sync_upload"
    assert payload["data"]["airlock_item_id"] == str(airlock_item_id)
    assert payload["data"]["intent_id"] == str(submit_intent_mock.return_value.intent_id)
    assert payload["data"]["job_id"] == str(submit_intent_mock.return_value.job_id)


@pytest.mark.asyncio
async def test_normalization_upload_route_requires_airlock_before_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    airlock_item_id = uuid.uuid4()
    submit_mock = AsyncMock(
        return_value=SimpleNamespace(
            item_id=airlock_item_id,
            status="QUARANTINED",
            quarantine_ref="q://1",
            checksum_sha256="abc",
            admitted=False,
        )
    )
    admit_mock = AsyncMock(
        return_value=SimpleNamespace(
            item_id=airlock_item_id,
            status="ADMITTED",
            quarantine_ref="q://1",
            checksum_sha256="abc",
            admitted=True,
        )
    )
    submit_intent_mock = AsyncMock(
        return_value=IntentSubmissionResult(
            intent_id=uuid.uuid4(),
            status="RECORDED",
            job_id=uuid.uuid4(),
            next_action="NONE",
            record_refs={
                "run_id": str(uuid.uuid4()),
                "run_token": "run-token",
                "run_status": "pending",
                "payroll_line_count": 1,
                "gl_line_count": 0,
                "exception_count": 0,
                "source_airlock_item_id": str(airlock_item_id),
                "idempotent": False,
            },
        )
    )
    monkeypatch.setattr(normalization_routes.AirlockAdmissionService, "submit_external_input", submit_mock)
    monkeypatch.setattr(normalization_routes.AirlockAdmissionService, "admit_airlock_item", admit_mock)
    monkeypatch.setattr(normalization_routes.IntentService, "submit_intent", submit_intent_mock)

    session = AsyncMock()
    user = SimpleNamespace(id=uuid.uuid4(), tenant_id=uuid.uuid4(), role=UserRole.finance_leader)
    request = SimpleNamespace(state=SimpleNamespace(request_id="req-1", correlation_id="corr-1"))
    body = normalization_routes.RunUploadRequest(
        organisation_id=uuid.uuid4(),
        source_id=uuid.uuid4(),
        source_version_id=uuid.uuid4(),
        run_type="payroll_normalization",
        reporting_period="2026-03-31",
        source_artifact_id=uuid.uuid4(),
        file_name="payroll.csv",
        file_content_base64=base64.b64encode(b"id,value\n1,2").decode("ascii"),
        sheet_name=None,
    )

    response = await normalization_routes.upload_run(
        body=body,
        request=request,
        session=session,
        user=user,
    )

    assert submit_mock.await_count == 1
    assert admit_mock.await_count == 1
    assert submit_intent_mock.await_args.kwargs["payload"]["admitted_airlock_item_id"] == str(airlock_item_id)
    assert response.source_airlock_item_id == airlock_item_id
    assert response.intent_id == submit_intent_mock.return_value.intent_id
    assert response.job_id == submit_intent_mock.return_value.job_id


@pytest.mark.asyncio
async def test_unlock_period_endpoint_blocks_when_canonical_approval_denied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(close_routes, "ensure_unlock_role", lambda _role: None)
    monkeypatch.setattr(
        close_routes,
        "GuardEngine",
        lambda: SimpleNamespace(
            evaluate_mutation=AsyncMock(return_value=SimpleNamespace(overall_passed=True, blocking_failures=[]))
        ),
    )
    monkeypatch.setattr(
        close_routes,
        "ApprovalPolicyResolver",
        lambda: SimpleNamespace(
            resolve_mutation=AsyncMock(
                return_value=ApprovalEvaluation(
                    approval_required=True,
                    is_granted=False,
                    required_role=UserRole.finance_leader.value,
                    policy_id=None,
                    next_action="APPROVAL_REQUIRED",
                    reason="approval denied",
                )
            )
        ),
    )

    with pytest.raises(HTTPException, match="approval denied"):
        await close_routes.unlock_period_endpoint(
            body=close_routes.UnlockPeriodRequest(
                org_entity_id=uuid.uuid4(),
                fiscal_year=2026,
                period_number=3,
                reason="need reopen",
            ),
            session=AsyncMock(),
            user=SimpleNamespace(id=uuid.uuid4(), tenant_id=uuid.uuid4(), role=UserRole.finance_leader),
        )


@pytest.mark.asyncio
async def test_gst_create_return_blocks_when_canonical_approval_denied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_id = uuid.uuid4()
    entity_id = uuid.uuid4()
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_scalar_result(SimpleNamespace(entity_name="GST Entity")))
    monkeypatch.setattr(gst_routes, "resolve_entity_id", AsyncMock(return_value=entity_id))
    monkeypatch.setattr(gst_routes, "assert_entity_access", AsyncMock(return_value=None))
    monkeypatch.setattr(
        gst_routes,
        "GuardEngine",
        lambda: SimpleNamespace(
            evaluate_mutation=AsyncMock(return_value=SimpleNamespace(overall_passed=True, blocking_failures=[]))
        ),
    )
    monkeypatch.setattr(
        gst_routes,
        "ApprovalPolicyResolver",
        lambda: SimpleNamespace(
            resolve_mutation=AsyncMock(
                return_value=ApprovalEvaluation(
                    approval_required=True,
                    is_granted=False,
                    required_role=UserRole.finance_leader.value,
                    policy_id=None,
                    next_action="APPROVAL_REQUIRED",
                    reason="gst approval denied",
                )
            )
        ),
    )

    with pytest.raises(HTTPException, match="gst approval denied"):
        await gst_routes.create_return(
            body=gst_routes.CreateGstReturnRequest(
                period_year=2026,
                period_month=3,
                entity_id=entity_id,
                gstin="29ABCDE1234F1Z5",
                return_type="GSTR1",
                taxable_value="100000.00",
                igst_amount="18000.00",
                cgst_amount="0",
                sgst_amount="0",
            ),
            session=session,
            user=SimpleNamespace(id=uuid.uuid4(), tenant_id=tenant_id, role=UserRole.finance_leader),
        )
