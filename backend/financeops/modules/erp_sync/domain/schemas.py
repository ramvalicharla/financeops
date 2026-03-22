from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field

from financeops.modules.erp_sync.domain.enums import ConnectorType, DatasetType


class SyncTokenPayload(BaseModel):
    tenant_id: str
    organisation_id: str
    entity_id: str
    dataset_type: DatasetType
    connector_type: ConnectorType
    connector_version: str
    source_system_instance_id: str
    sync_definition_id: str
    sync_definition_version: int
    period_resolution_hash: str
    extraction_scope_hash: str
    raw_snapshot_payload_hash: str
    mapping_version_token: str
    normalization_version: str
    pii_masking_enabled: bool
    data_residency_region: str


class DriftMetric(BaseModel):
    metric_name: str
    erp_value: Decimal | int | None = None
    financeops_value: Decimal | int | None = None
    variance: Decimal | None = None
    variance_pct: Decimal | None = None
    status: str
    threshold_breached: bool = False


class DriftReport(BaseModel):
    sync_run_id: str
    dataset_type: DatasetType
    period_label: str
    entity_id: str
    connector_type: ConnectorType
    metrics_checked: list[DriftMetric] = Field(default_factory=list)
    total_variances: int = 0
    drift_detected: bool = False
    drift_severity: str = "none"
    generated_at: str
