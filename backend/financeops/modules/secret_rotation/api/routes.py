from __future__ import annotations

import logging
import uuid
from contextlib import suppress
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import (
    get_async_session,
    get_current_user,
    require_finance_leader,
)
from financeops.db.models.users import IamUser, UserRole
from financeops.modules.secret_rotation.models import SecretRotationLog
from financeops.modules.secret_rotation.service import (
    PLATFORM_TENANT_ID,
    get_rotation_log,
    get_rotation_log_entry,
    rotate_erp_api_key,
    rotate_smtp_credentials,
    rotate_webhook_secret,
)
from financeops.shared_kernel.pagination import Paginated

router = APIRouter(prefix="/secrets", tags=["secrets"])
log = logging.getLogger(__name__)


class RotateWebhookResponse(BaseModel):
    schedule_id: str
    rotated_at: str
    hint: str | None = None


class RotateERPRequest(BaseModel):
    new_api_key: str


class RotateERPResponse(BaseModel):
    connector_id: str
    rotated_at: str


class RotateSMTPRequest(BaseModel):
    smtp_host: str
    smtp_user: str
    smtp_password: str


class RotateSMTPResponse(BaseModel):
    status: str
    action_required: str
    verified_host: str
    rotated_at: str


class RotationLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    secret_type: str
    resource_id: uuid.UUID | None = None
    resource_type: str | None = None
    rotated_by: uuid.UUID | None = None
    rotation_method: str
    status: str
    failure_reason: str | None = None
    previous_secret_hint: str | None = None
    new_secret_hint: str | None = None
    initiated_at: datetime
    completed_at: datetime | None = None
    created_at: datetime


async def _list_platform_logs_for_superadmin(
    db: AsyncSession,
    *,
    secret_type: str | None,
    resource_id: uuid.UUID | None,
    limit: int,
    offset: int,
) -> list[SecretRotationLog]:
    from financeops.db.rls import clear_tenant_context, get_current_tenant_from_db, set_tenant_context

    previous_context = await get_current_tenant_from_db(db)
    await set_tenant_context(db, PLATFORM_TENANT_ID)
    try:
        return await get_rotation_log(
            db,
            tenant_id=PLATFORM_TENANT_ID,
            secret_type=secret_type,
            resource_id=resource_id,
            limit=limit,
            offset=offset,
        )
    finally:
        if previous_context:
            await set_tenant_context(db, previous_context)
        else:
            await clear_tenant_context(db)


async def _get_platform_log_entry_for_superadmin(
    db: AsyncSession,
    *,
    log_id: uuid.UUID,
) -> SecretRotationLog | None:
    from financeops.db.rls import clear_tenant_context, get_current_tenant_from_db, set_tenant_context

    previous_context = await get_current_tenant_from_db(db)
    await set_tenant_context(db, PLATFORM_TENANT_ID)
    try:
        return await get_rotation_log_entry(db, tenant_id=PLATFORM_TENANT_ID, log_id=log_id)
    finally:
        if previous_context:
            await set_tenant_context(db, previous_context)
        else:
            await clear_tenant_context(db)


