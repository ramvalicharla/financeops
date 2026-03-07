from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import ValidationError
from financeops.services.consolidation.entity_loader import (
    LoadedEntitySnapshot,
    LoadedSnapshotHeader,
    LoadedSnapshotLine,
)
from financeops.services.consolidation.fx_application import (
    apply_fx_to_snapshots,
    ensure_locked_rates_available,
)
from financeops.services.fx.selector import SelectedRateDecision


def _uuid(value: str) -> UUID:
    return UUID(value)


def _bundle(
    *,
    entity_id: UUID,
    entity_currency: str,
    line_rows: list[LoadedSnapshotLine],
) -> LoadedEntitySnapshot:
    return LoadedEntitySnapshot(
        header=LoadedSnapshotHeader(
            snapshot_id=_uuid("90000000-0000-0000-0000-000000000001"),
            entity_id=entity_id,
            period_year=2026,
            period_month=3,
            snapshot_type="normalized_pnl_v1",
            entity_currency=entity_currency,
            produced_by_module="phase1b",
            source_artifact_reference="ref",
        ),
        lines=line_rows,
    )


@pytest.mark.asyncio
async def test_apply_fx_month_end_locked_uses_locked_manual_rate(async_session: AsyncSession, test_tenant) -> None:
    bundle = _bundle(
        entity_id=_uuid("00000000-0000-0000-0000-000000000010"),
        entity_currency="EUR",
        line_rows=[
            LoadedSnapshotLine(
                snapshot_line_id=_uuid("91000000-0000-0000-0000-000000000001"),
                snapshot_id=_uuid("90000000-0000-0000-0000-000000000001"),
                account_code="4000",
                local_amount=Decimal("100.000000"),
                currency="EUR",
                ic_reference=None,
                counterparty_entity=None,
                transaction_date=None,
                ic_account_class=None,
            )
        ],
    )

    with patch(
        "financeops.services.consolidation.fx_application.list_manual_monthly_rates",
        new=AsyncMock(
            return_value=[
                SimpleNamespace(rate=Decimal("1.100000"), is_month_end_locked=True),
            ]
        ),
    ):
        rows = await apply_fx_to_snapshots(
            async_session,
            tenant_id=test_tenant.id,
            period_year=2026,
            period_month=3,
            parent_currency="USD",
            rate_mode="month_end_locked",
            bundles=[bundle],
        )
    assert len(rows) == 1
    assert rows[0].fx_rate_used == Decimal("1.100000")
    assert rows[0].expected_rate == Decimal("1.100000")
    assert rows[0].parent_amount == Decimal("110.000000")


@pytest.mark.asyncio
async def test_apply_fx_daily_uses_selected_rate_and_same_currency_shortcut(
    async_session: AsyncSession,
    test_tenant,
) -> None:
    entity_id = _uuid("00000000-0000-0000-0000-000000000020")
    bundle = _bundle(
        entity_id=entity_id,
        entity_currency="EUR",
        line_rows=[
            LoadedSnapshotLine(
                snapshot_line_id=_uuid("92000000-0000-0000-0000-000000000001"),
                snapshot_id=_uuid("90000000-0000-0000-0000-000000000001"),
                account_code="4100",
                local_amount=Decimal("10.000000"),
                currency="EUR",
                ic_reference=None,
                counterparty_entity=None,
                transaction_date=date(2026, 3, 15),
                ic_account_class=None,
            ),
            LoadedSnapshotLine(
                snapshot_line_id=_uuid("92000000-0000-0000-0000-000000000002"),
                snapshot_id=_uuid("90000000-0000-0000-0000-000000000001"),
                account_code="4200",
                local_amount=Decimal("5.000000"),
                currency="USD",
                ic_reference=None,
                counterparty_entity=None,
                transaction_date=date(2026, 3, 15),
                ic_account_class=None,
            ),
        ],
    )

    async def _resolve_selected_rate(*args, **kwargs):  # type: ignore[no-untyped-def]
        as_of_date = kwargs["as_of_date"]
        if as_of_date.day == 15:
            rate = Decimal("1.250000")
        else:
            rate = Decimal("1.200000")
        return SelectedRateDecision(
            selected_rate=rate,
            selected_source="provider_consensus",
            selection_method="median",
            degraded=False,
        )

    with patch(
        "financeops.services.consolidation.fx_application.list_manual_monthly_rates",
        new=AsyncMock(return_value=[]),
    ), patch(
        "financeops.services.consolidation.fx_application.resolve_selected_rate",
        new=AsyncMock(side_effect=_resolve_selected_rate),
    ):
        rows = await apply_fx_to_snapshots(
            async_session,
            tenant_id=test_tenant.id,
            period_year=2026,
            period_month=3,
            parent_currency="USD",
            rate_mode="daily",
            bundles=[bundle],
        )

    by_account = {row.account_code: row for row in rows}
    assert by_account["4100"].fx_rate_used == Decimal("1.250000")
    assert by_account["4100"].parent_amount == Decimal("12.500000")
    assert by_account["4200"].fx_rate_used == Decimal("1.000000")
    assert by_account["4200"].parent_amount == Decimal("5.000000")


@pytest.mark.asyncio
async def test_ensure_locked_rates_available_fails_without_month_end_lock(
    async_session: AsyncSession,
    test_tenant,
) -> None:
    with patch(
        "financeops.services.consolidation.fx_application.list_manual_monthly_rates",
        new=AsyncMock(return_value=[SimpleNamespace(rate=Decimal("1.100000"), is_month_end_locked=False)]),
    ):
        with pytest.raises(ValidationError):
            await ensure_locked_rates_available(
                async_session,
                tenant_id=test_tenant.id,
                period_year=2026,
                period_month=3,
                entity_currencies={"EUR"},
                parent_currency="USD",
            )
