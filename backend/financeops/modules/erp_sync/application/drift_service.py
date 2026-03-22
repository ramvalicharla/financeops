from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import NotFoundError
from financeops.db.models.erp_sync import ExternalSyncDriftReport, ExternalSyncRun
from financeops.modules.erp_sync.domain.enums import DriftSeverity
from financeops.modules.erp_sync.domain.schemas import DriftMetric
from financeops.services.audit_writer import AuditWriter


class DriftService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def run_drift_check(
        self,
        *,
        tenant_id: uuid.UUID,
        sync_run_id: uuid.UUID,
        created_by: uuid.UUID,
        metrics: Sequence[Mapping[str, Any]] | None = None,
    ) -> dict[str, Any]:
        existing = (
            await self._session.execute(
                select(ExternalSyncDriftReport).where(
                    ExternalSyncDriftReport.tenant_id == tenant_id,
                    ExternalSyncDriftReport.sync_run_id == sync_run_id,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return {
                "drift_report_id": str(existing.id),
                "drift_detected": bool(existing.drift_detected),
                "drift_severity": existing.drift_severity,
                "total_variances": int(existing.total_variances),
            }

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

        drift_metrics = self._build_metrics(
            run=run,
            metrics=metrics or [],
        )
        severity = self._classify_severity(drift_metrics)
        drift_detected = severity != DriftSeverity.NONE
        total_variances = sum(1 for metric in drift_metrics if metric.status != "MATCHED")

        row = await AuditWriter.insert_financial_record(
            self._session,
            model_class=ExternalSyncDriftReport,
            tenant_id=tenant_id,
            record_data={
                "sync_run_id": str(sync_run_id),
                "drift_severity": severity.value,
                "total_variances": total_variances,
            },
            values={
                "sync_run_id": sync_run_id,
                "drift_detected": drift_detected,
                "drift_severity": severity.value,
                "total_variances": total_variances,
                "metrics_checked_json": [metric.model_dump(mode="json") for metric in drift_metrics],
                "generated_at": datetime.now(UTC),
                "created_by": created_by,
            },
        )
        return {
            "drift_report_id": str(row.id),
            "drift_detected": drift_detected,
            "drift_severity": severity.value,
            "total_variances": total_variances,
        }

    @staticmethod
    def blocks_publish(drift_severity: str) -> bool:
        return drift_severity == DriftSeverity.CRITICAL.value

    def _build_metrics(
        self,
        *,
        run: ExternalSyncRun,
        metrics: Sequence[Mapping[str, Any]],
    ) -> list[DriftMetric]:
        if metrics:
            return [self._coerce_metric(item) for item in metrics]

        expected_count = int(run.extraction_total_records or 0)
        fetched = int(run.extraction_fetched_records or 0)
        variance = Decimal(str(expected_count - fetched))
        variance_pct = self._pct(erp=Decimal(str(expected_count)), financeops=Decimal(str(fetched)))
        status = "MATCHED" if variance == Decimal("0") else "VARIANCE"
        return [
            DriftMetric(
                metric_name="line_count",
                erp_value=expected_count,
                financeops_value=fetched,
                variance=variance,
                variance_pct=variance_pct,
                status=status,
                threshold_breached=(variance_pct or Decimal("0")) >= Decimal("1"),
            )
        ]

    def _coerce_metric(self, metric: Mapping[str, Any]) -> DriftMetric:
        erp_value = metric.get("erp_value")
        financeops_value = metric.get("financeops_value")
        variance = self._to_decimal(metric.get("variance"))
        variance_pct = self._to_decimal(metric.get("variance_pct"))
        if variance is None and erp_value is not None and financeops_value is not None:
            erp_dec = self._to_decimal(erp_value) or Decimal("0")
            fo_dec = self._to_decimal(financeops_value) or Decimal("0")
            variance = erp_dec - fo_dec
        if variance_pct is None and erp_value is not None and financeops_value is not None:
            variance_pct = self._pct(
                erp=self._to_decimal(erp_value) or Decimal("0"),
                financeops=self._to_decimal(financeops_value) or Decimal("0"),
            )
        status = str(metric.get("status") or ("MATCHED" if (variance or Decimal("0")) == Decimal("0") else "VARIANCE"))
        return DriftMetric(
            metric_name=str(metric.get("metric_name") or "metric"),
            erp_value=erp_value if isinstance(erp_value, (Decimal, int)) else self._to_decimal(erp_value),
            financeops_value=(
                financeops_value
                if isinstance(financeops_value, (Decimal, int))
                else self._to_decimal(financeops_value)
            ),
            variance=variance,
            variance_pct=variance_pct,
            status=status,
            threshold_breached=bool(metric.get("threshold_breached", False)),
        )

    def _classify_severity(self, metrics: Sequence[DriftMetric]) -> DriftSeverity:
        if not metrics:
            return DriftSeverity.NONE
        max_pct = Decimal("0")
        has_variance = False
        for metric in metrics:
            if metric.status in {"ERP_MISSING", "FO_MISSING", "STRUCTURAL_MISMATCH"}:
                return DriftSeverity.CRITICAL
            pct = metric.variance_pct or Decimal("0")
            if pct.copy_abs() > max_pct:
                max_pct = pct.copy_abs()
            if metric.status != "MATCHED" or (metric.variance or Decimal("0")) != Decimal("0"):
                has_variance = True
        if not has_variance:
            return DriftSeverity.NONE
        if max_pct > Decimal("5"):
            return DriftSeverity.CRITICAL
        if max_pct >= Decimal("1"):
            return DriftSeverity.SIGNIFICANT
        return DriftSeverity.MINOR

    @staticmethod
    def _to_decimal(value: Any) -> Decimal | None:
        if value is None:
            return None
        if isinstance(value, Decimal):
            return value
        if isinstance(value, int):
            return Decimal(value)
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError):
            return None

    @staticmethod
    def _pct(*, erp: Decimal, financeops: Decimal) -> Decimal | None:
        if erp == Decimal("0"):
            return None
        return ((erp - financeops) / erp * Decimal("100")).quantize(Decimal("0.000001"))

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        return await self.run_drift_check(
            tenant_id=kwargs["tenant_id"],
            sync_run_id=kwargs["sync_run_id"],
            created_by=kwargs["created_by"],
            metrics=kwargs.get("metrics"),
        )
