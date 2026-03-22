from __future__ import annotations

from financeops.modules.mis_manager.domain.value_objects import (
    SnapshotTokenInput,
    VersionTokenInput,
)
from financeops.shared_kernel.tokens import build_token


def build_version_token(payload: VersionTokenInput) -> str:
    value = {
        "template_id": str(payload.template_id),
        "structure_hash": payload.structure_hash,
        "header_hash": payload.header_hash,
        "row_signature_hash": payload.row_signature_hash,
        "column_signature_hash": payload.column_signature_hash,
        "detection_summary_json": payload.detection_summary_json,
    }
    return build_token(value)


def build_snapshot_token(payload: SnapshotTokenInput) -> str:
    value = {
        "source_file_hash": payload.source_file_hash,
        "sheet_name": payload.sheet_name,
        "structure_hash": payload.structure_hash,
        "mapping_set_identity": payload.mapping_set_identity,
        "validation_rule_set_identity": payload.validation_rule_set_identity,
        "reporting_period": payload.reporting_period.isoformat(),
        "template_version_id": str(payload.template_version_id),
        "status": payload.status,
    }
    return build_token(value)
