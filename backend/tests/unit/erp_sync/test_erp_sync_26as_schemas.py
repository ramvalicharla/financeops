from __future__ import annotations

from datetime import date
from decimal import Decimal

from financeops.modules.erp_sync.domain.canonical.form_26as_ais import (
    Canonical26ASEntry,
    CanonicalAISEntry,
    CanonicalAISRegister,
    CanonicalForm26AS,
)


def _visible_pan_chars(masked_pan: str) -> int:
    return len([ch for ch in masked_pan if ch.isalnum() and ch not in {"X", "x", "*"}])


def test_canonical_form26as_fields_masking_and_dataset_token() -> None:
    payload = CanonicalForm26AS(
        financial_year="2024-25",
        entity_id="entity_001",
        pan_number="XXXXXX1234",
        entries=[
            Canonical26ASEntry(
                deductor_tan="MUMA12345A",
                deductor_name="ACME LTD",
                tds_section="194C",
                payment_date=date(2025, 3, 31),
                amount_paid=Decimal("1000.00"),
                tds_deducted=Decimal("100.00"),
                tds_deposited=Decimal("100.00"),
                certificate_number="CERT-001",
                remarks=None,
                pii_masked=True,
            )
        ],
        total_tds_as_per_26as=Decimal("100.00"),
        assessment_year="2025-26",
        pii_masked=True,
        dataset_token="sha256:26as",
    )

    assert payload.pan_number is not None
    assert _visible_pan_chars(payload.pan_number) <= 4
    assert payload.pii_masked is True
    assert isinstance(payload.dataset_token, str)


def test_canonical_ais_register_fields_masking_and_dataset_token() -> None:
    payload = CanonicalAISRegister(
        financial_year="2024-25",
        entity_id="entity_001",
        entries=[
            CanonicalAISEntry(
                transaction_type="salary",
                source="CBDT",
                amount=Decimal("2500.00"),
                tds_tcs=Decimal("250.00"),
                financial_year="2024-25",
                pii_masked=True,
            )
        ],
        total_income_reported=Decimal("2500.00"),
        total_tds_tcs=Decimal("250.00"),
        pii_masked=True,
        dataset_token="sha256:ais",
    )

    assert payload.pii_masked is True
    assert payload.entries[0].pii_masked is True
    assert isinstance(payload.dataset_token, str)
