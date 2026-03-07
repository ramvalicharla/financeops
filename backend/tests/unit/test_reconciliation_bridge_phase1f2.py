from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from financeops.modules.reconciliation_bridge.application.matching_service import (
    MatchingService,
)
from financeops.modules.reconciliation_bridge.domain.value_objects import (
    SessionTokenInput,
)
from financeops.modules.reconciliation_bridge.infrastructure.token_builder import (
    build_session_token,
)


def test_reconciliation_session_token_is_deterministic() -> None:
    tenant_id = uuid.uuid4()
    payload = SessionTokenInput(
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        reconciliation_type="gl_vs_trial_balance",
        source_a_type="gl_entries",
        source_a_ref="gl_ref",
        source_b_type="trial_balance_rows",
        source_b_ref="tb_ref",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        matching_rule_version="recon_match_v1",
        tolerance_rule_version="recon_tolerance_v1",
        materiality_config_json={"absolute_threshold": "10"},
    )
    assert build_session_token(payload) == build_session_token(payload)


def test_reconciliation_variance_calculation_is_correct() -> None:
    service = MatchingService()
    rows = service.match_gl_vs_tb(
        source_a_rows=[
            {
                "account": "4000",
                "entity": "HQ",
                "currency": "USD",
                "period": "2026-01",
                "value": Decimal("1000"),
            }
        ],
        source_b_rows=[
            {
                "account": "4000",
                "entity": "HQ",
                "currency": "USD",
                "period": "2026-01",
                "value": Decimal("950"),
            }
        ],
        materiality_config_json={"absolute_threshold": "0"},
    )
    assert len(rows) == 1
    assert rows[0].variance_value == Decimal("50.000000")
    assert rows[0].variance_abs == Decimal("50.000000")


def test_reconciliation_materiality_flag_logic() -> None:
    service = MatchingService()
    rows = service.match_gl_vs_tb(
        source_a_rows=[
            {
                "account": "5000",
                "entity": "HQ",
                "currency": "USD",
                "period": "2026-01",
                "value": Decimal("120"),
            }
        ],
        source_b_rows=[
            {
                "account": "5000",
                "entity": "HQ",
                "currency": "USD",
                "period": "2026-01",
                "value": Decimal("100"),
            }
        ],
        materiality_config_json={"absolute_threshold": "50"},
    )
    assert rows[0].materiality_flag is False
