from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import ValidationError
from financeops.db.models.erp_sync import (
    ExternalSyncHealthAlert,
    ExternalSyncRun,
    ExternalSyncSLAConfig,
)
from financeops.modules.erp_sync.domain.enums import DatasetType, SyncRunStatus
from financeops.services.audit_writer import AuditWriter


DEFAULT_SLA_HOURS: dict[DatasetType, int] = {
    DatasetType.BANK_STATEMENT: 4,
    DatasetType.BANK_TRANSACTION_REGISTER: 4,
    DatasetType.AR_AGEING: 12,
    DatasetType.AP_AGEING: 12,
    DatasetType.INVOICE_REGISTER: 12,
    DatasetType.PURCHASE_REGISTER: 12,
    DatasetType.TRIAL_BALANCE: 24,
    DatasetType.GENERAL_LEDGER: 24,
    DatasetType.PROFIT_AND_LOSS: 24,
    DatasetType.BALANCE_SHEET: 24,
    DatasetType.GST_RETURN_GSTR1: 72,
    DatasetType.GST_RETURN_GSTR2B: 72,
    DatasetType.GST_RETURN_GSTR3B: 72,
    DatasetType.CHART_OF_ACCOUNTS: 168,
    DatasetType.VENDOR_MASTER: 168,
    DatasetType.CUSTOMER_MASTER: 168,
}


