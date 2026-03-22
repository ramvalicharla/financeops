from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
from financeops.db.models.anomaly_pattern_engine import AnomalyResult, AnomalyStatisticalRule
from financeops.db.models.users import IamUser
from financeops.shared_kernel.pagination import Paginated

router = APIRouter(prefix="/anomalies", tags=["anomalies"])


class AnomalyAlertResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    alert_type: str
    rule_code: str
    severity: str
    category: str
    detected_at: datetime
    alert_status: str
    snoozed_until: datetime | None
    resolved_at: datetime | None
    escalated_at: datetime | None
    status_note: str | None
    status_updated_by: uuid.UUID | None
    run_id: uuid.UUID
    line_no: int
    anomaly_code: str
    anomaly_name: str
    anomaly_score: Decimal
    confidence_score: Decimal
    persistence_classification: str
    correlation_flag: bool
    materiality_elevated: bool
    risk_elevated: bool
    board_flag: bool
    source_summary_json: dict[str, Any]
    source_table: str | None
    source_row_id: str | None
    created_by: uuid.UUID
    created_at: datetime


class AlertStatusUpdateRequest(BaseModel):
    status: Literal["SNOOZED", "RESOLVED", "ESCALATED"]
    snoozed_until: date | None = None
    note: str | None = None

    @model_validator(mode="after")
    def _validate_snoozed_until(self) -> "AlertStatusUpdateRequest":
        if self.status == "SNOOZED" and self.snoozed_until is None:
            raise ValueError("snoozed_until is required when status is SNOOZED")
        return self


class ThresholdUpdateRequest(BaseModel):
    threshold_value: str
    config: dict[str, Any] = Field(default_factory=dict)


class ThresholdUpdateResponse(BaseModel):
    rule_code: str
    updated: bool


class ThresholdRowResponse(BaseModel):
    rule_code: str
    current_threshold: str
    config: dict[str, Any]
    status: str
    effective_from: date


def _extract_source_reference(row: AnomalyResult) -> tuple[str | None, str | None]:
    source_summary = row.source_summary_json or {}
    source_table = source_summary.get("source_table")
    source_row_id = source_summary.get("source_row_id")

    if source_table is None:
        source_table = source_summary.get("table")
    if source_row_id is None:
        source_row_id = source_summary.get("row_id")

    if source_row_id is None:
        source_row_id = source_summary.get("gl_entry_id")
        if source_row_id is not None and source_table is None:
            source_table = "gl_entries"

    return (
        str(source_table) if source_table is not None else None,
        str(source_row_id) if source_row_id is not None else None,
    )


def _alert_to_response(row: AnomalyResult) -> AnomalyAlertResponse:
    source_table, source_row_id = _extract_source_reference(row)
    return AnomalyAlertResponse(
        id=row.id,
        tenant_id=row.tenant_id,
        alert_type=row.anomaly_code,
        rule_code=row.anomaly_code,
        severity=row.severity.upper(),
        category=row.anomaly_domain,
        detected_at=row.created_at,
        alert_status=row.alert_status,
        snoozed_until=row.snoozed_until,
        resolved_at=row.resolved_at,
        escalated_at=row.escalated_at,
        status_note=row.status_note,
        status_updated_by=row.status_updated_by,
        run_id=row.run_id,
        line_no=row.line_no,
        anomaly_code=row.anomaly_code,
        anomaly_name=row.anomaly_name,
        anomaly_score=row.anomaly_score,
        confidence_score=row.confidence_score,
        persistence_classification=row.persistence_classification,
        correlation_flag=row.correlation_flag,
        materiality_elevated=row.materiality_elevated,
        risk_elevated=row.risk_elevated,
        board_flag=row.board_flag,
        source_summary_json=row.source_summary_json or {},
        source_table=source_table,
        source_row_id=source_row_id,
        created_by=row.created_by,
        created_at=row.created_at,
    )


