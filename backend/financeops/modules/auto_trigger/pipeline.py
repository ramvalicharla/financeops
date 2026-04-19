from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

import sentry_sdk
from celery import chord, group
from sqlalchemy import desc, select
from sqlalchemy.exc import DBAPIError, IntegrityError, InterfaceError, OperationalError

from financeops.tasks.async_runner import run_async
from financeops.db.models.anomaly_pattern_engine import AnomalyRun
from financeops.db.models.mis_manager import MisDataSnapshot
from financeops.db.models.payroll_gl_normalization import NormalizationRun
from financeops.db.models.reconciliation import GlEntry, TrialBalanceRow
from financeops.db.session import AsyncSessionLocal, clear_tenant_context, set_tenant_context
from financeops.modules.anomaly_pattern_engine.application.correlation_service import CorrelationService
from financeops.modules.anomaly_pattern_engine.application.materiality_service import MaterialityService
from financeops.modules.anomaly_pattern_engine.application.persistence_service import PersistenceService
from financeops.modules.anomaly_pattern_engine.application.run_service import RunService as AnomalyRunService
from financeops.modules.anomaly_pattern_engine.application.scoring_service import ScoringService
from financeops.modules.anomaly_pattern_engine.application.statistical_service import StatisticalService
from financeops.modules.anomaly_pattern_engine.application.validation_service import ValidationService as AnomalyValidationService
from financeops.modules.anomaly_pattern_engine.infrastructure.repository import AnomalyPatternRepository
from financeops.modules.auto_trigger.models import PipelineRun, PipelineStepLog
from financeops.modules.mis_manager.application.canonical_dictionary_service import CanonicalDictionaryService
from financeops.modules.mis_manager.application.drift_detection_service import DriftDetectionService
from financeops.modules.mis_manager.application.ingest_service import MisIngestService
from financeops.modules.mis_manager.application.mapping_service import MappingService as MisMappingService
from financeops.modules.mis_manager.application.snapshot_service import SnapshotService
from financeops.modules.mis_manager.application.template_detection_service import TemplateDetectionService
from financeops.modules.mis_manager.application.validation_service import ValidationService as MisValidationService
from financeops.modules.mis_manager.infrastructure.repository import MisManagerRepository
from financeops.modules.payroll_gl_reconciliation.application.classification_service import ClassificationService
from financeops.modules.payroll_gl_reconciliation.application.mapping_service import MappingService as PayrollMappingService
from financeops.modules.payroll_gl_reconciliation.application.matching_service import MatchingService
from financeops.modules.payroll_gl_reconciliation.application.rule_service import RuleService
from financeops.modules.payroll_gl_reconciliation.application.run_service import (
    PayrollGlReconciliationRunService,
)
from financeops.modules.payroll_gl_reconciliation.application.validation_service import (
    ValidationService as PayrollValidationService,
)
from financeops.modules.payroll_gl_reconciliation.infrastructure.repository import (
    PayrollGlReconciliationRepository,
)
from financeops.services.reconciliation_service import run_gl_tb_reconciliation
from financeops.tasks.celery_app import celery_app

log = logging.getLogger(__name__)


class StepSkippedError(RuntimeError):
    def __init__(self, reason: str, summary: dict[str, Any] | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.summary = dict(summary or {})


def _build_anomaly_service(session) -> AnomalyRunService:
    return AnomalyRunService(
        repository=AnomalyPatternRepository(session),
        validation_service=AnomalyValidationService(),
        statistical_service=StatisticalService(),
        scoring_service=ScoringService(),
        materiality_service=MaterialityService(),
        persistence_service=PersistenceService(),
        correlation_service=CorrelationService(),
    )


def _build_mis_service(session) -> MisIngestService:
    dictionary_service = CanonicalDictionaryService()
    mapping_service = MisMappingService(dictionary_service)
    drift_service = DriftDetectionService()
    template_detection_service = TemplateDetectionService(drift_service)
    snapshot_service = SnapshotService(mapping_service)
    validation_service = MisValidationService()
    repository = MisManagerRepository(session)
    return MisIngestService(
        repository=repository,
        template_detection_service=template_detection_service,
        mapping_service=mapping_service,
        snapshot_service=snapshot_service,
        validation_service=validation_service,
    )


def _build_payroll_reconciliation_service(session) -> PayrollGlReconciliationRunService:
    return PayrollGlReconciliationRunService(
        repository=PayrollGlReconciliationRepository(session),
        mapping_service=PayrollMappingService(),
        rule_service=RuleService(),
        matching_service=MatchingService(),
        classification_service=ClassificationService(),
        validation_service=PayrollValidationService(),
    )


def _parse_uuid(value: str, *, field_name: str) -> uuid.UUID:
    return uuid.UUID(str(value).strip())


def _deterministic_pipeline_run_id(
    *,
    tenant_id: uuid.UUID,
    sync_run_id: uuid.UUID,
    attempt_no: int,
) -> uuid.UUID:
    return uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"financeops:auto-trigger:{tenant_id}:{sync_run_id}:attempt:{attempt_no}",
    )


