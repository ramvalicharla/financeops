from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from financeops.api.deps import get_current_user
from financeops.db.models.users import IamUser
from financeops.llm.streaming import stream_llm_response

router = APIRouter(prefix="/ai", tags=["ai"])


class AIStreamRequest(BaseModel):
    prompt: str
    system_prompt: str = ""
    task_type: str = "advisory"


@router.post("/stream")
async def stream_ai_response(
    body: AIStreamRequest,
    current_user: IamUser = Depends(get_current_user),
) -> StreamingResponse:
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
