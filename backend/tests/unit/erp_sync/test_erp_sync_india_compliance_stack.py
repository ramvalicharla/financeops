from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from financeops.modules.erp_sync.application.normalization_service import NormalizationService
from financeops.modules.erp_sync.application.validation_service import ValidationService
from financeops.modules.erp_sync.domain.enums import DatasetType, SyncRunStatus


@pytest.mark.parametrize(
    ("dataset_type", "raw_payload"),
    [
        (
            DatasetType.GST_RETURN_GSTR9,
            {
                "financial_year": "2024-25",
                "gstin": "27ABCDE1234F1Z5",
                "total_outward_supplies": Decimal("1000.00"),
                "total_inward_supplies": Decimal("700.00"),
                "total_itc_availed": Decimal("95.00"),
                "total_tax_paid": Decimal("150.00"),
                "filing_status": "FILED",
                "filing_date": date(2025, 12, 31),
            },
        ),
        (
            DatasetType.GST_RETURN_GSTR9C,
            {
                "financial_year": "2024-25",
                "gstin": "27ABCDE1234F1Z5",
                "turnover_as_per_books": Decimal("1200.00"),
                "turnover_as_per_gst": Decimal("1190.00"),
                "variance": Decimal("10.00"),
                "reason_for_variance": "year-end adjustments",
                "auditor_certified": True,
                "filing_status": "FILED",
            },
        ),
        (
            DatasetType.FORM_26AS,
            {
                "financial_year": "2024-25",
                "pan_number": "XXXXXX1234",
                "assessment_year": "2025-26",
                "total_tds_as_per_26as": Decimal("100.00"),
                "pii_masked": True,
                "records": [
                    {
                        "deductor_tan": "MUMA12345A",
                        "deductor_name": "ACME LTD",
                        "tds_section": "194C",
                        "payment_date": date(2025, 3, 31),
                        "amount_paid": Decimal("1000.00"),
                        "tds_deducted": Decimal("100.00"),
                        "tds_deposited": Decimal("100.00"),
                        "certificate_number": "CERT-001",
                        "remarks": None,
                        "pii_masked": True,
                    }
                ],
            },
        ),
        (
            DatasetType.AIS_REGISTER,
            {
                "financial_year": "2024-25",
                "total_income_reported": Decimal("2500.00"),
                "total_tds_tcs": Decimal("250.00"),
                "pii_masked": True,
                "records": [
                    {
                        "transaction_type": "salary",
                        "source": "CBDT",
                        "amount": Decimal("2500.00"),
                        "tds_tcs": Decimal("250.00"),
                        "financial_year": "2024-25",
                        "pii_masked": True,
                    }
                ],
            },
        ),
    ],
)
def test_india_compliance_normalization_and_validation_flow(
    dataset_type: DatasetType,
    raw_payload: dict[str, object],
) -> None:
    normalization = NormalizationService()
    validation = ValidationService()

    canonical_payload = normalization.normalize(
        dataset_type=dataset_type,
        raw_payload=raw_payload,
        entity_id="entity_001",
        currency="INR",
    )

    validation_result = validation.validate(
        dataset_type=dataset_type.value,
        canonical_payload=canonical_payload,
        raw_payload={"payload_hash": "hash_1"},
        context={
            "entity_id": "entity_001",
            "currency_consistency_pass": True,
            "expected_raw_snapshot_hash": "hash_1",
        },
    )

    assert isinstance(canonical_payload.get("dataset_token"), str)
    assert validation_result["passed"] is True
    assert validation_result["run_status"] == SyncRunStatus.COMPLETED.value
    assert len(validation_result["categories"]) == 20
