from __future__ import annotations

from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import ValidationError
from financeops.db.models.consolidation import (
    NormalizedFinancialSnapshot,
    NormalizedFinancialSnapshotLine,
)
from financeops.services.audit_writer import AuditWriter
from financeops.services.consolidation.entity_loader import (
    EntitySnapshotMapping,
    load_entity_snapshots,
)


def _uuid(value: str) -> UUID:
    return UUID(value)


async def _seed_snapshot(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    entity_id: UUID,
    period_year: int,
    period_month: int,
    currency: str,
    source_ref: str,
) -> NormalizedFinancialSnapshot:
    return await AuditWriter.insert_financial_record(
        session,
        model_class=NormalizedFinancialSnapshot,
        tenant_id=tenant_id,
        record_data={
            "entity_id": str(entity_id),
            "period_year": period_year,
            "period_month": period_month,
            "snapshot_type": "normalized_pnl_v1",
            "entity_currency": currency,
            "source_artifact_reference": source_ref,
        },
        values={
            "entity_id": entity_id,
            "period_year": period_year,
            "period_month": period_month,
            "snapshot_type": "normalized_pnl_v1",
            "entity_currency": currency,
            "produced_by_module": "phase1b_fx",
            "source_artifact_reference": source_ref,
            "supersedes_snapshot_id": None,
            "correlation_id": "corr-snap",
        },
    )


async def _seed_snapshot_line(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    snapshot_id: UUID,
    account_code: str,
    amount: str,
) -> NormalizedFinancialSnapshotLine:
    return await AuditWriter.insert_financial_record(
        session,
        model_class=NormalizedFinancialSnapshotLine,
        tenant_id=tenant_id,
        record_data={
            "snapshot_id": str(snapshot_id),
            "account_code": account_code,
            "local_amount": amount,
            "currency": "USD",
        },
        values={
            "snapshot_id": snapshot_id,
            "account_code": account_code,
            "local_amount": Decimal(amount),
            "currency": "USD",
            "ic_reference": None,
            "counterparty_entity": None,
            "transaction_date": None,
            "ic_account_class": None,
            "correlation_id": "corr-line",
        },
    )


@pytest.mark.asyncio
async def test_load_entity_snapshots_validates_and_orders_deterministically(
    async_session: AsyncSession,
    test_tenant,
) -> None:
    entity_a = _uuid("00000000-0000-0000-0000-000000000111")
    entity_b = _uuid("00000000-0000-0000-0000-000000000222")
    snap_a = await _seed_snapshot(
        async_session,
        tenant_id=test_tenant.id,
        entity_id=entity_a,
        period_year=2026,
        period_month=3,
        currency="USD",
        source_ref="src-a",
    )
    snap_b = await _seed_snapshot(
        async_session,
        tenant_id=test_tenant.id,
        entity_id=entity_b,
        period_year=2026,
        period_month=3,
        currency="USD",
        source_ref="src-b",
    )
    await _seed_snapshot_line(
        async_session,
        tenant_id=test_tenant.id,
        snapshot_id=snap_a.id,
        account_code="5000",
        amount="10.000000",
    )
    await _seed_snapshot_line(
        async_session,
        tenant_id=test_tenant.id,
        snapshot_id=snap_a.id,
        account_code="4000",
        amount="20.000000",
    )
    await _seed_snapshot_line(
        async_session,
        tenant_id=test_tenant.id,
        snapshot_id=snap_b.id,
        account_code="3000",
        amount="30.000000",
    )

    bundles = await load_entity_snapshots(
        async_session,
        tenant_id=test_tenant.id,
        period_year=2026,
        period_month=3,
        mappings=[
            EntitySnapshotMapping(entity_id=entity_b, snapshot_id=snap_b.id),
            EntitySnapshotMapping(entity_id=entity_a, snapshot_id=snap_a.id),
        ],
    )

    assert [str(row.header.entity_id) for row in bundles] == [str(entity_a), str(entity_b)]
    assert [row.account_code for row in bundles[0].lines] == ["4000", "5000"]


@pytest.mark.asyncio
async def test_load_entity_snapshots_rejects_period_mismatch(
    async_session: AsyncSession,
    test_tenant,
) -> None:
    entity_id = _uuid("00000000-0000-0000-0000-000000000333")
    snapshot = await _seed_snapshot(
        async_session,
        tenant_id=test_tenant.id,
        entity_id=entity_id,
        period_year=2025,
        period_month=12,
        currency="USD",
        source_ref="src-c",
    )

    with pytest.raises(ValidationError):
        await load_entity_snapshots(
            async_session,
            tenant_id=test_tenant.id,
            period_year=2026,
            period_month=3,
            mappings=[EntitySnapshotMapping(entity_id=entity_id, snapshot_id=snapshot.id)],
        )
