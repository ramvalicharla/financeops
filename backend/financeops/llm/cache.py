from __future__ import annotations

import hashlib
import json


def compute_cache_key(
    task_type: str,
    prompt: str,
    system_prompt: str,
    model: str,
) -> str:
    """
    Deterministic cache key from task + prompt content.
    """
    payload = json.dumps(
        {
            "task_type": task_type,
            "prompt": prompt,
            "system_prompt": system_prompt,
            "model": model,
        },
        sort_keys=True,
        ensure_ascii=True,
    )
    return "ai_cache:" + hashlib.sha256(payload.encode()).hexdigest()


CACHE_TTL_SECONDS: dict[str, int] = {
    "classification": 3600,
    "variance_analysis": 3600,
    "standards_lookup": 86400,
    "commentary": 1800,
    "default": 3600,
}

