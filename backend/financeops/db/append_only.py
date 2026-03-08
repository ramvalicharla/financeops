from __future__ import annotations

from collections.abc import Iterable

APPEND_ONLY_TABLES: tuple[str, ...] = (
    "audit_trail",
    "credit_transactions",
    "mis_templates",
    "mis_uploads",
    "mis_template_versions",
    "mis_template_sections",
    "mis_template_columns",
    "mis_template_row_mappings",
    "mis_data_snapshots",
    "mis_normalized_lines",
    "mis_ingestion_exceptions",
    "mis_drift_events",
    "mis_canonical_metric_dictionary",
    "mis_canonical_dimension_dictionary",
    "gl_entries",
    "trial_balance_rows",
    "recon_items",
    "reconciliation_sessions",
    "reconciliation_scopes",
    "reconciliation_lines",
    "reconciliation_exceptions",
    "reconciliation_resolution_events",
    "reconciliation_evidence_links",
    "normalization_sources",
    "normalization_source_versions",
    "normalization_mappings",
    "normalization_runs",
    "payroll_normalized_lines",
    "gl_normalized_lines",
    "normalization_exceptions",
    "normalization_evidence_links",
    "payroll_gl_reconciliation_mappings",
    "payroll_gl_reconciliation_rules",
    "payroll_gl_reconciliation_runs",
    "payroll_gl_reconciliation_run_scopes",
    "metric_definitions",
    "metric_definition_components",
    "variance_definitions",
    "trend_definitions",
    "materiality_rules",
    "metric_runs",
    "metric_results",
    "variance_results",
    "trend_results",
    "metric_evidence_links",
    "risk_definitions",
    "risk_definition_dependencies",
    "risk_weight_configurations",
    "risk_materiality_rules",
    "risk_runs",
    "risk_results",
    "risk_contributing_signals",
    "risk_rollforward_events",
    "risk_evidence_links",
    "anomaly_definitions",
    "anomaly_pattern_rules",
    "anomaly_persistence_rules",
    "anomaly_correlation_rules",
    "anomaly_statistical_rules",
    "anomaly_runs",
    "anomaly_results",
    "anomaly_contributing_signals",
    "anomaly_rollforward_events",
    "anomaly_evidence_links",
    "bank_statements",
    "bank_transactions",
    "bank_recon_items",
    "working_capital_snapshots",
    "gst_returns",
    "gst_recon_items",
    "monthend_checklists",
    "auditor_grants",
    "auditor_access_logs",
    "fx_rate_fetch_runs",
    "fx_rate_quotes",
    "fx_manual_monthly_rates",
    "fx_variance_results",
    "normalized_financial_snapshots",
    "normalized_financial_snapshot_lines",
    "consolidation_runs",
    "consolidation_run_events",
    "consolidation_entities",
    "consolidation_line_items",
    "intercompany_pairs",
    "consolidation_eliminations",
    "consolidation_results",
    "revenue_runs",
    "revenue_run_events",
    "revenue_contracts",
    "revenue_performance_obligations",
    "revenue_contract_line_items",
    "revenue_schedules",
    "revenue_journal_entries",
    "revenue_adjustments",
    "lease_runs",
    "lease_run_events",
    "leases",
    "lease_payments",
    "lease_liability_schedule",
    "lease_rou_schedule",
    "lease_modifications",
    "lease_journal_entries",
    "prepaid_runs",
    "prepaid_run_events",
    "prepaids",
    "prepaid_amortization_schedule",
    "prepaid_journal_entries",
    "prepaid_adjustments",
    "far_runs",
    "far_run_events",
    "assets",
    "asset_depreciation_schedule",
    "asset_impairments",
    "asset_disposals",
    "asset_journal_entries",
    "cp_tenants",
    "cp_organisations",
    "cp_groups",
    "cp_entities",
    "cp_user_organisation_assignments",
    "cp_user_entity_assignments",
    "cp_tenant_package_assignments",
    "cp_tenant_module_enablement",
    "cp_module_feature_flags",
    "cp_roles",
    "cp_role_permissions",
    "cp_user_role_assignments",
    "cp_workflow_templates",
    "cp_workflow_template_versions",
    "cp_workflow_template_stages",
    "cp_workflow_stage_role_map",
    "cp_workflow_stage_user_map",
    "cp_workflow_instances",
    "cp_workflow_stage_instances",
    "cp_workflow_instance_events",
    "cp_workflow_stage_events",
    "cp_workflow_approvals",
    "cp_tenant_quota_assignments",
    "cp_tenant_quota_usage_events",
    "cp_tenant_quota_windows",
    "cp_tenant_isolation_policy",
    "cp_tenant_migration_events",
)

APPEND_ONLY_TRIGGER_FUNCTION = "financeops_block_update_delete"


def append_only_function_sql() -> str:
    return f"""
    CREATE OR REPLACE FUNCTION {APPEND_ONLY_TRIGGER_FUNCTION}()
    RETURNS trigger AS $$
    BEGIN
      RAISE EXCEPTION 'append-only table "%": % is not allowed', TG_TABLE_NAME, TG_OP
      USING ERRCODE = '55000';
    END;
    $$ LANGUAGE plpgsql;
    """


def append_only_trigger_name(table_name: str) -> str:
    return f"trg_append_only_{table_name}"


def create_trigger_sql(table_name: str) -> str:
    trigger_name = append_only_trigger_name(table_name)
    return (
        f"CREATE TRIGGER {trigger_name} "
        f"BEFORE UPDATE OR DELETE ON {table_name} "
        f"FOR EACH ROW EXECUTE FUNCTION {APPEND_ONLY_TRIGGER_FUNCTION}();"
    )


def drop_trigger_sql(table_name: str) -> str:
    trigger_name = append_only_trigger_name(table_name)
    return f"DROP TRIGGER IF EXISTS {trigger_name} ON {table_name};"


def iter_unique_tables(tables: Iterable[str]) -> list[str]:
    # Preserve first-seen order while de-duplicating.
    seen: set[str] = set()
    ordered: list[str] = []
    for table_name in tables:
        if table_name not in seen:
            seen.add(table_name)
            ordered.append(table_name)
    return ordered
