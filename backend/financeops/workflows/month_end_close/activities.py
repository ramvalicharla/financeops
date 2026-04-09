from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
from datetime import date, timedelta
from uuid import UUID
from uuid import uuid5

from sqlalchemy import select
from temporalio import activity

from financeops.core.intent.enums import IntentSourceChannel, IntentType
from financeops.core.intent.service import IntentActor, IntentService
from financeops.db.models.board_pack_generator import BoardPackGeneratorDefinition
from financeops.db.models.ratio_variance_engine import MetricRun
from financeops.db.models.users import UserRole
from financeops.db.session import tenant_session
from financeops.platform.db.models.organisations import CpOrganisation

log = logging.getLogger(__name__)


def _to_uuid(raw: str) -> UUID:
    return UUID(str(raw))


def _to_dict(value: object, *, default_key: str) -> dict:
    if isinstance(value, Mapping):
        return dict(value)
    if is_dataclass(value):
        return dict(asdict(value))
    if hasattr(value, "model_dump"):
        try:
            return dict(value.model_dump(mode="json"))
        except Exception:
            return {default_key: value}
    return {default_key: value}


def _period_start(period: str) -> date:
    year, month = period.split("-", 1)
    return date(int(year), int(month), 1)


def _period_end(period: str) -> date:
    start = _period_start(period)
    if start.month == 12:
        return date(start.year + 1, 1, 1) - timedelta(days=1)
    return date(start.year, start.month + 1, 1) - timedelta(days=1)


def _workflow_actor(tenant_id: UUID, *, workflow_name: str, period: str) -> IntentActor:
    return IntentActor(
        user_id=uuid5(tenant_id, f"{workflow_name}:{period}"),
        tenant_id=tenant_id,
        role=UserRole.finance_leader.value,
        source_channel=IntentSourceChannel.SYSTEM.value,
        request_id=None,
        correlation_id=f"{workflow_name}:{period}",
    )


