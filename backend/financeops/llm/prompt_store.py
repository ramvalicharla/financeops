"""
Runtime prompt store — queries AiPromptVersion for an active record matching a
task_type key and returns the prompt_text if found.  Called by gateway_generate
before every LLM request so prompts can be updated without redeployment.

If no active record exists for the task_type the caller's hardcoded system
prompt is used unchanged — the DB versioning system is purely additive.
"""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.prompts import AiPromptVersion

log = logging.getLogger(__name__)


async def load_active_system_prompt(
    session: AsyncSession,
    task_type: str,
) -> str | None:
    """
    Return the active prompt_text for *task_type* from AiPromptVersion, or
    None if no active record exists.

    The prompt_key convention is the task_type string itself (e.g.
    "invoice_classifier", "variance_analysis").  Callers that need a different
    key scheme can extend this function.
    """
    row = (
        await session.execute(
            select(AiPromptVersion)
            .where(
                AiPromptVersion.prompt_key == task_type,
                AiPromptVersion.is_active.is_(True),
            )
            .order_by(AiPromptVersion.version.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    if row is None:
        return None

    log.debug(
        "prompt_store hit task_type=%s version=%d model_target=%s",
        task_type,
        row.version,
        row.model_target,
    )
    return row.prompt_text


__all__ = ["load_active_system_prompt"]
