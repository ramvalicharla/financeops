from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import (
    get_async_session,
    get_current_user,
    require_auditor_or_above,
    require_finance_leader,
)
from financeops.core.exceptions import NotFoundError, ValidationError
from financeops.db.models.users import IamUser, UserRole
from financeops.modules.compliance.erasure_service import erase_user_pii, list_erasure_logs
from financeops.modules.compliance.gdpr_models import GDPRBreachRecord, GDPRConsentRecord
from financeops.modules.compliance.gdpr_service import (
    export_user_data,
    get_consent_summary,
    record_breach,
    record_consent,
    run_retention_check,
)
from financeops.modules.compliance.iso27001_service import (
    get_iso27001_dashboard,
    get_iso27001_evidence_package,
    run_auto_evaluation as run_iso_auto_evaluation,
)
from financeops.modules.compliance.models import ComplianceControl, ErasureLog
from financeops.modules.compliance.soc2_service import (
    get_soc2_dashboard,
    get_soc2_evidence_package,
    run_auto_evaluation as run_soc2_auto_evaluation,
    set_control_status,
)
from financeops.shared_kernel.pagination import Paginated

router = APIRouter(prefix="/compliance", tags=["compliance"])


class ErasureRequest(BaseModel):
    user_id: uuid.UUID | None = None
    request_method: str | None = None


class ErasureResponse(BaseModel):
    status: str
    user_id_hash: str
    fields_erased: list[str]
    completed_at: str


class ErasureLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    user_id_hash: str
    requested_by: uuid.UUID | None = None
    request_method: str
    status: str
    pii_fields_erased: list[str]
    completed_at: datetime | None = None
    created_at: datetime


class ControlStatusUpdateRequest(BaseModel):
    status: str
    notes: str | None = None


class GDPRExportRequest(BaseModel):
    user_id: uuid.UUID | None = None


class GDPRConsentRequest(BaseModel):
    consent_type: str
    granted: bool
    lawful_basis: str = "consent"


class GDPRBreachRequest(BaseModel):
    breach_type: str
    description: str
    affected_user_count: int = 0
    affected_data_types: list[str] = Field(default_factory=list)
    discovered_at: datetime
    reported_to_dpa_at: datetime | None = None
    notified_users_at: datetime | None = None
    severity: str
    status: str = "open"
    remediation_notes: str | None = None


def _require_platform_admin(user: IamUser) -> IamUser:
    if user.role != UserRole.super_admin:
        raise HTTPException(status_code=403, detail="platform_admin role required")
    return user


def _require_finance_or_platform(user: IamUser) -> IamUser:
    if user.role not in {UserRole.super_admin, UserRole.finance_leader}:
        raise HTTPException(status_code=403, detail="finance_leader or platform_admin role required")
    return user


def _serialize(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    return value


def _serialize_control(row: ComplianceControl) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "framework": row.framework,
        "control_id": row.control_id,
        "control_name": row.control_name,
        "control_description": row.control_description,
        "category": row.category,
        "status": row.status,
        "rag_status": row.rag_status,
        "last_evaluated_at": row.last_evaluated_at.isoformat() if row.last_evaluated_at else None,
        "next_evaluation_due": row.next_evaluation_due.isoformat() if row.next_evaluation_due else None,
        "evidence_summary": row.evidence_summary,
        "auto_evaluable": row.auto_evaluable,
    }


