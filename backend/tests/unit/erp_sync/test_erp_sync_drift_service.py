from __future__ import annotations

from decimal import Decimal

from financeops.modules.erp_sync.application.drift_service import DriftService
from financeops.modules.erp_sync.domain.enums import DriftSeverity
from financeops.modules.erp_sync.domain.schemas import DriftMetric


def _service() -> DriftService:
    return DriftService(session=None)  # type: ignore[arg-type]


def test_drift_severity_none_for_matched_metrics() -> None:
    service = _service()
    metrics = [
        DriftMetric(
            metric_name="line_count",
            erp_value=100,
            financeops_value=100,
            variance=Decimal("0"),
            variance_pct=Decimal("0"),
            status="MATCHED",
            threshold_breached=False,
        )
    ]
    assert service._classify_severity(metrics) == DriftSeverity.NONE


def test_drift_severity_minor_for_sub_one_percent_variance() -> None:
    service = _service()
    metrics = [
        DriftMetric(
            metric_name="total_debits",
            erp_value=Decimal("1000"),
            financeops_value=Decimal("995"),
            variance=Decimal("5"),
            variance_pct=Decimal("0.5"),
            status="VARIANCE",
            threshold_breached=False,
        )
    ]
    assert service._classify_severity(metrics) == DriftSeverity.MINOR


def test_drift_severity_significant_for_one_to_five_percent_variance() -> None:
    service = _service()
    metrics = [
        DriftMetric(
            metric_name="total_credits",
            erp_value=Decimal("1000"),
            financeops_value=Decimal("980"),
            variance=Decimal("20"),
            variance_pct=Decimal("2.0"),
            status="VARIANCE",
            threshold_breached=True,
        )
    ]
    assert service._classify_severity(metrics) == DriftSeverity.SIGNIFICANT


def test_drift_severity_critical_for_structural_mismatch() -> None:
    service = _service()
    metrics = [
        DriftMetric(
            metric_name="row_set",
            erp_value=None,
            financeops_value=None,
            variance=None,
            variance_pct=None,
            status="STRUCTURAL_MISMATCH",
            threshold_breached=True,
        )
    ]
    assert service._classify_severity(metrics) == DriftSeverity.CRITICAL
