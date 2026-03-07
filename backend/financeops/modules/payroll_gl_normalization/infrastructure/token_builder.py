from __future__ import annotations

from financeops.modules.payroll_gl_normalization.domain.value_objects import (
    RunTokenInput,
    SourceVersionTokenInput,
)
from financeops.utils.determinism import canonical_json_dumps, sha256_hex_text


def build_source_version_token(payload: SourceVersionTokenInput) -> str:
    value = {
        "source_id": str(payload.source_id),
        "structure_hash": payload.structure_hash,
        "header_hash": payload.header_hash,
        "row_signature_hash": payload.row_signature_hash,
        "source_detection_summary_json": payload.source_detection_summary_json,
    }
    return sha256_hex_text(canonical_json_dumps(value))


def build_run_token(payload: RunTokenInput) -> str:
    value = {
        "source_id": str(payload.source_id),
        "source_version_id": str(payload.source_version_id),
        "mapping_version_token": payload.mapping_version_token,
        "run_type": payload.run_type,
        "reporting_period": payload.reporting_period.isoformat(),
        "source_file_hash": payload.source_file_hash,
        "run_status": payload.run_status,
    }
    return sha256_hex_text(canonical_json_dumps(value))
