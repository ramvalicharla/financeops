from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID

from financeops.services.fixed_assets.journal_builder import build_far_journal_preview


def _uuid(value: str) -> UUID:
    return UUID(value)


def test_far_journal_builder_creates_one_of_source_links() -> None:
    schedule = SimpleNamespace(
        id=_uuid("00000000-0000-0000-0000-00000000f601"),
        asset_id=_uuid("00000000-0000-0000-0000-00000000f602"),
        depreciation_date=date(2026, 1, 31),
        period_seq=1,
        schedule_version_token="tok-root",
        depreciation_amount_reporting_currency=Decimal("100.000000"),
        source_acquisition_reference="SRC-FAR-JRN-1",
        parent_reference_id=_uuid("00000000-0000-0000-0000-00000000f603"),
        source_reference_id=_uuid("00000000-0000-0000-0000-00000000f604"),
    )
    impairment = SimpleNamespace(
        id=_uuid("00000000-0000-0000-0000-00000000f605"),
        asset_id=schedule.asset_id,
        impairment_date=date(2026, 2, 15),
        impairment_amount_reporting_currency=Decimal("25.000000"),
        created_at=datetime.now(UTC),
        source_acquisition_reference=schedule.source_acquisition_reference,
        parent_reference_id=schedule.parent_reference_id,
        source_reference_id=schedule.source_reference_id,
    )
    disposal = SimpleNamespace(
        id=_uuid("00000000-0000-0000-0000-00000000f606"),
        asset_id=schedule.asset_id,
        disposal_date=date(2026, 3, 1),
        gain_loss_reporting_currency=Decimal("-5.000000"),
        created_at=datetime.now(UTC),
        source_acquisition_reference=schedule.source_acquisition_reference,
        parent_reference_id=schedule.parent_reference_id,
        source_reference_id=schedule.source_reference_id,
    )

    rows = build_far_journal_preview(
        run_id=_uuid("00000000-0000-0000-0000-00000000f607"),
        schedule_rows=[schedule],
        impairment_rows=[impairment],
        disposal_rows=[disposal],
    )

    assert len(rows) == 3
    for row in rows:
        populated = [row.depreciation_schedule_id, row.impairment_id, row.disposal_id]
        assert len([item for item in populated if item is not None]) == 1
    assert rows[0].journal_reference.startswith("FAR-")
