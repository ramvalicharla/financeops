from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import NotFoundError
from financeops.db.models.erp_sync import (
    ExternalBackdatedModificationAlert,
    ExternalPeriodLock,
    ExternalRawSnapshot,
    ExternalSyncRun,
)
from financeops.services.audit_writer import AuditWriter


class PeriodLockService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def auto_lock_on_publish(
        self,
        *,
        tenant_id: uuid.UUID,
        sync_run_id: uuid.UUID,
        created_by: uuid.UUID,
    ) -> dict[str, Any]:
        run = await self._get_run(tenant_id=tenant_id, sync_run_id=sync_run_id)
        period_key = run.reporting_period_label or "NO_PERIOD"

        existing = (
            await self._session.execute(
                select(ExternalPeriodLock).where(
                    ExternalPeriodLock.tenant_id == tenant_id,
                    ExternalPeriodLock.organisation_id == run.organisation_id,
                    ExternalPeriodLock.entity_id == run.entity_id,
                    ExternalPeriodLock.dataset_type == run.dataset_type,
                    ExternalPeriodLock.period_key == period_key,
                    ExternalPeriodLock.lock_status == "locked",
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return {
                "period_lock_id": str(existing.id),
                "dataset_type": existing.dataset_type,
                "period_key": existing.period_key,
                "status": "existing",
            }

        lock_row = await AuditWriter.insert_financial_record(
            self._session,
            model_class=ExternalPeriodLock,
            tenant_id=tenant_id,
            record_data={
                "organisation_id": str(run.organisation_id),
                "entity_id": str(run.entity_id) if run.entity_id else None,
                "dataset_type": run.dataset_type,
                "period_key": period_key,
            },
            values={
                "organisation_id": run.organisation_id,
                "entity_id": run.entity_id,
                "dataset_type": run.dataset_type,
                "period_key": period_key,
                "lock_status": "locked",
                "lock_reason": "Auto-lock on publish",
                "source_sync_run_id": run.id,
                "supersedes_id": None,
                "created_by": created_by,
            },
        )
        return {
            "period_lock_id": str(lock_row.id),
            "dataset_type": lock_row.dataset_type,
            "period_key": lock_row.period_key,
            "status": "created",
        }

    async def detect_backdated_modifications(
        self,
        *,
        tenant_id: uuid.UUID,
        sync_run_id: uuid.UUID,
        created_by: uuid.UUID,
    ) -> dict[str, Any]:
        run = await self._get_run(tenant_id=tenant_id, sync_run_id=sync_run_id)
        period_key = run.reporting_period_label or "NO_PERIOD"

        lock = (
            await self._session.execute(
                select(ExternalPeriodLock)
                .where(
                    ExternalPeriodLock.tenant_id == tenant_id,
                    ExternalPeriodLock.organisation_id == run.organisation_id,
                    ExternalPeriodLock.entity_id == run.entity_id,
                    ExternalPeriodLock.dataset_type == run.dataset_type,
                    ExternalPeriodLock.period_key == period_key,
                    ExternalPeriodLock.lock_status == "locked",
                )
                .order_by(ExternalPeriodLock.created_at.desc(), ExternalPeriodLock.id.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if lock is None or lock.source_sync_run_id is None:
            return {"backdated_detected": False, "alert_id": None}

        current_snapshot = await self._latest_snapshot_hash(tenant_id=tenant_id, sync_run_id=run.id)
        locked_snapshot = await self._latest_snapshot_hash(tenant_id=tenant_id, sync_run_id=lock.source_sync_run_id)
        if current_snapshot is None or locked_snapshot is None or current_snapshot == locked_snapshot:
            return {"backdated_detected": False, "alert_id": None}

        alert = await AuditWriter.insert_financial_record(
            self._session,
            model_class=ExternalBackdatedModificationAlert,
            tenant_id=tenant_id,
            record_data={
                "sync_run_id": str(run.id),
                "period_lock_id": str(lock.id),
                "severity": "critical",
            },
            values={
                "sync_run_id": run.id,
                "period_lock_id": lock.id,
                "severity": "critical",
                "alert_status": "open",
                "message": "Backdated modification detected on locked period",
                "details_json": {
                    "current_payload_hash": current_snapshot,
                    "locked_payload_hash": locked_snapshot,
                },
                "acknowledged_by": None,
                "acknowledged_at": None,
                "created_by": created_by,
            },
        )
        return {"backdated_detected": True, "alert_id": str(alert.id)}

    async def has_unacknowledged_critical_alerts(
        self,
        *,
        tenant_id: uuid.UUID,
        sync_run_id: uuid.UUID,
    ) -> bool:
        row = (
            await self._session.execute(
                select(ExternalBackdatedModificationAlert.id).where(
                    ExternalBackdatedModificationAlert.tenant_id == tenant_id,
                    ExternalBackdatedModificationAlert.sync_run_id == sync_run_id,
                    ExternalBackdatedModificationAlert.severity == "critical",
                    ExternalBackdatedModificationAlert.alert_status == "open",
                    ExternalBackdatedModificationAlert.acknowledged_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        return row is not None

    async def _get_run(self, *, tenant_id: uuid.UUID, sync_run_id: uuid.UUID) -> ExternalSyncRun:
        run = (
            await self._session.execute(
                select(ExternalSyncRun).where(
                    ExternalSyncRun.tenant_id == tenant_id,
                    ExternalSyncRun.id == sync_run_id,
                )
            )
        ).scalar_one_or_none()
        if run is None:
            raise NotFoundError("Sync run not found")
        return run

    async def _latest_snapshot_hash(
        self,
        *,
        tenant_id: uuid.UUID,
        sync_run_id: uuid.UUID,
    ) -> str | None:
        snapshot = (
            await self._session.execute(
                select(ExternalRawSnapshot)
                .where(
                    ExternalRawSnapshot.tenant_id == tenant_id,
                    ExternalRawSnapshot.sync_run_id == sync_run_id,
                )
                .order_by(ExternalRawSnapshot.created_at.desc(), ExternalRawSnapshot.id.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        return snapshot.payload_hash if snapshot else None

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        action = str(kwargs.get("action", "")).strip().lower()
        if action == "auto_lock_on_publish":
            return await self.auto_lock_on_publish(
                tenant_id=kwargs["tenant_id"],
                sync_run_id=kwargs["sync_run_id"],
                created_by=kwargs["created_by"],
            )
        if action == "detect_backdated_modifications":
            return await self.detect_backdated_modifications(
                tenant_id=kwargs["tenant_id"],
                sync_run_id=kwargs["sync_run_id"],
                created_by=kwargs["created_by"],
            )
        if action == "has_unacknowledged_critical":
            return {
                "has_unacknowledged_critical": await self.has_unacknowledged_critical_alerts(
                    tenant_id=kwargs["tenant_id"],
                    sync_run_id=kwargs["sync_run_id"],
                )
            }
        raise ValueError("Unsupported period lock service action")
