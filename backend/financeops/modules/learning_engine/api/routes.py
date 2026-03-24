from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user, require_finance_leader
from financeops.core.exceptions import NotFoundError, ValidationError
from financeops.db.models.users import IamUser, UserRole
from financeops.modules.learning_engine.benchmarks.classification_benchmark import run_classification_benchmark
from financeops.modules.learning_engine.benchmarks.commentary_benchmark import run_commentary_benchmark
from financeops.modules.learning_engine.models import LearningSignal
from financeops.modules.learning_engine.service import (
    capture_signal,
    get_learning_stats,
    list_benchmark_results,
    validate_correction,
)
from financeops.shared_kernel.pagination import Paginated

router = APIRouter(prefix="/learning", tags=["learning"])


class CaptureSignalRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    signal_type: str
    task_type: str
    original_ai_output: dict
    human_correction: dict
    model_used: str
    provider: str
    prompt_tokens: int = 0
    completion_tokens: int = 0


class ValidateCorrectionRequest(BaseModel):
    quality_score: Decimal


def _require_platform_admin(user: IamUser) -> IamUser:
    if user.role not in {
        UserRole.super_admin,
        UserRole.platform_owner,
        UserRole.platform_admin,
    }:
        raise HTTPException(status_code=403, detail="platform_admin role required")
    return user


def _serialize_signal(signal: LearningSignal) -> dict:
    return {
        "id": str(signal.id),
        "tenant_id": str(signal.tenant_id),
        "signal_type": signal.signal_type,
        "task_type": signal.task_type,
        "model_used": signal.model_used,
        "provider": signal.provider,
        "prompt_tokens": signal.prompt_tokens,
        "completion_tokens": signal.completion_tokens,
        "created_at": signal.created_at.isoformat(),
    }


@router.post("/signal")
async def capture_signal_endpoint(
    body: CaptureSignalRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    signal = await capture_signal(
        session,
        tenant_id=user.tenant_id,
        user_id=user.id,
        signal_type=body.signal_type,
        task_type=body.task_type,
        original_ai_output=body.original_ai_output,
        human_correction=body.human_correction,
        model_used=body.model_used,
        provider=body.provider,
        prompt_tokens=body.prompt_tokens,
        completion_tokens=body.completion_tokens,
    )
    return _serialize_signal(signal)


@router.get("/stats")
async def learning_stats_endpoint(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    stats = await get_learning_stats(session, tenant_id=user.tenant_id)
    return {
        "total_signals": stats["total_signals"],
        "signals_by_type": stats["signals_by_type"],
        "signals_by_task": stats["signals_by_task"],
        "correction_rate_by_task": {k: format(v, "f") for k, v in stats["correction_rate_by_task"].items()},
        "most_corrected_task": stats["most_corrected_task"],
        "recent_signals": [_serialize_signal(row) for row in stats["recent_signals"]],
    }


@router.post("/benchmark/run")
async def run_benchmark_endpoint(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    _require_platform_admin(user)
    classification = await run_classification_benchmark(session, run_by=str(user.id))
    commentary = await run_commentary_benchmark(session, run_by=str(user.id))
    return {
        "task_id": str(uuid.uuid4()),
        "status": "completed",
        "results": [
            {
                "id": str(classification.id),
                "benchmark_name": classification.benchmark_name,
                "accuracy_pct": format(Decimal(str(classification.accuracy_pct)), "f"),
            },
            {
                "id": str(commentary.id),
                "benchmark_name": commentary.benchmark_name,
                "accuracy_pct": format(Decimal(str(commentary.accuracy_pct)), "f"),
            },
        ],
    }


@router.get("/benchmark/results", response_model=Paginated[dict])
async def benchmark_results_endpoint(
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Paginated[dict]:
    _require_platform_admin(user)
    rows, total = await list_benchmark_results(session, limit=limit, offset=offset)
    return Paginated[dict](
        data=[
            {
                "id": str(row.id),
                "benchmark_name": row.benchmark_name,
                "benchmark_version": row.benchmark_version,
                "model": row.model,
                "provider": row.provider,
                "total_cases": row.total_cases,
                "passed_cases": row.passed_cases,
                "accuracy_pct": format(Decimal(str(row.accuracy_pct)), "f"),
                "avg_latency_ms": format(Decimal(str(row.avg_latency_ms)), "f"),
                "total_cost_usd": format(Decimal(str(row.total_cost_usd)), "f"),
                "run_at": row.run_at.isoformat(),
                "run_by": row.run_by,
            }
            for row in rows
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/corrections/{correction_id}/validate")
async def validate_correction_endpoint(
    correction_id: uuid.UUID,
    body: ValidateCorrectionRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    _require_platform_admin(user)
    try:
        row = await validate_correction(
            session,
            correction_id=correction_id,
            validated_by=user.id,
            quality_score=body.quality_score,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc

    return {
        "id": str(row.id),
        "signal_id": str(row.signal_id),
        "is_validated": row.is_validated,
        "validated_at": row.validated_at.isoformat() if row.validated_at else None,
        "quality_score": format(Decimal(str(row.quality_score or Decimal("0"))), "f"),
    }


__all__ = ["router"]
