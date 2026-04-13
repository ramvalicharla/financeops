from __future__ import annotations

import json
import logging
from uuid import UUID
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import PromptInjectionError, ValidationError
from financeops.db.rls import clear_tenant_context, set_tenant_context
from financeops.db.session import AsyncSessionLocal
from financeops.llm.cache import CACHE_TTL_SECONDS, compute_cache_key
from financeops.llm.circuit_breaker import CircuitBreakerRegistry
from financeops.llm.cost_ledger import check_budget, record_ai_call
from financeops.llm.fallback import AIResult, ModelConfig, _get_provider, execute_with_fallback
from financeops.llm.pii_masker import PIIMasker
from financeops.llm.providers.base import LLMRequest, LLMResponse
from financeops.llm.retry import with_retry
from financeops.llm.token_manager import compute_token_budget
from financeops.security.prompt_injection import PromptInjectionScanner
from financeops.observability.ai_metrics import observe_ai_cost, observe_ai_tokens
from financeops.llm.pipeline import PipelineContext, PipelineResult, run_pipeline
from financeops.llm.prompt_store import load_active_system_prompt
from financeops.modules.learning_engine.service import get_tenant_context_for_task

log = logging.getLogger(__name__)
_masker = PIIMasker()
_scanner = PromptInjectionScanner()


def _format_learning_examples(examples: list[dict]) -> str:
    lines: list[str] = []
    for idx, row in enumerate(examples, start=1):
        quality = row.get("quality_score")
        lines.append(f"Example {idx} (quality={quality}):")
        lines.append(f"Input: {row.get('input_context', '')}")
        lines.append(f"Correct Output: {row.get('correct_output', '')}")
        lines.append("")
    return "\n".join(lines).strip()


async def execute_with_cache(
    task_type: str,
    prompt: str,
    system_prompt: str,
    model: str,
    redis_client,
    fallback_fn,  # type: ignore[no-untyped-def]
) -> tuple[str, bool]:
    key = compute_cache_key(task_type, prompt, system_prompt, model)
    if redis_client is not None:
        cached = await redis_client.get(key)
        if cached:
            try:
                from financeops.observability.business_metrics import ai_cache_hit_counter

                ai_cache_hit_counter.labels(task_type=task_type).inc()
            except Exception:
                pass
            return str(cached), True

    response = await fallback_fn()
    if redis_client is not None:
        ttl = CACHE_TTL_SECONDS.get(task_type, CACHE_TTL_SECONDS["default"])
        await redis_client.setex(key, ttl, response)
    return str(response), False


def _safe_uuid(tenant_id: str) -> UUID | None:
    try:
        return uuid.UUID(str(tenant_id))
    except Exception:
        return None


async def _call_provider(
    *,
    model_config: ModelConfig,
    task_type: str,
    prompt: str,
    system_prompt: str,
    tenant_id: str,
    redis_client,
    trace_id: str | None = None,
) -> tuple[LLMResponse, bool, bool]:
    scan_result = _scanner.scan(prompt)
    prompt_after_scan = prompt
    if scan_result.is_injection:
        log.warning(
            "prompt_injection_detected risk=%s pattern=%s tenant=%s",
            scan_result.risk_level,
            scan_result.matched_pattern,
            tenant_id,
        )
        if scan_result.risk_level in {"critical", "high"}:
            raise PromptInjectionError("Request contains unsafe content and cannot be processed.")
        if scan_result.sanitised_text:
            prompt_after_scan = scan_result.sanitised_text

    masking_result = None
    prompt_to_send = prompt_after_scan
    system_prompt_to_send = system_prompt
    pii_was_masked = False

    if _masker.should_mask(model_config.provider):
        prompt_masking = _masker.mask(prompt_after_scan)
        system_masking = _masker.mask(system_prompt)
        combined_map: dict[str, str] = {}
        combined_map.update(prompt_masking.mask_map)
        combined_map.update(system_masking.mask_map)
        pii_types = sorted(set(prompt_masking.pii_found + system_masking.pii_found))
        masking_result = {"mask_map": combined_map, "pii_found": pii_types}
        prompt_to_send = prompt_masking.masked_text
        system_prompt_to_send = system_masking.masked_text
        pii_was_masked = bool(combined_map)
        if pii_types:
            log.info(
                "pii_masked provider=%s types=%s tenant=%s trace_id=%s",
                model_config.provider,
                pii_types,
                tenant_id,
                trace_id,
            )

    budget = compute_token_budget(
        model=model_config.model_name,
        system_prompt=system_prompt_to_send,
        user_prompt=prompt_to_send,
    )
    if budget.truncated:
        prompt_to_send = budget.truncated_user_prompt
        log.warning(
            "prompt_truncated model=%s truncation_pct=%s trace_id=%s",
            model_config.model_name,
            str(budget.truncation_pct),
            trace_id,
        )

    provider = _get_provider(model_config.provider, model_config.model_name)

    async def _invoke_provider_payload() -> str:
        request = LLMRequest(
            prompt=prompt_to_send,
            system_prompt=system_prompt_to_send,
            model=model_config.model_name,
            tenant_id=tenant_id,
        )
        response = await with_retry(provider.generate, None, request)
        payload = {
            "content": response.content,
            "prompt_tokens": response.prompt_tokens,
            "completion_tokens": response.completion_tokens,
            "total_tokens": response.total_tokens,
            "duration_ms": response.duration_ms,
            "provider": response.provider,
            "model": response.model,
        }
        return json.dumps(payload, separators=(",", ":"))

    payload_text, was_cached = await execute_with_cache(
        task_type=task_type,
        prompt=prompt_to_send,
        system_prompt=system_prompt_to_send,
        model=model_config.model_name,
        redis_client=redis_client,
        fallback_fn=_invoke_provider_payload,
    )
    payload = json.loads(payload_text)
    content = str(payload.get("content", ""))
    if masking_result and masking_result["mask_map"]:
        content = _masker.unmask(content, masking_result["mask_map"])

    response = LLMResponse(
        content=content,
        model=str(payload.get("model", model_config.model_name)),
        provider=str(payload.get("provider", model_config.provider)),
        prompt_tokens=int(payload.get("prompt_tokens", 0)),
        completion_tokens=int(payload.get("completion_tokens", 0)),
        total_tokens=int(payload.get("total_tokens", 0)),
        duration_ms=float(payload.get("duration_ms", 0.0)),
        raw_response={},
    )
    return response, was_cached, pii_was_masked


