from __future__ import annotations

from contextlib import nullcontext
import uuid
from typing import Any

import sentry_sdk
from celery import chord
from celery.result import AsyncResult
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError, InterfaceError, OperationalError

from financeops.config import settings
from financeops.core.intent.context import MutationContext, governed_mutation_context
from financeops.db.models.board_pack_generator import BoardPackGeneratorRun
from financeops.db.models.users import IamUser, UserRole
from financeops.db.session import AsyncSessionLocal, clear_tenant_context, set_tenant_context
from financeops.modules.board_pack_generator.application.generate_service import (
    BoardPackGenerateService,
    BoardPackGenerationError,
    InvalidRunStateError,
)
from financeops.modules.board_pack_generator.domain.pack_definition import SectionConfig
from financeops.modules.closing_checklist.service import run_auto_complete_for_event
from financeops.modules.notifications.service import send_notification
from financeops.tasks.async_runner import run_async
from financeops.tasks.celery_app import celery_app


def _governed_context(run_row: BoardPackGeneratorRun | None):
    if run_row is None:
        return nullcontext()
    metadata = dict(getattr(run_row, "run_metadata", {}) or {})
    intent_id = metadata.get("intent_id")
    job_id = metadata.get("job_id")
    if not intent_id or not job_id:
        return nullcontext()
    return governed_mutation_context(
        MutationContext(
            intent_id=uuid.UUID(str(intent_id)),
            job_id=uuid.UUID(str(job_id)),
            actor_user_id=run_row.triggered_by,
            actor_role=None,
            intent_type="GENERATE_BOARD_PACK",
        )
    )


