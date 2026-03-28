# Unified Migration Sequence
## Current head after entity_id pre-blockers: 0083

## Completed migrations (0001-0082)
[already in place - do not modify]

## Phase: entity_id pre-blockers
| Number | Filename | Scope |
|--------|----------|-------|
| 0083 | entity_id_accounting_blockers | erp_sync subset + reconciliation |

## Phase: ERP OAuth + accounting layer foundation
| Number | Filename | Plan | Key tables |
|--------|----------|------|------------|
| 0084 | erp_oauth_sessions_and_connection_hardening | Plan B P1.1 | erp_oauth_sessions |
| 0085 | accounting_jv_aggregate_core | Plan A Phase 2 | accounting_jv_aggregates, accounting_jv_lines |
| 0086 | accounting_jv_state_machine_events | Plan A Phase 2 | accounting_jv_state_events |
| 0087 | accounting_approval_and_sla | Plan A Phase 3 | accounting_jv_approvals, approval_sla_timers |
| 0088 | accounting_vendor_and_attachment_metadata | Plan A Phase 4 | accounting_vendors, accounting_attachments |
| 0089 | accounting_duplicate_fingerprints | Plan A Phase 4 | accounting_duplicate_fingerprints |

## Phase: CoA crosswalk + ERP push foundation
| Number | Filename | Plan | Key tables |
|--------|----------|------|------------|
| 0090 | entity_id_category1_assets_revenue_lease_prepaid | entity_id Cat 1 remaining | fixed_assets, lease, prepaid, revenue, cash_flow |
| 0091 | coa_crosswalk_external_ref_extension | Plan A/B Phase 5 | erp_account_external_refs |
| 0092 | erp_push_runs_events_idempotency | Plan B P2.1 / Plan A Phase 7 | erp_push_runs, erp_push_events, erp_push_idempotency_keys |
| 0093 | accounting_tax_gst_tds_rules | Plan A Phase 8 | accounting_gst_rules, accounting_tds_rules, accounting_tax_determination_logs |

## Phase: entity_id Category 2 + ERP webhooks + ingestion
| Number | Filename | Plan | Key tables |
|--------|----------|------|------------|
| 0094 | entity_id_category2_analytics_batch1 | entity_id Cat 2 | mis, ratio_variance, risk, working_capital, board_pack |
| 0095 | entity_id_category2_consolidation_batch2 | entity_id Cat 2 | consolidation, equity, fx |
| 0096 | entity_id_category2_ops_batch3 | entity_id Cat 2 | anomaly, monthend, payroll, auditor |
| 0097 | erp_webhook_event_ingest | Plan B P3 | erp_webhook_events |
| 0098 | inbound_email_vendor_portal_intake | Plan A Phase 10 | accounting_inbound_email_messages, vendor_portal_submissions |

## Phase: notifications + reporting + RBAC
| Number | Filename | Plan | Key tables |
|--------|----------|------|------------|
| 0099 | notifications_reminder_workflow | Plan A Phase 11 | accounting_notification_events, approval_reminder_runs |
| 0100 | ap_ageing_audit_export_support | Plan A Phase 11 | accounting_ap_ageing_snapshots, accounting_audit_export_runs |
| 0101 | accounting_rbac_seed_and_policy_links | Plan A Phase 11 | RBAC seed data |

## Key rules
- One head only at all times
- Strictly sequential numbering - no gaps
- Every migration has upgrade() and downgrade()
- All entity_id columns: nullable=True in this pass
- No NOT NULL enforcement until accounting layer is live
- Next migration to write after 0083: 0084
- Accounting layer Phase 1 starts at: 0084