async def _list_runs_for_sync(
    *,
    session,
    tenant_id: uuid.UUID,
    sync_run_id: uuid.UUID,
) -> list[PipelineRun]:
    result = await session.execute(
        select(PipelineRun)
        .where(
            PipelineRun.tenant_id == tenant_id,
            PipelineRun.sync_run_id == sync_run_id,
        )
        .order_by(PipelineRun.triggered_at.desc(), PipelineRun.id.desc())
    )
    return list(result.scalars().all())


async def resolve_pipeline_run_id_for_trigger(
    *,
    session,
    tenant_id: uuid.UUID,
    sync_run_id: uuid.UUID,
) -> uuid.UUID:
    rows = await _list_runs_for_sync(
        session=session,
        tenant_id=tenant_id,
        sync_run_id=sync_run_id,
    )
    if rows and rows[0].status != "failed":
        return rows[0].id
    attempt_no = len(rows) + 1
    return _deterministic_pipeline_run_id(
        tenant_id=tenant_id,
        sync_run_id=sync_run_id,
        attempt_no=attempt_no,
    )


async def _create_or_reuse_pipeline_run(
    *,
    session,
    tenant_id: uuid.UUID,
    sync_run_id: uuid.UUID,
) -> tuple[PipelineRun, bool]:
    rows = await _list_runs_for_sync(
        session=session,
        tenant_id=tenant_id,
        sync_run_id=sync_run_id,
    )
    if rows and rows[0].status != "failed":
        return rows[0], False

    attempt_no = len(rows) + 1
    run = PipelineRun(
        id=_deterministic_pipeline_run_id(
            tenant_id=tenant_id,
            sync_run_id=sync_run_id,
            attempt_no=attempt_no,
        ),
        tenant_id=tenant_id,
        sync_run_id=sync_run_id,
        status="running",
        triggered_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
    )
    session.add(run)
    try:
        await session.flush()
        return run, True
    except IntegrityError:
        await session.rollback()
        rows = await _list_runs_for_sync(
            session=session,
            tenant_id=tenant_id,
            sync_run_id=sync_run_id,
        )
        if rows:
            return rows[0], False
        raise


def _dispatch_pipeline_fanout(*, pipeline_run_id: str, tenant_id: str) -> None:
    fanout = group(
        run_gl_reconciliation.s(pipeline_run_id, tenant_id),
        run_payroll_reconciliation.s(pipeline_run_id, tenant_id),
        run_mis_recomputation.s(pipeline_run_id, tenant_id),
        run_anomaly_detection.s(pipeline_run_id, tenant_id),
    )
    chord(fanout)(finalise_pipeline_run.s(pipeline_run_id, tenant_id))


