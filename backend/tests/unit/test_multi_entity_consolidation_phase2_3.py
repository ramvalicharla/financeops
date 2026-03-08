from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import pytest

from financeops.modules.multi_entity_consolidation.application.aggregation_service import (
    AggregationService,
)
from financeops.modules.multi_entity_consolidation.application.hierarchy_service import (
    HierarchyService,
)
from financeops.modules.multi_entity_consolidation.domain.value_objects import (
    ConsolidationRunTokenInput,
)
from financeops.modules.multi_entity_consolidation.infrastructure.token_builder import (
    build_consolidation_run_token,
)


@dataclass
class _Node:
    id: uuid.UUID
    entity_id: uuid.UUID
    parent_node_id: uuid.UUID | None
    node_level: int


@dataclass
class _Metric:
    id: uuid.UUID
    metric_code: str
    metric_value: Decimal
    dimension_json: dict


@dataclass
class _Variance:
    id: uuid.UUID
    metric_code: str
    comparison_type: str
    baseline_value: Decimal
    current_value: Decimal
    variance_abs: Decimal


def test_hierarchy_service_rejects_cycle() -> None:
    a = uuid.uuid4()
    b = uuid.uuid4()
    c = uuid.uuid4()
    service = HierarchyService()
    nodes = [
        _Node(id=a, entity_id=uuid.uuid4(), parent_node_id=c, node_level=0),
        _Node(id=b, entity_id=uuid.uuid4(), parent_node_id=a, node_level=1),
        _Node(id=c, entity_id=uuid.uuid4(), parent_node_id=b, node_level=2),
    ]
    with pytest.raises(ValueError, match="Hierarchy cycle detected"):
        service.deterministic_entity_order(nodes=nodes)


def test_consolidation_run_token_is_deterministic_for_same_inputs() -> None:
    tenant_id = uuid.uuid4()
    org_id = uuid.uuid4()
    payload = ConsolidationRunTokenInput(
        tenant_id=tenant_id,
        organisation_id=org_id,
        reporting_period=date(2026, 1, 31),
        hierarchy_version_token="h1",
        scope_version_token="s1",
        rule_version_token="r1",
        intercompany_version_token="i1",
        adjustment_version_token="a1",
        source_run_refs=[
            {"source_type": "metric_run", "run_id": "00000000-0000-0000-0000-000000000002"},
            {"source_type": "variance_run", "run_id": "00000000-0000-0000-0000-000000000001"},
        ],
        run_status="created",
    )
    token_a = build_consolidation_run_token(payload)
    token_b = build_consolidation_run_token(payload)
    assert token_a == token_b


def test_aggregation_service_is_stable_and_quantized() -> None:
    service = AggregationService()
    metric_rows = [
        _Metric(
            id=uuid.uuid4(),
            metric_code="revenue",
            metric_value=Decimal("10.1234567"),
            dimension_json={"legal_entity": "A", "currency_code": "usd"},
        ),
        _Metric(
            id=uuid.uuid4(),
            metric_code="revenue",
            metric_value=Decimal("2.0000004"),
            dimension_json={"legal_entity": "B", "currency_code": "usd"},
        ),
    ]
    variance_rows = [
        _Variance(
            id=uuid.uuid4(),
            metric_code="revenue",
            comparison_type="mom",
            baseline_value=Decimal("10"),
            current_value=Decimal("12.123457"),
            variance_abs=Decimal("2.123457"),
        )
    ]
    metrics = service.aggregate_metrics(metric_rows=metric_rows, allowed_entity_ids={"A", "B"})
    variances = service.aggregate_variances(variance_rows=variance_rows, allowed_entity_ids={"A", "B"})
    assert len(metrics) == 1
    assert metrics[0].aggregated_value == Decimal("12.123457")
    assert metrics[0].entity_count == 2
    assert len(variances) == 1
    assert variances[0].variance_pct == Decimal("21.234570")

