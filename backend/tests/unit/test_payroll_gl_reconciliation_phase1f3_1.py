from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from financeops.modules.payroll_gl_reconciliation.application.classification_service import (
    ClassificationService,
)
from financeops.modules.payroll_gl_reconciliation.application.matching_service import (
    MatchingService,
)
from financeops.modules.payroll_gl_reconciliation.domain.enums import (
    CoreDifferenceType,
    PayrollGlDifferenceType,
)
from financeops.modules.payroll_gl_reconciliation.domain.value_objects import (
    PayrollGlRunTokenInput,
)
from financeops.modules.payroll_gl_reconciliation.infrastructure.token_builder import (
    build_payroll_gl_run_token,
)


def _payroll_line(
    *,
    metric: str,
    amount: str,
    entity: str = "LE1",
    department: str = "Ops",
    cost_center: str = "CC1",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        row_no=1,
        employee_code="E001",
        canonical_metric_code=metric,
        amount_value=Decimal(amount),
        legal_entity=entity,
        department=department,
        cost_center=cost_center,
        currency_code="USD",
    )


def _gl_line(
    *,
    account_code: str,
    signed_amount: str,
    posting_date: date,
    entity: str = "LE1",
    department: str = "Ops",
    cost_center: str = "CC1",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        row_no=1,
        account_code=account_code,
        signed_amount=Decimal(signed_amount),
        legal_entity=entity,
        department=department,
        cost_center=cost_center,
        currency_code="USD",
        posting_date=posting_date,
    )


def _mapping(metric: str, account: str) -> SimpleNamespace:
    return SimpleNamespace(
        payroll_metric_code=metric,
        gl_account_selector_json={"account_codes": [account]},
        cost_center_rule_json={"mode": "strict"},
        department_rule_json={"mode": "strict"},
        entity_rule_json={"mode": "strict"},
    )


def test_run_token_is_deterministic() -> None:
    payload = PayrollGlRunTokenInput(
        tenant_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        organisation_id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
        payroll_run_id=uuid.UUID("33333333-3333-3333-3333-333333333333"),
        gl_run_id=uuid.UUID("44444444-4444-4444-4444-444444444444"),
        mapping_version_token="a" * 64,
        rule_version_token="b" * 64,
        reporting_period=date(2026, 1, 31),
    )
    first = build_payroll_gl_run_token(payload, status="created")
    second = build_payroll_gl_run_token(payload, status="created")
    assert first == second


def test_matching_service_exact_tie_generates_none_difference() -> None:
    service = MatchingService()
    lines = service.match(
        payroll_lines=[_payroll_line(metric="gross_pay", amount="1000")],
        gl_lines=[_gl_line(account_code="5000", signed_amount="1000", posting_date=date(2026, 1, 31))],
        mappings=[_mapping("gross_pay", "5000")],
        reporting_period=date(2026, 1, 31),
        materiality_config_json={"absolute_threshold": "10", "percentage_threshold": "0.25"},
        tolerance_json={"absolute_threshold": Decimal("1"), "percentage_threshold": Decimal("0.1")},
        max_timing_lag_days=5,
    )
    assert len(lines) == 1
    assert lines[0].core_difference_type == CoreDifferenceType.NONE


def test_matching_service_applies_timing_difference() -> None:
    service = MatchingService()
    lines = service.match(
        payroll_lines=[_payroll_line(metric="gross_pay", amount="1000")],
        gl_lines=[_gl_line(account_code="5000", signed_amount="900", posting_date=date(2026, 2, 2))],
        mappings=[_mapping("gross_pay", "5000")],
        reporting_period=date(2026, 1, 31),
        materiality_config_json={"absolute_threshold": "10", "percentage_threshold": "0.25"},
        tolerance_json={"absolute_threshold": Decimal("1"), "percentage_threshold": Decimal("0.1")},
        max_timing_lag_days=5,
    )
    assert len(lines) == 1
    assert lines[0].payroll_difference_type == PayrollGlDifferenceType.TIMING_DIFFERENCE


def test_classification_service_returns_exception_for_difference() -> None:
    classifier = ClassificationService()
    line = SimpleNamespace(
        line_key="k",
        core_difference_type=CoreDifferenceType.VALUE_MISMATCH,
        payroll_difference_type=PayrollGlDifferenceType.CLASSIFICATION_DIFFERENCE,
        materiality_flag=True,
        variance_value=Decimal("10"),
    )
    result = classifier.classify_line(line)
    assert result is not None
    assert result.exception_code == "PAYROLL_GL_CLASSIFICATION_DIFFERENCE"
    assert result.severity == "error"