async def _load_run_row(
    session,
    *,
    run_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> BoardPackGeneratorRun | None:
    return (
        await session.execute(
            select(BoardPackGeneratorRun).where(
                BoardPackGeneratorRun.id == run_id,
                BoardPackGeneratorRun.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()


async def _notify_board_pack_ready(
    session,
    *,
    run_row: BoardPackGeneratorRun,
    tenant_id: uuid.UUID,
) -> None:
    period = run_row.period_end.strftime("%Y-%m")
    await run_auto_complete_for_event(
        tenant_id=tenant_id,
        period=period,
        event="board_pack_generated",
    )
    finance_leader = (
        await session.execute(
            select(IamUser).where(
                IamUser.tenant_id == tenant_id,
                IamUser.role == UserRole.finance_leader,
                IamUser.is_active.is_(True),
            )
        )
    ).scalars().first()
    if finance_leader is None:
        return
    try:
        await send_notification(
            session,
            tenant_id=tenant_id,
            recipient_user_id=finance_leader.id,
            notification_type="board_pack_ready",
            title="Board pack ready",
            body="Your board pack has been generated.",
            action_url=f"/board-pack/{run_row.id}",
            metadata={"board_pack_id": str(run_row.id), "period": period},
        )
    except Exception:
        pass


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
    - Returns {"run_id": str, "status": "..."} on success
    - Sentry capture_exception on unhandled errors
    """

    async def _run() -> dict[str, Any]:
        parsed_run_id = uuid.UUID(str(run_id))
        parsed_tenant_id = uuid.UUID(str(tenant_id))
        service = BoardPackGenerateService()

        async with AsyncSessionLocal() as session:
            try:
                await set_tenant_context(session, str(parsed_tenant_id))
                run_row = await _load_run_row(
                    session,
                    run_id=parsed_run_id,
                    tenant_id=parsed_tenant_id,
                )
                if run_row is None:
                    raise BoardPackGenerationError("Board pack run not found")

                if settings.ENABLE_CHUNKED_TASKS:
                    with _governed_context(run_row):
                        running_run, context = await service.start_generation(
                            db=session,
                            run_id=parsed_run_id,
                            tenant_id=parsed_tenant_id,
                        )
                    section_tasks = [
                        generate_board_pack_section_task.s(
                            str(running_run.id),
                            str(parsed_tenant_id),
                            section_config.model_dump(mode="json"),
                        )
                        for section_config in sorted(
                            context.definition.section_configs,
                            key=lambda row: row.order,
                        )
                    ]
                    chord(section_tasks)(
                        finalise_board_pack_task.s(str(running_run.id), str(parsed_tenant_id))
                    )
                    return {
                        "run_id": str(parsed_run_id),
                        "worker_run_id": str(running_run.id),
                        "status": "RUNNING",
                    }

                with _governed_context(run_row):
                    await service.generate(
                        db=session,
                        run_id=parsed_run_id,
                        tenant_id=parsed_tenant_id,
                    )
                completed_run = await _load_run_row(
                    session,
                    run_id=parsed_run_id,
                    tenant_id=parsed_tenant_id,
                )
                if completed_run is not None:
                    await _notify_board_pack_ready(
                        session,
                        run_row=completed_run,
                        tenant_id=parsed_tenant_id,
                    )
                return {"run_id": str(parsed_run_id), "status": "COMPLETE"}
            finally:
                await clear_tenant_context(session)

    try:
        return run_async(_run())
    except (InvalidRunStateError, BoardPackGenerationError):
        raise
    except (OperationalError, InterfaceError, DBAPIError, ConnectionError, TimeoutError, OSError) as exc:
        raise self.retry(exc=exc)
    except Exception as exc:
        sentry_sdk.capture_exception(exc)
        raise


@celery_app.task(
    name="board_pack_generator.export",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    acks_late=True,
)
def export_board_pack_artifacts_task(
    self,
    run_id: str,
    tenant_id: str,
) -> dict[str, Any]:
    async def _run() -> dict[str, Any]:
        parsed_run_id = uuid.UUID(str(run_id))
        parsed_tenant_id = uuid.UUID(str(tenant_id))
        service = BoardPackGenerateService()

        async with AsyncSessionLocal() as session:
            try:
                await set_tenant_context(session, str(parsed_tenant_id))
                artifacts = await service.export_run_artifacts(
                    db=session,
                    run_id=parsed_run_id,
                    tenant_id=parsed_tenant_id,
                )
                await session.commit()
                return {
                    "run_id": str(parsed_run_id),
                    "artifact_ids": [str(artifact.id) for artifact in artifacts],
                    "status": "COMPLETE",
                }
            finally:
                await clear_tenant_context(session)

    try:
        return run_async(_run())
    except (InvalidRunStateError, BoardPackGenerationError):
        raise
    except (OperationalError, InterfaceError, DBAPIError, ConnectionError, TimeoutError, OSError) as exc:
        raise self.retry(exc=exc)
    except Exception as exc:
        sentry_sdk.capture_exception(exc)
        raise


@celery_app.task(
    name="board_pack_generator.generate_section",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    acks_late=True,
    time_limit=120,
)
def generate_board_pack_section_task(
    self,
    run_id: str,
    tenant_id: str,
    section_config: dict[str, Any],
) -> dict[str, Any]:
    async def _run() -> dict[str, Any]:
        parsed_run_id = uuid.UUID(str(run_id))
        parsed_tenant_id = uuid.UUID(str(tenant_id))
        service = BoardPackGenerateService()

        async with AsyncSessionLocal() as session:
            try:
                await set_tenant_context(session, str(parsed_tenant_id))
                run_row = await _load_run_row(
                    session,
                    run_id=parsed_run_id,
                    tenant_id=parsed_tenant_id,
                )
                if run_row is None:
                    raise BoardPackGenerationError("Board pack run not found")
                definition = await service._load_definition(
                    db=session,
                    definition_id=run_row.definition_id,
                    tenant_id=parsed_tenant_id,
                )
                context = service._build_context(run=run_row, definition=definition)
                parsed_section = SectionConfig.model_validate(section_config)
                with _governed_context(run_row):
                    rendered = await service.generate_section(
                        db=session,
                        tenant_id=parsed_tenant_id,
                        run_id=parsed_run_id,
                        context=context,
                        section_config=parsed_section,
                    )
                await session.commit()
                return {
                    "run_id": str(parsed_run_id),
                    "section_order": rendered.section_order,
                    "section_type": rendered.section_type.value,
                    "section_hash": rendered.section_hash,
                }
            except Exception as exc:
                await service.fail_generation(
                    db=session,
                    tenant_id=parsed_tenant_id,
                    run_id=parsed_run_id,
                    error_message=str(exc),
                )
                raise
            finally:
                await clear_tenant_context(session)

    try:
        return run_async(_run())
    except (InvalidRunStateError, BoardPackGenerationError):
        raise
    except (OperationalError, InterfaceError, DBAPIError, ConnectionError, TimeoutError, OSError) as exc:
        raise self.retry(exc=exc)
    except Exception as exc:
        sentry_sdk.capture_exception(exc)
        raise


@celery_app.task(
    name="board_pack_generator.finalise",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    acks_late=True,
)
def finalise_board_pack_task(
    self,
    results: list[dict[str, Any]],
    run_id: str,
    tenant_id: str,
) -> dict[str, Any]:
    async def _run() -> dict[str, Any]:
        parsed_run_id = uuid.UUID(str(run_id))
        parsed_tenant_id = uuid.UUID(str(tenant_id))
        service = BoardPackGenerateService()

        async with AsyncSessionLocal() as session:
            try:
                await set_tenant_context(session, str(parsed_tenant_id))
                run_row = await _load_run_row(
                    session,
                    run_id=parsed_run_id,
                    tenant_id=parsed_tenant_id,
                )
                if run_row is None:
                    raise BoardPackGenerationError("Board pack run not found")
                definition = await service._load_definition(
                    db=session,
                    definition_id=run_row.definition_id,
                    tenant_id=parsed_tenant_id,
                )
                context = service._build_context(run=run_row, definition=definition)
                rendered_sections = await service.load_rendered_sections(
                    db=session,
                    tenant_id=parsed_tenant_id,
                    run_id=parsed_run_id,
                )
                expected_count = len(context.definition.section_configs)
                unique_orders = {section.section_order for section in rendered_sections}
                if len(unique_orders) != expected_count:
                    raise BoardPackGenerationError(
                        f"Expected {expected_count} rendered sections, found {len(unique_orders)}"
                    )
                with _governed_context(run_row):
                    await service.complete_generation(
                        db=session,
                        tenant_id=parsed_tenant_id,
                        running_run=run_row,
                        context=context,
                        rendered_sections=rendered_sections,
                    )
                await _notify_board_pack_ready(
                    session,
                    run_row=run_row,
                    tenant_id=parsed_tenant_id,
                )
                return {
                    "run_id": str(parsed_run_id),
                    "status": "COMPLETE",
                    "section_count": len(results),
                }
            except Exception as exc:
                await service.fail_generation(
                    db=session,
                    tenant_id=parsed_tenant_id,
                    run_id=parsed_run_id,
                    error_message=str(exc),
                )
                raise
            finally:
                await clear_tenant_context(session)

    try:
        return run_async(_run())
    except (InvalidRunStateError, BoardPackGenerationError):
        raise
    except (OperationalError, InterfaceError, DBAPIError, ConnectionError, TimeoutError, OSError) as exc:
        raise self.retry(exc=exc)
    except Exception as exc:
        sentry_sdk.capture_exception(exc)
        raise