@router.post("/erasure", response_model=ErasureResponse)
async def erasure_endpoint(
    body: ErasureRequest | None = None,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> ErasureResponse:
    payload = body or ErasureRequest()
    target_user_id = payload.user_id or user.id
    if payload.request_method:
        request_method = payload.request_method
    elif target_user_id == user.id:
        request_method = "self"
    else:
        request_method = "admin"

    try:
        result = await erase_user_pii(
            session=session,
            tenant_id=user.tenant_id,
            user_id=target_user_id,
            requested_by=user.id,
            request_method=request_method,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail="User not found") from exc
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc

    return ErasureResponse(**result)


@router.get("/erasure-log", response_model=Paginated[ErasureLogResponse])
async def erasure_log_endpoint(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> Paginated[ErasureLogResponse]:
    rows, total = await list_erasure_logs(
        session=session,
        tenant_id=user.tenant_id,
        limit=limit,
        offset=offset,
    )
    return Paginated[ErasureLogResponse](
        data=[ErasureLogResponse.model_validate(row) for row in rows if isinstance(row, ErasureLog)],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/soc2/dashboard")
async def soc2_dashboard(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    _require_finance_or_platform(user)
    payload = await get_soc2_dashboard(session, user.tenant_id)
    return _serialize(payload)


@router.post("/soc2/evaluate")
async def soc2_evaluate(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    _require_finance_or_platform(user)
    payload = await run_soc2_auto_evaluation(session, user.tenant_id)
    return payload


@router.get("/soc2/evidence")
async def soc2_evidence(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_auditor_or_above),
) -> dict:
    payload = await get_soc2_evidence_package(session, user.tenant_id)
    return _serialize(payload)


@router.get("/soc2/controls", response_model=Paginated[dict])
async def soc2_controls(
    status_filter: str | None = Query(default=None, alias="status"),
    rag_status: str | None = Query(default=None),
    category: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Paginated[dict]:
    _require_finance_or_platform(user)
    stmt = select(ComplianceControl).where(
        ComplianceControl.tenant_id == user.tenant_id,
        ComplianceControl.framework == "SOC2",
    )
    if status_filter:
        stmt = stmt.where(ComplianceControl.status == status_filter)
    if rag_status:
        stmt = stmt.where(ComplianceControl.rag_status == rag_status)
    if category:
        stmt = stmt.where(ComplianceControl.category == category)
    total = len((await session.execute(stmt.with_only_columns(ComplianceControl.id))).scalars().all())
    rows = (
        await session.execute(
            stmt.order_by(ComplianceControl.category, ComplianceControl.control_id).offset(offset).limit(limit)
        )
    ).scalars().all()
    return Paginated[dict](
        data=[_serialize_control(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.patch("/soc2/controls/{control_id}/status")
async def soc2_update_control_status(
    control_id: str,
    body: ControlStatusUpdateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    _require_platform_admin(user)
    row = await set_control_status(
        session,
        tenant_id=user.tenant_id,
        framework="SOC2",
        control_id=control_id,
        new_status=body.status,
        triggered_by="manual_update",
        notes=body.notes,
    )
    return _serialize_control(row)


@router.get("/iso27001/dashboard")
async def iso_dashboard(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    _require_finance_or_platform(user)
    payload = await get_iso27001_dashboard(session, user.tenant_id)
    return _serialize(payload)


@router.post("/iso27001/evaluate")
async def iso_evaluate(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    _require_platform_admin(user)
    payload = await run_iso_auto_evaluation(session, user.tenant_id)
    return payload


@router.get("/iso27001/evidence")
async def iso_evidence(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_auditor_or_above),
) -> dict:
    payload = await get_iso27001_evidence_package(session, user.tenant_id)
    return _serialize(payload)


@router.get("/iso27001/controls", response_model=Paginated[dict])
async def iso_controls(
    status_filter: str | None = Query(default=None, alias="status"),
    rag_status: str | None = Query(default=None),
    category: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Paginated[dict]:
    _require_finance_or_platform(user)
    stmt = select(ComplianceControl).where(
        ComplianceControl.tenant_id == user.tenant_id,
        ComplianceControl.framework == "ISO27001",
    )
    if status_filter:
        stmt = stmt.where(ComplianceControl.status == status_filter)
    if rag_status:
        stmt = stmt.where(ComplianceControl.rag_status == rag_status)
    if category:
        stmt = stmt.where(ComplianceControl.category == category)
    total = len((await session.execute(stmt.with_only_columns(ComplianceControl.id))).scalars().all())
    rows = (
        await session.execute(
            stmt.order_by(ComplianceControl.category, ComplianceControl.control_id).offset(offset).limit(limit)
        )
    ).scalars().all()
    return Paginated[dict](
        data=[_serialize_control(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.patch("/iso27001/controls/{control_id}/status")
async def iso_update_control_status(
    control_id: str,
    body: ControlStatusUpdateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    _require_platform_admin(user)
    row = await set_control_status(
        session,
        tenant_id=user.tenant_id,
        framework="ISO27001",
        control_id=control_id,
        new_status=body.status,
        triggered_by="manual_update",
        notes=body.notes,
    )
    return _serialize_control(row)


@router.post("/gdpr/export")
async def gdpr_export(
    body: GDPRExportRequest | None = None,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    requested_user = body.user_id if body else None
    target_user = requested_user or user.id
    if requested_user is not None and requested_user != user.id:
        _require_finance_or_platform(user)
    payload = await export_user_data(
        session,
        tenant_id=user.tenant_id,
        user_id=target_user,
        requested_by=user.id,
    )
    return _serialize(payload)


@router.post("/gdpr/consent")
async def gdpr_consent_create(
    body: GDPRConsentRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    row = await record_consent(
        session,
        tenant_id=user.tenant_id,
        user_id=user.id,
        consent_type=body.consent_type,
        granted=body.granted,
        lawful_basis=body.lawful_basis,
    )
    return {
        "id": str(row.id),
        "consent_type": row.consent_type,
        "granted": row.granted,
        "granted_at": row.granted_at.isoformat() if row.granted_at else None,
        "withdrawn_at": row.withdrawn_at.isoformat() if row.withdrawn_at else None,
        "lawful_basis": row.lawful_basis,
    }


@router.get("/gdpr/consent")
async def gdpr_consent_list(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    rows = (
        await session.execute(
            select(GDPRConsentRecord).where(
                GDPRConsentRecord.tenant_id == user.tenant_id,
                GDPRConsentRecord.user_id == user.id,
            )
        )
    ).scalars().all()
    return [
        {
            "consent_type": row.consent_type,
            "granted": row.granted,
            "granted_at": row.granted_at.isoformat() if row.granted_at else None,
            "withdrawn_at": row.withdrawn_at.isoformat() if row.withdrawn_at else None,
            "lawful_basis": row.lawful_basis,
        }
        for row in rows
    ]


@router.get("/gdpr/consent/summary")
async def gdpr_consent_summary(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    _require_finance_or_platform(user)
    payload = await get_consent_summary(session, user.tenant_id)
    return _serialize(payload)


@router.post("/gdpr/breach", status_code=status.HTTP_201_CREATED)
async def gdpr_breach_create(
    body: GDPRBreachRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    _require_finance_or_platform(user)
    row = await record_breach(
        session,
        tenant_id=user.tenant_id,
        breach_data=body.model_dump(),
        created_by=user.id,
    )
    return {
        "id": str(row.id),
        "breach_type": row.breach_type,
        "severity": row.severity,
        "status": row.status,
        "affected_user_count": row.affected_user_count,
        "discovered_at": row.discovered_at.isoformat(),
        "created_at": row.created_at.isoformat(),
    }


@router.get("/gdpr/breaches", response_model=Paginated[dict])
async def gdpr_breach_list(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Paginated[dict]:
    _require_finance_or_platform(user)
    stmt = select(GDPRBreachRecord).where(GDPRBreachRecord.tenant_id == user.tenant_id)
    total = len((await session.execute(stmt.with_only_columns(GDPRBreachRecord.id))).scalars().all())
    rows = (
        await session.execute(
            stmt.order_by(GDPRBreachRecord.discovered_at.desc()).offset(offset).limit(limit)
        )
    ).scalars().all()
    return Paginated[dict](
        data=[
            {
                "id": str(row.id),
                "breach_type": row.breach_type,
                "description": row.description,
                "affected_user_count": row.affected_user_count,
                "affected_data_types": row.affected_data_types,
                "discovered_at": row.discovered_at.isoformat(),
                "reported_to_dpa_at": row.reported_to_dpa_at.isoformat() if row.reported_to_dpa_at else None,
                "notified_users_at": row.notified_users_at.isoformat() if row.notified_users_at else None,
                "severity": row.severity,
                "status": row.status,
                "remediation_notes": row.remediation_notes,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/gdpr/retention-check")
async def gdpr_retention_check(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    _require_platform_admin(user)
    payload = await run_retention_check(session, user.tenant_id)
    return payload