@router.get("", response_model=Paginated[AnomalyAlertResponse] | list[AnomalyAlertResponse])
async def list_anomaly_alerts(
    request: Request,
    severity: str | None = Query(default=None),
    category: str | None = Query(default=None),
    status_filter: str = Query(default="OPEN", alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Paginated[AnomalyAlertResponse] | list[AnomalyAlertResponse]:
    stmt = select(AnomalyResult).where(AnomalyResult.tenant_id == user.tenant_id)

    if severity:
        stmt = stmt.where(AnomalyResult.severity == severity.lower())
    if category:
        stmt = stmt.where(AnomalyResult.anomaly_domain == category)

    normalized_status = status_filter.strip().upper()
    if normalized_status not in {"OPEN", "SNOOZED", "RESOLVED", "ESCALATED", "ALL"}:
        raise HTTPException(status_code=422, detail="Invalid status filter")
    if normalized_status != "ALL":
        stmt = stmt.where(AnomalyResult.alert_status == normalized_status)

    total = (
        await session.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()
    result = await session.execute(
        stmt.order_by(AnomalyResult.created_at.desc(), AnomalyResult.id.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = result.scalars().all()
    data = [_alert_to_response(row) for row in rows]
    if "limit" not in request.query_params and "offset" not in request.query_params:
        return data
    return Paginated[AnomalyAlertResponse](data=data, total=int(total), limit=limit, offset=offset)


@router.get("/thresholds", response_model=Paginated[ThresholdRowResponse] | list[ThresholdRowResponse])
async def list_anomaly_thresholds(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Paginated[ThresholdRowResponse] | list[ThresholdRowResponse]:
    base_stmt = select(AnomalyStatisticalRule).where(
        AnomalyStatisticalRule.tenant_id == user.tenant_id
    )
    total = (
        await session.execute(select(func.count()).select_from(base_stmt.subquery()))
    ).scalar_one()
    result = await session.execute(
        base_stmt
        .order_by(
            AnomalyStatisticalRule.rule_code.asc(),
            AnomalyStatisticalRule.effective_from.desc(),
            AnomalyStatisticalRule.created_at.desc(),
        )
        .limit(limit)
        .offset(offset)
    )
    rows = result.scalars().all()
    data = [
        ThresholdRowResponse(
            rule_code=row.rule_code,
            current_threshold=str(row.z_threshold),
            config=row.configuration_json or {},
            status=row.status,
            effective_from=row.effective_from,
        )
        for row in rows
    ]
    if "limit" not in request.query_params and "offset" not in request.query_params:
        return data
    return Paginated[ThresholdRowResponse](data=data, total=int(total), limit=limit, offset=offset)


@router.put("/thresholds/{rule_code}", response_model=ThresholdUpdateResponse)
async def update_anomaly_threshold(
    rule_code: str,
    body: ThresholdUpdateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> ThresholdUpdateResponse:
    try:
        threshold_value = Decimal(body.threshold_value)
    except (InvalidOperation, TypeError) as exc:
        raise HTTPException(status_code=422, detail="threshold_value must be a valid decimal string") from exc

    result = await session.execute(
        select(AnomalyStatisticalRule)
        .where(
            AnomalyStatisticalRule.tenant_id == user.tenant_id,
            AnomalyStatisticalRule.rule_code == rule_code,
            AnomalyStatisticalRule.status == "active",
        )
        .order_by(AnomalyStatisticalRule.created_at.desc(), AnomalyStatisticalRule.id.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if row is None:
        return ThresholdUpdateResponse(rule_code=rule_code, updated=False)

    row.z_threshold = threshold_value
    row.configuration_json = body.config
    await session.flush()
    return ThresholdUpdateResponse(rule_code=rule_code, updated=True)


@router.get("/{alert_id}", response_model=AnomalyAlertResponse)
async def get_anomaly_alert(
    alert_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> AnomalyAlertResponse:
    result = await session.execute(
        select(AnomalyResult).where(
            AnomalyResult.tenant_id == user.tenant_id,
            AnomalyResult.id == alert_id,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Anomaly alert not found")
    return _alert_to_response(row)


@router.patch("/{alert_id}/status", response_model=AnomalyAlertResponse)
async def update_anomaly_alert_status(
    alert_id: uuid.UUID,
    body: AlertStatusUpdateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> AnomalyAlertResponse:
    result = await session.execute(
        select(AnomalyResult).where(
            AnomalyResult.tenant_id == user.tenant_id,
            AnomalyResult.id == alert_id,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Anomaly alert not found")

    now = datetime.now(UTC)
    row.alert_status = body.status
    row.status_note = body.note
    row.status_updated_by = user.id

    if body.status == "SNOOZED":
        row.snoozed_until = datetime.combine(body.snoozed_until, time.min, tzinfo=UTC)
    elif body.status == "RESOLVED":
        row.resolved_at = now
    elif body.status == "ESCALATED":
        row.escalated_at = now

    await session.flush()
    await session.refresh(row)
    return _alert_to_response(row)
