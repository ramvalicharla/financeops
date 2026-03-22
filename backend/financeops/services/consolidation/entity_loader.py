from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import ValidationError
from financeops.db.models.consolidation import (
    NormalizedFinancialSnapshot,
    NormalizedFinancialSnapshotLine,
)
from financeops.services.fx.normalization import normalize_currency_code

SNAPSHOT_TYPE_NORMALIZED_PNL_V1 = "normalized_pnl_v1"


@dataclass(frozen=True)
class EntitySnapshotMapping:
    entity_id: UUID
    snapshot_id: UUID


@dataclass(frozen=True)
class LoadedSnapshotHeader:
    snapshot_id: UUID
    entity_id: UUID
    period_year: int
    period_month: int
    snapshot_type: str
    entity_currency: str
    produced_by_module: str
    source_artifact_reference: str


@dataclass(frozen=True)
class LoadedSnapshotLine:
    snapshot_line_id: UUID
    snapshot_id: UUID
    account_code: str
    local_amount: Decimal
    currency: str
    ic_reference: str | None
    counterparty_entity: UUID | None
    transaction_date: date | None
    ic_account_class: str | None


@dataclass(frozen=True)
class LoadedEntitySnapshot:
    header: LoadedSnapshotHeader
    lines: list[LoadedSnapshotLine]


def _ensure_unique_mappings(mappings: list[EntitySnapshotMapping]) -> None:
    entity_ids = [item.entity_id for item in mappings]
    snapshot_ids = [item.snapshot_id for item in mappings]
    if len(entity_ids) != len(set(entity_ids)):
        raise ValidationError("Duplicate entity_id values in entity-to-snapshot mapping")
    if len(snapshot_ids) != len(set(snapshot_ids)):
        raise ValidationError("Duplicate snapshot_id values in entity-to-snapshot mapping")


async def load_entity_snapshots(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    period_year: int,
    period_month: int,
    mappings: list[EntitySnapshotMapping],
) -> list[LoadedEntitySnapshot]:
    if not mappings:
        raise ValidationError("At least one entity snapshot mapping is required")
    _ensure_unique_mappings(mappings)

    snapshot_ids = [item.snapshot_id for item in mappings]
    headers_result = await session.execute(
        select(NormalizedFinancialSnapshot).where(
            NormalizedFinancialSnapshot.tenant_id == tenant_id,
            NormalizedFinancialSnapshot.id.in_(snapshot_ids),
        )
    )
    headers = list(headers_result.scalars().all())
    headers_by_id = {row.id: row for row in headers}
    if len(headers_by_id) != len(snapshot_ids):
        raise ValidationError("One or more source snapshots were not found for this tenant")

    for mapping in mappings:
        header = headers_by_id[mapping.snapshot_id]
        if header.entity_id != mapping.entity_id:
            raise ValidationError("Snapshot entity does not match submitted entity mapping")
        if header.period_year != period_year or header.period_month != period_month:
            raise ValidationError("Snapshot period does not match consolidation period")
        if header.snapshot_type != SNAPSHOT_TYPE_NORMALIZED_PNL_V1:
            raise ValidationError("Snapshot type must be normalized_pnl_v1")

    lines_result = await session.execute(
        select(NormalizedFinancialSnapshotLine)
        .where(
            NormalizedFinancialSnapshotLine.tenant_id == tenant_id,
            NormalizedFinancialSnapshotLine.snapshot_id.in_(snapshot_ids),
        )
        .order_by(
            NormalizedFinancialSnapshotLine.snapshot_id,
            NormalizedFinancialSnapshotLine.account_code,
            NormalizedFinancialSnapshotLine.id,
        )
    )
    lines = list(lines_result.scalars().all())
    lines_by_snapshot: dict[UUID, list[LoadedSnapshotLine]] = {}
    for row in lines:
        payload = LoadedSnapshotLine(
            snapshot_line_id=row.id,
            snapshot_id=row.snapshot_id,
            account_code=row.account_code,
            local_amount=row.local_amount,
            currency=normalize_currency_code(row.currency),
            ic_reference=row.ic_reference,
            counterparty_entity=row.counterparty_entity,
            transaction_date=row.transaction_date,
            ic_account_class=row.ic_account_class,
        )
        lines_by_snapshot.setdefault(row.snapshot_id, []).append(payload)

    ordered_mappings = sorted(
        mappings,
        key=lambda item: (str(item.entity_id), str(item.snapshot_id)),
    )
    bundles: list[LoadedEntitySnapshot] = []
    for mapping in ordered_mappings:
        header_row = headers_by_id[mapping.snapshot_id]
        header = LoadedSnapshotHeader(
            snapshot_id=header_row.id,
            entity_id=header_row.entity_id,
            period_year=header_row.period_year,
            period_month=header_row.period_month,
            snapshot_type=header_row.snapshot_type,
            entity_currency=normalize_currency_code(header_row.entity_currency),
            produced_by_module=header_row.produced_by_module,
            source_artifact_reference=header_row.source_artifact_reference,
        )
        bundle_lines = sorted(
            lines_by_snapshot.get(mapping.snapshot_id, []),
            key=lambda item: (item.account_code, str(item.snapshot_line_id)),
        )
        bundles.append(LoadedEntitySnapshot(header=header, lines=bundle_lines))
    return bundles

