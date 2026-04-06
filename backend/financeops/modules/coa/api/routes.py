from __future__ import annotations

import csv
import hashlib
import io
import json
import uuid
from decimal import Decimal
from pathlib import PurePath
from typing import Any

import redis.asyncio as aioredis
from fastapi import APIRouter, Body, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import Response
from openpyxl import Workbook
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import (
    get_async_session,
    get_current_user,
    get_redis,
    require_finance_team,
    require_org_setup,
)
from financeops.config import limiter, settings
from financeops.core.exceptions import ValidationError
from financeops.db.models.users import IamUser
from financeops.db.transaction import commit_session
from financeops.modules.coa.api.schemas import (
    CoaHierarchyResponse,
    CoaLedgerAccountResponse,
    CoaApplyRequest,
    CoaApplyResponse,
    CoaSkipResponse,
    CoaTemplateResponse,
    CoaUploadBatchResponse,
    CoaUploadResponse,
    CoaValidateResponse,
    ErpAutoSuggestRequest,
    ErpBulkConfirmRequest,
    ErpConfirmRequest,
    ErpMappingResponse,
    ErpMappingSummaryResponse,
    GlobalTBResponse,
    RawTBLineInput,
    TenantCoaAccountResponse,
    TenantCoaCreateRequest,
    TenantCoaInitialiseRequest,
    TenantCoaUpdateRequest,
    TrialBalanceClassifyMultiEntityRequest,
    TrialBalanceClassifyRequest,
)
from financeops.modules.coa.application.coa_upload_service import CoaUploadService
from financeops.modules.coa.application.erp_mapping_service import ErpMappingService
from financeops.modules.coa.application.global_tb_service import (
    ClassifiedTBLine,
    GlobalTBResult,
    GlobalTrialBalanceService,
)
from financeops.modules.coa.application.tenant_coa_resolver import TenantCoaResolver
from financeops.modules.coa.application.template_service import CoaTemplateService
from financeops.modules.coa.application.tenant_coa_service import TenantCoaService
from financeops.modules.org_setup.application.org_setup_service import OrgSetupService
from financeops.services.audit_service import log_action
from financeops.modules.coa.models import (
    CoaSourceType,
    CoaUploadMode,
    CoaFsClassification,
    CoaFsSchedule,
    CoaLedgerAccount,
    ErpAccountMapping,
    TenantCoaAccount,
    CoaUploadBatch,
)
from financeops.db.models.users import UserRole
router = APIRouter(prefix="/coa", tags=["chart-of-accounts"])
_COA_CACHE_TTL_SECONDS = 120
_COA_UPLOAD_EXTENSIONS = {".csv", ".xlsx"}


def _is_platform_admin(role: UserRole) -> bool:
    return role in {
        UserRole.super_admin,
        UserRole.platform_owner,
        UserRole.platform_admin,
    }


def _tenant_account_response(
    account: TenantCoaAccount,
    ledger: CoaLedgerAccount | None = None,
) -> TenantCoaAccountResponse:
    return TenantCoaAccountResponse(
        id=account.id,
        tenant_id=account.tenant_id,
        ledger_account_id=account.ledger_account_id,
        parent_subgroup_id=account.parent_subgroup_id,
        account_code=account.account_code,
        display_name=account.display_name,
        is_custom=account.is_custom,
        is_active=account.is_active,
        sort_order=account.sort_order,
        platform_account_code=ledger.code if ledger is not None else None,
        platform_account_name=ledger.name if ledger is not None else None,
        bs_pl_flag=ledger.bs_pl_flag if ledger is not None else None,
        asset_liability_class=ledger.asset_liability_class if ledger is not None else None,
        normal_balance=ledger.normal_balance if ledger is not None else None,
    )


def _mapping_response(mapping: ErpAccountMapping) -> ErpMappingResponse:
    return ErpMappingResponse(
        id=mapping.id,
        tenant_id=mapping.tenant_id,
        entity_id=mapping.entity_id,
        erp_connector_type=mapping.erp_connector_type,
        erp_account_code=mapping.erp_account_code,
        erp_account_name=mapping.erp_account_name,
        erp_account_type=mapping.erp_account_type,
        tenant_coa_account_id=mapping.tenant_coa_account_id,
        mapping_confidence=mapping.mapping_confidence,
        is_auto_mapped=mapping.is_auto_mapped,
        is_confirmed=mapping.is_confirmed,
        confirmed_by=mapping.confirmed_by,
        confirmed_at=mapping.confirmed_at,
        is_active=mapping.is_active,
    )


