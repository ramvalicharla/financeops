from __future__ import annotations

from datetime import date
from decimal import Decimal

from financeops.modules.erp_sync.domain.canonical.gst_returns import CanonicalGSTR9C, CanonicalGSTR9Summary


def test_canonical_gstr9_summary_fields_and_dataset_token() -> None:
    row = CanonicalGSTR9Summary(
        financial_year="2024-25",
        entity_id="entity_001",
        gstin="27ABCDE1234F1Z5",
        total_outward_supplies=Decimal("1000.00"),
        total_inward_supplies=Decimal("700.00"),
        total_itc_availed=Decimal("95.00"),
        total_tax_paid=Decimal("150.00"),
        filing_status="FILED",
        filing_date=date(2025, 12, 31),
        dataset_token="sha256:gstr9",
    )

    assert isinstance(row.dataset_token, str)
    assert isinstance(row.total_outward_supplies, Decimal)
    assert isinstance(row.total_inward_supplies, Decimal)
    assert isinstance(row.total_itc_availed, Decimal)
    assert isinstance(row.total_tax_paid, Decimal)


def test_canonical_gstr9c_fields_and_dataset_token() -> None:
    row = CanonicalGSTR9C(
        financial_year="2024-25",
        entity_id="entity_001",
        gstin="27ABCDE1234F1Z5",
        turnover_as_per_books=Decimal("1200.00"),
        turnover_as_per_gst=Decimal("1190.00"),
        variance=Decimal("10.00"),
        reason_for_variance="year-end adjustments",
        auditor_certified=True,
        filing_status="FILED",
        dataset_token="sha256:gstr9c",
    )

    assert isinstance(row.dataset_token, str)
    assert isinstance(row.turnover_as_per_books, Decimal)
    assert isinstance(row.turnover_as_per_gst, Decimal)
    assert isinstance(row.variance, Decimal)
