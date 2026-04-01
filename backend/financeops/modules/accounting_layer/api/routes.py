from __future__ import annotations

from datetime import date
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import AuthorizationError
from financeops.api.deps import get_async_session, get_current_user
from financeops.db.models.accounting_jv import AccountingJVAggregate
from financeops.db.models.users import IamUser, UserRole
from financeops.modules.accounting_layer.api.reporting_routes import reporting_router
from financeops.modules.accounting_layer.application.approval_service import (
    get_jv_approvals,
    get_sla_metrics,
    submit_approval,
)
from financeops.modules.accounting_layer.application.financial_statements_service import (
    get_balance_sheet,
    get_cash_flow_statement,
    get_profit_and_loss,
)
from financeops.modules.accounting_layer.application.journal_service import (
    approve_journal,
    create_journal_draft,
    get_journal,
    list_journals,
    post_journal,
    review_journal,
    reverse_journal,
    submit_journal,
)
from financeops.modules.accounting_layer.application.revaluation_service import (
    run_fx_revaluation,
)
from financeops.modules.accounting_layer.application.trial_balance_service import (
    get_trial_balance,
)
from financeops.modules.accounting_layer.application.jv_service import (
    create_jv,
    get_jv,
    get_jv_state_history,
    list_jvs,
    transition_jv,
    update_jv_lines,
)
from financeops.modules.accounting_layer.domain.schemas import (
    ApprovalRequest,
    ApprovalResponse,
    BalanceSheetResponse,
    CashFlowResponse,
    JournalActionResponse,
    JournalCreate,
    JournalResponse,
    JVCreate,
    JVLineResponse,
    PnLResponse,
    RevaluationRunRequest,
    RevaluationRunResponse,
    JVResponse,
    JVStateEventResponse,
    JVTransitionRequest,
    JVUpdateLines,
    SLAMetricsResponse,
    TrialBalanceResponse,
)
from financeops.shared_kernel.response import ok

jv_router = APIRouter(prefix="/jv", tags=["Accounting JV"])
journals_router = APIRouter(prefix="/journals", tags=["Accounting Journals"])
router = APIRouter()


def _is_admin(user: IamUser) -> bool:
    return user.role in {UserRole.super_admin, UserRole.finance_leader, UserRole.platform_owner}


def _can_review(user: IamUser) -> bool:
    return user.role in {
        UserRole.finance_team,
        UserRole.finance_leader,
        UserRole.super_admin,
        UserRole.platform_owner,
        UserRole.platform_admin,
    }


def _can_approve(user: IamUser) -> bool:
    return user.role in {
        UserRole.finance_leader,
        UserRole.super_admin,
        UserRole.platform_owner,
        UserRole.platform_admin,
    }


def _can_post(user: IamUser) -> bool:
    return user.role in {
        UserRole.finance_leader,
        UserRole.super_admin,
        UserRole.platform_owner,
        UserRole.platform_admin,
    }


def _serialize_jv(jv: AccountingJVAggregate) -> dict[str, Any]:
    active_lines = [line for line in jv.lines if line.jv_version == jv.version]
    if not active_lines and jv.lines:
        latest_version = max(line.jv_version for line in jv.lines)
        active_lines = [line for line in jv.lines if line.jv_version == latest_version]

    base_payload = JVResponse.model_validate(jv).model_dump(mode="json")
    base_payload["lines"] = [
        JVLineResponse.model_validate(line).model_dump(mode="json")
        for line in active_lines
    ]
    return base_payload