def _line_to_dict(line: ClassifiedTBLine) -> dict[str, Any]:
    return {
        "erp_account_code": line.erp_account_code,
        "erp_account_name": line.erp_account_name,
        "tenant_coa_account_id": line.tenant_coa_account_id,
        "platform_account_code": line.platform_account_code,
        "platform_account_name": line.platform_account_name,
        "fs_classification": line.fs_classification,
        "fs_schedule": line.fs_schedule,
        "fs_line_item": line.fs_line_item,
        "fs_subline": line.fs_subline,
        "debit_amount": line.debit_amount,
        "credit_amount": line.credit_amount,
        "net_amount": line.net_amount,
        "currency": line.currency,
        "is_unmapped": line.is_unmapped,
        "is_unconfirmed": line.is_unconfirmed,
    }


def _global_tb_response(payload: GlobalTBResult) -> GlobalTBResponse:
    return GlobalTBResponse(
        entity_results={
            str(entity_id): [_line_to_dict(line) for line in lines]
            for entity_id, lines in payload.entity_results.items()
        },
        consolidated=[_line_to_dict(line) for line in payload.consolidated],
        unmapped_lines=[_line_to_dict(line) for line in payload.unmapped_lines],
        unconfirmed_lines=[_line_to_dict(line) for line in payload.unconfirmed_lines],
        total_debits=payload.total_debits,
        total_credits=payload.total_credits,
        is_balanced=payload.is_balanced,
        unmapped_count=payload.unmapped_count,
        unconfirmed_count=payload.unconfirmed_count,
    )


def _cache_key(prefix: str, *, tenant_id: uuid.UUID, request: Request) -> str:
    pairs = sorted((str(key), str(value)) for key, value in request.query_params.multi_items())
    payload = "&".join(f"{key}={value}" for key, value in pairs)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"coa:{prefix}:{tenant_id}:{digest}"


async def _get_cached_payload(
    redis_client: aioredis.Redis | None,
    *,
    key: str,
) -> Any | None:
    if redis_client is None:
        return None
    try:
        raw = await redis_client.get(key)
        return None if not raw else json.loads(raw)
    except Exception:
        return None


async def _set_cached_payload(
    redis_client: aioredis.Redis | None,
    *,
    key: str,
    payload: Any,
) -> None:
    if redis_client is None:
        return
    try:
        await redis_client.setex(name=key, time=_COA_CACHE_TTL_SECONDS, value=json.dumps(payload))
    except Exception:
        return


@router.get("/templates", response_model=list[CoaTemplateResponse])
async def list_templates(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
    redis_client: aioredis.Redis = Depends(get_redis),
) -> list[CoaTemplateResponse]:
    key = _cache_key("templates", tenant_id=user.tenant_id, request=request)
    cached = await _get_cached_payload(redis_client, key=key)
    if isinstance(cached, list):
        return [CoaTemplateResponse.model_validate(item) for item in cached]

    service = CoaTemplateService(session)
    rows = await service.get_all_templates()
    response = [
        CoaTemplateResponse(
            id=row.id,
            code=row.code,
            name=row.name,
            description=row.description,
            is_active=row.is_active,
        )
        for row in rows
    ]
    await _set_cached_payload(
        redis_client,
        key=key,
        payload=[item.model_dump(mode="json") for item in response],
    )
    return response


