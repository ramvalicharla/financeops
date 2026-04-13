from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from financeops.accounting_policy_engine import AccountingPolicyService, Policy
from financeops.config import settings
from financeops.modules.multi_entity_consolidation.domain.entities import ConsolidatedMetricRow


def test_policy_resolution_selects_highest_version_id_before_current_date() -> None:
    service = AccountingPolicyService(
        policies=[
            Policy(
                policy_id="policy.ic.v1",
                policy_version_id=1,
                effective_date=date(2024, 1, 1),
                rule_type="intercompany_profit_elimination",
                parameters={},
            ),
            Policy(
                policy_id="policy.ic.v3.future",
                policy_version_id=3,
                effective_date=date(2026, 6, 1),
                rule_type="intercompany_profit_elimination",
                parameters={},
            ),
            Policy(
                policy_id="policy.ic.v2",
                policy_version_id=2,
                effective_date=date(2025, 1, 1),
                rule_type="intercompany_profit_elimination",
                parameters={},
            ),
        ]
    )

    selected = service.resolve_policy(
        rule_type="intercompany_profit_elimination",
        current_date=date(2026, 1, 31),
    )

    assert selected.policy_id == "policy.ic.v2"
    assert selected.policy_version_id == 2


def test_intercompany_policy_application_is_deterministic_and_auditable() -> None:
    service = AccountingPolicyService(
        policies=[
            Policy(
                policy_id="policy.ic.v2",
                policy_version_id=2,
                effective_date=date(2025, 1, 1),
                rule_type="intercompany_profit_elimination",
                parameters={
                    "unrealized_profit_rate": Decimal("0.250000"),
                    "policy_effect": "adjustment",
                },
            )
        ]
    )
    entries = [
        {
            "intercompany_pair_id": "pair-1",
            "entity_from": "entity-a",
            "entity_to": "entity-b",
            "account_code": "4000",
            "eliminated_amount_parent": "100.000000",
            "transaction_reference": "IC-REF-1",
            "elimination_status": "applied",
        }
    ]

    first = service.apply_intercompany_profit_elimination_policy(
        elimination_entries=entries,
        current_date=date(2026, 1, 31),
    )
    second = service.apply_intercompany_profit_elimination_policy(
        elimination_entries=entries,
        current_date=date(2026, 1, 31),
    )

    assert first == second
    assert first["policy_applied_entries"][0]["eliminated_amount_parent"] == "75.000000"
    assert first["audit_trace"]["policy_id"] == "policy.ic.v2"
    assert first["audit_trace"]["affected_entries"][0]["before"] == "100.000000"
    assert first["audit_trace"]["affected_entries"][0]["after"] == "75.000000"
    assert first["audit_trace"]["policy_source"] == "explicit"


def test_minority_interest_policy_application_modifies_entries() -> None:
    service = AccountingPolicyService(
        policies=[
            Policy(
                policy_id="policy.nci.v2",
                policy_version_id=2,
                effective_date=date(2025, 1, 1),
                rule_type="minority_interest_adjustment",
                parameters={
                    "basis": "full_goodwill",
                    "adjustment_multiplier": Decimal("1.500000"),
                    "policy_effect": "adjustment",
                },
            )
        ]
    )

    result = service.apply_minority_interest_policy(
        minority_interest_summary={
            "validation_report": {"status": "PASS", "reason": "ready"},
            "aggregate_amount": "20.000000",
            "entity_traces": [
                {
                    "entity_id": "entity-c",
                    "source_metric_result_id": "metric-1",
                    "metric_code": "nci_balance",
                    "source_balance": "100.000000",
                    "ownership_percentage": "80.000000",
                    "minority_interest_value": "20.000000",
                }
            ],
            "applied": True,
        },
        current_date=date(2026, 1, 31),
    )

    assert result["aggregate_amount"] == "30.000000"
    assert result["entity_traces"][0]["minority_interest_value"] == "30.000000"
    assert result["policy_application"]["audit_trace"]["affected_entries"][0]["basis"] == "full_goodwill"


def test_revenue_policy_application_modifies_entries_correctly() -> None:
    service = AccountingPolicyService(
        policies=[
            Policy(
                policy_id="policy.revenue.v2",
                policy_version_id=2,
                effective_date=date(2025, 1, 1),
                rule_type="revenue_reclassification",
                parameters={
                    "metric_codes": ["revenue"],
                    "reclassification_rate": Decimal("0.100000"),
                    "policy_effect": "adjustment",
                },
            )
        ]
    )

    result = service.apply_revenue_reclassification_policy(
        consolidated_metrics=[
            ConsolidatedMetricRow(
                metric_code="revenue",
                aggregated_value=Decimal("250.000000"),
                entity_count=1,
                currency_code="USD",
                source_metric_refs=["metric-1"],
            )
        ],
        current_date=date(2026, 1, 31),
    )

    assert result["policy_applied_entries"][0]["aggregated_value"] == "225.000000"
    assert result["audit_trace"]["affected_entries"][0]["adjustment"] == "25.000000"


def test_missing_policy_raises_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "REQUIRE_EXPLICIT_POLICY", True)
    service = AccountingPolicyService(policies=[])

    with pytest.raises(
        ValueError, match="validation_report.status=FAIL: missing policy for rule_type"
    ):
        service.resolve_policy(
            rule_type="minority_interest_adjustment",
            current_date=date(2026, 1, 31),
        )


def test_require_explicit_policy_true_blocks_default_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "REQUIRE_EXPLICIT_POLICY", True)
    service = AccountingPolicyService(policies=[])

    with pytest.raises(
        ValueError, match="validation_report.status=FAIL: missing policy for rule_type"
    ):
        service.resolve_policy(
            rule_type="intercompany_profit_elimination",
            current_date=date(2026, 1, 31),
        )


def test_require_explicit_policy_false_uses_default_with_trace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "REQUIRE_EXPLICIT_POLICY", False)
    service = AccountingPolicyService(policies=[])

    result = service.apply_intercompany_profit_elimination_policy(
        elimination_entries=[
            {
                "intercompany_pair_id": "pair-1",
                "entity_from": "entity-a",
                "entity_to": "entity-b",
                "account_code": "4000",
                "eliminated_amount_parent": "100.000000",
                "transaction_reference": "IC-REF-1",
                "elimination_status": "applied",
            }
        ],
        current_date=date(2026, 1, 31),
    )

    assert result["policy_applied_entries"][0]["policy_adjustment_amount"] == "0.000000"
    assert result["audit_trace"]["policy_source"] == "default"
    assert result["audit_trace"]["reason"] == "no explicit policy configured"


def test_numeric_default_parameters_work_correctly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "REQUIRE_EXPLICIT_POLICY", False)
    service = AccountingPolicyService(policies=[])

    result = service.apply_revenue_reclassification_policy(
        consolidated_metrics=[
            ConsolidatedMetricRow(
                metric_code="revenue",
                aggregated_value=Decimal("250.000000"),
                entity_count=1,
                currency_code="USD",
                source_metric_refs=["metric-1"],
            )
        ],
        current_date=date(2026, 1, 31),
    )

    assert result["policy_applied_entries"][0]["aggregated_value"] == "250.000000"
    assert result["audit_trace"]["policy_source"] == "default"
