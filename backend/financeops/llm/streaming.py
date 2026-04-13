from __future__ import annotations

import json
import logging
import uuid
from collections.abc import AsyncGenerator

from financeops.core.exceptions import PromptInjectionError
from financeops.llm.fallback import FALLBACK_CHAINS, ModelConfig, _get_provider
from financeops.llm.providers.base import LLMRequest

log = logging.getLogger(__name__)


def _sse(payload: dict[str, object]) -> str:
    return f"data: {json.dumps(payload, separators=(',', ':'))}\n\n"


async def stream_llm_response(
    *,
    prompt: str,
    system_prompt: str = "",
    task_type: str = "advisory",
    tenant_id: str = "",
    trace_id: str | None = None,
) -> AsyncGenerator[str, None]:
    """
    Stream model output as SSE using the same injection and masking path as gateway.
    Iterates the full fallback chain for the task_type — if a model fails during
    streaming, the next model in the chain is tried before giving up.
    """
    from financeops.llm.gateway import _masker, _scanner

    trace = trace_id or str(uuid.uuid4())

    scan_result = _scanner.scan(prompt)
    if scan_result.is_injection and scan_result.risk_level in {"critical", "high"}:
        raise PromptInjectionError("Request contains unsafe content and cannot be processed.")

    safe_prompt = scan_result.sanitised_text or prompt
    chain: list[ModelConfig] = FALLBACK_CHAINS.get(task_type) or FALLBACK_CHAINS["advisory"]

    last_exc: Exception | None = None
    for model_cfg in chain:
        provider = _get_provider(model_cfg.provider, model_cfg.model_name)

        prompt_masking = _masker.mask(safe_prompt) if _masker.should_mask(model_cfg.provider) else None
        system_masking = _masker.mask(system_prompt) if _masker.should_mask(model_cfg.provider) else None

        prompt_to_send = prompt_masking.masked_text if prompt_masking else safe_prompt
        system_to_send = system_masking.masked_text if system_masking else system_prompt

        mask_map: dict[str, str] = {}
        if prompt_masking:
            mask_map.update(prompt_masking.mask_map)
        if system_masking:
            mask_map.update(system_masking.mask_map)

        request = LLMRequest(
            prompt=prompt_to_send,
            system_prompt=system_to_send,
            model=model_cfg.model_name,
            tenant_id=tenant_id,
        )

        try:
            yielded_any = False
            async for chunk in provider.stream_complete(request):
                if mask_map:
                    chunk = _masker.unmask(chunk, mask_map)
                yield _sse({"trace_id": trace, "chunk": chunk})
                yielded_any = True
            yield _sse({"trace_id": trace, "done": True})
            return  # success — stop iterating the chain
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            log.warning(
                "stream_llm_response model=%s/%s failed%s: %s — trying next in chain",
                model_cfg.provider,
                model_cfg.model_name,
                " (after partial output)" if yielded_any else "",
                exc,
            )
            continue

    # All models exhausted
    yield _sse({"trace_id": trace, "error": str(last_exc) if last_exc else "All models failed"})


__all__ = ["stream_llm_response"]
