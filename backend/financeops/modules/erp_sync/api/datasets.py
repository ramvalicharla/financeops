from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Request

from financeops.api.deps import get_current_user
from financeops.db.models.users import IamUser
from financeops.modules.erp_sync.application.normalization_service import (
    NormalizationNotImplemented,
    NormalizationService,
)
from financeops.modules.erp_sync.application.period_service import (
    AS_AT_DATASETS,
    NO_PERIOD_DATASETS,
    PeriodService,
)
from financeops.modules.erp_sync.domain.enums import DatasetType, PeriodGranularity
from financeops.shared_kernel.response import ok

router = APIRouter()


@router.get("/datasets")
async def list_datasets(
    request: Request,
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    _ = user  # dependency enforces tenant context
    normalization = NormalizationService()
    support = normalization.list_normalizer_support()
    items = []
    for dataset in DatasetType:
        if dataset.value in NO_PERIOD_DATASETS:
            granularity = PeriodGranularity.NO_PERIOD.value
        elif dataset.value in AS_AT_DATASETS:
            granularity = PeriodGranularity.AS_AT.value
        else:
            granularity = "date_range"
        items.append(
            {
                "dataset_type": dataset.value,
                "period_mode": granularity,
                "normalizer_status": support.get(dataset.value, "stub"),
            }
        )
    return ok({"items": items}, request_id=getattr(request.state, "request_id", None)).model_dump(mode="json")


@router.get("/datasets/{dataset_type}")
async def get_dataset(
    request: Request,
    dataset_type: str,
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    _ = user
    dataset = DatasetType(dataset_type)
    normalization = NormalizationService()
    model_cls = normalization.DATASET_MODEL_MAP.get(dataset)
    return ok(
        {
            "dataset_type": dataset.value,
            "schema_model": model_cls.__name__ if model_cls else None,
            "normalizer_status": normalization.list_normalizer_support().get(dataset.value, "stub"),
        },
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.get("/datasets/{dataset_type}/periods")
async def get_dataset_periods(
    request: Request,
    dataset_type: str,
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    _ = user
    dataset = DatasetType(dataset_type)
    service = PeriodService()
    today = datetime.now(UTC).date()
    periods: list[dict[str, Any]]
    if dataset.value in NO_PERIOD_DATASETS:
        periods = [
            service.resolve_period(
                dataset_type=dataset.value,
                granularity=PeriodGranularity.NO_PERIOD,
            ).to_dict()
        ]
    elif dataset.value in AS_AT_DATASETS:
        periods = [
            service.resolve_period(
                dataset_type=dataset.value,
                granularity=PeriodGranularity.AS_AT,
                as_at_date=today,
            ).to_dict()
        ]
    else:
        periods = [
            service.resolve_period(
                dataset_type=dataset.value,
                granularity=PeriodGranularity.MONTHLY,
                period_end=today,
            ).to_dict(),
            service.resolve_period(
                dataset_type=dataset.value,
                granularity=PeriodGranularity.QUARTERLY,
                period_end=today,
            ).to_dict(),
            service.resolve_period(
                dataset_type=dataset.value,
                granularity=PeriodGranularity.YEARLY,
                period_end=today,
            ).to_dict(),
        ]
    return ok(
        {"dataset_type": dataset.value, "periods": periods},
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.get("/datasets/{dataset_type}/template")
async def get_dataset_template(
    request: Request,
    dataset_type: str,
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    _ = user
    dataset = DatasetType(dataset_type)
    normalization = NormalizationService()
    model_cls = normalization.DATASET_MODEL_MAP.get(dataset)
    template = model_cls.model_json_schema() if model_cls is not None else {}
    return ok(
        {"dataset_type": dataset.value, "template": template},
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.post("/datasets/{dataset_type}/preview")
async def preview_dataset(
    request: Request,
    dataset_type: str,
    body: dict[str, Any] | None = None,
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    payload = body or {}
    dataset = DatasetType(dataset_type)
    normalization = NormalizationService()
    try:
        preview = normalization.normalize(
            dataset_type=dataset,
            raw_payload=dict(payload.get("raw_payload", {})),
            entity_id=str(payload.get("entity_id", user.tenant_id)),
            currency=str(payload.get("currency", "INR")),
        )
        response: dict[str, Any] = {
            "dataset_type": dataset.value,
            "preview": preview,
            "normalization_status": "ok",
        }
    except NormalizationNotImplemented as exc:
        response = {
            "dataset_type": dataset.value,
            "preview": {},
            "normalization_status": "stub",
            "message": str(exc),
        }
    return ok(response, request_id=getattr(request.state, "request_id", None)).model_dump(mode="json")
