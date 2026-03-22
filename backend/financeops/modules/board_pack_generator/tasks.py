from __future__ import annotations

import asyncio
import uuid
from typing import Any

import sentry_sdk
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError, InterfaceError, OperationalError

from financeops.db.session import AsyncSessionLocal, clear_tenant_context, set_tenant_context
from financeops.db.models.board_pack_generator import BoardPackGeneratorRun
from financeops.modules.board_pack_generator.application.generate_service import (
    BoardPackGenerateService,
    BoardPackGenerationError,
    InvalidRunStateError,
)
from financeops.modules.closing_checklist.service import run_auto_complete_for_event
from financeops.tasks.celery_app import celery_app


@celery_app.task(
    name="board_pack_generator.generate",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    acks_late=True,
)
def generate_board_pack_task(
    self,
    run_id: str,
    tenant_id: str,
) -> dict[str, Any]:
    """
    Celery task wrapper for BoardPackGenerateService.generate().
    - Accepts str UUIDs (JSON-serialisable)
    - Creates its own AsyncSession
    - Sets app.current_tenant_id for RLS before any DB call
    - On BoardPackGenerationError or InvalidRunStateError: do not retry
    - On transient DB/network errors: retry with self.retry()
    - Returns {"run_id": str, "status": "COMPLETE"} on success
    - Sentry capture_exception on unhandled errors
    """

    async def _run() -> dict[str, Any]:
        parsed_run_id = uuid.UUID(str(run_id))
        parsed_tenant_id = uuid.UUID(str(tenant_id))
        service = BoardPackGenerateService()

        async with AsyncSessionLocal() as session:
            try:
                await set_tenant_context(session, str(parsed_tenant_id))
                await service.generate(
                    db=session,
                    run_id=parsed_run_id,
                    tenant_id=parsed_tenant_id,
                )
                session_execute = getattr(session, "execute", None)
                if callable(session_execute):
                    run_row = (
                        await session_execute(
                            select(BoardPackGeneratorRun).where(
                                BoardPackGeneratorRun.id == parsed_run_id,
                                BoardPackGeneratorRun.tenant_id == parsed_tenant_id,
                            )
                        )
                    ).scalar_one_or_none()
                    if run_row is not None:
                        period = run_row.period_end.strftime("%Y-%m")
                        await run_auto_complete_for_event(
                            tenant_id=parsed_tenant_id,
                            period=period,
                            event="board_pack_generated",
                        )
                return {"run_id": str(parsed_run_id), "status": "COMPLETE"}
            finally:
                await clear_tenant_context(session)

    try:
        return asyncio.run(_run())
    except (InvalidRunStateError, BoardPackGenerationError):
        raise
    except (OperationalError, InterfaceError, DBAPIError, ConnectionError, TimeoutError, OSError) as exc:
        raise self.retry(exc=exc)
    except Exception as exc:
        sentry_sdk.capture_exception(exc)
        raise
