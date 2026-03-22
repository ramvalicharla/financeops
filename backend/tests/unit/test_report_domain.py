from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from pydantic import ValidationError

from financeops.modules.custom_report_builder.domain.enums import (
    FilterOperator,
    SortDirection,
)
from financeops.modules.custom_report_builder.domain.filter_dsl import (
    FilterCondition,
    FilterConfig,
    ReportDefinitionSchema,
    SortConfig,
)
from financeops.modules.custom_report_builder.domain.metric_registry import (
    METRIC_REGISTRY,
    MetricDefinition,
    get_metric,
    validate_metric_keys,
)


@pytest.mark.unit
def test_t_101_metric_registry_has_minimum_entries() -> None:
    assert len(METRIC_REGISTRY) >= 20


@pytest.mark.unit
def test_t_102_metric_definitions_have_required_non_empty_fields() -> None:
    for metric in METRIC_REGISTRY.values():
        assert isinstance(metric, MetricDefinition)
        assert metric.key
        assert metric.label
        assert metric.source_table
        assert metric.source_column
        assert metric.data_type
        assert metric.engine


@pytest.mark.unit
def test_t_103_get_metric_returns_expected_definition_for_known_key() -> None:
    metric = get_metric("mis.kpi.revenue")
    assert metric.key == "mis.kpi.revenue"
    assert metric.source_table == "metric_results"


@pytest.mark.unit
def test_t_104_get_metric_raises_for_unknown_key() -> None:
    with pytest.raises((KeyError, ValueError)):
        get_metric("unknown.metric")


@pytest.mark.unit
def test_t_105_validate_metric_keys_empty_input_returns_empty() -> None:
    assert validate_metric_keys([]) == []


@pytest.mark.unit
def test_t_106_validate_metric_keys_bad_key_returns_invalid_key() -> None:
    assert validate_metric_keys(["bad.key"]) == ["bad.key"]


@pytest.mark.unit
def test_t_107_validate_metric_keys_mixed_returns_only_invalid() -> None:
    invalid = validate_metric_keys(["mis.kpi.revenue", "bad.key", "fx.revenue_translated", "bad.two"])
    assert invalid == ["bad.key", "bad.two"]


@pytest.mark.unit
def test_t_108_report_definition_rejects_empty_metric_keys() -> None:
    with pytest.raises(ValidationError):
        ReportDefinitionSchema(
            name="My Report",
            metric_keys=[],
            filter_config=FilterConfig(),
        )


@pytest.mark.unit
def test_t_109_report_definition_rejects_invalid_metric_keys() -> None:
    with pytest.raises(ValidationError):
        ReportDefinitionSchema(
            name="My Report",
            metric_keys=["bad.metric"],
            filter_config=FilterConfig(),
        )


@pytest.mark.unit
def test_t_110_filter_config_rejects_non_decimal_amount_strings() -> None:
    with pytest.raises(ValidationError):
        FilterConfig(amount_min="abc")
    with pytest.raises(ValidationError):
        FilterConfig(amount_max="abc")


@pytest.mark.unit
def test_t_111_filter_config_accepts_valid_decimal_amount_strings() -> None:
    cfg = FilterConfig(amount_min="1234.56", amount_max="9999.01")
    assert cfg.amount_min == "1234.56"
    assert cfg.amount_max == "9999.01"


@pytest.mark.unit
def test_t_112_filter_config_rejects_float_amount_when_strict() -> None:
    with pytest.raises(ValidationError):
        FilterConfig.model_validate({"amount_min": 1234.56}, strict=True)


@pytest.mark.unit
def test_t_113_filter_condition_between_with_range_value_is_valid() -> None:
    condition = FilterCondition(
        field="amount",
        operator=FilterOperator.BETWEEN,
        value=["100.00", "200.00"],
    )
    assert condition.operator == FilterOperator.BETWEEN
    assert condition.value == ["100.00", "200.00"]


@pytest.mark.unit
def test_t_114_sort_config_defaults_to_asc() -> None:
    cfg = SortConfig(field="metric_key")
    assert cfg.direction == SortDirection.ASC