@router.post("/rotate/webhook/{schedule_id}", response_model=RotateWebhookResponse)
async def rotate_webhook_secret_endpoint(
    schedule_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> RotateWebhookResponse:
    try:
        payload = await rotate_webhook_secret(
            session=db,
            tenant_id=user.tenant_id,
            schedule_id=schedule_id,
            user_id=user.id,
            method="manual",
        )
        await db.commit()
    except LookupError as exc:
        await db.rollback()
        log.exception("operation_failed module=%s", __name__, exc_info=exc)
        raise HTTPException(status_code=404, detail="internal_error") from exc
    except ValueError as exc:
        await db.rollback()
        log.exception("operation_failed module=%s", __name__, exc_info=exc)
        raise HTTPException(status_code=422, detail="internal_error") from exc
    except Exception as exc:
        with suppress(Exception):
            await db.commit()
        log.exception("operation_failed module=%s", __name__, exc_info=exc)
        raise HTTPException(status_code=500, detail="internal_error") from exc

    return RotateWebhookResponse(**payload)


@router.post("/rotate/erp/{connector_instance_id}", response_model=RotateERPResponse)
async def rotate_erp_secret_endpoint(
    connector_instance_id: uuid.UUID,
    body: RotateERPRequest,
    db: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> RotateERPResponse:
    try:
        payload = await rotate_erp_api_key(
            session=db,
            tenant_id=user.tenant_id,
            connector_instance_id=connector_instance_id,
            new_api_key=body.new_api_key,
            user_id=user.id,
            method="manual",
        )
        await db.commit()
    except LookupError as exc:
        await db.rollback()
        log.exception("operation_failed module=%s", __name__, exc_info=exc)
        raise HTTPException(status_code=404, detail="internal_error") from exc
    except ValueError as exc:
        await db.rollback()
        log.exception("operation_failed module=%s", __name__, exc_info=exc)
        raise HTTPException(status_code=422, detail="internal_error") from exc
    except Exception as exc:
        with suppress(Exception):
            await db.commit()
        log.exception("operation_failed module=%s", __name__, exc_info=exc)
        raise HTTPException(status_code=500, detail="internal_error") from exc

    return RotateERPResponse(**payload)


@router.post("/rotate/smtp", response_model=RotateSMTPResponse)
async def rotate_smtp_endpoint(
    body: RotateSMTPRequest,
    db: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> RotateSMTPResponse:
    try:
        payload = await rotate_smtp_credentials(
            session=db,
            new_smtp_host=body.smtp_host,
            new_smtp_user=body.smtp_user,
            new_smtp_password=body.smtp_password,
            user_id=user.id,
            method="manual",
        )
        await db.commit()
    except ValueError as exc:
        await db.rollback()
        log.exception("operation_failed module=%s", __name__, exc_info=exc)
        raise HTTPException(status_code=422, detail="internal_error") from exc
    except RuntimeError as exc:
        with suppress(Exception):
            await db.commit()
        log.exception("operation_failed module=%s", __name__, exc_info=exc)
        raise HTTPException(status_code=422, detail="internal_error") from exc
    except Exception as exc:
        with suppress(Exception):
            await db.commit()
        log.exception("operation_failed module=%s", __name__, exc_info=exc)
        raise HTTPException(status_code=500, detail="internal_error") from exc

    return RotateSMTPResponse(**payload)


@router.get("/rotation-log", response_model=Paginated[RotationLogResponse] | list[RotationLogResponse])
async def list_rotation_log_endpoint(
    request: Request,
    secret_type: str | None = Query(default=None),
    resource_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Paginated[RotationLogResponse] | list[RotationLogResponse]:
    try:
        tenant_rows = await get_rotation_log(
            db,
            tenant_id=user.tenant_id,
            secret_type=secret_type,
            resource_id=resource_id,
            limit=limit,
            offset=offset,
        )
    except ValueError as exc:
        log.exception("operation_failed module=%s", __name__, exc_info=exc)
        raise HTTPException(status_code=422, detail="internal_error") from exc

    rows = list(tenant_rows)
    total_stmt = select(SecretRotationLog).where(SecretRotationLog.tenant_id == user.tenant_id)
    if secret_type is not None:
        total_stmt = total_stmt.where(SecretRotationLog.secret_type == secret_type)
    if resource_id is not None:
        total_stmt = total_stmt.where(SecretRotationLog.resource_id == resource_id)
    total = (
        await db.execute(select(func.count()).select_from(total_stmt.subquery()))
    ).scalar_one()
    normalized_secret_type = str(secret_type or "").strip().lower()
    if user.role == UserRole.super_admin and (secret_type is None or normalized_secret_type == "smtp"):
        platform_rows = await _list_platform_logs_for_superadmin(
            db,
            secret_type=secret_type,
            resource_id=resource_id,
            limit=limit + offset,
            offset=0,
        )
        rows.extend(platform_rows)
        rows.sort(key=lambda row: (row.initiated_at, row.id), reverse=True)
        total = len(rows)
        rows = rows[offset : offset + limit]

    data = [RotationLogResponse.model_validate(row) for row in rows]
    if "limit" not in request.query_params and "offset" not in request.query_params:
        return data
    return Paginated[RotationLogResponse](data=data, total=int(total), limit=limit, offset=offset)


@router.get("/rotation-log/{log_id}", response_model=RotationLogResponse)
async def get_rotation_log_entry_endpoint(
    log_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> RotationLogResponse:
    row = await get_rotation_log_entry(db, tenant_id=user.tenant_id, log_id=log_id)
    if row is None and user.role == UserRole.super_admin:
        row = await _get_platform_log_entry_for_superadmin(db, log_id=log_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Rotation log entry not found")
    return RotationLogResponse.model_validate(row)