def _workflow_idempotency_key(
    *,
    tenant_id: UUID,
    period: str,
    intent_type: IntentType,
    payload: dict,
    target_id: UUID | None = None,
) -> str:
    fingerprint = {
        "tenant_id": str(tenant_id),
        "period": period,
        "intent_type": intent_type.value,
        "target_id": str(target_id) if target_id is not None else None,
        "payload": payload,
    }
    raw = json.dumps(fingerprint, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def _submit_workflow_intent(
    session,
    *,
    tenant_id: UUID,
    period: str,
    workflow_name: str,
    intent_type: IntentType,
    payload: dict,
    target_id: UUID | None = None,
):
    return await IntentService(session).submit_intent(
        intent_type=intent_type,
        actor=_workflow_actor(tenant_id, workflow_name=workflow_name, period=period),
        payload=payload,
        target_id=target_id,
        idempotency_key=_workflow_idempotency_key(
            tenant_id=tenant_id,
            period=period,
            intent_type=intent_type,
            payload=payload,
            target_id=target_id,
        ),
    )


@activity.defn(name="sync_erp_data")
async def sync_erp_data(tenant_id: str, period: str) -> dict:
    """Pull latest data from configured ERP connectors."""
    async with tenant_session(_to_uuid(tenant_id)) as session:
        try:
            from financeops.modules.erp_sync.application import sync_service

            result = await sync_service.run_sync_for_tenant(
                session=session,
                tenant_id=_to_uuid(tenant_id),
                period=period,
            )
            await session.commit()
            payload = _to_dict(result, default_key="result")
            return {
                "synced_connectors": int(payload.get("connector_count", 0)),
                "records": int(payload.get("record_count", 0)),
            }
        except Exception as exc:
            log.warning("sync_erp_data_fallback tenant=%s period=%s error=%s", tenant_id, period, exc)
            await session.rollback()
            return {"synced_connectors": 0, "records": 0}


@activity.defn(name="run_gl_reconciliation")
async def run_gl_reconciliation(tenant_id: str, period: str) -> dict:
    """Run GL/TB reconciliation for all entities."""
    async with tenant_session(_to_uuid(tenant_id)) as session:
        try:
            from financeops.services.reconciliation_service import run_reconciliation

            result = await run_reconciliation(
                session=session,
                tenant_id=_to_uuid(tenant_id),
                period=period,
            )
            await session.commit()
            payload = _to_dict(result, default_key="result")
            return {
                "breaks": int(payload.get("break_count", 0)),
                "entities": int(payload.get("entity_count", 0)),
            }
        except Exception as exc:
            await session.rollback()
            raise RuntimeError(f"gl_reconciliation_failed:{exc}") from exc


@activity.defn(name="run_consolidation")
async def run_consolidation(tenant_id: str, period: str) -> dict:
    """Run multi-entity consolidation."""
    tenant_uuid = _to_uuid(tenant_id)
    async with tenant_session(tenant_uuid) as session:
        try:
            reporting_period = _period_start(period)
            organisation_id = (
                await session.execute(
                    select(CpOrganisation.id)
                    .where(CpOrganisation.tenant_id == tenant_uuid)
                    .order_by(CpOrganisation.created_at.asc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if organisation_id is None:
                await session.commit()
                return {"entities_consolidated": 0}

            source_run_id = (
                await session.execute(
                    select(MetricRun.id)
                    .where(
                        MetricRun.tenant_id == tenant_uuid,
                        MetricRun.reporting_period == reporting_period,
                    )
                    .order_by(MetricRun.created_at.desc(), MetricRun.id.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if source_run_id is None:
                await session.commit()
                return {"entities_consolidated": 0}

            create_result = await _submit_workflow_intent(
                session,
                tenant_id=tenant_uuid,
                period=period,
                workflow_name="month_end_close_consolidation",
                intent_type=IntentType.RUN_CONSOLIDATION,
                payload={
                    "organisation_id": str(organisation_id),
                    "reporting_period": reporting_period.isoformat(),
                    "source_run_refs": [
                        {"source_type": "metric_run", "run_id": str(source_run_id)},
                        {"source_type": "variance_run", "run_id": str(source_run_id)},
                    ],
                },
            )
            run_id = (create_result.record_refs or {}).get("run_id")
            if run_id is None:
                await session.commit()
                return {"entities_consolidated": 0}

            execute_result = await _submit_workflow_intent(
                session,
                tenant_id=tenant_uuid,
                period=period,
                workflow_name="month_end_close_consolidation_execute",
                intent_type=IntentType.EXECUTE_CONSOLIDATION,
                payload={},
                target_id=UUID(str(run_id)),
            )
            await session.commit()
            payload = dict(execute_result.record_refs or {})
            return {"entities_consolidated": int(payload.get("entity_count", 0))}
        except Exception as exc:
            await session.rollback()
            raise RuntimeError(f"consolidation_failed:{exc}") from exc


@activity.defn(name="recompute_mis")
async def recompute_mis(tenant_id: str, period: str) -> dict:
    """Recompute MIS after reconciliation."""
    async with tenant_session(_to_uuid(tenant_id)) as session:
        try:
            from financeops.services.mis_service import recompute_mis as recompute_mis_service

            result = await recompute_mis_service(
                session=session,
                tenant_id=_to_uuid(tenant_id),
                period=period,
            )
            await session.commit()
            payload = _to_dict(result, default_key="result")
            return {"lines_updated": int(payload.get("line_count", 0))}
        except Exception:
            await session.rollback()
            return {"lines_updated": 0}


@activity.defn(name="run_anomaly_detection")
async def run_anomaly_detection(tenant_id: str, period: str) -> dict:
    """Run anomaly detection on finalised data."""
    async with tenant_session(_to_uuid(tenant_id)) as session:
        try:
            from financeops.modules.anomaly_pattern_engine.application import run_service

            result = await run_service.run_detection_for_period(
                session=session,
                tenant_id=_to_uuid(tenant_id),
                period=period,
            )
            await session.commit()
            payload = _to_dict(result, default_key="result")
            return {"anomalies_detected": int(payload.get("anomaly_count", 0))}
        except Exception:
            await session.rollback()
            return {"anomalies_detected": 0}


@activity.defn(name="generate_board_pack")
async def generate_board_pack(tenant_id: str, period: str) -> dict:
    """Generate board pack for the period."""
    tenant_uuid = _to_uuid(tenant_id)
    async with tenant_session(tenant_uuid) as session:
        try:
            definition_id = (
                await session.execute(
                    select(BoardPackGeneratorDefinition.id)
                    .where(
                        BoardPackGeneratorDefinition.tenant_id == tenant_uuid,
                        BoardPackGeneratorDefinition.is_active.is_(True),
                    )
                    .order_by(
                        BoardPackGeneratorDefinition.updated_at.desc(),
                        BoardPackGeneratorDefinition.id.desc(),
                    )
                    .limit(1)
                )
            ).scalar_one_or_none()
            if definition_id is None:
                await session.commit()
                return {"board_pack_id": None}

            result = await _submit_workflow_intent(
                session,
                tenant_id=tenant_uuid,
                period=period,
                workflow_name="month_end_close_board_pack",
                intent_type=IntentType.GENERATE_BOARD_PACK,
                payload={
                    "definition_id": str(definition_id),
                    "period_start": _period_start(period).isoformat(),
                    "period_end": _period_end(period).isoformat(),
                },
            )
            await session.commit()
            board_pack_id = (result.record_refs or {}).get("run_id")
            return {"board_pack_id": str(board_pack_id) if board_pack_id else None}
        except Exception:
            await session.rollback()
            return {"board_pack_id": None}


@activity.defn(name="notify_completion")
async def notify_completion(tenant_id: str, period: str, results: dict) -> None:
    """Notify Finance Leader that close is complete."""
    log.info(
        "month_end_close_complete tenant=%s period=%s results=%s",
        tenant_id,
        period,
        results,
    )