@celery_app.task(
    name="auto_trigger.trigger_post_sync_pipeline",
    bind=True,
    acks_late=True,
    max_retries=3,
    default_retry_delay=60,
)
def trigger_post_sync_pipeline(
    self,
    tenant_id: str,
    sync_run_id: str,
) -> dict[str, Any]:
    try:
        run_result = run_async(
            trigger_post_sync_pipeline_async(
                tenant_id=tenant_id,
                sync_run_id=sync_run_id,
            )
        )
        pipeline_run_id = str(run_result["pipeline_run_id"])
        created = bool(run_result["created"])
        if created:
            _dispatch_pipeline_fanout(
                pipeline_run_id=pipeline_run_id,
                tenant_id=tenant_id,
            )
            return {
                "pipeline_run_id": pipeline_run_id,
                "status": "queued",
                "idempotent": False,
            }
        return {
            "pipeline_run_id": pipeline_run_id,
            "status": "already_running",
            "idempotent": True,
        }
    except (OperationalError, InterfaceError, DBAPIError, ConnectionError, TimeoutError, OSError) as exc:
        raise self.retry(exc=exc)
    except Exception as exc:
        sentry_sdk.capture_exception(exc)
        raise


async def trigger_post_sync_pipeline_async(
    *,
    tenant_id: str,
    sync_run_id: str,
) -> dict[str, Any]:
    parsed_tenant_id = _parse_uuid(tenant_id, field_name="tenant_id")
    parsed_sync_run_id = _parse_uuid(sync_run_id, field_name="sync_run_id")
    async with AsyncSessionLocal() as session:
        try:
            await set_tenant_context(session, str(parsed_tenant_id))
            run, created = await _create_or_reuse_pipeline_run(
                session=session,
                tenant_id=parsed_tenant_id,
                sync_run_id=parsed_sync_run_id,
            )
            await session.flush()
            await session.commit()
            return {
                "pipeline_run_id": str(run.id),
                "created": created,
            }
        finally:
            await clear_tenant_context(session)


async def _insert_step_log(
    *,
    session,
    pipeline_run_id: uuid.UUID,
    tenant_id: uuid.UUID,
    step_name: str,
    status: str,
    started_at: datetime,
    completed_at: datetime | None = None,
    error_message: str | None = None,
    result_summary: dict[str, Any] | None = None,
) -> PipelineStepLog:
    row = PipelineStepLog(
        pipeline_run_id=pipeline_run_id,
        tenant_id=tenant_id,
        step_name=step_name,
        status=status,
        started_at=started_at,
        completed_at=completed_at,
        error_message=error_message,
        result_summary=dict(result_summary or {}) if result_summary is not None else None,
        created_at=datetime.now(UTC),
    )
    session.add(row)
    await session.flush()
    return row


async def _run_step(
    *,
    pipeline_run_id: str,
    tenant_id: str,
    step_name: str,
    runner,
) -> dict[str, Any]:
    parsed_pipeline_run_id = _parse_uuid(pipeline_run_id, field_name="pipeline_run_id")
    parsed_tenant_id = _parse_uuid(tenant_id, field_name="tenant_id")
    async with AsyncSessionLocal() as session:
        try:
            await set_tenant_context(session, str(parsed_tenant_id))
            run = (
                await session.execute(
                    select(PipelineRun).where(
                        PipelineRun.id == parsed_pipeline_run_id,
                        PipelineRun.tenant_id == parsed_tenant_id,
                    )
                )
            ).scalar_one_or_none()
            if run is None:
                return {
                    "pipeline_run_id": pipeline_run_id,
                    "step_name": step_name,
                    "status": "skipped",
                    "reason": "pipeline_run_not_found",
                }

            started_at = datetime.now(UTC)
            await _insert_step_log(
                session=session,
                pipeline_run_id=parsed_pipeline_run_id,
                tenant_id=parsed_tenant_id,
                step_name=step_name,
                status="running",
                started_at=started_at,
            )
            await session.flush()

            try:
                result_summary = await runner(
                    session=session,
                    tenant_id=parsed_tenant_id,
                    pipeline_run_id=parsed_pipeline_run_id,
                )
                completed_at = datetime.now(UTC)
                await _insert_step_log(
                    session=session,
                    pipeline_run_id=parsed_pipeline_run_id,
                    tenant_id=parsed_tenant_id,
                    step_name=step_name,
                    status="completed",
                    started_at=started_at,
                    completed_at=completed_at,
                    result_summary=dict(result_summary or {}),
                )
                await session.flush()
                await session.commit()
                return {
                    "pipeline_run_id": pipeline_run_id,
                    "step_name": step_name,
                    "status": "completed",
                    "result_summary": dict(result_summary or {}),
                }
            except StepSkippedError as exc:
                completed_at = datetime.now(UTC)
                summary = dict(exc.summary)
                summary.setdefault("reason", exc.reason)
                await _insert_step_log(
                    session=session,
                    pipeline_run_id=parsed_pipeline_run_id,
                    tenant_id=parsed_tenant_id,
                    step_name=step_name,
                    status="skipped",
                    started_at=started_at,
                    completed_at=completed_at,
                    result_summary=summary,
                )
                await session.flush()
                await session.commit()
                return {
                    "pipeline_run_id": pipeline_run_id,
                    "step_name": step_name,
                    "status": "skipped",
                    "result_summary": summary,
                }
            except Exception as exc:
                completed_at = datetime.now(UTC)
                await _insert_step_log(
                    session=session,
                    pipeline_run_id=parsed_pipeline_run_id,
                    tenant_id=parsed_tenant_id,
                    step_name=step_name,
                    status="failed",
                    started_at=started_at,
                    completed_at=completed_at,
                    error_message=str(exc),
                )
                await session.flush()
                await session.commit()
                log.exception(
                    "Pipeline step failed: pipeline_run_id=%s step=%s tenant_id=%s",
                    pipeline_run_id,
                    step_name,
                    tenant_id,
                )
                return {
                    "pipeline_run_id": pipeline_run_id,
                    "step_name": step_name,
                    "status": "failed",
                    "error_message": str(exc),
                }
        finally:
            await clear_tenant_context(session)


