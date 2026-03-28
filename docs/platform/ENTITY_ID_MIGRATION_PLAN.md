# entity_id Migration Plan

## Category 1 — Must Fix (migration required)
These are financial transaction/history tables that will be queried in accounting-layer context and should be entity-scoped for safe isolation.

- `cash_flow_engine.py`: `cash_flow_statement_definitions`, `cash_flow_line_mappings`, `cash_flow_bridge_rule_definitions`, `cash_flow_runs`, `cash_flow_line_results`, `cash_flow_evidence_links`
- `erp_sync.py`: `external_connection_versions`, `external_sync_definition_versions`, `external_raw_snapshots`, `external_normalized_snapshots`, `external_mapping_definitions`, `external_mapping_versions`, `external_sync_evidence_links`, `external_sync_errors`, `external_sync_publish_events`, `external_backdated_modification_alerts`, `external_sync_drift_reports`, `external_sync_health_alerts`, `external_sync_sla_configs`
- `fixed_assets.py`: `far_runs`, `far_run_events`, `asset_depreciation_schedule`, `asset_impairments`, `asset_disposals`, `asset_journal_entries`
- `lease.py`: `lease_runs`, `lease_run_events`, `leases`, `lease_payments`, `lease_liability_schedule`, `lease_rou_schedule`, `lease_modifications`, `lease_journal_entries`
- `prepaid.py`: `prepaid_runs`, `prepaid_run_events`, `prepaids`, `prepaid_amortization_schedule`, `prepaid_journal_entries`, `prepaid_adjustments`
- `reconciliation.py`: `gl_entries`, `trial_balance_rows`, `recon_items`
- `reconciliation_bridge.py`: `reconciliation_sessions`, `reconciliation_scopes`, `reconciliation_lines`, `reconciliation_exceptions`, `reconciliation_resolution_events`, `reconciliation_evidence_links`
- `revenue.py`: `revenue_runs`, `revenue_run_events`, `revenue_contracts`, `revenue_performance_obligations`, `revenue_contract_line_items`, `revenue_schedules`, `revenue_journal_entries`, `revenue_adjustments`

## Category 2 — Should Fix (migration required)
These are module-level operational/reporting tables that are entity-scoped in practice and should be upgraded after Category 1.

- `anomaly_pattern_engine.py`: `anomaly_definitions`, `anomaly_pattern_rules`, `anomaly_persistence_rules`, `anomaly_correlation_rules`, `anomaly_statistical_rules`, `anomaly_runs`, `anomaly_results`, `anomaly_contributing_signals`, `anomaly_rollforward_events`, `anomaly_evidence_links`
- `auditor.py`: `auditor_grants`, `auditor_access_logs`
- `board_pack_generator.py`: `board_pack_runs`, `board_pack_sections`, `board_pack_artifacts`
- `board_pack_narrative_engine.py`: `board_pack_definitions`, `board_pack_section_definitions`, `narrative_templates`, `board_pack_inclusion_rules`, `board_pack_runs`, `board_pack_results`, `board_pack_section_results`, `board_pack_narrative_blocks`, `board_pack_evidence_links`
- `consolidation.py`: `consolidation_runs`, `consolidation_run_events`, `intercompany_pairs`, `consolidation_eliminations`, `consolidation_results`, `normalized_financial_snapshot_lines`
- `custom_report_builder.py`: `report_definitions`, `report_runs`, `report_results`
- `equity_engine.py`: `equity_statement_definitions`, `equity_line_definitions`, `equity_rollforward_rule_definitions`, `equity_source_mappings`, `equity_runs`, `equity_line_results`, `equity_statement_results`, `equity_evidence_links`
- `financial_risk_engine.py`: `risk_definitions`, `risk_definition_dependencies`, `risk_weight_configurations`, `risk_materiality_rules`, `risk_runs`, `risk_results`, `risk_contributing_signals`, `risk_rollforward_events`, `risk_evidence_links`
- `fx_rates.py`: `fx_rate_fetch_runs`, `fx_rate_quotes`, `fx_manual_monthly_rates`, `fx_variance_results`
- `fx_translation_reporting.py`: `reporting_currency_definitions`, `fx_translation_rule_definitions`, `fx_rate_selection_policies`, `fx_translation_runs`, `fx_translated_metric_results`, `fx_translated_variance_results`, `fx_translation_evidence_links`
- `mis_manager.py`: `mis_templates`, `mis_uploads`, `mis_template_versions`, `mis_template_sections`, `mis_template_columns`, `mis_template_row_mappings`, `mis_data_snapshots`, `mis_normalized_lines`, `mis_ingestion_exceptions`, `mis_drift_events`, `mis_canonical_metric_dictionary`, `mis_canonical_dimension_dictionary`
- `monthend.py`: `monthend_checklists`, `monthend_tasks`
- `multi_entity_consolidation.py`: `entity_hierarchies`, `consolidation_scopes`, `consolidation_rule_definitions`, `intercompany_mapping_rules`, `consolidation_adjustment_definitions`, `multi_entity_consolidation_runs`, `multi_entity_consolidation_metric_results`, `multi_entity_consolidation_variance_results`, `multi_entity_consolidation_evidence_links`
- `ownership_consolidation.py`: `ownership_structure_definitions`, `ownership_consolidation_rule_definitions`, `minority_interest_rule_definitions`, `ownership_consolidation_runs`, `ownership_consolidation_metric_results`, `ownership_consolidation_variance_results`, `ownership_consolidation_evidence_links`
- `payroll_gl_normalization.py`: `normalization_sources`, `normalization_source_versions`, `normalization_mappings`, `normalization_runs`, `payroll_normalized_lines`, `gl_normalized_lines`, `normalization_exceptions`, `normalization_evidence_links`
- `payroll_gl_reconciliation.py`: `payroll_gl_reconciliation_mappings`, `payroll_gl_reconciliation_rules`, `payroll_gl_reconciliation_runs`, `payroll_gl_reconciliation_run_scopes`
- `ratio_variance_engine.py`: `metric_definitions`, `metric_definition_components`, `variance_definitions`, `trend_definitions`, `materiality_rules`, `metric_runs`, `metric_results`, `variance_results`, `trend_results`, `metric_evidence_links`
- `working_capital.py`: `working_capital_snapshots`

