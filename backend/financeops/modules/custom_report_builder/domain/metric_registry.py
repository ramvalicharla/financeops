from __future__ import annotations

from pydantic import BaseModel


class MetricDefinition(BaseModel):
    key: str
    label: str
    source_table: str
    source_column: str
    data_type: str
    engine: str


METRIC_REGISTRY: dict[str, MetricDefinition] = {
    # MIS KPIs
    "mis.kpi.revenue": MetricDefinition(
        key="mis.kpi.revenue",
        label="Revenue",
        source_table="metric_results",
        source_column="metric_value",
        data_type="decimal",
        engine="mis_manager",
    ),
    "mis.kpi.gross_profit": MetricDefinition(
        key="mis.kpi.gross_profit",
        label="Gross Profit",
        source_table="metric_results",
        source_column="metric_value",
        data_type="decimal",
        engine="mis_manager",
    ),
    "mis.kpi.ebitda": MetricDefinition(
        key="mis.kpi.ebitda",
        label="EBITDA",
        source_table="metric_results",
        source_column="metric_value",
        data_type="decimal",
        engine="mis_manager",
    ),
    "mis.kpi.net_profit": MetricDefinition(
        key="mis.kpi.net_profit",
        label="Net Profit",
        source_table="metric_results",
        source_column="metric_value",
        data_type="decimal",
        engine="mis_manager",
    ),
    "mis.kpi.operating_expenses": MetricDefinition(
        key="mis.kpi.operating_expenses",
        label="Operating Expenses",
        source_table="metric_results",
        source_column="metric_value",
        data_type="decimal",
        engine="mis_manager",
    ),
    "mis.kpi.total_assets": MetricDefinition(
        key="mis.kpi.total_assets",
        label="Total Assets",
        source_table="metric_results",
        source_column="metric_value",
        data_type="decimal",
        engine="mis_manager",
    ),
    # Cash flow
    "cashflow.operating_cf": MetricDefinition(
        key="cashflow.operating_cf",
        label="Operating Cash Flow",
        source_table="cash_flow_line_results",
        source_column="computed_value",
        data_type="decimal",
        engine="cash_flow_engine",
    ),
    "cashflow.investing_cf": MetricDefinition(
        key="cashflow.investing_cf",
        label="Investing Cash Flow",
        source_table="cash_flow_line_results",
        source_column="computed_value",
        data_type="decimal",
        engine="cash_flow_engine",
    ),
    "cashflow.financing_cf": MetricDefinition(
        key="cashflow.financing_cf",
        label="Financing Cash Flow",
        source_table="cash_flow_line_results",
        source_column="computed_value",
        data_type="decimal",
        engine="cash_flow_engine",
    ),
    "cashflow.net_cash_change": MetricDefinition(
        key="cashflow.net_cash_change",
        label="Net Cash Change",
        source_table="cash_flow_line_results",
        source_column="computed_value",
        data_type="decimal",
        engine="cash_flow_engine",
    ),
    # Ratio/variance
    "variance.revenue_variance_pct": MetricDefinition(
        key="variance.revenue_variance_pct",
        label="Revenue Variance %",
        source_table="variance_results",
        source_column="variance_pct",
        data_type="decimal",
        engine="ratio_variance_engine",
    ),
    "variance.ebitda_variance_pct": MetricDefinition(
        key="variance.ebitda_variance_pct",
        label="EBITDA Variance %",
        source_table="variance_results",
        source_column="variance_pct",
        data_type="decimal",
        engine="ratio_variance_engine",
    ),
    "variance.gross_margin_variance_bps": MetricDefinition(
        key="variance.gross_margin_variance_bps",
        label="Gross Margin Variance (bps)",
        source_table="variance_results",
        source_column="variance_bps",
        data_type="decimal",
        engine="ratio_variance_engine",
    ),
    # FX
    "fx.revenue_translated": MetricDefinition(
        key="fx.revenue_translated",
        label="FX Revenue Translated",
        source_table="fx_translated_metric_results",
        source_column="translated_value",
        data_type="decimal",
        engine="fx_translation_reporting",
    ),
    "fx.ebitda_translated": MetricDefinition(
        key="fx.ebitda_translated",
        label="FX EBITDA Translated",
        source_table="fx_translated_metric_results",
        source_column="translated_value",
        data_type="decimal",
        engine="fx_translation_reporting",
    ),
    # Consolidation
    "consolidation.consolidated_revenue": MetricDefinition(
        key="consolidation.consolidated_revenue",
        label="Consolidated Revenue",
        source_table="multi_entity_consolidation_metric_results",
        source_column="aggregated_value",
        data_type="decimal",
        engine="multi_entity_consolidation",
    ),
    "consolidation.consolidated_ebitda": MetricDefinition(
        key="consolidation.consolidated_ebitda",
        label="Consolidated EBITDA",
        source_table="multi_entity_consolidation_metric_results",
        source_column="aggregated_value",
        data_type="decimal",
        engine="multi_entity_consolidation",
    ),
    "consolidation.consolidated_net_profit": MetricDefinition(
        key="consolidation.consolidated_net_profit",
        label="Consolidated Net Profit",
        source_table="multi_entity_consolidation_metric_results",
        source_column="aggregated_value",
        data_type="decimal",
        engine="multi_entity_consolidation",
    ),
    # Payroll GL
    "payroll.total_payroll_cost": MetricDefinition(
        key="payroll.total_payroll_cost",
        label="Total Payroll Cost",
        source_table="payroll_gl_reconciliation_results",
        source_column="payroll_total_amount",
        data_type="decimal",
        engine="payroll_gl_reconciliation",
    ),
    "payroll.headcount": MetricDefinition(
        key="payroll.headcount",
        label="Headcount",
        source_table="payroll_gl_reconciliation_results",
        source_column="employee_count",
        data_type="integer",
        engine="payroll_gl_reconciliation",
    ),
}


def get_metric(key: str) -> MetricDefinition:
    if key not in METRIC_REGISTRY:
        raise ValueError(f"Unknown metric key: {key}")
    return METRIC_REGISTRY[key]


def list_metrics() -> list[MetricDefinition]:
    return [METRIC_REGISTRY[key] for key in sorted(METRIC_REGISTRY.keys())]


def validate_metric_keys(keys: list[str]) -> list[str]:
    return [key for key in keys if key not in METRIC_REGISTRY]


__all__ = [
    "METRIC_REGISTRY",
    "MetricDefinition",
    "get_metric",
    "list_metrics",
    "validate_metric_keys",
]

