from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import NotFoundError, ValidationError
from financeops.modules.learning_engine.models import AIBenchmarkResult, LearningCorrection, LearningSignal


def _q4(value: Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.0000"), rounding=ROUND_HALF_UP)


def _q2(value: Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def compute_correction_delta(
    original: dict,
    correction: dict,
) -> dict:
    original_dict = dict(original or {})
    correction_dict = dict(correction or {})

    original_keys = set(original_dict.keys())
    correction_keys = set(correction_dict.keys())
    changed_fields: list[str] = []
    additions: dict[str, Any] = {}
    removals: dict[str, Any] = {}
    modifications: dict[str, dict[str, Any]] = {}

    for key in sorted(correction_keys - original_keys):
        additions[key] = correction_dict[key]
        changed_fields.append(key)

    for key in sorted(original_keys - correction_keys):
        removals[key] = original_dict[key]
        changed_fields.append(key)

    for key in sorted(original_keys & correction_keys):
        old_value = original_dict[key]
        new_value = correction_dict[key]
        if old_value != new_value:
            modifications[key] = {"from": old_value, "to": new_value}
            changed_fields.append(key)

    return {
        "changed_fields": changed_fields,
        "additions": additions,
        "removals": removals,
        "modifications": modifications,
    }


async def capture_signal(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    signal_type: str,
    task_type: str,
    original_ai_output: dict,
    human_correction: dict,
    model_used: str,
    provider: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
) -> LearningSignal:
    delta = compute_correction_delta(original_ai_output, human_correction)
    signal = LearningSignal(
        tenant_id=tenant_id,
        signal_type=signal_type,
        task_type=task_type,
        original_ai_output=original_ai_output,
        human_correction=human_correction,
        correction_delta=delta,
        model_used=model_used,
        provider=provider,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        user_id=user_id,
    )
    session.add(signal)
    await session.flush()

    correction = LearningCorrection(
        tenant_id=tenant_id,
        signal_id=signal.id,
        task_type=task_type,
        input_context=json.dumps(original_ai_output, sort_keys=True),
        correct_output=json.dumps(human_correction, sort_keys=True),
        is_validated=False,
    )
    session.add(correction)
    await session.flush()
    return signal


async def get_learning_stats(
    session: AsyncSession,
    tenant_id: uuid.UUID,
) -> dict:
    total_signals = int(
        (
            await session.execute(
                select(func.count())
                .select_from(LearningSignal)
                .where(LearningSignal.tenant_id == tenant_id)
            )
        ).scalar_one()
    )
    rows_by_type = (
        await session.execute(
            select(LearningSignal.signal_type, func.count(LearningSignal.id))
            .where(LearningSignal.tenant_id == tenant_id)
            .group_by(LearningSignal.signal_type)
        )
    ).all()
    rows_by_task = (
        await session.execute(
            select(LearningSignal.task_type, func.count(LearningSignal.id))
            .where(LearningSignal.tenant_id == tenant_id)
            .group_by(LearningSignal.task_type)
        )
    ).all()

    signals_by_type = {str(row[0]): int(row[1]) for row in rows_by_type}
    signals_by_task = {str(row[0]): int(row[1]) for row in rows_by_task}

    correction_rate_by_task: dict[str, Decimal] = {}
    denominator = Decimal(str(total_signals or 1))
    for task_type, count in signals_by_task.items():
        correction_rate_by_task[task_type] = _q4(Decimal(str(count)) / denominator)

    most_corrected_task = ""
    if signals_by_task:
        most_corrected_task = max(signals_by_task.items(), key=lambda item: item[1])[0]

    recent = (
        await session.execute(
            select(LearningSignal)
            .where(LearningSignal.tenant_id == tenant_id)
            .order_by(desc(LearningSignal.created_at), desc(LearningSignal.id))
            .limit(10)
        )
    ).scalars().all()

    return {
        "total_signals": total_signals,
        "signals_by_type": signals_by_type,
        "signals_by_task": signals_by_task,
        "correction_rate_by_task": correction_rate_by_task,
        "most_corrected_task": most_corrected_task,
        "recent_signals": recent,
    }


async def get_tenant_context_for_task(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    task_type: str,
    limit: int = 5,
) -> list[dict]:
    rows = (
        await session.execute(
            select(LearningCorrection)
            .where(
                LearningCorrection.tenant_id == tenant_id,
                LearningCorrection.task_type == task_type,
                LearningCorrection.is_validated.is_(True),
            )
            .order_by(
                desc(LearningCorrection.quality_score),
                desc(LearningCorrection.updated_at),
                desc(LearningCorrection.id),
            )
            .limit(limit)
        )
    ).scalars().all()

    payload: list[dict] = []
    for row in rows:
        payload.append(
            {
                "input_context": row.input_context,
                "correct_output": row.correct_output,
                "quality_score": Decimal(str(row.quality_score or Decimal("0"))),
            }
        )
    return payload


async def validate_correction(
    session: AsyncSession,
    correction_id: uuid.UUID,
    validated_by: uuid.UUID,
    quality_score: Decimal,
) -> LearningCorrection:
    if quality_score < Decimal("0") or quality_score > Decimal("1"):
        raise ValidationError("quality_score must be between 0.00 and 1.00")
    row = (
        await session.execute(
            select(LearningCorrection).where(LearningCorrection.id == correction_id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError("Learning correction not found")

    row.is_validated = True
    row.validated_at = datetime.now(UTC)
    row.validated_by = validated_by
    row.quality_score = _q2(quality_score)
    row.updated_at = datetime.now(UTC)
    await session.flush()
    return row


async def list_benchmark_results(
    session: AsyncSession,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[AIBenchmarkResult], int]:
    stmt = select(AIBenchmarkResult)
    total = int((await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one())
    rows = (
        await session.execute(
            stmt.order_by(desc(AIBenchmarkResult.run_at), desc(AIBenchmarkResult.id))
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    return rows, total


__all__ = [
    "capture_signal",
    "compute_correction_delta",
    "get_learning_stats",
    "get_tenant_context_for_task",
    "list_benchmark_results",
    "validate_correction",
]

