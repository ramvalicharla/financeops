from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class SignatureBundle:
    header_hash: str
    row_signature_hash: str
    column_signature_hash: str
    section_signature_hash: str
    structure_hash: str


@dataclass(frozen=True)
class VersionTokenInput:
    template_id: UUID
    structure_hash: str
    header_hash: str
    row_signature_hash: str
    column_signature_hash: str
    detection_summary_json: dict[str, Any]


@dataclass(frozen=True)
class SnapshotTokenInput:
    source_file_hash: str
    sheet_name: str
    structure_hash: str
    mapping_set_identity: str
    validation_rule_set_identity: str
    reporting_period: date
    template_version_id: UUID
    status: str
