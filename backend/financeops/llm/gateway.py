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
from financeops.security.prompt_injection import PromptInjectionScanner
from financeops.observability.ai_metrics import observe_ai_cost, observe_ai_tokens
from financeops.llm.pipeline import PipelineContext, PipelineResult, run_pipeline

log = logging.getLogger(__name__)
_masker = PIIMasker()
_scanner = PromptInjectionScanner()


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
        prompt_masking = _masker.mask(prompt)
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
                "pii_masked provider=%s types=%s tenant=%s",
                model_config.provider,
                pii_types,
                tenant_id,
            )

    provider = _get_provider(model_config.provider, model_config.model_name)

    async def _invoke_provider_payload() -> str:
        request = LLMRequest(
            prompt=prompt_to_send,
            system_prompt=system_prompt_to_send,
            model=model_config.model_name,
            tenant_id=tenant_id,
        )
        response = await provider.generate(request)
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
) -> AIResult:
    """
    Top-level gateway entry point for single-shot LLM requests (no pipeline).
    Uses circuit breaker + fallback chain.
    """
    registry = circuit_registry or CircuitBreakerRegistry(redis_client=redis_client)
    tenant_uuid = _safe_uuid(tenant_id)
    own_session = db_session is None
    session: AsyncSession | None = db_session

    if own_session:
        session = AsyncSessionLocal()
        await set_tenant_context(session, tenant_id)

    try:
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
            system_prompt=system_prompt,
            tenant_id=tenant_id,
            circuit_registry=registry,
            provider_invoke=_provider_invoke,
        )

        if session is not None:
            await session.flush()
            if own_session:
                await session.commit()
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