async def gateway_generate(
    *,
    task_type: str,
    prompt: str,
    system_prompt: str,
    tenant_id: str,
    redis_client=None,
    db_session: AsyncSession | None = None,
    circuit_registry: CircuitBreakerRegistry | None = None,
    trace_id: str | None = None,
) -> AIResult:
    """
    Top-level gateway entry point for single-shot LLM requests (no pipeline).
    Uses circuit breaker + fallback chain.
    """
    registry = circuit_registry or CircuitBreakerRegistry(redis_client=redis_client)
    request_trace_id = trace_id or str(uuid.uuid4())
    tenant_uuid = _safe_uuid(tenant_id)
    own_session = db_session is None
    session: AsyncSession | None = db_session

    if own_session:
        session = AsyncSessionLocal()
        await set_tenant_context(session, tenant_id)

    try:
        log.info(
            "ai_request_started trace_id=%s task_type=%s tenant=%s prompt_length=%d",
            request_trace_id,
            task_type,
            tenant_id,
            len(prompt),
        )
        # Load active DB prompt if one exists for this task_type; fall back to caller-supplied
        effective_system_prompt = system_prompt
        if session is not None:
            try:
                db_prompt = await load_active_system_prompt(session, task_type)
                if db_prompt is not None:
                    effective_system_prompt = db_prompt
                    log.debug(
                        "prompt_store loaded system_prompt task_type=%s trace_id=%s",
                        task_type,
                        request_trace_id,
                    )
            except Exception as exc:
                log.warning(
                    "prompt_store lookup failed task_type=%s error=%s — using caller prompt",
                    task_type,
                    exc,
                )

        enriched_system_prompt = effective_system_prompt
        if session is not None and tenant_uuid is not None:
            try:
                examples = await get_tenant_context_for_task(
                    session,
                    tenant_id=tenant_uuid,
                    task_type=task_type,
                )
                if examples:
                    enriched_system_prompt = (
                        f"{system_prompt}\n\nExamples from previous corrections:\n"
                        f"{_format_learning_examples(examples)}"
                    )
            except Exception as exc:
                log.warning("learning_context_injection_failed tenant=%s task=%s error=%s", tenant_id, task_type, exc)

        if session is not None and tenant_uuid is not None:
            budget_status = await check_budget(session, tenant_uuid)
            if not bool(budget_status["allowed"]):
                raise ValidationError("monthly_budget_exhausted")

        attempt_index = {"count": 0}

        async def _provider_invoke(
            model_cfg: ModelConfig,
            prompt_value: str,
            system_prompt_value: str,
            tenant_value: str,
        ) -> tuple[LLMResponse, bool, bool]:
            was_fallback = attempt_index["count"] > 0
            attempt_index["count"] += 1
            response, was_cached, pii_was_masked = await _call_provider(
                model_config=model_cfg,
                task_type=task_type,
                prompt=prompt_value,
                system_prompt=system_prompt_value,
                tenant_id=tenant_value,
                redis_client=redis_client,
                trace_id=request_trace_id,
            )
            if session is not None and tenant_uuid is not None:
                event = await record_ai_call(
                    session=session,
                    tenant_id=tenant_uuid,
                    task_type=task_type,
                    provider=response.provider,
                    model=response.model,
                    prompt_tokens=response.prompt_tokens,
                    completion_tokens=response.completion_tokens,
                    was_cached=was_cached,
                    was_fallback=was_fallback,
                    pii_was_masked=pii_was_masked,
                )
                observe_ai_cost(
                    provider=response.provider,
                    model=response.model,
                    task_type=task_type,
                    cost_usd=event.cost_usd,
                )
                observe_ai_tokens(
                    provider=response.provider,
                    model=response.model,
                    prompt_tokens=response.prompt_tokens,
                    completion_tokens=response.completion_tokens,
                )
            return response, was_cached, pii_was_masked

        result = await execute_with_fallback(
            task_type=task_type,
            prompt=prompt,
            system_prompt=enriched_system_prompt,
            tenant_id=tenant_id,
            circuit_registry=registry,
            provider_invoke=_provider_invoke,
        )
        result.trace_id = request_trace_id

        if session is not None:
            await session.flush()
            if own_session:
                await session.commit()
        log.info(
            "ai_request_completed trace_id=%s task_type=%s tenant=%s model=%s provider=%s",
            request_trace_id,
            task_type,
            tenant_id,
            result.model_used,
            result.provider,
        )
        return result
    except Exception:
        if session is not None and own_session:
            await session.rollback()
        raise
    finally:
        if session is not None and own_session:
            try:
                await clear_tenant_context(session)
            except Exception:
                pass
            await session.close()


async def gateway_pipeline(
    ctx: PipelineContext,
    redis_client=None,
    db_session: AsyncSession | None = None,
) -> PipelineResult:
    """
    Top-level gateway entry point for the full 5-stage pipeline.
    """
    registry = CircuitBreakerRegistry(redis_client=redis_client)
    return await run_pipeline(
        ctx,
        registry,
        redis_client=redis_client,
        db_session=db_session,
    )
