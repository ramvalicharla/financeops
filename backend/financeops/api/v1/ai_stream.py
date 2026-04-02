from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from financeops.api.deps import require_finance_team
from financeops.config import limiter, settings
from financeops.db.models.users import IamUser
from financeops.llm.streaming import stream_llm_response

router = APIRouter(prefix="/ai", tags=["ai"])


class AIStreamRequest(BaseModel):
    prompt: str
    system_prompt: str = ""
    task_type: str = "advisory"


@limiter.limit(settings.AI_STREAM_RATE_LIMIT)
@router.post("/stream")
async def stream_ai_response(
    request: Request,
    body: AIStreamRequest,
    current_user: IamUser = Depends(require_finance_team),
) -> StreamingResponse:
    del request
    trace_id = str(uuid.uuid4())
    stream = stream_llm_response(
        prompt=body.prompt,
        system_prompt=body.system_prompt,
        task_type=body.task_type,
        tenant_id=str(current_user.tenant_id),
        trace_id=trace_id,
    )
    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "X-AI-Trace-ID": trace_id,
        },
    )


__all__ = ["router"]
