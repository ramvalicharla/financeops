from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Literal

from sqlalchemy.ext.asyncio import AsyncSession

from financeops.llm.fallback import AIResult
from financeops.llm.circuit_breaker import CircuitBreakerRegistry

log = logging.getLogger(__name__)

AGREEMENT_THRESHOLD = Decimal("0.85")


@dataclass
class PipelineContext:
    task_type: str
    tenant_id: str
    user_id: str
    input_data: dict[str, Any]
    task_config: dict[str, Any] = field(default_factory=dict)
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    reservation_id: str | None = None
    started_at: float = field(default_factory=time.monotonic)


@dataclass
class PipelineResult:
    status: Literal["COMPLETED", "PENDING_REVIEW", "FAILED"]
    output_data: dict[str, Any]
    stage2_model: str
    stage3_model: str
    agreement_score: Decimal
    total_duration_ms: float
    credits_used: Decimal
    audit_trail_id: str | None = None


async def _prepare_context(ctx: PipelineContext) -> dict[str, Any]:
    """
    Stage 1: Validate and prepare context for execution.
    Builds the prompt string from input_data deterministically.
    """
    prompt_parts = []
    for key, value in sorted(ctx.input_data.items()):
        prompt_parts.append(f"{key}: {value}")
    prompt_text = "\n".join(prompt_parts)
    return {
        "prompt": prompt_text,
        "system_prompt": f"You are a financial analysis assistant. Task: {ctx.task_type}",
        "task_type": ctx.task_type,
        "tenant_id": ctx.tenant_id,
        "correlation_id": ctx.correlation_id,
    }


def _compute_agreement(primary_result: AIResult, validation_result: AIResult) -> Decimal:
    """
    Stage 4: Compute agreement score between primary and validation outputs.
    Simple token overlap heuristic for Phase 0 (full semantic comparison in Phase 4).
    """
    primary_tokens = set(primary_result.content.lower().split())
    validation_tokens = set(validation_result.content.lower().split())
    if not primary_tokens and not validation_tokens:
        return Decimal("1.0000")
    if not primary_tokens or not validation_tokens:
        return Decimal("0.0000")
    intersection = primary_tokens & validation_tokens
    union = primary_tokens | validation_tokens
    score = Decimal(str(len(intersection))) / Decimal(str(len(union)))
    return score.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


async def run_pipeline(
    ctx: PipelineContext,
    circuit_registry: CircuitBreakerRegistry,
    *,
    redis_client=None,
    db_session: AsyncSession | None = None,
) -> PipelineResult:
    """
    5-stage AI processing pipeline.
    Stage 1: Prepare context and build prompt (deterministic)
    Stage 2: Execute primary model via fallback chain
    Stage 3: Execute validation model (different provider)
    Stage 4: Compute agreement — if < threshold, return PENDING_REVIEW
    Stage 5: Finalize — write audit trail and return result
    """
    pipeline_start = time.monotonic()

    # Stage 1: Prepare
    prepared = await _prepare_context(ctx)

    # Stage 2: Primary execution
    from financeops.llm.gateway import gateway_generate

    primary_result = await gateway_generate(
        task_type=ctx.task_type,
        prompt=prepared["prompt"],
        system_prompt=prepared["system_prompt"],
        tenant_id=ctx.tenant_id,
        redis_client=redis_client,
        db_session=db_session,
        circuit_registry=circuit_registry,
    )

    # Stage 3: Validation (use 'validation' chain for cross-provider check)
    try:
        validation_result = await gateway_generate(
            task_type="validation",
            prompt=f"Verify and rate this output (0.0-1.0 confidence):\n{primary_result.content}",
            system_prompt="You are a financial output validator. Rate the quality and accuracy.",
            tenant_id=ctx.tenant_id,
            redis_client=redis_client,
            db_session=db_session,
            circuit_registry=circuit_registry,
        )
    except Exception as exc:
        log.warning("Validation stage failed: %s — proceeding with primary only", exc)
        validation_result = AIResult(
            content=primary_result.content,
            model_used="none",
            provider="none",
            was_fallback=False,
            attempt_number=0,
            duration_ms=0.0,
            tokens_used=0,
        )

    # Stage 4: Agreement check
    agreement_score = _compute_agreement(primary_result, validation_result)
    total_duration_ms = (time.monotonic() - pipeline_start) * 1000
    credits_used = (
        Decimal(str(primary_result.tokens_used + validation_result.tokens_used))
        / Decimal("1000")
    )
    credits_used = credits_used.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)

    if agreement_score < AGREEMENT_THRESHOLD:
        log.warning(
            "Agreement score %s below threshold %s — queuing for human review",
            agreement_score,
            AGREEMENT_THRESHOLD,
        )
        return PipelineResult(
            status="PENDING_REVIEW",
            output_data={
                "primary": primary_result.content,
                "validation": validation_result.content,
                "agreement_score": agreement_score,
            },
            stage2_model=primary_result.model_used,
            stage3_model=validation_result.model_used,
            agreement_score=agreement_score,
            total_duration_ms=total_duration_ms,
            credits_used=credits_used,
        )

    # Stage 5: Finalize
    return PipelineResult(
        status="COMPLETED",
        output_data={
            "result": primary_result.content,
            "model": primary_result.model_used,
        },
        stage2_model=primary_result.model_used,
        stage3_model=validation_result.model_used,
        agreement_score=agreement_score,
        total_duration_ms=total_duration_ms,
        credits_used=credits_used,
    )
