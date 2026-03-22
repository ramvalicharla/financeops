from __future__ import annotations

from temporalio import activity

from financeops.llm.gateway import gateway_generate


@activity.defn(name="ai_pipeline_prepare_prompt")
async def ai_pipeline_prepare_prompt(task_type: str, payload: dict) -> dict:
    prompt_lines = [f"{key}: {value}" for key, value in sorted(payload.items())]
    return {
        "task_type": task_type,
        "prompt": "\n".join(prompt_lines),
        "system_prompt": f"You are a financial AI assistant for task={task_type}",
    }


@activity.defn(name="ai_pipeline_generate")
async def ai_pipeline_generate(tenant_id: str, prepared: dict) -> dict:
    result = await gateway_generate(
        task_type=str(prepared["task_type"]),
        prompt=str(prepared["prompt"]),
        system_prompt=str(prepared["system_prompt"]),
        tenant_id=tenant_id,
    )
    return {
        "content": result.content,
        "model_used": result.model_used,
        "provider": result.provider,
        "tokens_used": result.tokens_used,
    }