@router.get("/templates/{template_id}/hierarchy", response_model=CoaHierarchyResponse)
async def get_template_hierarchy(
    template_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> CoaHierarchyResponse:
    service = CoaTemplateService(session)
    payload = await service.get_full_hierarchy(template_id, user.tenant_id)
    return CoaHierarchyResponse(**payload)


@router.get("/templates/{template_id}/accounts", response_model=list[CoaLedgerAccountResponse])
async def get_template_accounts(
    template_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[CoaLedgerAccountResponse]:
    service = CoaTemplateService(session)
    rows = await service.get_ledger_accounts_for_template(template_id, user.tenant_id)
    return [CoaLedgerAccountResponse.model_validate(row, from_attributes=True) for row in rows]


@router.get("/accounts", response_model=list[CoaLedgerAccountResponse])
async def get_effective_accounts(
    template_id: uuid.UUID | None = Query(default=None),
    group_code: str | None = Query(default=None),
    subgroup_code: str | None = Query(default=None),
    include_inactive: bool = Query(default=False),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[CoaLedgerAccountResponse]:
    resolver = TenantCoaResolver(session)
    rows = await resolver.resolve_accounts(
        tenant_id=user.tenant_id,
        template_id=template_id,
        group_code=group_code,
        subgroup_code=subgroup_code,
        include_inactive=include_inactive,
    )
    return [CoaLedgerAccountResponse.model_validate(row, from_attributes=True) for row in rows]


def _validate_upload_file(*, file: UploadFile, file_bytes: bytes) -> None:
    filename = file.filename or "coa_upload.csv"
    if filename != PurePath(filename).name or any(separator in filename for separator in ("/", "\\")):
        raise ValidationError("file_validation_failed: invalid file name")
    lower_name = filename.lower()
    if not any(lower_name.endswith(extension) for extension in _COA_UPLOAD_EXTENSIONS):
        raise ValidationError("file_validation_failed: only .csv or .xlsx files are supported")
    if len(file_bytes) > 5 * 1024 * 1024:
        raise ValidationError("file_validation_failed: file size exceeds 5MB limit")


@limiter.limit(settings.UPLOAD_RATE_LIMIT)
@router.post("/upload", response_model=CoaUploadResponse)
async def upload_coa(
    request: Request,
    file: UploadFile = File(...),
    template_id: uuid.UUID = Form(...),
    mode: str = Form(default="APPEND"),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> CoaUploadResponse:
    del request
    try:
        upload_mode = CoaUploadMode(mode.upper())
    except ValueError as exc:
        raise ValidationError("mode must be APPEND, REPLACE, or VALIDATE_ONLY") from exc

    file_bytes = await file.read()
    if not file_bytes:
        raise ValidationError("Uploaded file is empty")
    _validate_upload_file(file=file, file_bytes=file_bytes)

    platform_admin = _is_platform_admin(user.role)
    source_type = (
        CoaSourceType.ADMIN_TEMPLATE if platform_admin else CoaSourceType.TENANT_CUSTOM
    )
    tenant_id = None if platform_admin else user.tenant_id

    service = CoaUploadService(session)
    result = await service.upload(
        actor_id=user.id,
        tenant_id=tenant_id,
        template_id=template_id,
        source_type=source_type,
        upload_mode=upload_mode,
        file_name=file.filename or "coa_upload.csv",
        file_bytes=file_bytes,
    )
    await commit_session(session)
    return CoaUploadResponse(
        batch_id=uuid.UUID(result["batch_id"]),
        upload_status=str(result["upload_status"]),
        total_rows=int(result["total_rows"]),
        valid_rows=int(result["valid_rows"]),
        invalid_rows=int(result["invalid_rows"]),
        errors=list(result["errors"]),
        upload_kind=str(result.get("upload_kind")) if result.get("upload_kind") else None,
        activation_summary=dict(result.get("activation_summary") or {}) or None,
        requires_review=bool(result.get("requires_review", False)),
        idempotent_replay=bool(result.get("idempotent_replay", False)),
    )


@limiter.limit(settings.UPLOAD_RATE_LIMIT)
@router.post("/validate", response_model=CoaValidateResponse)
async def validate_coa(
    request: Request,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_async_session),
    _: IamUser = Depends(require_finance_team),
) -> CoaValidateResponse:
    del request
    file_bytes = await file.read()
    if not file_bytes:
        raise ValidationError("Uploaded file is empty")
    _validate_upload_file(file=file, file_bytes=file_bytes)

    service = CoaUploadService(session)
    result = await service.validate_only(
        file_name=file.filename or "coa_upload.csv",
        file_bytes=file_bytes,
    )
    return CoaValidateResponse(
        total_rows=int(result["total_rows"]),
        valid_rows=int(result["valid_rows"]),
        invalid_rows=int(result["invalid_rows"]),
        errors=list(result["errors"]),
    )


@limiter.limit(settings.UPLOAD_RATE_LIMIT)
@router.post("/apply", response_model=CoaApplyResponse)
async def apply_coa(
    request: Request,
    body: CoaApplyRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> CoaApplyResponse:
    del request
    service = CoaUploadService(session)
    result = await service.apply_batch(
        batch_id=body.batch_id,
        actor_tenant_id=user.tenant_id,
        is_platform_admin=_is_platform_admin(user.role),
    )
    await commit_session(session)
    return CoaApplyResponse(
        batch_id=uuid.UUID(result["batch_id"]),
        applied_rows=int(result["applied_rows"]),
        template_id=uuid.UUID(result["template_id"]),
        source_type=str(result["source_type"]),
    )


@router.post("/skip", response_model=CoaSkipResponse)
async def skip_coa_for_now(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> CoaSkipResponse:
    service = OrgSetupService(session)
    progress = await service.mark_coa_skipped(user.tenant_id)
    await log_action(
        session,
        tenant_id=user.tenant_id,
        user_id=user.id,
        action="tenant.coa.skip",
        resource_type="org_setup",
        resource_id=str(user.tenant_id),
        resource_name="chart_of_accounts",
        new_value={"coa_status": "skipped"},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await commit_session(session)
    return CoaSkipResponse(
        coa_status="skipped",
        next_step=progress.current_step,
        onboarding_score=await service.get_onboarding_score(user.tenant_id),
    )


@router.get("/upload/batches", response_model=list[CoaUploadBatchResponse])
async def list_coa_upload_batches(
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[CoaUploadBatchResponse]:
    stmt = select(CoaUploadBatch).order_by(CoaUploadBatch.created_at.desc()).limit(limit)
    if not _is_platform_admin(user.role):
        stmt = stmt.where(CoaUploadBatch.tenant_id == user.tenant_id)
    rows = (await session.execute(stmt)).scalars().all()
    return [CoaUploadBatchResponse.model_validate(row, from_attributes=True) for row in rows]


@router.get("/fs-classifications")
async def get_fs_classifications(
    session: AsyncSession = Depends(get_async_session),
    _: IamUser = Depends(get_current_user),
) -> list[dict[str, Any]]:
    rows = (
        await session.execute(
            select(CoaFsClassification).order_by(CoaFsClassification.sort_order, CoaFsClassification.code)
        )
    ).scalars().all()
    return [
        {
            "id": row.id,
            "code": row.code,
            "name": row.name,
            "sort_order": row.sort_order,
            "is_active": row.is_active,
        }
        for row in rows
    ]


@router.get("/fs-schedules")
async def get_fs_schedules(
    gaap: str = Query(...),
    session: AsyncSession = Depends(get_async_session),
    _: IamUser = Depends(get_current_user),
) -> list[dict[str, Any]]:
    rows = (
        await session.execute(
            select(CoaFsSchedule)
            .where(CoaFsSchedule.gaap == gaap.upper())
            .order_by(CoaFsSchedule.sort_order, CoaFsSchedule.code)
        )
    ).scalars().all()
    return [
        {
            "id": row.id,
            "code": row.code,
            "name": row.name,
            "gaap": row.gaap,
            "schedule_number": row.schedule_number,
            "sort_order": row.sort_order,
            "is_active": row.is_active,
        }
        for row in rows
    ]


@router.post("/tenant/initialise")
async def initialise_tenant_coa(
    body: TenantCoaInitialiseRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
    _: object = Depends(require_org_setup),
) -> dict[str, bool]:
    service = TenantCoaService(session)
    await service.initialise_tenant_coa(user.tenant_id, body.template_id)
    await session.flush()
    return {"initialised": True}


@router.get("/tenant/accounts", response_model=list[TenantCoaAccountResponse])
async def get_tenant_accounts(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
    _: object = Depends(require_org_setup),
) -> list[TenantCoaAccountResponse]:
    service = TenantCoaService(session)
    accounts = await service.get_tenant_accounts(user.tenant_id)
    ledger_ids = [row.ledger_account_id for row in accounts if row.ledger_account_id]
    ledger_rows = (
        await session.execute(
            select(CoaLedgerAccount).where(
                CoaLedgerAccount.id.in_(ledger_ids),
                or_(
                    CoaLedgerAccount.tenant_id == user.tenant_id,
                    CoaLedgerAccount.tenant_id.is_(None),
                ),
            )
        )
    ).scalars().all()
    ledger_by_id = {row.id: row for row in ledger_rows}
    return [_tenant_account_response(account, ledger_by_id.get(account.ledger_account_id)) for account in accounts]


@router.post("/tenant/accounts", response_model=TenantCoaAccountResponse)
async def add_tenant_custom_account(
    body: TenantCoaCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
    _: object = Depends(require_org_setup),
) -> TenantCoaAccountResponse:
    service = TenantCoaService(session)
    account = await service.add_custom_account(
        tenant_id=user.tenant_id,
        parent_subgroup_id=body.parent_subgroup_id,
        account_code=body.account_code,
        display_name=body.display_name,
    )
    await session.flush()
    return _tenant_account_response(account)


@router.patch("/tenant/accounts/{account_id}", response_model=TenantCoaAccountResponse)
async def update_tenant_account(
    account_id: uuid.UUID,
    body: TenantCoaUpdateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
    _: object = Depends(require_org_setup),
) -> TenantCoaAccountResponse:
    service = TenantCoaService(session)
    account = await service.update_account(
        tenant_id=user.tenant_id,
        account_id=account_id,
        display_name=body.display_name,
        is_active=body.is_active,
    )
    await session.flush()
    ledger = None
    if account.ledger_account_id:
        ledger = (
            await session.execute(
                select(CoaLedgerAccount).where(
                    CoaLedgerAccount.id == account.ledger_account_id,
                    or_(
                        CoaLedgerAccount.tenant_id == user.tenant_id,
                        CoaLedgerAccount.tenant_id.is_(None),
                    ),
                )
            )
        ).scalar_one_or_none()
    return _tenant_account_response(account, ledger)


@router.get("/tenant/accounts/{account_id}")
async def get_tenant_account_by_id(
    account_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
    _: object = Depends(require_org_setup),
) -> dict[str, Any]:
    service = TenantCoaService(session)
    payload = await service.get_account_with_hierarchy(user.tenant_id, account_id)
    account = payload["account"]
    ledger = None
    if account.ledger_account_id:
        ledger = (
            await session.execute(
                select(CoaLedgerAccount).where(
                    CoaLedgerAccount.id == account.ledger_account_id,
                    or_(
                        CoaLedgerAccount.tenant_id == user.tenant_id,
                        CoaLedgerAccount.tenant_id.is_(None),
                    ),
                )
            )
        ).scalar_one_or_none()
    response = _tenant_account_response(account, ledger).model_dump()
    response["hierarchy_path"] = {
        "schedule": payload["schedule"].name if payload["schedule"] is not None else None,
        "line_item": payload["line_item"].name if payload["line_item"] is not None else None,
        "subline": payload["subline"].name if payload["subline"] is not None else None,
        "group": payload["group"].name if payload["group"] is not None else None,
        "subgroup": payload["subgroup"].name if payload["subgroup"] is not None else None,
    }
    return response


@router.post("/erp-mappings/auto-suggest", response_model=list[ErpMappingResponse])
async def auto_suggest_erp_mappings(
    body: ErpAutoSuggestRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
    _: object = Depends(require_org_setup),
) -> list[ErpMappingResponse]:
    service = ErpMappingService(session)
    rows = await service.auto_suggest_mappings(
        tenant_id=user.tenant_id,
        entity_id=body.entity_id,
        erp_connector_type=body.erp_connector_type,
        erp_accounts=[item.model_dump() for item in body.erp_accounts],
    )
    await session.flush()
    return [_mapping_response(row) for row in rows]


@router.get("/erp-mappings", response_model=list[ErpMappingResponse])
async def list_erp_mappings(
    request: Request,
    entity_id: uuid.UUID,
    erp_connector_type: str | None = Query(default=None),
    is_confirmed: bool | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
    _: object = Depends(require_org_setup),
    redis_client: aioredis.Redis = Depends(get_redis),
) -> list[ErpMappingResponse]:
    key = _cache_key("erp_mappings", tenant_id=user.tenant_id, request=request)
    cached = await _get_cached_payload(redis_client, key=key)
    if isinstance(cached, list):
        return [ErpMappingResponse.model_validate(item) for item in cached]
    stmt = select(ErpAccountMapping).where(
        ErpAccountMapping.tenant_id == user.tenant_id,
        ErpAccountMapping.entity_id == entity_id,
    )
    if erp_connector_type:
        stmt = stmt.where(ErpAccountMapping.erp_connector_type == erp_connector_type)
    if is_confirmed is not None:
        stmt = stmt.where(ErpAccountMapping.is_confirmed.is_(is_confirmed))
    rows = (
        await session.execute(
            stmt.order_by(ErpAccountMapping.erp_account_code).limit(limit).offset(offset)
        )
    ).scalars().all()
    response = [_mapping_response(row) for row in rows]
    await _set_cached_payload(
        redis_client,
        key=key,
        payload=[item.model_dump(mode="json") for item in response],
    )
    return response


@router.patch("/erp-mappings/{mapping_id}/confirm", response_model=ErpMappingResponse)
async def confirm_erp_mapping(
    mapping_id: uuid.UUID,
    body: ErpConfirmRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
    _: object = Depends(require_org_setup),
) -> ErpMappingResponse:
    service = ErpMappingService(session)
    row = await service.confirm_mapping(
        tenant_id=user.tenant_id,
        mapping_id=mapping_id,
        tenant_coa_account_id=body.tenant_coa_account_id,
        confirmed_by=user.id,
    )
    await session.flush()
    return _mapping_response(row)


@router.post("/erp-mappings/bulk-confirm")
async def bulk_confirm_erp_mappings(
    body: ErpBulkConfirmRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
    _: object = Depends(require_org_setup),
) -> dict[str, int]:
    mapping_ids = body.mapping_ids
    if body.auto_confirm_above is not None:
        try:
            threshold = Decimal(body.auto_confirm_above)
        except Exception as exc:  # noqa: BLE001
            raise ValidationError("auto_confirm_above must be a Decimal string") from exc
        candidate_rows = (
            await session.execute(
                select(ErpAccountMapping).where(
                    ErpAccountMapping.tenant_id == user.tenant_id,
                    ErpAccountMapping.id.in_(body.mapping_ids),
                )
            )
        ).scalars().all()
        mapping_ids = [
            row.id
            for row in candidate_rows
            if row.mapping_confidence is not None and row.mapping_confidence >= threshold
        ]

    service = ErpMappingService(session)
    count = await service.bulk_confirm_mappings(
        tenant_id=user.tenant_id,
        mapping_ids=mapping_ids,
        confirmed_by=user.id,
    )
    await session.flush()
    return {"confirmed_count": count}


@router.get("/erp-mappings/summary", response_model=ErpMappingSummaryResponse)
async def get_erp_mapping_summary(
    entity_id: uuid.UUID,
    erp_connector_type: str | None = Query(default=None),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
    _: object = Depends(require_org_setup),
) -> ErpMappingSummaryResponse:
    service = ErpMappingService(session)
    payload = await service.get_mapping_summary(
        tenant_id=user.tenant_id,
        entity_id=entity_id,
        erp_connector_type=erp_connector_type,
    )
    return ErpMappingSummaryResponse(**payload)


@router.get("/erp-mappings/unmapped", response_model=list[ErpMappingResponse])
async def get_unmapped_erp_accounts(
    request: Request,
    entity_id: uuid.UUID,
    erp_connector_type: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
    _: object = Depends(require_org_setup),
    redis_client: aioredis.Redis = Depends(get_redis),
) -> list[ErpMappingResponse]:
    key = _cache_key("erp_unmapped", tenant_id=user.tenant_id, request=request)
    cached = await _get_cached_payload(redis_client, key=key)
    if isinstance(cached, list):
        return [ErpMappingResponse.model_validate(item) for item in cached]
    service = ErpMappingService(session)
    rows = await service.get_unmapped_accounts(
        tenant_id=user.tenant_id,
        entity_id=entity_id,
        erp_connector_type=erp_connector_type,
        limit=limit,
        offset=offset,
    )
    response = [_mapping_response(row) for row in rows]
    await _set_cached_payload(
        redis_client,
        key=key,
        payload=[item.model_dump(mode="json") for item in response],
    )
    return response


@router.post("/trial-balance/classify", response_model=GlobalTBResponse)
async def classify_trial_balance(
    body: TrialBalanceClassifyRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
    _: object = Depends(require_org_setup),
) -> GlobalTBResponse:
    service = GlobalTrialBalanceService(session)
    result = await service.classify_tb(
        tenant_id=user.tenant_id,
        entity_id=body.entity_id,
        raw_tb=[line.model_dump() for line in body.raw_tb],
        gaap=body.gaap,
    )
    return _global_tb_response(result)


@router.post("/trial-balance/classify-multi-entity", response_model=GlobalTBResponse)
async def classify_multi_entity_trial_balance(
    body: TrialBalanceClassifyMultiEntityRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
    _: object = Depends(require_org_setup),
) -> GlobalTBResponse:
    entity_payload: dict[uuid.UUID, list[dict[str, Any]]] = {}
    for entity_id, lines in body.entity_raw_tbs.items():
        entity_payload[uuid.UUID(entity_id)] = [line.model_dump() for line in lines]
    service = GlobalTrialBalanceService(session)
    result = await service.classify_multi_entity_tb(
        tenant_id=user.tenant_id,
        entity_raw_tbs=entity_payload,
        gaap=body.gaap,
    )
    return _global_tb_response(result)


@router.get("/trial-balance/export")
async def export_classified_trial_balance(
    entity_id: uuid.UUID,
    gaap: str = Query(default="INDAS"),
    format: str = Query(default="csv", pattern="^(csv|xlsx)$"),
    raw_tb: list[RawTBLineInput] | None = Body(default=None),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
    _: object = Depends(require_org_setup),
) -> Response:
    lines = [line.model_dump() for line in (raw_tb or [])]
    service = GlobalTrialBalanceService(session)
    result = await service.classify_tb(
        tenant_id=user.tenant_id,
        entity_id=entity_id,
        raw_tb=lines,
        gaap=gaap,
    )
    export_lines = result.entity_results.get(entity_id, [])

    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "erp_account_code",
                "erp_account_name",
                "platform_account_code",
                "platform_account_name",
                "fs_classification",
                "fs_schedule",
                "fs_line_item",
                "fs_subline",
                "debit_amount",
                "credit_amount",
                "net_amount",
                "currency",
                "is_unmapped",
                "is_unconfirmed",
            ]
        )
        for line in export_lines:
            writer.writerow(
                [
                    line.erp_account_code,
                    line.erp_account_name,
                    line.platform_account_code or "",
                    line.platform_account_name or "",
                    line.fs_classification or "",
                    line.fs_schedule or "",
                    line.fs_line_item or "",
                    line.fs_subline or "",
                    str(line.debit_amount),
                    str(line.credit_amount),
                    str(line.net_amount),
                    line.currency,
                    str(line.is_unmapped),
                    str(line.is_unconfirmed),
                ]
            )
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=classified_trial_balance.csv"},
        )

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Classified TB"
    sheet.append(
        [
            "ERP Account Code",
            "ERP Account Name",
            "Platform Account Code",
            "Platform Account Name",
            "FS Classification",
            "FS Schedule",
            "FS Line Item",
            "FS Subline",
            "Debit",
            "Credit",
            "Net",
            "Currency",
            "Unmapped",
            "Unconfirmed",
        ]
    )
    for line in export_lines:
        sheet.append(
            [
                line.erp_account_code,
                line.erp_account_name,
                line.platform_account_code,
                line.platform_account_name,
                line.fs_classification,
                line.fs_schedule,
                line.fs_line_item,
                line.fs_subline,
                str(line.debit_amount),
                str(line.credit_amount),
                str(line.net_amount),
                line.currency,
                line.is_unmapped,
                line.is_unconfirmed,
            ]
        )

    xlsx = io.BytesIO()
    workbook.save(xlsx)
    return Response(
        content=xlsx.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=classified_trial_balance.xlsx"},
    )