async def _invoke_gl_reconciliation(
    *,
    session,
    tenant_id: uuid.UUID,
    pipeline_run_id: uuid.UUID,
) -> dict[str, Any]:
    del pipeline_run_id  # not used in this reconciler
    source_row = (
        await session.execute(
            select(
                GlEntry.period_year,
                GlEntry.period_month,
                GlEntry.entity_name,
            )
            .where(GlEntry.tenant_id == tenant_id)
            .order_by(
                desc(GlEntry.period_year),
                desc(GlEntry.period_month),
                GlEntry.created_at.desc(),
            )
            .limit(1)
        )
    ).first()
    if source_row is None:
        source_row = (
            await session.execute(
                select(
                    TrialBalanceRow.period_year,
                    TrialBalanceRow.period_month,
                    TrialBalanceRow.entity_name,
                )
                .where(TrialBalanceRow.tenant_id == tenant_id)
                .order_by(
                    desc(TrialBalanceRow.period_year),
                    desc(TrialBalanceRow.period_month),
                    TrialBalanceRow.created_at.desc(),
                )
                .limit(1)
            )
        ).first()
    if source_row is None:
        raise StepSkippedError("no_gl_tb_source_data")

    period_year, period_month, entity_name = source_row
    breaks = await run_gl_tb_reconciliation(
        session,
        tenant_id=tenant_id,
        period_year=int(period_year),
        period_month=int(period_month),
        entity_name=str(entity_name),
        run_by=tenant_id,
    )
    return {
        "period_year": int(period_year),
        "period_month": int(period_month),
        "entity_name": str(entity_name),
        "break_count": len(breaks),
    }


