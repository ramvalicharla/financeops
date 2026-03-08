from __future__ import annotations

import uuid
from datetime import date
from types import SimpleNamespace

from financeops.modules.board_pack_narrative_engine.application.inclusion_service import (
    InclusionService,
)
from financeops.modules.board_pack_narrative_engine.application.narrative_service import (
    NarrativeService,
)
from financeops.modules.board_pack_narrative_engine.application.section_service import (
    SectionService,
)
from financeops.modules.board_pack_narrative_engine.domain.value_objects import (
    BoardPackRunTokenInput,
)
from financeops.modules.board_pack_narrative_engine.infrastructure.token_builder import (
    build_board_pack_run_token,
)


def test_board_pack_run_token_is_deterministic() -> None:
    payload = BoardPackRunTokenInput(
        tenant_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        organisation_id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
        reporting_period=date(2026, 1, 31),
        board_pack_definition_version_token="a" * 64,
        section_definition_version_token="b" * 64,
        narrative_template_version_token="c" * 64,
        inclusion_rule_version_token="d" * 64,
        source_metric_run_ids=["m2", "m1"],
        source_risk_run_ids=["r2", "r1"],
        source_anomaly_run_ids=["a2", "a1"],
        status="created",
    )
    assert build_board_pack_run_token(payload) == build_board_pack_run_token(payload)


def test_inclusion_service_logic_is_deterministic() -> None:
    service = InclusionService()
    rules = [
        SimpleNamespace(
            rule_code="A",
            id=uuid.uuid4(),
            inclusion_logic_json={"section_codes": ["key_risks"], "min_risk_count": 1},
        ),
        SimpleNamespace(
            rule_code="B",
            id=uuid.uuid4(),
            inclusion_logic_json={"top_limit": 7},
        ),
    ]
    assert (
        service.should_include_section(
            section_code="key_risks",
            rules=rules,
            risk_count=2,
            anomaly_count=0,
        )
        is True
    )
    assert (
        service.should_include_section(
            section_code="key_risks",
            rules=rules,
            risk_count=0,
            anomaly_count=0,
        )
        is False
    )
    assert service.top_limit(rules=rules) == 7


def test_section_and_narrative_assembly_are_stable() -> None:
    section_service = SectionService()
    narrative_service = NarrativeService()
    sections = section_service.build_sections(
        section_rows=[
            SimpleNamespace(
                section_order_default=2,
                section_code="key_risks",
                section_name="Key Risks",
                id=uuid.uuid4(),
            ),
            SimpleNamespace(
                section_order_default=1,
                section_code="executive_summary",
                section_name="Executive Summary",
                id=uuid.uuid4(),
            ),
        ],
        metric_rows=[
            SimpleNamespace(metric_code="revenue", metric_value="100", id=uuid.uuid4()),
            SimpleNamespace(metric_code="ebitda", metric_value="20", id=uuid.uuid4()),
        ],
        risk_rows=[
            SimpleNamespace(risk_code="liquidity", severity="high"),
        ],
        anomaly_rows=[
            SimpleNamespace(anomaly_code="payroll_spike", severity="medium", persistence_classification="sustained"),
        ],
        top_limit=5,
    )
    assert [row.section_code for row in sections] == ["executive_summary", "key_risks"]

    narratives = narrative_service.render_blocks(
        sections=sections,
        templates=[
            SimpleNamespace(
                template_code="executive_summary",
                template_text="{section_title}: {section_summary_text}",
                id=uuid.uuid4(),
            ),
            SimpleNamespace(
                template_code="key_risks",
                template_text="{section_title}: {section_summary_text}",
                id=uuid.uuid4(),
            ),
        ],
        reporting_period="2026-01-31",
    )
    assert len(narratives) == 2
    assert narratives[0].block_order == 1
    assert narratives[1].block_order == 2
    assert "Executive Summary" in narratives[0].narrative_text
    assert "Key Risks" in narratives[1].narrative_text