class HealthService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def evaluate_sla(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        connection_id: uuid.UUID,
        dataset_type: DatasetType,
        created_by: uuid.UUID,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        check_time = now or datetime.now(UTC)
        sla_hours, failure_threshold = await self._resolve_sla_config(
            tenant_id=tenant_id,
            organisation_id=organisation_id,
            connection_id=connection_id,
            dataset_type=dataset_type,
        )
        runs = (
            await self._session.execute(
                select(ExternalSyncRun)
                .where(
                    ExternalSyncRun.tenant_id == tenant_id,
                    ExternalSyncRun.connection_id == connection_id,
                    ExternalSyncRun.dataset_type == dataset_type.value,
                )
                .order_by(ExternalSyncRun.created_at.desc(), ExternalSyncRun.id.desc())
                .limit(20)
            )
        ).scalars().all()

        last_success = next(
            (
                run
                for run in runs
                if run.run_status in {SyncRunStatus.COMPLETED.value, SyncRunStatus.PUBLISHED.value}
            ),
            None,
        )
        consecutive_failures = 0
        for run in runs:
            if run.run_status in {SyncRunStatus.FAILED.value, SyncRunStatus.HALTED.value, SyncRunStatus.DRIFT_ALERT.value}:
                consecutive_failures += 1
            else:
                break

        alerts_created: list[dict[str, Any]] = []
        stale_after = timedelta(hours=sla_hours)
        stale_since = check_time - stale_after

        if last_success is None or last_success.created_at < stale_since:
            alert = await self._insert_alert_if_absent(
                tenant_id=tenant_id,
                connection_id=connection_id,
                sync_run_id=last_success.id if last_success else None,
                dataset_type=dataset_type.value,
                alert_type="scheduled_sync_missed",
                message=f"SLA breach: no successful {dataset_type.value} sync in {sla_hours}h",
                payload={
                    "sla_hours": sla_hours,
                    "last_success_at": last_success.created_at.isoformat() if last_success else None,
                },
                created_by=created_by,
            )
            alerts_created.append(alert)

        if consecutive_failures >= failure_threshold:
            alert = await self._insert_alert_if_absent(
                tenant_id=tenant_id,
                connection_id=connection_id,
                sync_run_id=runs[0].id if runs else None,
                dataset_type=dataset_type.value,
                alert_type="consecutive_failure_threshold",
                message=f"Consecutive failures reached {consecutive_failures}",
                payload={
                    "failure_threshold": failure_threshold,
                    "consecutive_failures": consecutive_failures,
                },
                created_by=created_by,
            )
            alerts_created.append(alert)

        if last_success is not None and last_success.created_at < (check_time - (stale_after * 2)):
            alert = await self._insert_alert_if_absent(
                tenant_id=tenant_id,
                connection_id=connection_id,
                sync_run_id=last_success.id,
                dataset_type=dataset_type.value,
                alert_type="data_staleness",
                message=f"Data stale for {dataset_type.value}",
                payload={
                    "sla_hours": sla_hours,
                    "last_success_at": last_success.created_at.isoformat(),
                },
                created_by=created_by,
            )
            alerts_created.append(alert)

        if consecutive_failures >= failure_threshold and (
            last_success is None or last_success.created_at < (check_time - timedelta(days=7))
        ):
            alert = await self._insert_alert_if_absent(
                tenant_id=tenant_id,
                connection_id=connection_id,
                sync_run_id=runs[0].id if runs else None,
                dataset_type=dataset_type.value,
                alert_type="connection_dead",
                message="Connection considered dead due to sustained failures",
                payload={
                    "failure_threshold": failure_threshold,
                    "consecutive_failures": consecutive_failures,
                    "last_success_at": last_success.created_at.isoformat() if last_success else None,
                },
                created_by=created_by,
            )
            alerts_created.append(alert)

        return {
            "connection_id": str(connection_id),
            "dataset_type": dataset_type.value,
            "sla_hours": sla_hours,
            "consecutive_failure_threshold": failure_threshold,
            "alerts_created": alerts_created,
        }

    async def _resolve_sla_config(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        connection_id: uuid.UUID,
        dataset_type: DatasetType,
    ) -> tuple[int, int]:
        config = (
            await self._session.execute(
                select(ExternalSyncSLAConfig)
                .where(
                    ExternalSyncSLAConfig.tenant_id == tenant_id,
                    ExternalSyncSLAConfig.organisation_id == organisation_id,
                    ExternalSyncSLAConfig.connection_id == connection_id,
                    ExternalSyncSLAConfig.dataset_type == dataset_type.value,
                    ExternalSyncSLAConfig.active.is_(True),
                )
                .order_by(ExternalSyncSLAConfig.created_at.desc(), ExternalSyncSLAConfig.id.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if config is None:
            return DEFAULT_SLA_HOURS.get(dataset_type, 24), 3
        return int(config.sla_hours), int(config.consecutive_failure_threshold)

    async def _insert_alert_if_absent(
        self,
        *,
        tenant_id: uuid.UUID,
        connection_id: uuid.UUID,
        sync_run_id: uuid.UUID | None,
        dataset_type: str | None,
        alert_type: str,
        message: str,
        payload: dict[str, Any],
        created_by: uuid.UUID,
    ) -> dict[str, Any]:
        existing = (
            await self._session.execute(
                select(ExternalSyncHealthAlert).where(
                    ExternalSyncHealthAlert.tenant_id == tenant_id,
                    ExternalSyncHealthAlert.connection_id == connection_id,
                    ExternalSyncHealthAlert.dataset_type == dataset_type,
                    ExternalSyncHealthAlert.alert_type == alert_type,
                    ExternalSyncHealthAlert.alert_status == "open",
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return {
                "alert_id": str(existing.id),
                "alert_type": existing.alert_type,
                "status": "existing",
            }

        row = await AuditWriter.insert_financial_record(
            self._session,
            model_class=ExternalSyncHealthAlert,
            tenant_id=tenant_id,
            record_data={
                "connection_id": str(connection_id),
                "dataset_type": dataset_type,
                "alert_type": alert_type,
            },
            values={
                "connection_id": connection_id,
                "sync_run_id": sync_run_id,
                "dataset_type": dataset_type,
                "alert_type": alert_type,
                "alert_status": "open",
                "message": message,
                "payload_json": payload,
                "created_by": created_by,
            },
        )
        return {"alert_id": str(row.id), "alert_type": row.alert_type, "status": "created"}

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        dataset_type = kwargs.get("dataset_type")
        if isinstance(dataset_type, str):
            dataset_type = DatasetType(dataset_type)
        if not isinstance(dataset_type, DatasetType):
            raise ValidationError("dataset_type is required for health evaluation")
        return await self.evaluate_sla(
            tenant_id=kwargs["tenant_id"],
            organisation_id=kwargs["organisation_id"],
            connection_id=kwargs["connection_id"],
            dataset_type=dataset_type,
            created_by=kwargs["created_by"],
            now=kwargs.get("now"),
        )
