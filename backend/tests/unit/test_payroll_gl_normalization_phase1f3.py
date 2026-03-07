from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from financeops.modules.payroll_gl_normalization.application.gl_normalization_service import (
    GlNormalizationService,
)
from financeops.modules.payroll_gl_normalization.application.mapping_service import (
    MappingService,
)
from financeops.modules.payroll_gl_normalization.application.validation_service import (
    ValidationService,
)
from financeops.modules.payroll_gl_normalization.domain.entities import PayrollNormalizedEntry
from financeops.modules.payroll_gl_normalization.domain.enums import LineStatus
from financeops.modules.payroll_gl_normalization.domain.value_objects import (
    RunTokenInput,
    SourceVersionTokenInput,
)
from financeops.modules.payroll_gl_normalization.infrastructure.token_builder import (
    build_run_token,
    build_source_version_token,
)


def test_source_version_token_generation_is_deterministic() -> None:
    payload = SourceVersionTokenInput(
        source_id=uuid.uuid4(),
        structure_hash="a" * 64,
        header_hash="b" * 64,
        row_signature_hash="c" * 64,
        source_detection_summary_json={"headers": ["Employee ID", "Gross Pay"]},
    )
    first = build_source_version_token(payload)
    second = build_source_version_token(payload)
    assert first == second


def test_run_token_generation_is_deterministic() -> None:
    payload = RunTokenInput(
        source_id=uuid.uuid4(),
        source_version_id=uuid.uuid4(),
        mapping_version_token="a" * 64,
        run_type="payroll_normalization",
        reporting_period=date(2026, 1, 31),
        source_file_hash="b" * 64,
        run_status="pending",
    )
    first = build_run_token(payload)
    second = build_run_token(payload)
    assert first == second


def test_gl_signed_amount_derivation_is_deterministic() -> None:
    service = GlNormalizationService()
    lines, exceptions = service.normalize(
        headers=["Account Code", "Debit", "Credit", "Currency", "Posting Date"],
        rows=[["4000", "100", "20", "USD", "2026-01-31"]],
        mappings=[
            {
                "mapping_type": "gl_dimension",
                "source_field_name": "Account Code",
                "canonical_field_name": "account_code",
            },
            {
                "mapping_type": "gl_metric",
                "source_field_name": "Debit",
                "canonical_field_name": "debit_amount",
            },
            {
                "mapping_type": "gl_metric",
                "source_field_name": "Credit",
                "canonical_field_name": "credit_amount",
            },
            {
                "mapping_type": "gl_dimension",
                "source_field_name": "Currency",
                "canonical_field_name": "currency_code",
            },
            {
                "mapping_type": "gl_dimension",
                "source_field_name": "Posting Date",
                "canonical_field_name": "posting_date",
            },
        ],
        reporting_period=date(2026, 1, 31),
    )
    assert len(lines) == 1
    assert lines[0].signed_amount == Decimal("80.000000")
    assert exceptions == []


def test_mapping_service_proposals_are_stable() -> None:
    mapping = MappingService()
    headers = ["Employee ID", "Employee Name", "Gross Pay", "Currency"]
    first = mapping.propose_mappings(source_family="payroll", headers=headers)
    second = mapping.propose_mappings(source_family="payroll", headers=headers)
    assert first == second
    assert mapping.mapping_version_token(first) == mapping.mapping_version_token(second)


def test_validation_duplicate_employee_metric_is_flagged() -> None:
    validation = ValidationService()
    lines = [
        PayrollNormalizedEntry(
            row_no=1,
            employee_code="E001",
            employee_name="Alice",
            payroll_period=date(2026, 1, 31),
            legal_entity="HQ",
            department="Ops",
            cost_center="CC1",
            business_unit="BU1",
            location="NY",
            grade=None,
            designation=None,
            currency_code="USD",
            canonical_metric_code="gross_pay",
            amount_value=Decimal("1000"),
            source_row_ref="row:1",
            source_column_ref="Gross Pay",
            normalization_status=LineStatus.VALID,
        ),
        PayrollNormalizedEntry(
            row_no=2,
            employee_code="E001",
            employee_name="Alice",
            payroll_period=date(2026, 1, 31),
            legal_entity="HQ",
            department="Ops",
            cost_center="CC1",
            business_unit="BU1",
            location="NY",
            grade=None,
            designation=None,
            currency_code="USD",
            canonical_metric_code="gross_pay",
            amount_value=Decimal("1000"),
            source_row_ref="row:2",
            source_column_ref="Gross Pay",
            normalization_status=LineStatus.VALID,
        ),
    ]
    exceptions = validation.validate_payroll_lines(lines=lines)
    assert len(exceptions) == 1
    assert exceptions[0].exception_code == "DUPLICATE_EMPLOYEE_PERIOD"
