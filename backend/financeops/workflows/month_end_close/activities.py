from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
from uuid import UUID

from temporalio import activity

from financeops.db.session import tenant_session

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
    async with tenant_session(_to_uuid(tenant_id)) as session:
        try:
            from financeops.services.consolidation.consolidation_service import run_consolidation as run_consolidation_service

            result = await run_consolidation_service(
                session=session,
                tenant_id=_to_uuid(tenant_id),
                period=period,
            )
            await session.commit()
            payload = _to_dict(result, default_key="result")
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
    async with tenant_session(_to_uuid(tenant_id)) as session:
        try:
            from financeops.modules.board_pack_generator.service import generate

            result = await generate(
                session=session,
                tenant_id=_to_uuid(tenant_id),
                period=period,
            )
            await session.commit()
            payload = _to_dict(result, default_key="result")
            board_pack_id = payload.get("id") or payload.get("board_pack_id")
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