@jv_router.post("/")
async def create_jv_endpoint(
    request: Request,
    body: JVCreate,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    jv = await create_jv(
        session,
        tenant_id=user.tenant_id,
        entity_id=body.entity_id,
        created_by=user.id,
        period_date=body.period_date,
        fiscal_year=body.fiscal_year,
        fiscal_period=body.fiscal_period,
        description=body.description,
        reference=body.reference,
        currency=body.currency,
        location_id=body.location_id,
        cost_centre_id=body.cost_centre_id,
        workflow_instance_id=body.workflow_instance_id,
        lines=[line.model_dump() for line in body.lines] if body.lines else None,
    )
    await session.flush()
    return ok(
        _serialize_jv(jv),
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@jv_router.get("/")
async def list_jvs_endpoint(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
    entity_id: uuid.UUID | None = Query(default=None),
    status: str | None = Query(default=None),
    fiscal_year: int | None = Query(default=None),
    fiscal_period: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    rows = await list_jvs(
        session,
        tenant_id=user.tenant_id,
        entity_id=entity_id,
        status=status,
        fiscal_year=fiscal_year,
        fiscal_period=fiscal_period,
        limit=limit,
        offset=offset,
    )
    payload = [_serialize_jv(row) for row in rows]
    return ok(payload, request_id=getattr(request.state, "request_id", None)).model_dump(mode="json")


@jv_router.get("/{jv_id}")
async def get_jv_endpoint(
    request: Request,
    jv_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    jv = await get_jv(session, jv_id=jv_id, tenant_id=user.tenant_id)
    return ok(
        _serialize_jv(jv),
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@jv_router.put("/{jv_id}/lines")
async def update_jv_lines_endpoint(
    request: Request,
    jv_id: uuid.UUID,
    body: JVUpdateLines,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    jv = await update_jv_lines(
        session,
        jv_id=jv_id,
        tenant_id=user.tenant_id,
        lines=[line.model_dump() for line in body.lines],
        expected_version=body.expected_version,
    )
    await session.flush()
    return ok(
        _serialize_jv(jv),
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@jv_router.post("/{jv_id}/transition")
async def transition_jv_endpoint(
    request: Request,
    jv_id: uuid.UUID,
    body: JVTransitionRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    jv = await transition_jv(
        session,
        jv_id=jv_id,
        tenant_id=user.tenant_id,
        to_status=body.to_status,
        triggered_by=user.id,
        actor_role=user.role.value,
        expected_version=body.expected_version,
        comment=body.comment,
        is_admin=_is_admin(user),
    )
    await session.flush()
    return ok(
        _serialize_jv(jv),
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@jv_router.get("/{jv_id}/history")
async def get_jv_history_endpoint(
    request: Request,
    jv_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    events = await get_jv_state_history(session, jv_id=jv_id, tenant_id=user.tenant_id)
    payload = [JVStateEventResponse.model_validate(event).model_dump(mode="json") for event in events]
    return ok(payload, request_id=getattr(request.state, "request_id", None)).model_dump(mode="json")


@jv_router.post("/{jv_id}/approve")
async def approve_jv_endpoint(
    request: Request,
    jv_id: uuid.UUID,
    body: ApprovalRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    approval = await submit_approval(
        session,
        jv_id=jv_id,
        tenant_id=user.tenant_id,
        acted_by=user.id,
        actor_role=user.role.value,
        decision=body.decision,
        decision_reason=body.decision_reason,
        expected_version=body.expected_version,
        idempotency_key=body.idempotency_key,
        delegated_from=body.delegated_from,
    )
    await session.flush()
    payload = ApprovalResponse.model_validate(approval).model_dump(mode="json")
    return ok(payload, request_id=getattr(request.state, "request_id", None)).model_dump(mode="json")


@jv_router.get("/{jv_id}/approvals")
async def get_jv_approvals_endpoint(
    request: Request,
    jv_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    approvals = await get_jv_approvals(session, jv_id=jv_id, tenant_id=user.tenant_id)
    payload = [ApprovalResponse.model_validate(item).model_dump(mode="json") for item in approvals]
    return ok(payload, request_id=getattr(request.state, "request_id", None)).model_dump(mode="json")


@jv_router.get("/sla/metrics")
async def sla_metrics_endpoint(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
    entity_id: uuid.UUID | None = Query(default=None),
    fiscal_year: int | None = Query(default=None),
    fiscal_period: int | None = Query(default=None),
) -> dict[str, Any]:
    metrics = await get_sla_metrics(
        session,
        tenant_id=user.tenant_id,
        entity_id=entity_id,
        fiscal_year=fiscal_year,
        fiscal_period=fiscal_period,
    )
    payload = SLAMetricsResponse(**metrics).model_dump(mode="json")
    return ok(payload, request_id=getattr(request.state, "request_id", None)).model_dump(mode="json")


@journals_router.post("/")
async def create_journal_endpoint(
    request: Request,
    body: JournalCreate,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    journal = await create_journal_draft(
        session,
        tenant_id=user.tenant_id,
        created_by=user.id,
        payload=body,
    )
    await session.flush()
    return ok(
        journal.model_dump(mode="json"),
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@journals_router.get("/")
async def list_journals_endpoint(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
    org_entity_id: uuid.UUID | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    journals = await list_journals(
        session,
        tenant_id=user.tenant_id,
        entity_id=org_entity_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    return ok(
        [item.model_dump(mode="json") for item in journals],
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@journals_router.post("/{journal_id}/approve")
async def approve_journal_endpoint(
    request: Request,
    journal_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    if not _can_approve(user):
        raise AuthorizationError("finance approver role required")
    result = await approve_journal(
        session,
        tenant_id=user.tenant_id,
        journal_id=journal_id,
        acted_by=user.id,
        actor_role=user.role.value,
    )
    await session.flush()
    payload = JournalActionResponse.model_validate(result).model_dump(mode="json")
    return ok(
        payload,
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@journals_router.post("/{journal_id}/post")
async def post_journal_endpoint(
    request: Request,
    journal_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    if not _can_post(user):
        raise AuthorizationError("finance poster role required")
    result = await post_journal(
        session,
        tenant_id=user.tenant_id,
        journal_id=journal_id,
        acted_by=user.id,
        actor_role=user.role.value,
    )
    await session.flush()
    payload = JournalActionResponse.model_validate(result).model_dump(mode="json")
    return ok(
        payload,
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@journals_router.post("/{journal_id}/reverse")
async def reverse_journal_endpoint(
    request: Request,
    journal_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    if not _can_post(user):
        raise AuthorizationError("finance poster role required")
    journal = await reverse_journal(
        session,
        tenant_id=user.tenant_id,
        journal_id=journal_id,
        acted_by=user.id,
        actor_role=user.role.value,
    )
    await session.flush()
    return ok(
        journal.model_dump(mode="json"),
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@journals_router.post("/{journal_id}/submit")
async def submit_journal_endpoint(
    request: Request,
    journal_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    result = await submit_journal(
        session,
        tenant_id=user.tenant_id,
        journal_id=journal_id,
        acted_by=user.id,
        actor_role=user.role.value,
    )
    await session.flush()
    payload = JournalActionResponse.model_validate(result).model_dump(mode="json")
    return ok(
        payload,
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@journals_router.post("/{journal_id}/review")
async def review_journal_endpoint(
    request: Request,
    journal_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    if not _can_review(user):
        raise AuthorizationError("finance reviewer role required")
    result = await review_journal(
        session,
        tenant_id=user.tenant_id,
        journal_id=journal_id,
        acted_by=user.id,
        actor_role=user.role.value,
    )
    await session.flush()
    payload = JournalActionResponse.model_validate(result).model_dump(mode="json")
    return ok(
        payload,
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@journals_router.get("/{journal_id}")
async def get_journal_endpoint(
    request: Request,
    journal_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    journal = await get_journal(
        session,
        tenant_id=user.tenant_id,
        journal_id=journal_id,
    )
    return ok(
        journal.model_dump(mode="json"),
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.get("/trial-balance")
async def get_trial_balance_endpoint(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
    org_entity_id: uuid.UUID = Query(...),
    as_of_date: date = Query(...),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
) -> dict[str, Any]:
    payload = await get_trial_balance(
        session,
        tenant_id=user.tenant_id,
        org_entity_id=org_entity_id,
        as_of_date=as_of_date,
        from_date=from_date,
        to_date=to_date,
    )
    result = TrialBalanceResponse.model_validate(payload).model_dump(mode="json")
    return ok(
        result,
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.get("/pnl")
async def get_pnl_endpoint(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
    org_entity_id: uuid.UUID = Query(...),
    from_date: date = Query(...),
    to_date: date = Query(...),
) -> dict[str, Any]:
    payload = await get_profit_and_loss(
        session,
        tenant_id=user.tenant_id,
        org_entity_id=org_entity_id,
        from_date=from_date,
        to_date=to_date,
    )
    result = PnLResponse.model_validate(payload).model_dump(mode="json")
    return ok(
        result,
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.get("/balance-sheet")
async def get_balance_sheet_endpoint(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
    org_entity_id: uuid.UUID = Query(...),
    as_of_date: date = Query(...),
) -> dict[str, Any]:
    payload = await get_balance_sheet(
        session,
        tenant_id=user.tenant_id,
        org_entity_id=org_entity_id,
        as_of_date=as_of_date,
    )
    result = BalanceSheetResponse.model_validate(payload).model_dump(mode="json")
    return ok(
        result,
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.get("/cash-flow")
async def get_cash_flow_endpoint(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
    org_entity_id: uuid.UUID = Query(...),
    from_date: date = Query(...),
    to_date: date = Query(...),
) -> dict[str, Any]:
    payload = await get_cash_flow_statement(
        session,
        tenant_id=user.tenant_id,
        org_entity_id=org_entity_id,
        from_date=from_date,
        to_date=to_date,
    )
    result = CashFlowResponse.model_validate(payload).model_dump(mode="json")
    return ok(
        result,
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.post("/revaluation/run")
async def run_revaluation_endpoint(
    request: Request,
    body: RevaluationRunRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    payload = await run_fx_revaluation(
        session,
        tenant_id=user.tenant_id,
        entity_id=body.org_entity_id,
        as_of_date=body.as_of_date,
        initiated_by=user.id,
        actor_role=user.role.value,
    )
    result = RevaluationRunResponse.model_validate(payload).model_dump(mode="json")
    return ok(
        result,
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


jv_router.include_router(reporting_router)
router.include_router(jv_router)
router.include_router(journals_router)
