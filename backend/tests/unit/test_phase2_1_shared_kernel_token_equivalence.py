from __future__ import annotations

import json
import uuid
from datetime import date
from pathlib import Path

from financeops.modules.anomaly_pattern_engine.domain.value_objects import (
    AnomalyRunTokenInput,
    DefinitionVersionTokenInput as AnDefInput,
)
from financeops.modules.anomaly_pattern_engine.infrastructure.token_builder import (
    build_anomaly_run_token,
    build_definition_version_token as build_anomaly_definition_version_token,
)
from financeops.modules.board_pack_narrative_engine.domain.value_objects import (
    BoardPackRunTokenInput,
    DefinitionVersionTokenInput as BoardPackDefInput,
)
from financeops.modules.board_pack_narrative_engine.infrastructure.token_builder import (
    build_board_pack_run_token,
    build_definition_version_token as build_board_pack_definition_version_token,
)
from financeops.modules.financial_risk_engine.domain.value_objects import (
    DefinitionVersionTokenInput as RiskDefInput,
    RiskRunTokenInput,
)
from financeops.modules.financial_risk_engine.infrastructure.token_builder import (
    build_definition_version_token as build_risk_definition_version_token,
    build_risk_run_token,
)
from financeops.modules.mis_manager.domain.value_objects import (
    SnapshotTokenInput,
    VersionTokenInput,
)
from financeops.modules.mis_manager.infrastructure.token_builder import (
    build_snapshot_token,
    build_version_token,
)
from financeops.modules.payroll_gl_normalization.domain.value_objects import (
    RunTokenInput,
    SourceVersionTokenInput,
)
from financeops.modules.payroll_gl_normalization.infrastructure.token_builder import (
    build_run_token as build_normalization_run_token,
    build_source_version_token,
)
from financeops.modules.payroll_gl_reconciliation.domain.value_objects import (
    MappingVersionTokenInput,
    PayrollGlRunTokenInput,
    RuleVersionTokenInput,
)
from financeops.modules.payroll_gl_reconciliation.infrastructure.token_builder import (
    build_mapping_version_token,
    build_payroll_gl_run_token,
    build_rule_version_token,
)
from financeops.modules.ratio_variance_engine.domain.value_objects import (
    DefinitionVersionTokenInput as RatioDefInput,
    MetricRunTokenInput,
)
from financeops.modules.ratio_variance_engine.infrastructure.token_builder import (
    build_definition_version_token as build_ratio_definition_version_token,
    build_metric_run_token,
)
from financeops.modules.reconciliation_bridge.domain.value_objects import SessionTokenInput
from financeops.modules.reconciliation_bridge.infrastructure.token_builder import (
    build_session_token,
)


def _baseline_path() -> Path:
    return (
        Path(__file__).resolve().parents[3] / "docs" / "phase_2_1_baseline_token_artifacts.json"
    )


