from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
from financeops.db.models.users import IamUser
from financeops.modules.multi_gaap.models import MultiGAAPConfig, MultiGAAPRun
from financeops.modules.multi_gaap.service import compute_gaap_view, get_gaap_comparison, get_or_create_config, get_specific_run, update_config

router = APIRouter(prefix="/gaap", tags=["gaap"])


class ConfigPatchRequest(BaseModel):
    primary_gaap: str | None = None
    secondary_gaaps: list[str] | None = None
    revenue_recognition_policy: dict | None = None
    lease_classification_policy: dict | None = None
    financial_instruments_policy: dict | None = None


class ComputeRequest(BaseModel):
    period: str
    gaap_framework: str


def _decimal(value: Decimal) -> str:
    return format(Decimal(str(value)), "f")


def _serialize_config(row: MultiGAAPConfig) -> dict:
    return {
        "id": str(row.id),
        "tenant_id": str(row.tenant_id),
        "primary_gaap": row.primary_gaap,
        "secondary_gaaps": row.secondary_gaaps or [],
        "revenue_recognition_policy": row.revenue_recognition_policy or {},
        "lease_classification_policy": row.lease_classification_policy or {},
        "financial_instruments_policy": row.financial_instruments_policy or {},
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


def _serialize_run(row: MultiGAAPRun) -> dict:
    return {
        "id": str(row.id),
        "period": row.period,
        "gaap_framework": row.gaap_framework,
        "revenue": _decimal(row.revenue),
        "gross_profit": _decimal(row.gross_profit),
        "ebitda": _decimal(row.ebitda),
        "ebit": _decimal(row.ebit),
        "profit_before_tax": _decimal(row.profit_before_tax),
        "profit_after_tax": _decimal(row.profit_after_tax),
        "total_assets": _decimal(row.total_assets),
        "total_equity": _decimal(row.total_equity),
        "adjustments": row.adjustments or [],
        "created_by": str(row.created_by),
        "created_at": row.created_at.isoformat(),
    }


@router.get("/config")
async def get_config_endpoint(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    row = await get_or_create_config(session, tenant_id=user.tenant_id)
    return _serialize_config(row)


@router.patch("/config")
async def patch_config_endpoint(
    body: ConfigPatchRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    row = await update_config(session, tenant_id=user.tenant_id, updates=body.model_dump(exclude_none=True))
    return _serialize_config(row)


@router.post("/compute")
async def compute_endpoint(
    body: ComputeRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    row = await compute_gaap_view(session, tenant_id=user.tenant_id, period=body.period, gaap_framework=body.gaap_framework, created_by=user.id)
    return _serialize_run(row)


@router.get("/comparison")
async def comparison_endpoint(
    period: str,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    payload = await get_gaap_comparison(session, tenant_id=user.tenant_id, period=period)
    return {
        "period": payload["period"],
        "frameworks": [
            {
                "gaap_framework": row["gaap_framework"],
                "revenue": _decimal(row["revenue"]),
                "gross_profit": _decimal(row["gross_profit"]),
                "ebitda": _decimal(row["ebitda"]),
                "profit_before_tax": _decimal(row["profit_before_tax"]),
                "profit_after_tax": _decimal(row["profit_after_tax"]),
                "adjustments": row["adjustments"],
            }
            for row in payload["frameworks"]
        ],
        "differences": {
            key: {sub_key: _decimal(sub_val) for sub_key, sub_val in value.items()}
            for key, value in payload["differences"].items()
        },
    }


@router.get("/{gaap_framework}/{period}")
async def get_specific_endpoint(
    gaap_framework: str,
    period: str,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    row = await get_specific_run(session, tenant_id=user.tenant_id, gaap_framework=gaap_framework, period=period)
    if row is None:
        return {}
    return _serialize_run(row)


__all__ = ["router"]
