from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass(frozen=True)
class SourceVersionTokenInput:
    source_id: uuid.UUID
    structure_hash: str
    header_hash: str
    row_signature_hash: str
    source_detection_summary_json: dict[str, Any]


@dataclass(frozen=True)
class RunTokenInput:
    source_id: uuid.UUID
    source_version_id: uuid.UUID
    mapping_version_token: str
    run_type: str
    reporting_period: date
    source_file_hash: str
    run_status: str
