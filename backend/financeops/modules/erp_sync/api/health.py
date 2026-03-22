from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
from financeops.db.models.erp_sync import (
    ExternalSyncHealthAlert,
    ExternalSyncRun,
)
from financeops.db.models.users import IamUser
from financeops.modules.erp_sync.application.health_service import HealthService
from financeops.modules.erp_sync.domain.enums import DatasetType
from financeops.shared_kernel.response import ok

router = APIRouter()


@router.get("/health")
async def get_sync_health(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    total_open_alerts = (
        await session.execute(
            select(func.count(ExternalSyncHealthAlert.id)).where(
                ExternalSyncHealthAlert.tenant_id == user.tenant_id,
                ExternalSyncHealthAlert.alert_status == "open",
            )
        )
    ).scalar_one()
    latest_runs = (
        await session.execute(
            select(ExternalSyncRun)
            .where(ExternalSyncRun.tenant_id == user.tenant_id)
            .order_by(ExternalSyncRun.created_at.desc(), ExternalSyncRun.id.desc())
            .limit(25)
        )
    ).scalars().all()
    return ok(
        {
            "status": "ok",
            "open_alerts": int(total_open_alerts or 0),
            "recent_runs": [
                {
                    "sync_run_id": str(row.id),
                    "connection_id": str(row.connection_id),
                    "dataset_type": row.dataset_type,
                    "run_status": row.run_status,
                }
                for row in latest_runs
            ],
        },
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.get("/health/alerts")
async def list_health_alerts(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    rows = (
        await session.execute(
            select(ExternalSyncHealthAlert)
            .where(ExternalSyncHealthAlert.tenant_id == user.tenant_id)
            .order_by(ExternalSyncHealthAlert.created_at.desc(), ExternalSyncHealthAlert.id.desc())
        )
    ).scalars().all()
    return ok(
        {
            "items": [
                {
                    "id": str(row.id),
                    "connection_id": str(row.connection_id),
                    "sync_run_id": str(row.sync_run_id) if row.sync_run_id else None,
                    "dataset_type": row.dataset_type,
                    "alert_type": row.alert_type,
                    "alert_status": row.alert_status,
                    "message": row.message,
                }
                for row in rows
            ]
        },
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.get("/health/{connection_id}")
async def get_connection_health(
    request: Request,
    connection_id: str,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    connection_uuid = uuid.UUID(connection_id)
    run = (
        await session.execute(
            select(ExternalSyncRun)
            .where(
                ExternalSyncRun.tenant_id == user.tenant_id,
                ExternalSyncRun.connection_id == connection_uuid,
            )
            .order_by(ExternalSyncRun.created_at.desc(), ExternalSyncRun.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    service = HealthService(session)
    evaluation: list[dict[str, Any]] = []
    if run is not None:
        evaluation.append(
            await service.evaluate_sla(
                tenant_id=user.tenant_id,
                organisation_id=run.organisation_id,
                connection_id=connection_uuid,
                dataset_type=DatasetType(run.dataset_type),
                created_by=user.id,
            )
        )
        await session.flush()

    return ok(
        {
            "connection_id": connection_id,
            "status": "ok",
            "latest_run": None
            if run is None
            else {
                "sync_run_id": str(run.id),
                "dataset_type": run.dataset_type,
                "run_status": run.run_status,
            },
            "evaluations": evaluation,
        },
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")
