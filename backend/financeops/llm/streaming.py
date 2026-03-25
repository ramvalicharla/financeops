from __future__ import annotations

import json
import uuid
from collections.abc import AsyncGenerator

from financeops.core.exceptions import PromptInjectionError
from financeops.llm.fallback import _get_provider, FALLBACK_CHAINS
from financeops.llm.providers.base import LLMRequest
from financeops.llm.retry import with_retry


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
    """
    from financeops.llm.gateway import _masker, _scanner

    trace = trace_id or str(uuid.uuid4())

    scan_result = _scanner.scan(prompt)
    if scan_result.is_injection and scan_result.risk_level in {"critical", "high"}:
        raise PromptInjectionError("Request contains unsafe content and cannot be processed.")

    safe_prompt = scan_result.sanitised_text or prompt
    chain = FALLBACK_CHAINS.get(task_type) or FALLBACK_CHAINS["advisory"]
    model_cfg = chain[0]
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

    async def _stream_chunks() -> AsyncGenerator[str, None]:
        async for chunk in provider.stream_complete(request):
            if mask_map:
                chunk = _masker.unmask(chunk, mask_map)
            yield chunk

    try:
        async for chunk in _stream_chunks():
            yield _sse({"trace_id": trace, "chunk": chunk})
        yield _sse({"trace_id": trace, "done": True})
    except Exception as exc:  # noqa: BLE001
        async def _fallback_once() -> str:
            response = await provider.generate(request)
            text = response.content
            if mask_map:
                text = _masker.unmask(text, mask_map)
            return text

        try:
            recovered = await with_retry(_fallback_once)
            yield _sse({"trace_id": trace, "chunk": recovered})
            yield _sse({"trace_id": trace, "done": True})
        except Exception:
            yield _sse({"trace_id": trace, "error": str(exc)})


__all__ = ["stream_llm_response"]