## Category 3 — No action needed
These are platform-level or tenant-level tables where `entity_id` is not required by design.

- `ai_cost.py`: `ai_cost_events`, `tenant_token_budgets`
- `audit.py`: `audit_trail`
- `auth_tokens.py`: `mfa_recovery_codes`, `password_reset_tokens`
- `credits.py`: `credit_balances`, `credit_transactions`, `credit_reservations`
- `erp_sync.py`: `external_connector_capability_registry`, `external_connector_version_registry`, `external_data_consent_logs`
- `observability_engine.py`: `observability_run_registry`, `run_token_diff_definitions`, `run_token_diff_results`, `lineage_graph_snapshots`, `governance_events`, `run_performance_metrics`, `observability_runs`, `observability_results`, `observability_evidence_links`
- `payment.py`: `billing_plans`, `tenant_subscriptions`, `subscription_events`, `billing_invoices`, `payment_methods`, `credit_ledger`, `credit_top_ups`, `webhook_events`, `grace_period_logs`, `proration_records`
- `prompts.py`: `ai_prompt_versions`
- `scheduled_delivery.py`: `delivery_schedules`, `delivery_logs`
- `tenants.py`: `iam_tenants`, `iam_workspaces`
- `users.py`: `iam_users`, `iam_sessions`

## Proposed migration sequence
Suggested sequence compatible with unified roadmap ordering:

1. `0083_entity_id_accounting_blockers.py`
   - Add/backfill/constraint `entity_id` for pre-0084 blockers only.
   - Scope: `erp_sync` must-fix subset + `reconciliation` + `reconciliation_bridge`.
   - Reason: these are the most likely dependencies for `accounting_jv_aggregates` source lineage and posting reconciliation.

2. `0084_accounting_layer_foundation.py`
   - Accounting-layer core tables (already planned in unified sequence).
   - Can safely reference entity-scoped source tables established in 0083.

3. `0085_entity_id_category1_assets_revenue_lease_prepaid.py`
   - Scope: `fixed_assets`, `lease`, `prepaid`, `revenue`, `cash_flow_engine`.

4. `0086_entity_id_category2_analytics_reporting_batch1.py`
   - Scope: `mis_manager`, `ratio_variance_engine`, `financial_risk_engine`, `working_capital`, `custom_report_builder`, `board_pack_generator`, `board_pack_narrative_engine`.

5. `0087_entity_id_category2_consolidation_batch2.py`
   - Scope: `consolidation`, `multi_entity_consolidation`, `ownership_consolidation`, `equity_engine`, `fx_translation_reporting`, `fx_rates`.

6. `0088_entity_id_category2_ops_batch3.py`
   - Scope: `anomaly_pattern_engine`, `monthend`, `payroll_gl_normalization`, `payroll_gl_reconciliation`, `auditor`.

Implementation note for each migration:
- Use add-as-null -> tenant-entity backfill -> validate no nulls -> set NOT NULL (where required).
- Add FK to `cp_entities`.
- Add index on `(tenant_id, entity_id)` for query paths.
- Preserve append-only semantics on history tables (no update/delete behavior changes).

## Pre-0084 blockers
If `accounting_jv_aggregates` depends on ERP-source lineage, these tables must be fixed in `0083` before `0084`:

- `external_raw_snapshots`
- `external_normalized_snapshots`
- `external_mapping_definitions`
- `external_mapping_versions`
- `external_sync_errors`
- `external_sync_publish_events`
- `external_sync_evidence_links`
- `gl_entries`
- `trial_balance_rows`
- `recon_items`
- `reconciliation_lines`
- `reconciliation_exceptions`

If accounting-layer FK design does not directly reference these tables, `0083` can be narrowed, but reconciliation query paths should still be entity-scoped before onboarding multi-entity customers.