def _current_snapshot() -> dict[str, str]:
    u1 = uuid.UUID("11111111-1111-1111-1111-111111111111")
    u2 = uuid.UUID("22222222-2222-2222-2222-222222222222")
    u3 = uuid.UUID("33333333-3333-3333-3333-333333333333")
    u4 = uuid.UUID("44444444-4444-4444-4444-444444444444")

    return {
        "mis_version_token": build_version_token(
            VersionTokenInput(
                template_id=u1,
                structure_hash="s1",
                header_hash="h1",
                row_signature_hash="r1",
                column_signature_hash="c1",
                detection_summary_json={"a": 1, "b": ["x", "y"]},
            )
        ),
        "mis_snapshot_token": build_snapshot_token(
            SnapshotTokenInput(
                source_file_hash="f1",
                sheet_name="Sheet1",
                structure_hash="s1",
                mapping_set_identity="map_v1",
                validation_rule_set_identity="val_v1",
                reporting_period=date(2026, 1, 31),
                template_version_id=u2,
                status="pending",
            )
        ),
        "reconciliation_session_token": build_session_token(
            SessionTokenInput(
                tenant_id=u1,
                organisation_id=u2,
                reconciliation_type="gl_vs_tb",
                source_a_type="gl",
                source_a_ref="A",
                source_b_type="tb",
                source_b_ref="B",
                period_start=date(2026, 1, 1),
                period_end=date(2026, 1, 31),
                matching_rule_version="m1",
                tolerance_rule_version="t1",
                materiality_config_json={"abs": 100},
            )
        ),
        "normalization_source_version_token": build_source_version_token(
            SourceVersionTokenInput(
                source_id=u1,
                structure_hash="s2",
                header_hash="h2",
                row_signature_hash="r2",
                source_detection_summary_json={"sheet": "Main"},
            )
        ),
        "normalization_run_token": build_normalization_run_token(
            RunTokenInput(
                source_id=u1,
                source_version_id=u2,
                mapping_version_token="mv",
                run_type="payroll_normalization",
                reporting_period=date(2026, 1, 31),
                source_file_hash="fh",
                run_status="created",
            )
        ),
        "payroll_gl_mapping_version_token": build_mapping_version_token(
            MappingVersionTokenInput(mapping_rows=[{"k": "a"}, {"k": "b"}])
        ),
        "payroll_gl_rule_version_token": build_rule_version_token(
            RuleVersionTokenInput(rule_rows=[{"r": "a"}])
        ),
        "payroll_gl_run_token": build_payroll_gl_run_token(
            PayrollGlRunTokenInput(
                tenant_id=u1,
                organisation_id=u2,
                payroll_run_id=u3,
                gl_run_id=u4,
                mapping_version_token="mv",
                rule_version_token="rv",
                reporting_period=date(2026, 1, 31),
            ),
            status="created",
        ),
        "ratio_definition_version_token": build_ratio_definition_version_token(
            RatioDefInput(rows=[{"code": "rev"}])
        ),
        "ratio_metric_run_token": build_metric_run_token(
            MetricRunTokenInput(
                tenant_id=u1,
                organisation_id=u2,
                reporting_period=date(2026, 1, 31),
                scope_json={"entity": "X"},
                mis_snapshot_id=u3,
                payroll_run_id=None,
                gl_run_id=None,
                reconciliation_session_id=None,
                payroll_gl_reconciliation_run_id=None,
                metric_definition_version_token="mdef",
                variance_definition_version_token="vdef",
                trend_definition_version_token="tdef",
                materiality_rule_version_token="mat",
                input_signature_hash="sig",
            ),
            status="created",
        ),
        "risk_definition_version_token": build_risk_definition_version_token(
            RiskDefInput(rows=[{"code": "liq"}])
        ),
        "risk_run_token": build_risk_run_token(
            RiskRunTokenInput(
                tenant_id=u1,
                organisation_id=u2,
                reporting_period=date(2026, 1, 31),
                risk_definition_version_token="rd",
                propagation_version_token="pd",
                weight_version_token="wd",
                materiality_version_token="md",
                source_metric_run_ids=["m2", "m1"],
                source_variance_run_ids=["v1"],
                source_trend_run_ids=["t1"],
                source_reconciliation_session_ids=["s1"],
                status="created",
            )
        ),
        "anomaly_definition_version_token": build_anomaly_definition_version_token(
            AnDefInput(rows=[{"code": "anom"}])
        ),
        "anomaly_run_token": build_anomaly_run_token(
            AnomalyRunTokenInput(
                tenant_id=u1,
                organisation_id=u2,
                reporting_period=date(2026, 1, 31),
                anomaly_definition_version_token="ad",
                pattern_rule_version_token="pd",
                persistence_rule_version_token="ps",
                correlation_rule_version_token="cd",
                statistical_rule_version_token="sd",
                source_metric_run_ids=["m2", "m1"],
                source_variance_run_ids=["v1"],
                source_trend_run_ids=["t1"],
                source_risk_run_ids=["r1"],
                source_reconciliation_session_ids=["s1"],
                status="created",
            )
        ),
        "board_pack_definition_version_token": build_board_pack_definition_version_token(
            BoardPackDefInput(rows=[{"code": "bp"}])
        ),
        "board_pack_run_token": build_board_pack_run_token(
            BoardPackRunTokenInput(
                tenant_id=u1,
                organisation_id=u2,
                reporting_period=date(2026, 1, 31),
                board_pack_definition_version_token="bd",
                section_definition_version_token="sd",
                narrative_template_version_token="nd",
                inclusion_rule_version_token="id",
                source_metric_run_ids=["m2", "m1"],
                source_risk_run_ids=["r1"],
                source_anomaly_run_ids=["a1"],
                status="created",
            )
        ),
    }


def test_phase2_1_shared_kernel_token_equivalence_no_drift() -> None:
    expected = json.loads(_baseline_path().read_text(encoding="utf-8"))
    assert _current_snapshot() == expected
