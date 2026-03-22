from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

from financeops.core.exceptions import ValidationError
from financeops.services.consolidation.entity_loader import EntitySnapshotMapping
from financeops.services.consolidation.fx_impact_calculator import quantize_persisted_amount
from financeops.services.consolidation.ic_matcher import IntercompanyToleranceConfig
from financeops.utils.determinism import canonical_json_dumps, sha256_hex_text

DEFAULT_AMOUNT_TOLERANCE_PARENT = Decimal("0.010000")
DEFAULT_FX_EXPLAINED_TOLERANCE_PARENT = Decimal("0.500000")
DEFAULT_TIMING_TOLERANCE_DAYS = 3
TERMINAL_EVENT_TYPES = {"completed", "completed_with_unexplained", "failed"}


@dataclass(frozen=True)
class RunCreateResult:
    run_id: UUID
    workflow_id: str
    request_signature: str
    status: str
    created_new: bool


@dataclass(frozen=True)
class ExportPayload:
    workbook_bytes: bytes
    checksum: str


def resolved_tolerance(
    *,
    amount_tolerance_parent: Decimal | None,
    fx_explained_tolerance_parent: Decimal | None,
    timing_tolerance_days: int | None,
) -> dict[str, Any]:
    amount = amount_tolerance_parent or DEFAULT_AMOUNT_TOLERANCE_PARENT
    fx_tol = fx_explained_tolerance_parent or DEFAULT_FX_EXPLAINED_TOLERANCE_PARENT
    timing_days = timing_tolerance_days or DEFAULT_TIMING_TOLERANCE_DAYS
    if amount <= Decimal("0") or fx_tol <= Decimal("0") or timing_days <= 0:
        raise ValidationError("Resolved tolerances must be positive")
    return {
        "amount_tolerance_parent": str(quantize_persisted_amount(amount)),
        "fx_explained_tolerance_parent": str(quantize_persisted_amount(fx_tol)),
        "timing_tolerance_days": int(timing_days),
    }


def sorted_mapping_payload(mappings: list[EntitySnapshotMapping]) -> list[dict[str, str]]:
    return [
        {"entity_id": str(item.entity_id), "snapshot_id": str(item.snapshot_id)}
        for item in sorted(mappings, key=lambda row: (str(row.entity_id), str(row.snapshot_id)))
    ]


def request_signature_payload(
    *,
    period_year: int,
    period_month: int,
    parent_currency: str,
    rate_mode: str,
    mappings: list[EntitySnapshotMapping],
    tolerance_payload: dict[str, Any],
) -> dict[str, Any]:
    return {
        "period_year": period_year,
        "period_month": period_month,
        "parent_currency": parent_currency,
        "rate_mode": rate_mode,
        "entity_snapshots": sorted_mapping_payload(mappings),
        "tolerances": tolerance_payload,
    }


def build_request_signature(payload: dict[str, Any]) -> str:
    return sha256_hex_text(canonical_json_dumps(payload))


def config_tolerance(configuration_json: dict[str, Any]) -> IntercompanyToleranceConfig:
    tolerances = configuration_json.get("tolerances", {})
    return IntercompanyToleranceConfig(
        amount_tolerance_parent=Decimal(str(tolerances["amount_tolerance_parent"])),
        fx_explained_tolerance_parent=Decimal(str(tolerances["fx_explained_tolerance_parent"])),
        timing_tolerance_days=int(tolerances["timing_tolerance_days"]),
    )


def config_mappings(configuration_json: dict[str, Any]) -> list[EntitySnapshotMapping]:
    raw_rows = configuration_json.get("entity_snapshots", [])
    return [
        EntitySnapshotMapping(
            entity_id=UUID(str(row["entity_id"])),
            snapshot_id=UUID(str(row["snapshot_id"])),
        )
        for row in raw_rows
    ]

