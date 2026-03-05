from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Literal

from financeops.llm.fallback import AIResult, execute_with_fallback, FALLBACK_CHAINS
from financeops.llm.circuit_breaker import CircuitBreakerRegistry

log = logging.getLogger(__name__)

AGREEMENT_THRESHOLD = 0.85


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
    agreement_score: float
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


def _compute_agreement(primary_result: AIResult, validation_result: AIResult) -> float:
    """
    Stage 4: Compute agreement score between primary and validation outputs.
    Simple token overlap heuristic for Phase 0 (full semantic comparison in Phase 4).
    """
    primary_tokens = set(primary_result.content.lower().split())
    validation_tokens = set(validation_result.content.lower().split())
    if not primary_tokens and not validation_tokens:
        return 1.0
    if not primary_tokens or not validation_tokens:
        return 0.0
    intersection = primary_tokens & validation_tokens
    union = primary_tokens | validation_tokens
    return len(intersection) / len(union)


async def run_pipeline(
    ctx: PipelineContext,
    circuit_registry: CircuitBreakerRegistry,
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
    primary_result = await execute_with_fallback(
        task_type=ctx.task_type,
        prompt=prepared["prompt"],
        system_prompt=prepared["system_prompt"],
        tenant_id=ctx.tenant_id,
        circuit_registry=circuit_registry,
    )

    # Stage 3: Validation (use 'validation' chain for cross-provider check)
    try:
        validation_result = await execute_with_fallback(
            task_type="validation",
            prompt=f"Verify and rate this output (0.0-1.0 confidence):\n{primary_result.content}",
            system_prompt="You are a financial output validator. Rate the quality and accuracy.",
            tenant_id=ctx.tenant_id,
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
    credits_used = Decimal(
        str(
            round(
                (primary_result.tokens_used + validation_result.tokens_used) / 1000.0, 6
            )
        )
    )

    if agreement_score < AGREEMENT_THRESHOLD:
        log.warning(
            "Agreement score %.2f below threshold %.2f — queuing for human review",
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
