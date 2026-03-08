from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from financeops.modules.equity_engine.application.rollforward_service import RollforwardService
from financeops.modules.equity_engine.domain.invariants import q6
from financeops.modules.equity_engine.domain.value_objects import EquityRunTokenInput
from financeops.modules.equity_engine.infrastructure.token_builder import build_equity_run_token


def test_equity_run_token_is_stable_for_same_inputs() -> None:
    tenant_id = uuid.uuid4()
    org_id = uuid.uuid4()
    payload = EquityRunTokenInput(
        tenant_id=tenant_id,
        organisation_id=org_id,
        reporting_period=date(2026, 1, 31),
        statement_definition_version_token="s1",
        line_definition_version_token="l1",
        rollforward_rule_version_token="r1",
        source_mapping_version_token="m1",
        consolidation_run_ref_nullable="00000000-0000-0000-0000-000000000001",
        fx_translation_run_ref_nullable="00000000-0000-0000-0000-000000000002",
        ownership_consolidation_run_ref_nullable="00000000-0000-0000-0000-000000000003",
        run_status="created",
    )
    assert build_equity_run_token(payload) == build_equity_run_token(payload)


def test_retained_earnings_bridge_arithmetic_is_correct() -> None:
    service = RollforwardService()
    movement = service.retained_earnings_movement(
        consolidation_values={"net_income": Decimal("42.500000")},
        rule=type("Rule", (), {"source_selector_json": {"pnl_metric_codes": ["net_income"]}})(),
    )
    assert movement == Decimal("42.500000")


def test_cta_derivation_is_correct() -> None:
    service = RollforwardService()
    movement = service.cta_movement(
        fx_rows=[
            {
                "metric_code": "net_income",
                "translated_value": Decimal("45.000000"),
                "source_value": Decimal("40.000000"),
            }
        ],
        rule=type("Rule", (), {"source_selector_json": {"metric_codes": ["net_income"]}})(),
    )
    assert movement == Decimal("5.000000")


def test_ownership_attribution_sum_is_correct() -> None:
    service = RollforwardService()
    value = service.ownership_amount(
        ownership_values={"a": Decimal("10.000000"), "b": Decimal("5.500000")},
        metric_codes=["a", "b"],
    )
    assert value == Decimal("15.500000")


def test_q6_enforces_deterministic_rounding() -> None:
    assert q6(Decimal("1.23456749")) == Decimal("1.234567")
    assert q6(Decimal("1.23456750")) == Decimal("1.234568")