async def _invoke_payroll_reconciliation(
    *,
    session,
    tenant_id: uuid.UUID,
    pipeline_run_id: uuid.UUID,
) -> dict[str, Any]:
    del pipeline_run_id  # not used in this reconciler
    payroll_run = (
        await session.execute(
            select(NormalizationRun)
            .where(
                NormalizationRun.tenant_id == tenant_id,
                NormalizationRun.run_type == "payroll_normalization",
                NormalizationRun.run_status == "finalized",
            )
            .order_by(NormalizationRun.created_at.desc(), NormalizationRun.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    gl_run = (
        await session.execute(
            select(NormalizationRun)
            .where(
                NormalizationRun.tenant_id == tenant_id,
                NormalizationRun.run_type == "gl_normalization",
                NormalizationRun.run_status == "finalized",
            )
            .order_by(NormalizationRun.created_at.desc(), NormalizationRun.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if payroll_run is None or gl_run is None:
        raise StepSkippedError("no_finalized_normalization_runs")

    service = _build_payroll_reconciliation_service(session)
    created = await service.create_run(
        tenant_id=tenant_id,
        organisation_id=payroll_run.organisation_id,
        payroll_run_id=payroll_run.id,
        gl_run_id=gl_run.id,
        reporting_period=payroll_run.reporting_period,
        created_by=tenant_id,
    )
    executed = await service.execute_run(
        tenant_id=tenant_id,
        run_id=uuid.UUID(str(created["run_id"])),
        actor_user_id=tenant_id,
    )
    return {
        "run_id": str(created["run_id"]),
        "status": str(executed.get("status", "")),
        "line_count": int(executed.get("line_count", 0)),
        "exception_count": int(executed.get("exception_count", 0)),
    }


async def _invoke_mis_recomputation(
    *,
    session,
    tenant_id: uuid.UUID,
    pipeline_run_id: uuid.UUID,
) -> dict[str, Any]:
    del pipeline_run_id  # not used in this recompute step
    snapshot_id = (
        await session.execute(
            select(MisDataSnapshot.id)
            .where(MisDataSnapshot.tenant_id == tenant_id)
            .order_by(MisDataSnapshot.created_at.desc(), MisDataSnapshot.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if snapshot_id is None:
        raise StepSkippedError("no_mis_snapshot")

    service = _build_mis_service(session)
    summary = await service.snapshot_summary(tenant_id=tenant_id, snapshot_id=snapshot_id)
    return {
        "snapshot_id": str(snapshot_id),
        "summary": summary,
    }


async def _invoke_anomaly_detection(
    *,
    session,
    tenant_id: uuid.UUID,
    pipeline_run_id: uuid.UUID,
) -> dict[str, Any]:
    del pipeline_run_id  # not used in this detector
    run = (
        await session.execute(
            select(AnomalyRun)
            .where(AnomalyRun.tenant_id == tenant_id)
            .order_by(AnomalyRun.created_at.desc(), AnomalyRun.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if run is None:
        raise StepSkippedError("no_anomaly_run")

    service = _build_anomaly_service(session)
    result = await service.execute_run(
        tenant_id=tenant_id,
        run_id=run.id,
        actor_user_id=tenant_id,
    )
    return {
        "run_id": str(result.get("run_id", run.id)),
        "status": str(result.get("status", "")),
        "idempotent": bool(result.get("idempotent", False)),
    }


@celery_app.task(name="auto_trigger.run_gl_reconciliation")
def run_gl_reconciliation(
    pipeline_run_id: str,
    tenant_id: str,
) -> dict[str, Any]:
    return run_async(
        run_gl_reconciliation_async(
            pipeline_run_id=pipeline_run_id,
            tenant_id=tenant_id,
        )
    )


async def run_gl_reconciliation_async(
    *,
    pipeline_run_id: str,
    tenant_id: str,
) -> dict[str, Any]:
    return await _run_step(
        pipeline_run_id=pipeline_run_id,
        tenant_id=tenant_id,
        step_name="gl_reconciliation",
        runner=_invoke_gl_reconciliation,
    )


@celery_app.task(name="auto_trigger.run_payroll_reconciliation")
def run_payroll_reconciliation(
    pipeline_run_id: str,
    tenant_id: str,
) -> dict[str, Any]:
    return run_async(
        run_payroll_reconciliation_async(
            pipeline_run_id=pipeline_run_id,
            tenant_id=tenant_id,
        )
    )


async def run_payroll_reconciliation_async(
    *,
    pipeline_run_id: str,
    tenant_id: str,
) -> dict[str, Any]:
    return await _run_step(
        pipeline_run_id=pipeline_run_id,
        tenant_id=tenant_id,
        step_name="payroll_reconciliation",
        runner=_invoke_payroll_reconciliation,
    )


@celery_app.task(name="auto_trigger.run_mis_recomputation")
def run_mis_recomputation(
    pipeline_run_id: str,
    tenant_id: str,
) -> dict[str, Any]:
    return run_async(
        run_mis_recomputation_async(
            pipeline_run_id=pipeline_run_id,
            tenant_id=tenant_id,
        )
    )


async def run_mis_recomputation_async(
    *,
    pipeline_run_id: str,
    tenant_id: str,
) -> dict[str, Any]:
    return await _run_step(
        pipeline_run_id=pipeline_run_id,
        tenant_id=tenant_id,
        step_name="mis_recomputation",
        runner=_invoke_mis_recomputation,
    )


@celery_app.task(name="auto_trigger.run_anomaly_detection")
def run_anomaly_detection(
    pipeline_run_id: str,
    tenant_id: str,
) -> dict[str, Any]:
    return run_async(
        run_anomaly_detection_async(
            pipeline_run_id=pipeline_run_id,
            tenant_id=tenant_id,
        )
    )


async def run_anomaly_detection_async(
    *,
    pipeline_run_id: str,
    tenant_id: str,
) -> dict[str, Any]:
    return await _run_step(
        pipeline_run_id=pipeline_run_id,
        tenant_id=tenant_id,
        step_name="anomaly_detection",
        runner=_invoke_anomaly_detection,
    )


@celery_app.task(name="auto_trigger.finalise_pipeline_run")
def finalise_pipeline_run(
    step_results: list[dict[str, Any]] | None,
    pipeline_run_id: str,
    tenant_id: str,
) -> dict[str, Any]:
    del step_results  # status is derived from persisted logs for idempotency

    return run_async(
        finalise_pipeline_run_async(
            pipeline_run_id=pipeline_run_id,
            tenant_id=tenant_id,
        )
    )


async def finalise_pipeline_run_async(
    *,
    pipeline_run_id: str,
    tenant_id: str,
) -> dict[str, Any]:
    parsed_pipeline_run_id = _parse_uuid(pipeline_run_id, field_name="pipeline_run_id")
    parsed_tenant_id = _parse_uuid(tenant_id, field_name="tenant_id")
    async with AsyncSessionLocal() as session:
        try:
            await set_tenant_context(session, str(parsed_tenant_id))
            row = (
                await session.execute(
                    select(PipelineRun).where(
                        PipelineRun.id == parsed_pipeline_run_id,
                        PipelineRun.tenant_id == parsed_tenant_id,
                    )
                )
            ).scalar_one_or_none()
            if row is None:
                return {
                    "pipeline_run_id": pipeline_run_id,
                    "status": "not_found",
                }

            logs = (
                await session.execute(
                    select(PipelineStepLog)
                    .where(PipelineStepLog.pipeline_run_id == parsed_pipeline_run_id)
                    .order_by(PipelineStepLog.created_at.desc(), PipelineStepLog.id.desc())
                )
            ).scalars().all()

            latest_by_step: dict[str, PipelineStepLog] = {}
            for log_row in logs:
                if log_row.step_name not in latest_by_step:
                    latest_by_step[log_row.step_name] = log_row

            statuses = {step: item.status for step, item in latest_by_step.items()}
            if not statuses:
                final_status = "failed"
                row.error_message = "No pipeline step logs were recorded"
            elif any(status == "failed" for status in statuses.values()):
                final_status = "partial"
                failed_steps = sorted(
                    step for step, status in statuses.items() if status == "failed"
                )
                row.error_message = f"Failed steps: {', '.join(failed_steps)}"
            elif all(status == "completed" for status in statuses.values()) and len(statuses) == 4:
                final_status = "completed"
                row.error_message = None
            else:
                final_status = "partial"
                row.error_message = None

            row.status = final_status
            row.completed_at = datetime.now(UTC)
            await session.flush()
            await session.commit()
            return {
                "pipeline_run_id": pipeline_run_id,
                "status": final_status,
                "step_statuses": statuses,
            }
        finally:
            await clear_tenant_context(session)


__all__ = [
    "trigger_post_sync_pipeline",
    "run_gl_reconciliation",
    "run_payroll_reconciliation",
    "run_mis_recomputation",
    "run_anomaly_detection",
    "finalise_pipeline_run",
    "run_gl_reconciliation_async",
    "run_payroll_reconciliation_async",
    "run_mis_recomputation_async",
    "run_anomaly_detection_async",
    "trigger_post_sync_pipeline_async",
    "finalise_pipeline_run_async",
    "resolve_pipeline_run_id_for_trigger",
]
