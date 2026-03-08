from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest

from financeops.modules.cash_flow_engine.application.bridge_service import BridgeService
from financeops.modules.cash_flow_engine.application.mapping_service import MappingService
from financeops.modules.cash_flow_engine.domain.invariants import q6
from financeops.modules.cash_flow_engine.domain.value_objects import CashFlowRunTokenInput
from financeops.modules.cash_flow_engine.infrastructure.token_builder import (
    build_cash_flow_run_token,
)


def test_cash_flow_run_token_is_stable_for_same_inputs() -> None:
    tenant_id = uuid.uuid4()
    org_id = uuid.uuid4()
    payload = CashFlowRunTokenInput(
        tenant_id=tenant_id,
        organisation_id=org_id,
        reporting_period=date(2026, 1, 31),
        statement_definition_version_token="s1",
        line_mapping_version_token="m1",
        bridge_rule_version_token="b1",
        source_consolidation_run_ref="00000000-0000-0000-0000-000000000001",
        source_fx_translation_run_ref_nullable=None,
        source_ownership_consolidation_run_ref_nullable=None,
        run_status="created",
    )
    assert build_cash_flow_run_token(payload) == build_cash_flow_run_token(payload)


def test_indirect_bridge_arithmetic_is_deterministic() -> None:
    service = BridgeService()
    derived = service.compute_derived_values(
        base_line_values={
            "net_income": Decimal("100.000000"),
            "depreciation": Decimal("20.000000"),
            "working_capital_change": Decimal("15.000000"),
        },
        bridge_logic_json={
            "derived_lines": [
                {
                    "line_code": "cash_from_operations",
                    "components": [
                        {"line_code": "net_income", "multiplier": "1"},
                        {"line_code": "depreciation", "multiplier": "1"},
                        {"line_code": "working_capital_change", "multiplier": "-1"},
                    ],
                }
            ]
        },
    )
    assert derived["cash_from_operations"] == Decimal("105.000000")


def test_line_mapping_applies_sign_multiplier() -> None:
    mapping = MappingService()
    assert mapping.compute_line_value(
        source_value=Decimal("10.000000"),
        sign_multiplier=Decimal("-1.000000"),
    ) == Decimal("-10.000000")


def test_mapping_applicability_supports_ownership_and_fx_paths() -> None:
    mapping = MappingService()
    assert (
        mapping.mapping_applicable(
            ownership_applicability="ownership_only",
            fx_applicability="any",
            has_ownership_source=True,
            has_fx_source=False,
        )
        is True
    )
    assert (
        mapping.mapping_applicable(
            ownership_applicability="non_ownership_only",
            fx_applicability="fx_only",
            has_ownership_source=False,
            has_fx_source=True,
        )
        is True
    )


def test_q6_enforces_deterministic_rounding() -> None:
    assert q6(Decimal("1.23456749")) == Decimal("1.234567")
    assert q6(Decimal("1.23456750")) == Decimal("1.234568")


@pytest.mark.asyncio
async def test_missing_source_metrics_fail_closed() -> None:
    from financeops.modules.cash_flow_engine.application.validation_service import (
        ValidationService,
    )

    with pytest.raises(ValueError, match="Missing source metrics"):
        ValidationService().validate_line_mappings_have_sources(
            missing_source_metrics=["revenue", "revenue", "depreciation"]
        )
