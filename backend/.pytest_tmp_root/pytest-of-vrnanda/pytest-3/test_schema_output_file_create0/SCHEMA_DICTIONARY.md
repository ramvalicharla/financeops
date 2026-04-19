# FinanceOps Schema Dictionary

Generated: 2026-04-19

This file is auto-generated. Do not edit manually.
Regenerate with: `python scripts/generate_schema_docs.py`

## Tables

### accounting_ap_ageing_snapshots

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| entity_id | UUID | No | — |
| vendor_id | UUID | Yes | — |
| snapshot_date | DATE | No | — |
| fiscal_year | INTEGER | No | — |
| fiscal_period | INTEGER | No | — |
| current_amount | NUMERIC(20, 4) | No | 0 |
| overdue_1_30 | NUMERIC(20, 4) | No | 0 |
| overdue_31_60 | NUMERIC(20, 4) | No | 0 |
| overdue_61_90 | NUMERIC(20, 4) | No | 0 |
| overdue_90_plus | NUMERIC(20, 4) | No | 0 |
| total_outstanding | NUMERIC(20, 4) | No | 0 |
| currency | VARCHAR(3) | No | INR |
| data_source | VARCHAR(16) | No | ERP_PULL |
| connector_type | VARCHAR(32) | Yes | — |
| raw_data | JSONB | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `entity_id` -> `cp_entities.id`
- `vendor_id` -> `accounting_vendors.id`

**Indexes:**
- `ix_accounting_ap_ageing_snapshots_tenant_id` (tenant_id)
- `ix_ap_ageing_snapshots_snapshot_date` (tenant_id, snapshot_date)
- `ix_ap_ageing_snapshots_tenant_entity` (tenant_id, entity_id)
- `ix_ap_ageing_snapshots_vendor` (vendor_id)

---

### accounting_attachments

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| jv_id | UUID | Yes | — |
| vendor_id | UUID | Yes | — |
| r2_key | VARCHAR(512) | No | — |
| r2_bucket | VARCHAR(128) | Yes | — |
| filename | VARCHAR(256) | No | — |
| mime_type | VARCHAR(128) | No | — |
| file_size_bytes | BIGINT | No | — |
| sha256_hash | VARCHAR(64) | No | — |
| document_type | VARCHAR(32) | Yes | — |
| worm_locked | BOOLEAN | No | False |
| worm_locked_at | DATETIME | Yes | — |
| scan_status | VARCHAR(16) | Yes | — |
| scan_completed_at | DATETIME | Yes | — |
| uploaded_by | UUID | No | — |
| uploaded_at | DATETIME | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `jv_id` -> `accounting_jv_aggregates.id`
- `uploaded_by` -> `iam_users.id`
- `vendor_id` -> `accounting_vendors.id`

**Indexes:**
- `ix_accounting_attachments_jv_id` (jv_id)
- `ix_accounting_attachments_tenant_id` (tenant_id)
- `ix_accounting_attachments_vendor_id` (vendor_id)

---

### accounting_audit_export_runs

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| entity_id | UUID | Yes | — |
| export_type | VARCHAR(32) | No | — |
| export_format | VARCHAR(8) | No | — |
| fiscal_year | INTEGER | Yes | — |
| fiscal_period_from | INTEGER | Yes | — |
| fiscal_period_to | INTEGER | Yes | — |
| date_from | DATE | Yes | — |
| date_to | DATE | Yes | — |
| filters | JSONB | Yes | — |
| status | VARCHAR(16) | No | PENDING |
| r2_key | VARCHAR(512) | Yes | — |
| row_count | INTEGER | Yes | — |
| error_message | TEXT | Yes | — |
| requested_by | UUID | No | — |
| completed_at | DATETIME | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `entity_id` -> `cp_entities.id`
- `requested_by` -> `iam_users.id`

**Indexes:**
- `ix_accounting_audit_export_runs_tenant_id` (tenant_id)
- `ix_audit_export_runs_entity` (entity_id)
- `ix_audit_export_runs_requested_by` (requested_by)
- `ix_audit_export_runs_tenant` (tenant_id)

---

### accounting_duplicate_fingerprints

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| attachment_id | UUID | No | — |
| jv_id | UUID | Yes | — |
| detection_layer | INTEGER | No | — |
| file_hash | VARCHAR(64) | Yes | — |
| invoice_number | VARCHAR(128) | Yes | — |
| vendor_gstin | VARCHAR(15) | Yes | — |
| layer2_fingerprint | VARCHAR(64) | Yes | — |
| vendor_id | UUID | Yes | — |
| amount_bucket | NUMERIC(20, 4) | Yes | — |
| date_bucket | DATE | Yes | — |
| layer3_fingerprint | VARCHAR(64) | Yes | — |
| conflict_attachment_id | UUID | Yes | — |
| conflict_jv_id | UUID | Yes | — |
| action | VARCHAR(16) | No | FLAGGED |
| action_reason | TEXT | Yes | — |
| action_by | UUID | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `action_by` -> `iam_users.id`
- `attachment_id` -> `accounting_attachments.id`
- `conflict_attachment_id` -> `accounting_attachments.id`
- `conflict_jv_id` -> `accounting_jv_aggregates.id`
- `jv_id` -> `accounting_jv_aggregates.id`

**Indexes:**
- `ix_accounting_duplicate_fingerprints_attachment_id` (attachment_id)
- `ix_accounting_duplicate_fingerprints_tenant_id` (tenant_id)

---

### accounting_fx_revaluation_lines

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| run_id | UUID | No | — |
| account_code | VARCHAR(50) | No | — |
| account_name | VARCHAR(300) | No | — |
| transaction_currency | VARCHAR(3) | No | — |
| functional_currency | VARCHAR(3) | No | — |
| foreign_balance | NUMERIC(20, 8) | No | — |
| historical_base_balance | NUMERIC(20, 8) | No | — |
| closing_rate | NUMERIC(20, 8) | No | — |
| revalued_base_balance | NUMERIC(20, 8) | No | — |
| fx_difference | NUMERIC(20, 8) | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `run_id` -> `accounting_fx_revaluation_runs.id`

**Indexes:**
- `ix_accounting_fx_revaluation_lines_run_id` (run_id)
- `ix_accounting_fx_revaluation_lines_tenant_id` (tenant_id)

---

### accounting_fx_revaluation_runs

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| entity_id | UUID | No | — |
| as_of_date | DATE | No | — |
| status | VARCHAR(16) | No | — |
| closing_rate_source | VARCHAR(32) | Yes | — |
| initiated_by | UUID | No | — |
| adjustment_jv_id | UUID | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `adjustment_jv_id` -> `accounting_jv_aggregates.id`
- `entity_id` -> `cp_entities.id`
- `initiated_by` -> `iam_users.id`

**Indexes:**
- `ix_accounting_fx_revaluation_runs_entity_id` (entity_id)
- `ix_accounting_fx_revaluation_runs_tenant_id` (tenant_id)

---

### accounting_governance_audit_events

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| entity_id | UUID | Yes | — |
| module | VARCHAR(64) | No | — |
| action | VARCHAR(64) | No | — |
| actor_user_id | UUID | No | — |
| target_id | VARCHAR(128) | No | — |
| payload_json | JSONB | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `actor_user_id` -> `iam_users.id`
- `entity_id` -> `cp_entities.id`

**Indexes:**
- `ix_accounting_governance_audit_events_action` (tenant_id, action)
- `ix_accounting_governance_audit_events_module` (tenant_id, module)
- `ix_accounting_governance_audit_events_target` (tenant_id, target_id)
- `ix_accounting_governance_audit_events_tenant_id` (tenant_id)

---

### accounting_gst_rules

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| entity_id | UUID | No | — |
| account_code | VARCHAR(32) | Yes | — |
| gst_type | VARCHAR(8) | No | — |
| gst_rate | NUMERIC(10, 4) | No | — |
| hsn_sac_code | VARCHAR(8) | Yes | — |
| description | TEXT | Yes | — |
| is_active | BOOLEAN | No | True |
| effective_from | DATE | No | — |
| effective_to | DATE | Yes | — |
| created_by | UUID | No | — |
| updated_at | DATETIME | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `created_by` -> `iam_users.id`
- `entity_id` -> `cp_entities.id`

**Indexes:**
- `ix_accounting_gst_rules_entity_id` (entity_id)
- `ix_accounting_gst_rules_tenant_id` (tenant_id)

---

### accounting_inbound_email_messages

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| entity_id | UUID | Yes | — |
| message_id | VARCHAR(512) | No | — |
| sender_email | VARCHAR(256) | No | — |
| sender_name | VARCHAR(256) | Yes | — |
| subject | TEXT | Yes | — |
| sender_whitelisted | BOOLEAN | No | False |
| processing_status | VARCHAR(32) | No | PENDING |
| processed_at | DATETIME | Yes | — |
| processing_error | TEXT | Yes | — |
| attachment_count | INTEGER | No | 0 |
| auto_reply_sent | BOOLEAN | No | False |
| raw_metadata | JSONB | Yes | — |
| received_at | DATETIME | No | now() |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `entity_id` -> `cp_entities.id`

**Indexes:**
- `ix_accounting_inbound_email_messages_entity_id` (entity_id)
- `ix_accounting_inbound_email_messages_tenant_id` (tenant_id)
- `ix_inbound_email_sender` (tenant_id, sender_email)
- `ix_inbound_email_status` (tenant_id, processing_status)

---

### accounting_jv_aggregates

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| entity_id | UUID | No | — |
| location_id | UUID | Yes | — |
| cost_centre_id | UUID | Yes | — |
| jv_number | VARCHAR(64) | No | — |
| status | VARCHAR(32) | No | DRAFT |
| version | INTEGER | No | 1 |
| period_date | DATE | No | — |
| fiscal_year | INTEGER | No | — |
| fiscal_period | INTEGER | No | — |
| description | TEXT | Yes | — |
| reference | VARCHAR(128) | Yes | — |
| source | VARCHAR(16) | No | MANUAL |
| external_reference_id | VARCHAR(128) | Yes | — |
| total_debit | NUMERIC(20, 4) | No | 0 |
| total_credit | NUMERIC(20, 4) | No | 0 |
| currency | VARCHAR(3) | No | INR |
| workflow_instance_id | UUID | Yes | — |
| created_by | UUID | No | — |
| created_by_intent_id | UUID | Yes | — |
| recorded_by_job_id | UUID | Yes | — |
| resubmission_count | INTEGER | No | 0 |
| voided_by | UUID | Yes | — |
| void_reason | TEXT | Yes | — |
| voided_at | DATETIME | Yes | — |
| submitted_at | DATETIME | Yes | — |
| first_reviewed_at | DATETIME | Yes | — |
| decided_at | DATETIME | Yes | — |
| updated_at | DATETIME | No | now() |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `cost_centre_id` -> `cp_cost_centres.id`
- `created_by` -> `iam_users.id`
- `created_by_intent_id` -> `canonical_intents.id`
- `entity_id` -> `cp_entities.id`
- `location_id` -> `cp_locations.id`
- `recorded_by_job_id` -> `canonical_jobs.id`
- `workflow_instance_id` -> `cp_workflow_instances.id`

**Indexes:**
- `ix_accounting_jv_aggregates_created_by_intent_id` (created_by_intent_id)
- `ix_accounting_jv_aggregates_entity_id` (entity_id)
- `ix_accounting_jv_aggregates_recorded_by_job_id` (recorded_by_job_id)
- `ix_accounting_jv_aggregates_tenant_id` (tenant_id)

---

### accounting_jv_approvals

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| jv_id | UUID | No | — |
| jv_version | INTEGER | No | — |
| acted_by | UUID | No | — |
| delegated_from | UUID | Yes | — |
| actor_role | VARCHAR(64) | No | — |
| decision | VARCHAR(16) | No | — |
| decision_reason | TEXT | Yes | — |
| approval_level | INTEGER | No | 1 |
| amount_threshold | NUMERIC(20, 4) | Yes | — |
| created_by_intent_id | UUID | Yes | — |
| recorded_by_job_id | UUID | Yes | — |
| idempotency_key | VARCHAR(128) | No | — |
| request_fingerprint | VARCHAR(64) | Yes | — |
| acted_at | DATETIME | No | now() |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `acted_by` -> `iam_users.id`
- `created_by_intent_id` -> `canonical_intents.id`
- `delegated_from` -> `iam_users.id`
- `jv_id` -> `accounting_jv_aggregates.id`
- `recorded_by_job_id` -> `canonical_jobs.id`

**Indexes:**
- `ix_accounting_jv_approvals_acted_by` (acted_by)
- `ix_accounting_jv_approvals_created_by_intent_id` (created_by_intent_id)
- `ix_accounting_jv_approvals_jv_id` (jv_id)
- `ix_accounting_jv_approvals_recorded_by_job_id` (recorded_by_job_id)
- `ix_accounting_jv_approvals_tenant_id` (tenant_id)

---

### accounting_jv_lines

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| jv_id | UUID | No | — |
| jv_version | INTEGER | No | — |
| line_number | INTEGER | No | — |
| account_code | VARCHAR(32) | No | — |
| account_name | VARCHAR(256) | Yes | — |
| entry_type | VARCHAR(6) | No | — |
| amount | NUMERIC(20, 4) | No | — |
| currency | VARCHAR(3) | No | INR |
| transaction_currency | VARCHAR(3) | Yes | — |
| functional_currency | VARCHAR(3) | Yes | — |
| fx_rate | NUMERIC(20, 8) | Yes | — |
| amount_inr | NUMERIC(20, 4) | Yes | — |
| base_amount | NUMERIC(20, 4) | Yes | — |
| entity_id | UUID | No | — |
| location_id | UUID | Yes | — |
| cost_centre_id | UUID | Yes | — |
| narration | TEXT | Yes | — |
| tax_code | VARCHAR(32) | Yes | — |
| is_tax_line | BOOLEAN | No | False |
| created_by_intent_id | UUID | Yes | — |
| recorded_by_job_id | UUID | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `cost_centre_id` -> `cp_cost_centres.id`
- `created_by_intent_id` -> `canonical_intents.id`
- `entity_id` -> `cp_entities.id`
- `jv_id` -> `accounting_jv_aggregates.id`
- `location_id` -> `cp_locations.id`
- `recorded_by_job_id` -> `canonical_jobs.id`

**Indexes:**
- `ix_accounting_jv_lines_created_by_intent_id` (created_by_intent_id)
- `ix_accounting_jv_lines_jv_id` (jv_id)
- `ix_accounting_jv_lines_recorded_by_job_id` (recorded_by_job_id)
- `ix_accounting_jv_lines_tenant_id` (tenant_id)

---

### accounting_jv_state_events

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| jv_id | UUID | No | — |
| jv_version | INTEGER | No | — |
| from_status | VARCHAR(32) | No | — |
| to_status | VARCHAR(32) | No | — |
| triggered_by | UUID | No | — |
| actor_role | VARCHAR(64) | Yes | — |
| comment | TEXT | Yes | — |
| created_by_intent_id | UUID | Yes | — |
| recorded_by_job_id | UUID | Yes | — |
| occurred_at | DATETIME | No | now() |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `created_by_intent_id` -> `canonical_intents.id`
- `jv_id` -> `accounting_jv_aggregates.id`
- `recorded_by_job_id` -> `canonical_jobs.id`
- `triggered_by` -> `iam_users.id`

**Indexes:**
- `ix_accounting_jv_state_events_created_by_intent_id` (created_by_intent_id)
- `ix_accounting_jv_state_events_jv_id` (jv_id)
- `ix_accounting_jv_state_events_recorded_by_job_id` (recorded_by_job_id)
- `ix_accounting_jv_state_events_tenant_id` (tenant_id)

---

### accounting_notification_events

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| jv_id | UUID | Yes | — |
| recipient_user_id | UUID | No | — |
| notification_type | VARCHAR(64) | No | — |
| channel | VARCHAR(16) | No | — |
| subject | VARCHAR(256) | Yes | — |
| body | TEXT | Yes | — |
| metadata | JSONB | Yes | — |
| sent_at | DATETIME | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `jv_id` -> `accounting_jv_aggregates.id`
- `recipient_user_id` -> `iam_users.id`

**Indexes:**
- `ix_accounting_notification_events_jv_id` (jv_id)
- `ix_accounting_notification_events_recipient` (recipient_user_id)
- `ix_accounting_notification_events_tenant` (tenant_id)
- `ix_accounting_notification_events_tenant_id` (tenant_id)

---

### accounting_periods

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| org_entity_id | UUID | Yes | — |
| fiscal_year | INTEGER | No | — |
| period_number | INTEGER | No | — |
| period_start | DATE | No | — |
| period_end | DATE | No | — |
| status | VARCHAR(16) | No | OPEN |
| locked_by | UUID | Yes | — |
| locked_at | DATETIME | Yes | — |
| reopened_by | UUID | Yes | — |
| reopened_at | DATETIME | Yes | — |
| notes | TEXT | Yes | — |
| created_at | DATETIME | No | now() |
| updated_at | DATETIME | Yes | now() |

**Foreign keys:**
- `locked_by` -> `iam_users.id`
- `org_entity_id` -> `cp_entities.id`
- `reopened_by` -> `iam_users.id`
- `tenant_id` -> `iam_tenants.id`

**Indexes:**
- `ix_accounting_periods_tenant` (tenant_id)
- `ix_accounting_periods_tenant_entity_period` (tenant_id, org_entity_id, fiscal_year, period_number)
- `uq_accounting_periods_tenant_global_period` (tenant_id, fiscal_year, period_number)

---

### accounting_tax_determination_logs

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| jv_id | UUID | No | — |
| jv_version | INTEGER | No | — |
| tax_type | VARCHAR(16) | No | — |
| gst_sub_type | VARCHAR(8) | Yes | — |
| tds_section | VARCHAR(16) | Yes | — |
| supplier_state_code | VARCHAR(2) | Yes | — |
| buyer_state_code | VARCHAR(2) | Yes | — |
| base_amount | NUMERIC(20, 4) | No | — |
| tax_amount | NUMERIC(20, 4) | No | — |
| cgst_amount | NUMERIC(20, 4) | Yes | — |
| sgst_amount | NUMERIC(20, 4) | Yes | — |
| igst_amount | NUMERIC(20, 4) | Yes | — |
| tds_amount | NUMERIC(20, 4) | Yes | — |
| outcome | VARCHAR(16) | No | — |
| outcome_reason | TEXT | Yes | — |
| gst_rule_id | UUID | Yes | — |
| tds_rule_id | UUID | Yes | — |
| determined_at | DATETIME | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `gst_rule_id` -> `accounting_gst_rules.id`
- `jv_id` -> `accounting_jv_aggregates.id`
- `tds_rule_id` -> `accounting_tds_rules.id`

**Indexes:**
- `ix_accounting_tax_determination_logs_jv_id` (jv_id)
- `ix_accounting_tax_determination_logs_tenant_id` (tenant_id)

---

### accounting_tds_rules

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| entity_id | UUID | No | — |
| vendor_id | UUID | Yes | — |
| tds_section | VARCHAR(16) | No | — |
| section_description | VARCHAR(256) | Yes | — |
| tds_rate | NUMERIC(10, 4) | No | — |
| threshold_amount | NUMERIC(20, 4) | Yes | — |
| surcharge_rate | NUMERIC(10, 4) | No | 0 |
| cess_rate | NUMERIC(10, 4) | No | 0 |
| is_active | BOOLEAN | No | True |
| effective_from | DATE | No | — |
| effective_to | DATE | Yes | — |
| created_by | UUID | No | — |
| updated_at | DATETIME | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `created_by` -> `iam_users.id`
- `entity_id` -> `cp_entities.id`
- `vendor_id` -> `accounting_vendors.id`

**Indexes:**
- `ix_accounting_tds_rules_entity_id` (entity_id)
- `ix_accounting_tds_rules_tenant_id` (tenant_id)
- `ix_accounting_tds_rules_vendor_id` (vendor_id)

---

### accounting_vendors

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| entity_id | UUID | No | — |
| vendor_name | VARCHAR(256) | No | — |
| vendor_code | VARCHAR(64) | Yes | — |
| gstin | VARCHAR(15) | Yes | — |
| pan | VARCHAR(10) | Yes | — |
| tan | VARCHAR(10) | Yes | — |
| tds_section | VARCHAR(16) | Yes | — |
| tds_rate | NUMERIC(10, 4) | Yes | — |
| tds_threshold | NUMERIC(20, 4) | Yes | — |
| email | VARCHAR(256) | Yes | — |
| phone | VARCHAR(32) | Yes | — |
| address | TEXT | Yes | — |
| state_code | VARCHAR(2) | Yes | — |
| is_active | BOOLEAN | No | True |
| erp_vendor_id | VARCHAR(128) | Yes | — |
| erp_connector_type | VARCHAR(32) | Yes | — |
| created_by | UUID | No | — |
| updated_at | DATETIME | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `created_by` -> `iam_users.id`
- `entity_id` -> `cp_entities.id`

**Indexes:**
- `ix_accounting_vendors_entity_id` (entity_id)
- `ix_accounting_vendors_tenant_id` (tenant_id)

---

### acct_common_test_run_events

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| run_id | UUID | No | — |
| event_seq | INTEGER | No | — |
| event_type | VARCHAR(64) | No | — |
| event_time | DATETIME | No | <function LifecycleTestRunEvent.<lambda> at 0x00000272B55A8E00> |
| idempotency_key | VARCHAR(128) | No | — |
| metadata_json | JSONB | Yes | — |
| correlation_id | VARCHAR(64) | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `run_id` -> `acct_common_test_runs.id`

**Indexes:**
- `ix_acct_common_test_run_events_tenant_id` (tenant_id)

---

### acct_common_test_runs

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| initiated_by | UUID | No | — |
| request_signature | VARCHAR(64) | No | — |
| configuration_json | JSONB | No | — |
| workflow_id | VARCHAR(128) | No | — |
| correlation_id | VARCHAR(64) | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Indexes:**
- `ix_acct_common_test_runs_tenant_id` (tenant_id)

---

### ai_benchmark_results

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: No
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| benchmark_name | VARCHAR(100) | No | — |
| benchmark_version | VARCHAR(20) | No | 1.0 |
| model | VARCHAR(100) | No | — |
| provider | VARCHAR(30) | No | — |
| total_cases | INTEGER | No | — |
| passed_cases | INTEGER | No | — |
| accuracy_pct | NUMERIC(5, 4) | No | — |
| avg_latency_ms | NUMERIC(8, 2) | No | — |
| total_cost_usd | NUMERIC(10, 6) | No | — |
| run_at | DATETIME | No | now() |
| run_by | VARCHAR(100) | No | — |
| details | JSONB | No | <function dict at 0x00000272FAF3FBA0> |

**Indexes:**
- `idx_ai_benchmark_results_name_run` (benchmark_name, run_at)

---

### ai_cfo_ledger

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| feature | VARCHAR(64) | No | — |
| provider | VARCHAR(32) | No | — |
| model | VARCHAR(64) | No | — |
| prompt_tokens | INTEGER | No | 0 |
| completion_tokens | INTEGER | No | 0 |
| cost_usd | NUMERIC(10, 6) | No | — |
| created_at | DATETIME | No | now() |

**Foreign keys:**
- `tenant_id` -> `iam_tenants.id`

**Indexes:**
- `ix_ai_cfo_ledger_tenant_created` (tenant_id, created_at)
- `ix_ai_cfo_ledger_tenant_provider` (tenant_id, provider)

---

### ai_cfo_narrative_blocks

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| created_by | UUID | Yes | — |
| provider | VARCHAR(32) | No | — |
| llm_model | VARCHAR(64) | No | — |
| summary | TEXT | No | — |
| highlights_json | JSONB | No | <function list at 0x00000272F997EB60> |
| drivers_json | JSONB | No | <function list at 0x00000272F997EE80> |
| risks_json | JSONB | No | <function list at 0x00000272F997EF20> |
| actions_json | JSONB | No | <function list at 0x00000272F997EFC0> |
| fact_basis_json | JSONB | No | <function dict at 0x00000272F997F060> |
| created_at | DATETIME | No | now() |

**Foreign keys:**
- `created_by` -> `iam_users.id`
- `tenant_id` -> `iam_tenants.id`

**Indexes:**
- `ix_ai_cfo_narrative_blocks_tenant_created` (tenant_id, created_at)
- `ix_ai_cfo_narrative_blocks_tenant_provider` (tenant_id, provider)

---

### ai_cost_events

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| task_type | VARCHAR(50) | No | — |
| provider | VARCHAR(30) | No | — |
| model | VARCHAR(100) | No | — |
| prompt_tokens | INTEGER | No | — |
| completion_tokens | INTEGER | No | — |
| total_tokens | INTEGER | No | — |
| cost_usd | NUMERIC(10, 6) | No | — |
| was_cached | BOOLEAN | No | false |
| was_fallback | BOOLEAN | No | false |
| pii_was_masked | BOOLEAN | No | false |
| pipeline_run_id | UUID | Yes | — |
| created_at | DATETIME | No | now() |

**Foreign keys:**
- `tenant_id` -> `iam_tenants.id`

**Indexes:**
- `idx_ai_cost_events_tenant_created` (tenant_id)

---

### ai_prompt_versions

- **Description**: Versioned AI prompt store. Active prompts are loaded at runtime.
- **RLS enabled**: No
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| prompt_key | VARCHAR(128) | No | — |
| version | INTEGER | No | — |
| prompt_text | TEXT | No | — |
| model_target | VARCHAR(128) | No | — |
| is_active | BOOLEAN | No | True |
| performance_notes | TEXT | Yes | — |
| activated_by | UUID | Yes | — |
| activated_at | DATETIME | Yes | — |
| deactivated_at | DATETIME | Yes | — |
| acceptance_rate | NUMERIC(5, 4) | Yes | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Indexes:**
- `ix_ai_prompt_versions_prompt_key` (prompt_key)

---

### airlock_events

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| airlock_item_id | UUID | No | — |
| event_type | VARCHAR(64) | No | — |
| from_status | VARCHAR(32) | Yes | — |
| to_status | VARCHAR(32) | Yes | — |
| actor_user_id | UUID | Yes | — |
| actor_role | VARCHAR(64) | Yes | — |
| event_at | DATETIME | No | now() |
| event_payload_json | JSONB | No | <function dict at 0x00000272F9924AE0> |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `actor_user_id` -> `iam_users.id`
- `airlock_item_id` -> `airlock_items.id`

**Indexes:**
- `ix_airlock_events_item` (tenant_id, airlock_item_id, created_at)
- `ix_airlock_events_tenant_id` (tenant_id)
- `ix_airlock_events_type` (tenant_id, event_type, created_at)

---

### airlock_items

- **Description**: Abstract base with UUID PK and created_at.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| tenant_id | UUID | No | — |
| entity_id | UUID | Yes | — |
| source_type | VARCHAR(64) | No | — |
| source_reference | VARCHAR(255) | Yes | — |
| file_name | VARCHAR(255) | Yes | — |
| mime_type | VARCHAR(128) | Yes | — |
| size_bytes | INTEGER | Yes | — |
| checksum_sha256 | VARCHAR(64) | Yes | — |
| quarantine_ref | VARCHAR(512) | Yes | — |
| status | VARCHAR(32) | No | 'RECEIVED' |
| submitted_by_user_id | UUID | No | — |
| reviewed_by_user_id | UUID | Yes | — |
| admitted_by_user_id | UUID | Yes | — |
| submitted_at | DATETIME | No | now() |
| reviewed_at | DATETIME | Yes | — |
| admitted_at | DATETIME | Yes | — |
| rejected_at | DATETIME | Yes | — |
| rejection_reason | TEXT | Yes | — |
| metadata_json | JSONB | No | <function dict at 0x00000272F9902F20> |
| findings_json | JSONB | No | <function list at 0x00000272F99247C0> |
| idempotency_key | VARCHAR(128) | No | — |
| updated_at | DATETIME | No | now() |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `admitted_by_user_id` -> `iam_users.id`
- `entity_id` -> `cp_entities.id`
- `reviewed_by_user_id` -> `iam_users.id`
- `submitted_by_user_id` -> `iam_users.id`

**Indexes:**
- `ix_airlock_items_entity` (tenant_id, entity_id, submitted_at)
- `ix_airlock_items_lookup` (tenant_id, source_type, status, submitted_at)
- `ix_airlock_items_tenant_id` (tenant_id)

---

### analytics_alerts

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| metric_name | VARCHAR(64) | No | — |
| threshold | NUMERIC(24, 6) | No | — |
| condition | VARCHAR(16) | No | — |
| description | TEXT | Yes | — |
| created_at | DATETIME | No | now() |

**Foreign keys:**
- `tenant_id` -> `iam_tenants.id`

**Indexes:**
- `ix_analytics_alerts_tenant_created` (tenant_id, created_at)
- `ix_analytics_alerts_tenant_metric` (tenant_id, metric_name)

---

### analytics_anomalies

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| org_entity_id | UUID | Yes | — |
| org_group_id | UUID | Yes | — |
| metric_name | VARCHAR(64) | No | — |
| anomaly_type | VARCHAR(64) | No | — |
| deviation_value | NUMERIC(24, 6) | No | — |
| severity | VARCHAR(16) | No | — |
| fact_json | JSONB | No | <function dict at 0x00000272F9952B60> |
| lineage_json | JSONB | No | <function dict at 0x00000272F9952CA0> |
| created_by | UUID | Yes | — |
| created_at | DATETIME | No | now() |

**Foreign keys:**
- `created_by` -> `iam_users.id`
- `org_entity_id` -> `cp_entities.id`
- `org_group_id` -> `cp_groups.id`
- `tenant_id` -> `iam_tenants.id`

**Indexes:**
- `ix_analytics_anomalies_tenant_created` (tenant_id, created_at)
- `ix_analytics_anomalies_tenant_metric` (tenant_id, metric_name)

---

### analytics_metrics

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| metric_name | VARCHAR(64) | No | — |
| metric_value | NUMERIC(24, 6) | No | — |
| dimension_json | JSONB | No | <function dict at 0x00000272AAE95E40> |
| created_at | DATETIME | No | now() |

**Foreign keys:**
- `tenant_id` -> `iam_tenants.id`

**Indexes:**
- `ix_analytics_metrics_tenant_created` (tenant_id, created_at)
- `ix_analytics_metrics_tenant_metric` (tenant_id, metric_name)

---

### analytics_recommendations

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| org_entity_id | UUID | Yes | — |
| org_group_id | UUID | Yes | — |
| recommendation_type | VARCHAR(64) | No | — |
| message | TEXT | No | — |
| severity | VARCHAR(16) | No | — |
| evidence_json | JSONB | No | <function dict at 0x00000272F997C680> |
| created_by | UUID | Yes | — |
| created_at | DATETIME | No | now() |

**Foreign keys:**
- `created_by` -> `iam_users.id`
- `org_entity_id` -> `cp_entities.id`
- `org_group_id` -> `cp_groups.id`
- `tenant_id` -> `iam_tenants.id`

**Indexes:**
- `ix_analytics_recommendations_tenant_created` (tenant_id, created_at)
- `ix_analytics_recommendations_tenant_type` (tenant_id, recommendation_type)

---

### analytics_snapshots

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| org_entity_id | UUID | Yes | — |
| org_group_id | UUID | Yes | — |
| snapshot_type | VARCHAR(16) | No | — |
| as_of_date | DATE | No | — |
| period_from | DATE | Yes | — |
| period_to | DATE | Yes | — |
| data_json | JSONB | No | <function dict at 0x00000272AAE945E0> |
| created_at | DATETIME | No | now() |

**Foreign keys:**
- `org_entity_id` -> `cp_entities.id`
- `org_group_id` -> `cp_groups.id`
- `tenant_id` -> `iam_tenants.id`

**Indexes:**
- `ix_analytics_snapshots_entity` (tenant_id, org_entity_id)
- `ix_analytics_snapshots_group` (tenant_id, org_group_id)
- `ix_analytics_snapshots_tenant` (tenant_id)
- `ix_analytics_snapshots_type_date` (tenant_id, snapshot_type, as_of_date)

---

### analytics_variances

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| metric_name | VARCHAR(64) | No | — |
| current_value | NUMERIC(24, 6) | No | — |
| previous_value | NUMERIC(24, 6) | No | — |
| variance_value | NUMERIC(24, 6) | No | — |
| variance_percent | NUMERIC(24, 6) | Yes | — |
| dimension_json | JSONB | No | <function dict at 0x00000272AAE96DE0> |
| created_at | DATETIME | No | now() |

**Foreign keys:**
- `tenant_id` -> `iam_tenants.id`

**Indexes:**
- `ix_analytics_variances_tenant_created` (tenant_id, created_at)
- `ix_analytics_variances_tenant_metric` (tenant_id, metric_name)

---

### anomaly_contributing_signals

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| run_id | UUID | No | — |
| anomaly_result_id | UUID | No | — |
| signal_type | VARCHAR(64) | No | — |
| signal_ref | TEXT | No | — |
| contribution_weight | NUMERIC(12, 6) | No | — |
| contribution_score | NUMERIC(12, 6) | No | — |
| signal_payload_json | JSONB | No | <function dict at 0x00000272FA4C20C0> |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `anomaly_result_id` -> `anomaly_results.id`
- `run_id` -> `anomaly_runs.id`

**Indexes:**
- `idx_anomaly_contributing_signals_run` (tenant_id, run_id, anomaly_result_id, id)
- `ix_anomaly_contributing_signals_tenant_id` (tenant_id)

---

### anomaly_correlation_rules

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| organisation_id | UUID | No | — |
| rule_code | VARCHAR(128) | No | — |
| rule_name | VARCHAR(255) | No | — |
| correlation_window | INTEGER | No | — |
| min_signal_count | INTEGER | No | — |
| correlation_logic_json | JSONB | No | <function dict at 0x00000272FA446A20> |
| version_token | VARCHAR(64) | No | — |
| effective_from | DATE | No | — |
| supersedes_id | UUID | Yes | — |
| status | VARCHAR(32) | No | candidate |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `supersedes_id` -> `anomaly_correlation_rules.id`

**Indexes:**
- `idx_anomaly_correlation_rules_lookup` (tenant_id, organisation_id, rule_code, effective_from, created_at)
- `ix_anomaly_correlation_rules_tenant_id` (tenant_id)
- `uq_anomaly_correlation_rules_one_active` (tenant_id, organisation_id, rule_code)

---

### anomaly_definitions

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| organisation_id | UUID | No | — |
| anomaly_code | VARCHAR(128) | No | — |
| anomaly_name | VARCHAR(255) | No | — |
| anomaly_domain | VARCHAR(64) | No | — |
| signal_selector_json | JSONB | No | <function dict at 0x00000272FA412700> |
| definition_json | JSONB | No | <function dict at 0x00000272FA4127A0> |
| version_token | VARCHAR(64) | No | — |
| effective_from | DATE | No | — |
| effective_to | DATE | Yes | — |
| supersedes_id | UUID | Yes | — |
| status | VARCHAR(32) | No | candidate |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `supersedes_id` -> `anomaly_definitions.id`

**Indexes:**
- `idx_anomaly_definitions_lookup` (tenant_id, organisation_id, anomaly_code, effective_from, created_at)
- `ix_anomaly_definitions_tenant_id` (tenant_id)
- `uq_anomaly_definitions_one_active` (tenant_id, organisation_id, anomaly_code)

---

### anomaly_evidence_links

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| run_id | UUID | No | — |
| anomaly_result_id | UUID | No | — |
| evidence_type | VARCHAR(64) | No | — |
| evidence_ref | TEXT | No | — |
| evidence_label | VARCHAR(255) | No | — |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `anomaly_result_id` -> `anomaly_results.id`
- `run_id` -> `anomaly_runs.id`

**Indexes:**
- `idx_anomaly_evidence_links_result` (tenant_id, run_id, anomaly_result_id)
- `idx_anomaly_evidence_links_run` (tenant_id, run_id, created_at)
- `ix_anomaly_evidence_links_tenant_id` (tenant_id)

---

### anomaly_pattern_rules

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| organisation_id | UUID | No | — |
| rule_code | VARCHAR(128) | No | — |
| rule_name | VARCHAR(255) | No | — |
| pattern_signature_json | JSONB | No | <function dict at 0x00000272FA413E20> |
| classification_behavior_json | JSONB | No | <function dict at 0x00000272FA413EC0> |
| version_token | VARCHAR(64) | No | — |
| effective_from | DATE | No | — |
| supersedes_id | UUID | Yes | — |
| status | VARCHAR(32) | No | candidate |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `supersedes_id` -> `anomaly_pattern_rules.id`

**Indexes:**
- `idx_anomaly_pattern_rules_lookup` (tenant_id, organisation_id, rule_code, effective_from, created_at)
- `ix_anomaly_pattern_rules_tenant_id` (tenant_id)
- `uq_anomaly_pattern_rules_one_active` (tenant_id, organisation_id, rule_code)

---

### anomaly_persistence_rules

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| organisation_id | UUID | No | — |
| rule_code | VARCHAR(128) | No | — |
| rule_name | VARCHAR(255) | No | — |
| rolling_window | INTEGER | No | — |
| recurrence_threshold | INTEGER | No | — |
| escalation_logic_json | JSONB | No | <function dict at 0x00000272FA445440> |
| version_token | VARCHAR(64) | No | — |
| effective_from | DATE | No | — |
| supersedes_id | UUID | Yes | — |
| status | VARCHAR(32) | No | candidate |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `supersedes_id` -> `anomaly_persistence_rules.id`

**Indexes:**
- `idx_anomaly_persistence_rules_lookup` (tenant_id, organisation_id, rule_code, effective_from, created_at)
- `ix_anomaly_persistence_rules_tenant_id` (tenant_id)
- `uq_anomaly_persistence_rules_one_active` (tenant_id, organisation_id, rule_code)

---

### anomaly_results

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| run_id | UUID | No | — |
| entity_id | UUID | Yes | — |
| line_no | INTEGER | No | — |
| anomaly_code | VARCHAR(128) | No | — |
| anomaly_name | VARCHAR(255) | No | — |
| anomaly_domain | VARCHAR(64) | No | — |
| anomaly_score | NUMERIC(12, 6) | No | — |
| z_score | NUMERIC(12, 6) | Yes | — |
| severity | VARCHAR(16) | No | — |
| alert_status | VARCHAR(50) | No | OPEN |
| snoozed_until | DATETIME | Yes | — |
| resolved_at | DATETIME | Yes | — |
| escalated_at | DATETIME | Yes | — |
| status_note | TEXT | Yes | — |
| status_updated_by | UUID | Yes | — |
| persistence_classification | VARCHAR(32) | No | — |
| correlation_flag | BOOLEAN | No | False |
| materiality_elevated | BOOLEAN | No | False |
| risk_elevated | BOOLEAN | No | False |
| board_flag | BOOLEAN | No | False |
| confidence_score | NUMERIC(12, 6) | No | — |
| seasonal_adjustment_flag | BOOLEAN | No | False |
| seasonal_normalized_value | NUMERIC(20, 6) | Yes | — |
| benchmark_group_id | VARCHAR(128) | Yes | — |
| benchmark_baseline_value | NUMERIC(20, 6) | Yes | — |
| benchmark_deviation_score | NUMERIC(20, 6) | Yes | — |
| source_summary_json | JSONB | No | <function dict at 0x00000272FA47FF60> |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `entity_id` -> `cp_entities.id`
- `run_id` -> `anomaly_runs.id`

**Indexes:**
- `idx_anomaly_results_domain_severity` (tenant_id, run_id, anomaly_domain, severity)
- `idx_anomaly_results_run` (tenant_id, run_id, line_no)
- `ix_anomaly_results_entity_id` (entity_id)
- `ix_anomaly_results_tenant_id` (tenant_id)

---

### anomaly_rollforward_events

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| run_id | UUID | No | — |
| anomaly_result_id | UUID | No | — |
| event_type | VARCHAR(64) | No | — |
| event_payload_json | JSONB | No | <function dict at 0x00000272FA4C3600> |
| actor_user_id | UUID | No | — |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `anomaly_result_id` -> `anomaly_results.id`
- `run_id` -> `anomaly_runs.id`

**Indexes:**
- `idx_anomaly_rollforward_events_run` (tenant_id, run_id, anomaly_result_id, created_at)
- `ix_anomaly_rollforward_events_tenant_id` (tenant_id)

---

### anomaly_runs

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| organisation_id | UUID | No | — |
| entity_id | UUID | Yes | — |
| reporting_period | DATE | No | — |
| anomaly_definition_version_token | VARCHAR(64) | No | — |
| pattern_rule_version_token | VARCHAR(64) | No | — |
| persistence_rule_version_token | VARCHAR(64) | No | — |
| correlation_rule_version_token | VARCHAR(64) | No | — |
| statistical_rule_version_token | VARCHAR(64) | No | — |
| source_metric_run_ids_json | JSONB | No | <function list at 0x00000272FA47C540> |
| source_variance_run_ids_json | JSONB | No | <function list at 0x00000272FA47DA80> |
| source_trend_run_ids_json | JSONB | No | <function list at 0x00000272FA47DB20> |
| source_risk_run_ids_json | JSONB | No | <function list at 0x00000272FA47DBC0> |
| source_reconciliation_session_ids_json | JSONB | No | <function list at 0x00000272FA47DC60> |
| run_token | VARCHAR(64) | No | — |
| status | VARCHAR(32) | No | created |
| validation_summary_json | JSONB | No | <function dict at 0x00000272FA47DD00> |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `entity_id` -> `cp_entities.id`

**Indexes:**
- `idx_anomaly_runs_lookup` (tenant_id, organisation_id, reporting_period, created_at)
- `idx_anomaly_runs_token` (tenant_id, run_token)
- `ix_anomaly_runs_entity_id` (entity_id)
- `ix_anomaly_runs_tenant_id` (tenant_id)

---

### anomaly_statistical_rules

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| organisation_id | UUID | No | — |
| rule_code | VARCHAR(128) | No | — |
| rule_name | VARCHAR(255) | No | — |
| rolling_window | INTEGER | No | — |
| baseline_type | VARCHAR(64) | No | — |
| z_threshold | NUMERIC(12, 6) | No | — |
| regime_shift_threshold_pct | NUMERIC(12, 6) | No | — |
| seasonal_period | INTEGER | Yes | — |
| seasonal_adjustment_flag | BOOLEAN | No | False |
| benchmark_group_id | VARCHAR(128) | Yes | — |
| configuration_json | JSONB | No | <function dict at 0x00000272FA47C040> |
| version_token | VARCHAR(64) | No | — |
| effective_from | DATE | No | — |
| supersedes_id | UUID | Yes | — |
| status | VARCHAR(32) | No | candidate |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `supersedes_id` -> `anomaly_statistical_rules.id`

**Indexes:**
- `idx_anomaly_statistical_rules_lookup` (tenant_id, organisation_id, rule_code, effective_from, created_at)
- `ix_anomaly_statistical_rules_tenant_id` (tenant_id)
- `uq_anomaly_statistical_rules_one_active` (tenant_id, organisation_id, rule_code)

---

### ap_line_items

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| snapshot_id | UUID | No | — |
| tenant_id | UUID | No | — |
| vendor_name | VARCHAR(300) | No | — |
| vendor_id | VARCHAR(100) | Yes | — |
| invoice_number | VARCHAR(100) | Yes | — |
| invoice_date | DATE | Yes | — |
| due_date | DATE | Yes | — |
| days_overdue | INTEGER | No | 0 |
| amount | NUMERIC(20, 2) | No | — |
| currency | VARCHAR(3) | No | INR |
| amount_base_currency | NUMERIC(20, 2) | No | — |
| aging_bucket | VARCHAR(20) | No | — |
| early_payment_discount_available | BOOLEAN | No | False |
| early_payment_discount_pct | NUMERIC(5, 4) | Yes | — |
| created_at | DATETIME | No | now() |

**Foreign keys:**
- `snapshot_id` -> `wc_snapshots.id`

**Indexes:**
- `idx_wc2_ap_line_items_snapshot_discount` (snapshot_id, early_payment_discount_available)

---

### approval_policies

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| module_name | VARCHAR(64) | No | — |
| require_reviewer | BOOLEAN | No | True |
| require_distinct_approver | BOOLEAN | No | True |
| require_distinct_poster | BOOLEAN | No | False |
| created_at | DATETIME | No | now() |
| updated_at | DATETIME | Yes | now() |

**Foreign keys:**
- `tenant_id` -> `iam_tenants.id`

**Indexes:**
- `ix_approval_policies_tenant_module` (tenant_id, module_name)

---

### approval_reminder_runs

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| jv_id | UUID | No | — |
| reminder_type | VARCHAR(16) | No | — |
| sent_to_user_id | UUID | No | — |
| sent_at | DATETIME | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `jv_id` -> `accounting_jv_aggregates.id`
- `sent_to_user_id` -> `iam_users.id`

**Indexes:**
- `ix_approval_reminder_runs_jv_id` (jv_id)
- `ix_approval_reminder_runs_tenant` (tenant_id)
- `ix_approval_reminder_runs_tenant_id` (tenant_id)

---

### approval_sla_breach_runs

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| jv_id | UUID | No | — |
| breach_type | VARCHAR(16) | No | — |
| sent_to_user_id | UUID | No | — |
| breached_at | DATETIME | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `jv_id` -> `accounting_jv_aggregates.id`
- `sent_to_user_id` -> `iam_users.id`

**Indexes:**
- `ix_approval_sla_breach_runs_breached_at` (tenant_id, breached_at)
- `ix_approval_sla_breach_runs_jv_id` (jv_id)
- `ix_approval_sla_breach_runs_tenant` (tenant_id)
- `ix_approval_sla_breach_runs_tenant_id` (tenant_id)
- `ix_approval_sla_breach_runs_type` (tenant_id, breach_type)

---

### approval_sla_timers

- **Description**: Abstract base with UUID PK and created_at.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| tenant_id | UUID | No | — |
| jv_id | UUID | No | — |
| review_sla_hours | INTEGER | No | 24 |
| approval_sla_hours | INTEGER | No | 48 |
| review_breached | BOOLEAN | No | False |
| approval_breached | BOOLEAN | No | False |
| review_breached_at | DATETIME | Yes | — |
| approval_breached_at | DATETIME | Yes | — |
| nudge_24h_sent | BOOLEAN | No | False |
| nudge_48h_sent | BOOLEAN | No | False |
| updated_at | DATETIME | No | now() |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `jv_id` -> `accounting_jv_aggregates.id`

**Indexes:**
- `ix_approval_sla_timers_tenant_id` (tenant_id)

---

### ar_line_items

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| snapshot_id | UUID | No | — |
| tenant_id | UUID | No | — |
| customer_name | VARCHAR(300) | No | — |
| customer_id | VARCHAR(100) | Yes | — |
| invoice_number | VARCHAR(100) | Yes | — |
| invoice_date | DATE | Yes | — |
| due_date | DATE | Yes | — |
| days_overdue | INTEGER | No | 0 |
| amount | NUMERIC(20, 2) | No | — |
| currency | VARCHAR(3) | No | INR |
| amount_base_currency | NUMERIC(20, 2) | No | — |
| aging_bucket | VARCHAR(20) | No | — |
| payment_probability_score | NUMERIC(5, 4) | Yes | — |
| created_at | DATETIME | No | now() |

**Foreign keys:**
- `snapshot_id` -> `wc_snapshots.id`

**Indexes:**
- `idx_wc2_ar_line_items_snapshot_bucket` (snapshot_id, aging_bucket)
- `idx_wc2_ar_line_items_snapshot_overdue_desc` (snapshot_id)

---

### asset_depreciation_schedule

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| run_id | UUID | No | — |
| asset_id | UUID | No | — |
| period_seq | INTEGER | No | — |
| depreciation_date | DATE | No | — |
| depreciation_period_year | INTEGER | No | — |
| depreciation_period_month | INTEGER | No | — |
| schedule_version_token | VARCHAR(64) | No | — |
| opening_carrying_amount_reporting_currency | NUMERIC(20, 6) | No | — |
| depreciation_amount_reporting_currency | NUMERIC(20, 6) | No | — |
| cumulative_depreciation_reporting_currency | NUMERIC(20, 6) | No | — |
| closing_carrying_amount_reporting_currency | NUMERIC(20, 6) | No | — |
| fx_rate_used | NUMERIC(20, 6) | No | — |
| fx_rate_date | DATE | No | — |
| fx_rate_source | VARCHAR(64) | No | — |
| schedule_status | VARCHAR(32) | No | — |
| source_acquisition_reference | VARCHAR(255) | No | — |
| parent_reference_id | UUID | Yes | — |
| source_reference_id | UUID | Yes | — |
| correlation_id | VARCHAR(64) | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `asset_id` -> `assets.id`
- `run_id` -> `far_runs.id`

**Indexes:**
- `idx_asset_schedule_tenant_asset` (tenant_id, asset_id)
- `idx_asset_schedule_tenant_run` (tenant_id, run_id, depreciation_date)
- `ix_asset_depreciation_schedule_tenant_id` (tenant_id)

---

### asset_disposals

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| run_id | UUID | No | — |
| asset_id | UUID | No | — |
| disposal_date | DATE | No | — |
| proceeds_reporting_currency | NUMERIC(20, 6) | No | — |
| disposal_cost_reporting_currency | NUMERIC(20, 6) | No | — |
| carrying_amount_reporting_currency | NUMERIC(20, 6) | No | — |
| gain_loss_reporting_currency | NUMERIC(20, 6) | No | — |
| idempotency_key | VARCHAR(128) | No | — |
| prior_schedule_version_token | VARCHAR(64) | No | — |
| new_schedule_version_token | VARCHAR(64) | No | — |
| fx_rate_used | NUMERIC(20, 6) | No | — |
| fx_rate_date | DATE | No | — |
| fx_rate_source | VARCHAR(64) | No | — |
| source_acquisition_reference | VARCHAR(255) | No | — |
| parent_reference_id | UUID | Yes | — |
| source_reference_id | UUID | Yes | — |
| correlation_id | VARCHAR(64) | Yes | — |
| supersedes_id | UUID | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `asset_id` -> `assets.id`
- `run_id` -> `far_runs.id`
- `supersedes_id` -> `asset_disposals.id`

**Indexes:**
- `idx_asset_disposals_tenant_asset` (tenant_id, asset_id)
- `idx_asset_disposals_tenant_run` (tenant_id, run_id, disposal_date)
- `ix_asset_disposals_tenant_id` (tenant_id)

---

### asset_impairments

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| run_id | UUID | No | — |
| asset_id | UUID | No | — |
| impairment_date | DATE | No | — |
| impairment_amount_reporting_currency | NUMERIC(20, 6) | No | — |
| idempotency_key | VARCHAR(128) | No | — |
| prior_schedule_version_token | VARCHAR(64) | No | — |
| new_schedule_version_token | VARCHAR(64) | No | — |
| reason | TEXT | No | — |
| fx_rate_used | NUMERIC(20, 6) | No | — |
| fx_rate_date | DATE | No | — |
| fx_rate_source | VARCHAR(64) | No | — |
| source_acquisition_reference | VARCHAR(255) | No | — |
| parent_reference_id | UUID | Yes | — |
| source_reference_id | UUID | Yes | — |
| correlation_id | VARCHAR(64) | Yes | — |
| supersedes_id | UUID | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `asset_id` -> `assets.id`
- `run_id` -> `far_runs.id`
- `supersedes_id` -> `asset_impairments.id`

**Indexes:**
- `idx_asset_impairments_tenant_asset` (tenant_id, asset_id)
- `idx_asset_impairments_tenant_run` (tenant_id, run_id, impairment_date)
- `ix_asset_impairments_tenant_id` (tenant_id)

---

### asset_journal_entries

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| run_id | UUID | No | — |
| asset_id | UUID | No | — |
| depreciation_schedule_id | UUID | Yes | — |
| impairment_id | UUID | Yes | — |
| disposal_id | UUID | Yes | — |
| journal_reference | VARCHAR(128) | No | — |
| line_seq | INTEGER | No | — |
| entry_date | DATE | No | — |
| debit_account | VARCHAR(64) | No | — |
| credit_account | VARCHAR(64) | No | — |
| amount_reporting_currency | NUMERIC(20, 6) | No | — |
| source_acquisition_reference | VARCHAR(255) | No | — |
| parent_reference_id | UUID | Yes | — |
| source_reference_id | UUID | Yes | — |
| correlation_id | VARCHAR(64) | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `asset_id` -> `assets.id`
- `depreciation_schedule_id` -> `asset_depreciation_schedule.id`
- `disposal_id` -> `asset_disposals.id`
- `impairment_id` -> `asset_impairments.id`
- `run_id` -> `far_runs.id`

**Indexes:**
- `idx_asset_journal_tenant_asset` (tenant_id, asset_id)
- `idx_asset_journal_tenant_run` (tenant_id, run_id, entry_date)
- `ix_asset_journal_entries_tenant_id` (tenant_id)

---

### assets

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| asset_code | VARCHAR(128) | No | — |
| description | TEXT | Yes | — |
| entity_id | UUID | No | — |
| asset_class | VARCHAR(64) | Yes | — |
| asset_currency | VARCHAR(3) | Yes | — |
| reporting_currency | VARCHAR(3) | Yes | — |
| capitalization_date | DATE | Yes | — |
| in_service_date | DATE | Yes | — |
| capitalized_amount_asset_currency | NUMERIC(20, 6) | Yes | — |
| depreciation_method | VARCHAR(32) | No | — |
| useful_life_months | INTEGER | Yes | — |
| reducing_balance_rate_annual | NUMERIC(20, 6) | Yes | — |
| residual_value_reporting_currency | NUMERIC(20, 6) | Yes | — |
| rate_mode | VARCHAR(32) | Yes | — |
| source_acquisition_reference | VARCHAR(255) | Yes | — |
| parent_reference_id | UUID | Yes | — |
| source_reference_id | UUID | Yes | — |
| correlation_id | VARCHAR(64) | Yes | — |
| supersedes_id | UUID | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `entity_id` -> `cp_entities.id`
- `supersedes_id` -> `assets.id`

**Indexes:**
- `idx_assets_tenant_code` (tenant_id, asset_code, created_at)
- `idx_assets_tenant_source` (tenant_id, source_acquisition_reference)
- `ix_assets_entity_id` (entity_id)
- `ix_assets_tenant_id` (tenant_id)

---

### audit_trail

- **Description**: TIER 1: IMMUTABLE EVIDENTIARY — INSERT ONLY.
- **RLS enabled**: Yes
- **Append-only**: Yes

| Column | Type | Nullable | Default |
|---|---|---|---|
| user_id | UUID | Yes | — |
| action | VARCHAR(128) | No | — |
| resource_type | VARCHAR(128) | No | — |
| resource_id | VARCHAR(255) | Yes | — |
| resource_name | VARCHAR(255) | Yes | — |
| old_value_hash | VARCHAR(64) | Yes | — |
| new_value_hash | VARCHAR(64) | Yes | — |
| ip_address | VARCHAR(45) | Yes | — |
| user_agent | TEXT | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Indexes:**
- `idx_audit_trail_resource` (tenant_id, resource_type, resource_id)
- `idx_audit_trail_tenant_created` (tenant_id, created_at)
- `ix_audit_trail_tenant_id` (tenant_id)

---

### auditor_access_logs

- **Description**: Immutable log of every auditor data access event — INSERT ONLY.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| grant_id | UUID | No | — |
| auditor_user_id | UUID | No | — |
| accessed_resource | VARCHAR(255) | No | — |
| resource_id | VARCHAR(255) | Yes | — |
| ip_address | VARCHAR(45) | Yes | — |
| user_agent | TEXT | Yes | — |
| access_result | VARCHAR(20) | No | granted |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Indexes:**
- `idx_auditor_logs_auditor` (auditor_user_id, created_at)
- `idx_auditor_logs_tenant` (tenant_id, created_at)
- `ix_auditor_access_logs_tenant_id` (tenant_id)

---

### auditor_grants

- **Description**: Auditor access grant — INSERT ONLY.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| auditor_user_id | UUID | No | — |
| scope | VARCHAR(20) | No | limited |
| allowed_modules | JSONB | No | <function AuditorGrant.<lambda> at 0x00000272F978A7A0> |
| expires_at | DATETIME | Yes | — |
| is_active | BOOLEAN | No | True |
| granted_by | UUID | No | — |
| revoked_at | DATETIME | Yes | — |
| revoked_by | UUID | Yes | — |
| notes | TEXT | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Indexes:**
- `idx_auditor_grants_active` (tenant_id, auditor_user_id, is_active)
- `idx_auditor_grants_auditor` (auditor_user_id)
- `idx_auditor_grants_tenant` (tenant_id)
- `ix_auditor_grants_tenant_id` (tenant_id)

---

### auditor_portal_access

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| entity_id | UUID | No | — |
| auditor_email | VARCHAR(300) | No | — |
| auditor_firm | VARCHAR(300) | No | — |
| engagement_name | VARCHAR(300) | No | — |
| access_level | VARCHAR(20) | No | read_only |
| modules_accessible | JSONB | No | <function list at 0x00000272FD5AC5E0> |
| valid_from | DATE | No | — |
| valid_until | DATE | No | — |
| is_active | BOOLEAN | No | True |
| access_token_hash | VARCHAR(64) | No | — |
| last_accessed_at | DATETIME | Yes | — |
| created_by | UUID | No | — |
| created_at | DATETIME | No | now() |
| updated_at | DATETIME | No | now() |

**Foreign keys:**
- `entity_id` -> `cp_entities.id`

**Indexes:**
- `idx_auditor_portal_access_tenant_engagement` (tenant_id, engagement_name)
- `idx_auditor_portal_access_tenant_entity` (tenant_id, entity_id)

---

### auditor_requests

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| access_id | UUID | No | — |
| tenant_id | UUID | No | — |
| entity_id | UUID | No | — |
| request_number | VARCHAR(20) | No | — |
| category | VARCHAR(50) | No | — |
| description | TEXT | No | — |
| status | VARCHAR(20) | No | open |
| due_date | DATE | Yes | — |
| response_notes | TEXT | Yes | — |
| evidence_urls | JSONB | No | <function list at 0x00000272FD5ADE40> |
| provided_at | DATETIME | Yes | — |
| provided_by | UUID | Yes | — |
| created_at | DATETIME | No | now() |

**Foreign keys:**
- `entity_id` -> `cp_entities.id`

**Indexes:**
- `idx_auditor_requests_access_status` (access_id, status)
- `idx_auditor_requests_tenant_entity` (tenant_id, entity_id)
- `idx_auditor_requests_tenant_status_due` (tenant_id, status, due_date)

---

### backup_run_log

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: No
- **Append-only**: Yes

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| backup_type | VARCHAR(30) | No | — |
| status | VARCHAR(20) | No | — |
| started_at | DATETIME | No | now() |
| completed_at | DATETIME | Yes | — |
| size_bytes | BIGINT | Yes | — |
| backup_location | TEXT | Yes | — |
| verification_passed | BOOLEAN | Yes | — |
| error_message | TEXT | Yes | — |
| triggered_by | VARCHAR(100) | No | — |
| retention_days | INTEGER | No | 30 |
| created_at | DATETIME | No | now() |

**Indexes:**
- `idx_backup_run_log_status_created` (status)
- `idx_backup_run_log_type_started` (backup_type)

---

### bank_recon_items

- **Description**: Bank reconciliation item — INSERT ONLY.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| statement_id | UUID | No | — |
| period_year | INTEGER | No | — |
| period_month | INTEGER | No | — |
| entity_id | UUID | No | — |
| entity_name | VARCHAR(255) | No | — |
| item_type | VARCHAR(50) | No | — |
| bank_transaction_id | UUID | Yes | — |
| gl_reference | VARCHAR(255) | Yes | — |
| amount | NUMERIC(20, 6) | No | — |
| created_by_intent_id | UUID | Yes | — |
| recorded_by_job_id | UUID | Yes | — |
| status | VARCHAR(50) | No | open |
| notes | TEXT | Yes | — |
| resolved_by | UUID | Yes | — |
| run_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `entity_id` -> `cp_entities.id`
- `statement_id` -> `bank_statements.id`

**Indexes:**
- `idx_bank_recon_entity_id` (tenant_id, entity_id)
- `idx_bank_recon_status` (tenant_id, status)
- `idx_bank_recon_tenant_period` (tenant_id, period_year, period_month)
- `ix_bank_recon_items_tenant_id` (tenant_id)

---

### bank_statements

- **Description**: Bank statement upload header — INSERT ONLY.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| bank_name | VARCHAR(255) | No | — |
| account_number_masked | VARCHAR(50) | No | — |
| currency | VARCHAR(3) | No | USD |
| period_year | INTEGER | No | — |
| period_month | INTEGER | No | — |
| entity_id | UUID | No | — |
| entity_name | VARCHAR(255) | No | — |
| location_id | UUID | Yes | — |
| cost_centre_id | UUID | Yes | — |
| opening_balance | NUMERIC(20, 6) | No | 0 |
| closing_balance | NUMERIC(20, 6) | No | — |
| transaction_count | INTEGER | No | 0 |
| file_name | VARCHAR(500) | No | — |
| file_hash | VARCHAR(64) | No | — |
| created_by_intent_id | UUID | Yes | — |
| recorded_by_job_id | UUID | Yes | — |
| status | VARCHAR(50) | No | pending |
| uploaded_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `cost_centre_id` -> `cp_cost_centres.id`
- `entity_id` -> `cp_entities.id`
- `location_id` -> `cp_locations.id`

**Indexes:**
- `idx_bank_stmts_entity` (tenant_id, entity_name)
- `idx_bank_stmts_entity_id` (tenant_id, entity_id)
- `idx_bank_stmts_tenant_period` (tenant_id, period_year, period_month)
- `ix_bank_statements_tenant_id` (tenant_id)

---

### bank_transactions

- **Description**: Individual bank statement line — INSERT ONLY.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| statement_id | UUID | No | — |
| entity_id | UUID | No | — |
| transaction_date | DATE | No | — |
| description | TEXT | No | — |
| debit_amount | NUMERIC(20, 6) | No | 0 |
| credit_amount | NUMERIC(20, 6) | No | 0 |
| balance | NUMERIC(20, 6) | No | — |
| reference | VARCHAR(255) | Yes | — |
| created_by_intent_id | UUID | Yes | — |
| recorded_by_job_id | UUID | Yes | — |
| match_status | VARCHAR(50) | No | unmatched |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `entity_id` -> `cp_entities.id`
- `statement_id` -> `bank_statements.id`

**Indexes:**
- `idx_bank_txns_entity_id` (tenant_id, entity_id)
- `idx_bank_txns_match` (tenant_id, match_status)
- `idx_bank_txns_statement` (tenant_id, statement_id)
- `idx_bank_txns_tenant_created` (tenant_id, created_at)
- `ix_bank_transactions_tenant_id` (tenant_id)

---

### billing_entitlements

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| plan_id | UUID | No | — |
| feature_name | VARCHAR(128) | No | — |
| access_type | VARCHAR(16) | No | — |
| limit_value | BIGINT | Yes | — |
| metadata | JSONB | No | <function dict at 0x00000272FAB1BD80> |
| is_active | BOOLEAN | No | True |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `plan_id` -> `billing_plans.id`

**Indexes:**
- `idx_billing_entitlements_plan_feature` (tenant_id, plan_id, feature_name, created_at)
- `ix_billing_entitlements_tenant_id` (tenant_id)

---

### billing_invoices

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| subscription_id | UUID | No | — |
| provider_invoice_id | VARCHAR(255) | No | — |
| status | VARCHAR(32) | No | — |
| currency | VARCHAR(3) | No | — |
| subtotal | NUMERIC(20, 6) | No | — |
| tax | NUMERIC(20, 6) | No | 0 |
| total | NUMERIC(20, 6) | No | — |
| amount | NUMERIC(20, 6) | Yes | — |
| issued_at | DATETIME | Yes | — |
| due_at | DATETIME | Yes | — |
| credits_applied | INTEGER | No | 0 |
| due_date | DATE | No | — |
| paid_at | DATETIME | Yes | — |
| voided_at | DATETIME | Yes | — |
| invoice_pdf_url | VARCHAR(512) | Yes | — |
| line_items | JSONB | No | <function list at 0x00000272FAAB6F20> |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `subscription_id` -> `tenant_subscriptions.id`

**Indexes:**
- `idx_billing_invoices_tenant` (tenant_id, subscription_id, status, created_at)
- `ix_billing_invoices_tenant_id` (tenant_id)

---

### billing_payments

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| invoice_id | UUID | No | — |
| amount | NUMERIC(20, 6) | No | — |
| payment_status | VARCHAR(32) | No | — |
| provider_reference | VARCHAR(255) | No | — |
| provider | VARCHAR(32) | Yes | — |
| metadata | JSONB | No | <function dict at 0x00000272FAB1B920> |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `invoice_id` -> `billing_invoices.id`

**Indexes:**
- `idx_billing_payments_tenant_invoice` (tenant_id, invoice_id, created_at)
- `ix_billing_payments_tenant_id` (tenant_id)

---

### billing_plans

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| name | VARCHAR(128) | Yes | — |
| plan_tier | VARCHAR(32) | No | — |
| pricing_type | VARCHAR(16) | Yes | — |
| price | NUMERIC(20, 6) | Yes | — |
| currency | VARCHAR(3) | Yes | — |
| billing_cycle | VARCHAR(16) | No | — |
| base_price_inr | NUMERIC(20, 6) | No | — |
| base_price_usd | NUMERIC(20, 6) | No | — |
| included_credits | INTEGER | No | — |
| max_entities | INTEGER | No | — |
| max_connectors | INTEGER | No | — |
| max_users | INTEGER | No | — |
| modules_enabled | JSONB | No | <function dict at 0x00000272FAA7A480> |
| trial_days | INTEGER | No | — |
| annual_discount_pct | NUMERIC(20, 6) | No | 0 |
| is_active | BOOLEAN | No | True |
| valid_from | DATE | No | — |
| valid_until | DATE | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Indexes:**
- `idx_billing_plans_tenant_active` (tenant_id, is_active, created_at)
- `ix_billing_plans_tenant_id` (tenant_id)

---

### billing_tenant_entitlements

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| feature_name | VARCHAR(128) | No | — |
| access_type | VARCHAR(16) | No | — |
| effective_limit | BIGINT | Yes | — |
| source | VARCHAR(16) | No | plan |
| source_reference_id | UUID | Yes | — |
| metadata | JSONB | No | <function dict at 0x00000272FAB4DF80> |
| is_active | BOOLEAN | No | True |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Indexes:**
- `idx_billing_tenant_entitlements_feature` (tenant_id, feature_name, created_at)
- `ix_billing_tenant_entitlements_tenant_id` (tenant_id)

---

### billing_usage_aggregates

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| feature_name | VARCHAR(128) | No | — |
| period_start | DATE | No | — |
| period_end | DATE | No | — |
| total_usage | BIGINT | No | — |
| last_event_id | UUID | Yes | — |
| metadata | JSONB | No | <function dict at 0x00000272FAB4F6A0> |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `last_event_id` -> `billing_usage_events.id`

**Indexes:**
- `idx_billing_usage_aggregates_period` (tenant_id, feature_name, period_start, period_end)
- `ix_billing_usage_aggregates_tenant_id` (tenant_id)

---

### billing_usage_events

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| feature_name | VARCHAR(128) | No | — |
| usage_quantity | BIGINT | No | — |
| event_time | DATETIME | No | <function utc_now at 0x00000272FAB4E480> |
| period_start | DATE | Yes | — |
| period_end | DATE | Yes | — |
| reference_type | VARCHAR(64) | Yes | — |
| reference_id | VARCHAR(255) | Yes | — |
| metadata | JSONB | No | <function dict at 0x00000272FAB4F2E0> |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Indexes:**
- `idx_billing_usage_events_feature_time` (tenant_id, feature_name, event_time)
- `ix_billing_usage_events_tenant_id` (tenant_id)

---

### board_pack_artifacts

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| run_id | UUID | No | — |
| tenant_id | UUID | No | — |
| format | VARCHAR(20) | No | — |
| storage_path | TEXT | No | — |
| file_size_bytes | BIGINT | Yes | — |
| created_by_intent_id | UUID | Yes | — |
| recorded_by_job_id | UUID | Yes | — |
| generated_at | DATETIME | No | now() |
| checksum | VARCHAR(64) | Yes | — |

**Foreign keys:**
- `run_id` -> `board_pack_runs.id`

**Indexes:**
- `idx_board_pack_artifacts_run_format` (run_id, format)

---

### board_pack_definitions

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| tenant_id | UUID | No | — |
| organisation_id | UUID | No | — |
| name | VARCHAR(255) | No | — |
| board_pack_code | VARCHAR(128) | No | — |
| board_pack_name | VARCHAR(255) | No | — |
| description | TEXT | Yes | — |
| audience_scope | VARCHAR(64) | No | board |
| section_types | JSONB | No | <function list at 0x00000272FA0B6D40> |
| entity_ids | JSONB | No | <function list at 0x00000272FA0B6DE0> |
| period_type | VARCHAR(50) | No | — |
| config | JSONB | No | <function dict at 0x00000272FA0B6E80> |
| section_order_json | JSONB | No | <function dict at 0x00000272FD182020> |
| inclusion_config_json | JSONB | No | <function dict at 0x00000272FD181F80> |
| version_token | VARCHAR(64) | No | — |
| effective_from | DATE | No | — |
| effective_to | DATE | Yes | — |
| supersedes_id | UUID | Yes | — |
| status | VARCHAR(32) | No | candidate |
| created_by | UUID | No | — |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |
| updated_at | DATETIME | No | now() |
| created_by_intent_id | UUID | Yes | — |
| recorded_by_job_id | UUID | Yes | — |
| is_active | BOOLEAN | No | True |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |

**Foreign keys:**
- `supersedes_id` -> `board_pack_definitions.id`

**Indexes:**
- `idx_board_pack_definitions_lookup` (tenant_id, organisation_id, board_pack_code, effective_from, created_at)
- `ix_board_pack_definitions_tenant_id` (tenant_id)
- `uq_board_pack_definitions_one_active` (tenant_id, organisation_id, board_pack_code)

---

### board_pack_evidence_links

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| run_id | UUID | No | — |
| section_result_id | UUID | Yes | — |
| narrative_block_id | UUID | Yes | — |
| evidence_type | VARCHAR(64) | No | — |
| evidence_ref | TEXT | No | — |
| evidence_label | VARCHAR(255) | No | — |
| evidence_payload_json | JSONB | No | <function dict at 0x00000272FD2A60C0> |
| board_attention_flag | BOOLEAN | No | False |
| severity_rank | NUMERIC(12, 6) | No | 0 |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `narrative_block_id` -> `board_pack_narrative_blocks.id`
- `run_id` -> `board_pack_runs.id`
- `section_result_id` -> `board_pack_section_results.id`

**Indexes:**
- `idx_board_pack_evidence_links_run` (tenant_id, run_id, created_at)
- `idx_board_pack_evidence_links_section` (tenant_id, run_id, section_result_id)
- `ix_board_pack_evidence_links_tenant_id` (tenant_id)

---

### board_pack_inclusion_rules

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| organisation_id | UUID | No | — |
| rule_code | VARCHAR(128) | No | — |
| rule_name | VARCHAR(255) | No | — |
| rule_type | VARCHAR(64) | No | — |
| inclusion_logic_json | JSONB | No | <function dict at 0x00000272FD251D00> |
| version_token | VARCHAR(64) | No | — |
| effective_from | DATE | No | — |
| effective_to | DATE | Yes | — |
| supersedes_id | UUID | Yes | — |
| status | VARCHAR(32) | No | candidate |
| created_by | UUID | No | — |
| created_by_intent_id | UUID | Yes | — |
| recorded_by_job_id | UUID | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `supersedes_id` -> `board_pack_inclusion_rules.id`

**Indexes:**
- `idx_board_pack_inclusion_rules_lookup` (tenant_id, organisation_id, rule_code, effective_from, created_at)
- `ix_board_pack_inclusion_rules_tenant_id` (tenant_id)
- `uq_board_pack_inclusion_rules_one_active` (tenant_id, organisation_id, rule_code)

---

### board_pack_narrative_blocks

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| run_id | UUID | No | — |
| section_result_id | UUID | No | — |
| narrative_template_code | VARCHAR(128) | No | — |
| narrative_text | TEXT | No | — |
| narrative_payload_json | JSONB | No | <function dict at 0x00000272FD273BA0> |
| block_order | INTEGER | No | — |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `run_id` -> `board_pack_runs.id`
- `section_result_id` -> `board_pack_section_results.id`

**Indexes:**
- `idx_board_pack_narrative_blocks_run` (tenant_id, run_id, section_result_id, block_order)
- `ix_board_pack_narrative_blocks_tenant_id` (tenant_id)

---

### board_pack_results

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| run_id | UUID | No | — |
| board_pack_code | VARCHAR(128) | No | — |
| reporting_period | DATE | No | — |
| status | VARCHAR(32) | No | generated |
| executive_summary_text | TEXT | No | — |
| overall_health_classification | VARCHAR(32) | No | — |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `run_id` -> `board_pack_runs.id`

**Indexes:**
- `idx_board_pack_results_run` (tenant_id, run_id, created_at)
- `ix_board_pack_results_tenant_id` (tenant_id)

---

### board_pack_runs

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| tenant_id | UUID | No | — |
| definition_id | UUID | No | — |
| period_start | DATE | No | — |
| period_end | DATE | No | — |
| status | VARCHAR(32) | No | created |
| triggered_by | UUID | No | — |
| started_at | DATETIME | Yes | — |
| completed_at | DATETIME | Yes | — |
| error_message | TEXT | Yes | — |
| chain_hash | VARCHAR(64) | No | — |
| run_metadata | JSONB | No | <function dict at 0x00000272FA0F8CC0> |
| created_by_intent_id | UUID | Yes | — |
| recorded_by_job_id | UUID | Yes | — |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |
| organisation_id | UUID | No | — |
| reporting_period | DATE | No | — |
| board_pack_definition_version_token | VARCHAR(64) | No | — |
| section_definition_version_token | VARCHAR(64) | No | — |
| narrative_template_version_token | VARCHAR(64) | No | — |
| inclusion_rule_version_token | VARCHAR(64) | No | — |
| source_metric_run_ids_json | JSONB | No | <function list at 0x00000272FD2534C0> |
| source_risk_run_ids_json | JSONB | No | <function list at 0x00000272FD270720> |
| source_anomaly_run_ids_json | JSONB | No | <function list at 0x00000272FD2707C0> |
| run_token | VARCHAR(64) | No | — |
| validation_summary_json | JSONB | No | <function dict at 0x00000272FD270860> |
| created_by | UUID | No | — |
| previous_hash | VARCHAR(64) | No | — |

**Foreign keys:**
- `definition_id` -> `board_pack_definitions.id`

**Indexes:**
- `idx_board_pack_runs_lookup` (tenant_id, organisation_id, reporting_period, created_at)
- `idx_board_pack_runs_tenant_definition_created_desc` (tenant_id, definition_id)
- `idx_board_pack_runs_tenant_status` (tenant_id, status)
- `idx_board_pack_runs_token` (tenant_id, run_token)
- `ix_board_pack_runs_tenant_id` (tenant_id)

---

### board_pack_section_definitions

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| organisation_id | UUID | No | — |
| section_code | VARCHAR(128) | No | — |
| section_name | VARCHAR(255) | No | — |
| section_type | VARCHAR(64) | No | — |
| render_logic_json | JSONB | No | <function dict at 0x00000272FD182520> |
| section_order_default | INTEGER | No | — |
| narrative_template_ref | VARCHAR(128) | Yes | — |
| risk_inclusion_rule_json | JSONB | No | <function dict at 0x00000272FD183C40> |
| anomaly_inclusion_rule_json | JSONB | No | <function dict at 0x00000272FD183CE0> |
| metric_inclusion_rule_json | JSONB | No | <function dict at 0x00000272FD183D80> |
| version_token | VARCHAR(64) | No | — |
| effective_from | DATE | No | — |
| effective_to | DATE | Yes | — |
| supersedes_id | UUID | Yes | — |
| status | VARCHAR(32) | No | candidate |
| created_by | UUID | No | — |
| created_by_intent_id | UUID | Yes | — |
| recorded_by_job_id | UUID | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `supersedes_id` -> `board_pack_section_definitions.id`

**Indexes:**
- `idx_board_pack_section_definitions_lookup` (tenant_id, organisation_id, section_code, effective_from, created_at)
- `ix_board_pack_section_definitions_tenant_id` (tenant_id)
- `uq_board_pack_section_definitions_one_active` (tenant_id, organisation_id, section_code)

---

### board_pack_section_results

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| run_id | UUID | No | — |
| section_code | VARCHAR(128) | No | — |
| section_order | INTEGER | No | — |
| section_title | VARCHAR(255) | No | — |
| section_summary_text | TEXT | No | — |
| section_payload_json | JSONB | No | <function dict at 0x00000272FD272840> |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `run_id` -> `board_pack_runs.id`

**Indexes:**
- `idx_board_pack_section_results_run` (tenant_id, run_id, section_order)
- `ix_board_pack_section_results_tenant_id` (tenant_id)

---

### board_pack_sections

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| run_id | UUID | No | — |
| tenant_id | UUID | No | — |
| section_type | VARCHAR(50) | No | — |
| section_order | INTEGER | No | — |
| data_snapshot | JSONB | No | — |
| section_hash | VARCHAR(64) | No | — |
| created_by_intent_id | UUID | Yes | — |
| recorded_by_job_id | UUID | Yes | — |
| rendered_at | DATETIME | No | now() |

**Foreign keys:**
- `run_id` -> `board_pack_runs.id`

**Indexes:**
- `idx_board_pack_sections_run_section_order` (run_id, section_order)

---

### budget_line_items

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: Yes

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| budget_version_id | UUID | No | — |
| tenant_id | UUID | No | — |
| entity_id | UUID | Yes | — |
| mis_line_item | VARCHAR(300) | No | — |
| mis_category | VARCHAR(100) | No | — |
| month_01 | NUMERIC(20, 2) | No | 0 |
| month_02 | NUMERIC(20, 2) | No | 0 |
| month_03 | NUMERIC(20, 2) | No | 0 |
| month_04 | NUMERIC(20, 2) | No | 0 |
| month_05 | NUMERIC(20, 2) | No | 0 |
| month_06 | NUMERIC(20, 2) | No | 0 |
| month_07 | NUMERIC(20, 2) | No | 0 |
| month_08 | NUMERIC(20, 2) | No | 0 |
| month_09 | NUMERIC(20, 2) | No | 0 |
| month_10 | NUMERIC(20, 2) | No | 0 |
| month_11 | NUMERIC(20, 2) | No | 0 |
| month_12 | NUMERIC(20, 2) | No | 0 |
| annual_total | NUMERIC(20, 2) | No | — |
| basis | TEXT | Yes | — |
| created_at | DATETIME | No | now() |

**Foreign keys:**
- `budget_version_id` -> `budget_versions.id`

**Indexes:**
- `idx_budget_line_items_tenant_version` (tenant_id, budget_version_id)
- `idx_budget_line_items_version_line` (budget_version_id, mis_line_item)

---

### budget_version_status_events

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| created_at | DATETIME | No | now() |
| budget_version_id | UUID | No | — |
| from_status | VARCHAR(20) | Yes | — |
| to_status | VARCHAR(20) | No | — |
| acted_by | UUID | Yes | — |
| notes | TEXT | Yes | — |

**Foreign keys:**
- `acted_by` -> `iam_users.id`
- `budget_version_id` -> `budget_versions.id`

**Indexes:**
- `idx_budget_status_events_status` (tenant_id, to_status, created_at)
- `idx_budget_status_events_version` (tenant_id, budget_version_id, created_at)

---

### budget_versions

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| fiscal_year | INTEGER | No | — |
| version_name | VARCHAR(100) | No | — |
| version_number | INTEGER | No | 1 |
| status | VARCHAR(20) | No | draft |
| is_board_approved | BOOLEAN | No | False |
| board_approved_at | DATETIME | Yes | — |
| board_approved_by | UUID | Yes | — |
| notes | TEXT | Yes | — |
| created_by | UUID | No | — |
| created_at | DATETIME | No | now() |
| updated_at | DATETIME | No | now() |

**Foreign keys:**
- `board_approved_by` -> `iam_users.id`
- `created_by` -> `iam_users.id`

**Indexes:**
- `idx_budget_versions_tenant_year` (tenant_id, fiscal_year)

---

### budgets

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| org_entity_id | UUID | No | — |
| period | VARCHAR(7) | No | — |
| account_id | UUID | No | — |
| budget_amount | NUMERIC(24, 6) | No | — |
| created_at | DATETIME | No | now() |

**Foreign keys:**
- `account_id` -> `tenant_coa_accounts.id`
- `org_entity_id` -> `cp_entities.id`
- `tenant_id` -> `iam_tenants.id`

**Indexes:**
- `ix_budgets_tenant_account` (tenant_id, account_id)
- `ix_budgets_tenant_entity_period` (tenant_id, org_entity_id, period)

---

### canonical_governance_events

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| entity_id | UUID | Yes | — |
| module_key | VARCHAR(64) | No | — |
| subject_type | VARCHAR(64) | No | — |
| subject_id | VARCHAR(128) | No | — |
| event_type | VARCHAR(64) | No | — |
| actor_user_id | UUID | Yes | — |
| actor_role | VARCHAR(64) | Yes | — |
| payload_json | JSONB | No | <function dict at 0x00000272F99513A0> |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `actor_user_id` -> `iam_users.id`
- `entity_id` -> `cp_entities.id`

**Indexes:**
- `ix_canonical_governance_events_module` (tenant_id, module_key, created_at)
- `ix_canonical_governance_events_subject` (tenant_id, subject_type, subject_id)
- `ix_canonical_governance_events_tenant_id` (tenant_id)
- `ix_canonical_governance_events_type` (tenant_id, event_type, created_at)

---

### canonical_intent_events

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| intent_id | UUID | No | — |
| event_type | VARCHAR(64) | No | — |
| from_status | VARCHAR(32) | Yes | — |
| to_status | VARCHAR(32) | Yes | — |
| actor_user_id | UUID | Yes | — |
| actor_role | VARCHAR(64) | Yes | — |
| event_at | DATETIME | No | now() |
| event_payload_json | JSONB | No | <function dict at 0x00000272F98B3740> |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `actor_user_id` -> `iam_users.id`
- `intent_id` -> `canonical_intents.id`

**Indexes:**
- `ix_canonical_intent_events_intent_id` (intent_id)
- `ix_canonical_intent_events_tenant_id` (tenant_id)

---

### canonical_intents

- **Description**: Abstract base with UUID PK and created_at.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| tenant_id | UUID | No | — |
| org_id | UUID | No | — |
| entity_id | UUID | No | — |
| intent_type | VARCHAR(64) | No | — |
| module_key | VARCHAR(64) | No | — |
| target_type | VARCHAR(64) | No | — |
| target_id | UUID | Yes | — |
| parent_intent_id | UUID | Yes | — |
| status | VARCHAR(32) | No | DRAFT |
| requested_by_user_id | UUID | No | — |
| requested_by_role | VARCHAR(64) | No | — |
| requested_at | DATETIME | No | now() |
| submitted_at | DATETIME | Yes | — |
| validated_at | DATETIME | Yes | — |
| approved_at | DATETIME | Yes | — |
| executed_at | DATETIME | Yes | — |
| recorded_at | DATETIME | Yes | — |
| rejected_at | DATETIME | Yes | — |
| rejection_reason | TEXT | Yes | — |
| payload_json | JSONB | No | <function dict at 0x00000272F95D9C60> |
| guard_results_json | JSONB | Yes | — |
| record_refs_json | JSONB | Yes | — |
| approval_policy_id | UUID | Yes | — |
| job_id | UUID | Yes | — |
| idempotency_key | VARCHAR(128) | No | — |
| source_channel | VARCHAR(16) | No | api |
| updated_at | DATETIME | No | now() |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `entity_id` -> `cp_entities.id`
- `org_id` -> `cp_organisations.id`
- `parent_intent_id` -> `canonical_intents.id`
- `requested_by_user_id` -> `iam_users.id`

**Indexes:**
- `ix_canonical_intents_entity_id` (entity_id)
- `ix_canonical_intents_job_id` (job_id)
- `ix_canonical_intents_lookup` (tenant_id, intent_type, status)
- `ix_canonical_intents_org_id` (org_id)
- `ix_canonical_intents_parent_intent_id` (parent_intent_id)
- `ix_canonical_intents_target_id` (target_id)
- `ix_canonical_intents_tenant_id` (tenant_id)

---

### canonical_jobs

- **Description**: Abstract base with UUID PK and created_at.
- **RLS enabled**: No
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| intent_id | UUID | No | — |
| job_type | VARCHAR(64) | No | — |
| status | VARCHAR(32) | No | PENDING |
| runner_type | VARCHAR(32) | No | INLINE |
| queue_name | VARCHAR(128) | No | — |
| idempotency_key | VARCHAR(128) | No | — |
| requested_at | DATETIME | No | now() |
| started_at | DATETIME | Yes | — |
| finished_at | DATETIME | Yes | — |
| failed_at | DATETIME | Yes | — |
| retry_count | INTEGER | No | 0 |
| max_retries | INTEGER | No | 0 |
| error_code | VARCHAR(64) | Yes | — |
| error_message | TEXT | Yes | — |
| error_details_json | JSONB | Yes | — |
| updated_at | DATETIME | No | now() |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `intent_id` -> `canonical_intents.id`

**Indexes:**
- `ix_canonical_jobs_intent_id` (intent_id)
- `ix_canonical_jobs_lookup` (status, runner_type)

---

### cash_flow_bridge_rule_definitions

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| organisation_id | UUID | No | — |
| rule_code | VARCHAR(128) | No | — |
| rule_name | VARCHAR(255) | No | — |
| bridge_logic_json | JSONB | No | <function dict at 0x00000272FA709A80> |
| ownership_logic_json | JSONB | No | <function dict at 0x00000272FA708540> |
| fx_logic_json | JSONB | No | <function dict at 0x00000272FA709B20> |
| version_token | VARCHAR(64) | No | — |
| effective_from | DATE | No | — |
| effective_to | DATE | Yes | — |
| supersedes_id | UUID | Yes | — |
| status | VARCHAR(32) | No | candidate |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `supersedes_id` -> `cash_flow_bridge_rule_definitions.id`

**Indexes:**
- `idx_cash_flow_bridge_rule_definitions_lookup` (tenant_id, organisation_id, rule_code, effective_from, created_at)
- `ix_cash_flow_bridge_rule_definitions_tenant_id` (tenant_id)
- `uq_cash_flow_bridge_rule_definitions_one_active` (tenant_id, organisation_id, rule_code)

---

### cash_flow_evidence_links

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| run_id | UUID | No | — |
| line_result_id | UUID | Yes | — |
| evidence_type | VARCHAR(64) | No | — |
| evidence_ref | TEXT | No | — |
| evidence_label | VARCHAR(255) | No | — |
| evidence_payload_json | JSONB | No | <function dict at 0x00000272FA74AB60> |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `line_result_id` -> `cash_flow_line_results.id`
- `run_id` -> `cash_flow_runs.id`

**Indexes:**
- `idx_cash_flow_evidence_links_run` (tenant_id, run_id, created_at)
- `ix_cash_flow_evidence_links_tenant_id` (tenant_id)

---

### cash_flow_forecast_assumptions

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| forecast_run_id | UUID | No | — |
| tenant_id | UUID | No | — |
| entity_id | UUID | No | — |
| week_number | INTEGER | No | — |
| week_start_date | DATE | No | — |
| customer_collections | NUMERIC(20, 2) | No | 0.00 |
| other_inflows | NUMERIC(20, 2) | No | 0.00 |
| supplier_payments | NUMERIC(20, 2) | No | 0.00 |
| payroll | NUMERIC(20, 2) | No | 0.00 |
| rent_and_utilities | NUMERIC(20, 2) | No | 0.00 |
| loan_repayments | NUMERIC(20, 2) | No | 0.00 |
| tax_payments | NUMERIC(20, 2) | No | 0.00 |
| capex | NUMERIC(20, 2) | No | 0.00 |
| other_outflows | NUMERIC(20, 2) | No | 0.00 |
| total_inflows | NUMERIC(20, 2) | No | 0.00 |
| total_outflows | NUMERIC(20, 2) | No | 0.00 |
| net_cash_flow | NUMERIC(20, 2) | No | 0.00 |
| closing_balance | NUMERIC(20, 2) | No | 0.00 |
| notes | TEXT | Yes | — |
| created_at | DATETIME | No | now() |
| updated_at | DATETIME | No | now() |

**Foreign keys:**
- `entity_id` -> `cp_entities.id`
- `forecast_run_id` -> `cash_flow_forecast_runs.id`

**Indexes:**
- `idx_cash_flow_forecast_assumptions_entity_id` (tenant_id, entity_id)
- `idx_cash_flow_forecast_assumptions_run_week` (forecast_run_id, week_number)

---

### cash_flow_forecast_runs

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| entity_id | UUID | No | — |
| location_id | UUID | Yes | — |
| cost_centre_id | UUID | Yes | — |
| run_name | VARCHAR(200) | No | — |
| base_date | DATE | No | — |
| weeks | INTEGER | No | 13 |
| opening_cash_balance | NUMERIC(20, 2) | No | — |
| currency | VARCHAR(3) | No | INR |
| status | VARCHAR(20) | No | draft |
| is_published | BOOLEAN | No | False |
| created_by | UUID | No | — |
| created_at | DATETIME | No | now() |

**Foreign keys:**
- `cost_centre_id` -> `cp_cost_centres.id`
- `entity_id` -> `cp_entities.id`
- `location_id` -> `cp_locations.id`

**Indexes:**
- `idx_cash_flow_forecast_runs_cost_centre_id` (cost_centre_id)
- `idx_cash_flow_forecast_runs_entity_id` (entity_id)
- `idx_cash_flow_forecast_runs_location_id` (location_id)
- `idx_cash_flow_forecast_runs_tenant_base_date` (tenant_id, base_date)

---

### cash_flow_line_mappings

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| organisation_id | UUID | No | — |
| mapping_code | VARCHAR(128) | No | — |
| line_code | VARCHAR(128) | No | — |
| line_name | VARCHAR(255) | No | — |
| section_code | VARCHAR(64) | No | — |
| line_order | INTEGER | No | — |
| method_type | VARCHAR(32) | No | — |
| source_metric_code | VARCHAR(128) | No | — |
| sign_multiplier | NUMERIC(9, 6) | No | 1.000000 |
| aggregation_type | VARCHAR(32) | No | sum |
| ownership_applicability | VARCHAR(32) | No | any |
| fx_applicability | VARCHAR(32) | No | any |
| version_token | VARCHAR(64) | No | — |
| effective_from | DATE | No | — |
| effective_to | DATE | Yes | — |
| supersedes_id | UUID | Yes | — |
| status | VARCHAR(32) | No | candidate |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `supersedes_id` -> `cash_flow_line_mappings.id`

**Indexes:**
- `idx_cash_flow_line_mappings_lookup` (tenant_id, organisation_id, mapping_code, line_order, effective_from, created_at)
- `ix_cash_flow_line_mappings_tenant_id` (tenant_id)
- `uq_cash_flow_line_mappings_one_active` (tenant_id, organisation_id, mapping_code)

---

### cash_flow_line_results

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| run_id | UUID | No | — |
| line_no | INTEGER | No | — |
| line_code | VARCHAR(128) | No | — |
| line_name | VARCHAR(255) | No | — |
| section_code | VARCHAR(64) | No | — |
| line_order | INTEGER | No | — |
| method_type | VARCHAR(32) | No | — |
| source_metric_code | VARCHAR(128) | No | — |
| source_value | NUMERIC(20, 6) | No | — |
| sign_multiplier | NUMERIC(9, 6) | No | — |
| computed_value | NUMERIC(20, 6) | No | — |
| currency_code | VARCHAR(3) | No | USD |
| ownership_basis_applied | BOOLEAN | No | False |
| fx_basis_applied | BOOLEAN | No | False |
| lineage_summary_json | JSONB | No | <function dict at 0x00000272FA749300> |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `run_id` -> `cash_flow_runs.id`

**Indexes:**
- `idx_cash_flow_line_results_run` (tenant_id, run_id, line_no)
- `idx_cash_flow_line_results_section` (tenant_id, run_id, section_code, line_order)
- `ix_cash_flow_line_results_tenant_id` (tenant_id)

---

### cash_flow_runs

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| organisation_id | UUID | No | — |
| entity_id | UUID | Yes | — |
| reporting_period | DATE | No | — |
| statement_definition_version_token | VARCHAR(64) | No | — |
| line_mapping_version_token | VARCHAR(64) | No | — |
| bridge_rule_version_token | VARCHAR(64) | No | — |
| source_consolidation_run_ref | UUID | No | — |
| source_fx_translation_run_ref_nullable | UUID | Yes | — |
| source_ownership_consolidation_run_ref_nullable | UUID | Yes | — |
| run_token | VARCHAR(64) | No | — |
| run_status | VARCHAR(32) | No | created |
| validation_summary_json | JSONB | No | <function dict at 0x00000272FA70B1A0> |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `entity_id` -> `cp_entities.id`
- `source_consolidation_run_ref` -> `multi_entity_consolidation_runs.id`
- `source_fx_translation_run_ref_nullable` -> `fx_translation_runs.id`
- `source_ownership_consolidation_run_ref_nullable` -> `ownership_consolidation_runs.id`

**Indexes:**
- `idx_cash_flow_runs_lookup` (tenant_id, organisation_id, reporting_period, created_at)
- `idx_cash_flow_runs_token` (tenant_id, run_token)
- `ix_cash_flow_runs_entity_id` (entity_id)
- `ix_cash_flow_runs_tenant_id` (tenant_id)

---

### cash_flow_statement_definitions

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| organisation_id | UUID | No | — |
| definition_code | VARCHAR(128) | No | — |
| definition_name | VARCHAR(255) | No | — |
| method_type | VARCHAR(32) | No | — |
| layout_json | JSONB | No | <function dict at 0x00000272FA6DDBC0> |
| version_token | VARCHAR(64) | No | — |
| effective_from | DATE | No | — |
| effective_to | DATE | Yes | — |
| supersedes_id | UUID | Yes | — |
| status | VARCHAR(32) | No | candidate |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `supersedes_id` -> `cash_flow_statement_definitions.id`

**Indexes:**
- `idx_cash_flow_statement_definitions_lookup` (tenant_id, organisation_id, definition_code, effective_from, created_at)
- `ix_cash_flow_statement_definitions_tenant_id` (tenant_id)
- `uq_cash_flow_statement_definitions_one_active` (tenant_id, organisation_id, definition_code)

---

### checklist_run_tasks

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| run_id | UUID | No | — |
| template_task_id | UUID | No | — |
| tenant_id | UUID | No | — |
| entity_id | UUID | No | — |
| task_name | VARCHAR(300) | No | — |
| assigned_to | UUID | Yes | — |
| assigned_role | VARCHAR(50) | Yes | — |
| due_date | DATE | Yes | — |
| status | VARCHAR(20) | No | not_started |
| completed_at | DATETIME | Yes | — |
| completed_by | UUID | Yes | — |
| notes | TEXT | Yes | — |
| is_auto_completed | BOOLEAN | No | False |
| auto_completed_by_event | VARCHAR(100) | Yes | — |
| order_index | INTEGER | No | 0 |
| created_at | DATETIME | No | now() |
| updated_at | DATETIME | No | now() |

**Foreign keys:**
- `assigned_to` -> `iam_users.id`
- `entity_id` -> `cp_entities.id`
- `run_id` -> `checklist_runs.id`
- `template_task_id` -> `checklist_template_tasks.id`

**Indexes:**
- `idx_checklist_run_tasks_entity` (tenant_id, entity_id)
- `idx_checklist_run_tasks_run_status` (run_id, status)

---

### checklist_runs

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: Yes

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| entity_id | UUID | No | — |
| template_id | UUID | No | — |
| period | VARCHAR(7) | No | — |
| status | VARCHAR(20) | No | open |
| progress_pct | NUMERIC(5, 2) | No | 0 |
| target_close_date | DATE | Yes | — |
| actual_close_date | DATE | Yes | — |
| created_by | UUID | No | — |
| created_at | DATETIME | No | now() |

**Foreign keys:**
- `entity_id` -> `cp_entities.id`
- `template_id` -> `checklist_templates.id`

**Indexes:**
- `idx_checklist_runs_entity` (tenant_id, entity_id)
- `idx_checklist_runs_tenant_period` (tenant_id, period)

---

### checklist_template_tasks

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| template_id | UUID | No | — |
| tenant_id | UUID | No | — |
| task_name | VARCHAR(300) | No | — |
| description | TEXT | Yes | — |
| assigned_role | VARCHAR(50) | Yes | — |
| days_relative_to_period_end | INTEGER | No | — |
| depends_on_task_ids | JSONB | No | <function list at 0x00000272FAC1A5C0> |
| auto_trigger_event | VARCHAR(100) | Yes | — |
| order_index | INTEGER | No | 0 |
| created_at | DATETIME | No | now() |
| updated_at | DATETIME | No | now() |

**Foreign keys:**
- `template_id` -> `checklist_templates.id`

**Indexes:**
- `idx_checklist_template_tasks_template_order` (template_id, order_index)

---

### checklist_templates

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| name | VARCHAR(200) | No | — |
| description | TEXT | Yes | — |
| is_default | BOOLEAN | No | True |
| created_by | UUID | No | — |
| created_at | DATETIME | No | now() |
| updated_at | DATETIME | No | now() |

**Indexes:**
- `idx_checklist_templates_tenant` (tenant_id)

---

### classification_rules

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| rule_name | VARCHAR(200) | No | — |
| description | TEXT | Yes | — |
| pattern_type | VARCHAR(30) | No | — |
| pattern_value | VARCHAR(500) | No | — |
| amount_min | NUMERIC(20, 4) | Yes | — |
| amount_max | NUMERIC(20, 4) | Yes | — |
| classification | VARCHAR(20) | No | — |
| confidence | NUMERIC(5, 4) | No | — |
| priority | INTEGER | No | 100 |
| is_active | BOOLEAN | No | True |
| created_at | DATETIME | No | now() |
| updated_at | DATETIME | Yes | now() |

**Foreign keys:**
- `tenant_id` -> `iam_tenants.id`

**Indexes:**
- `idx_classification_rules_is_active` (is_active)
- `idx_classification_rules_priority` (priority)
- `idx_classification_rules_tenant_id` (tenant_id)

---

### close_checklists

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| org_entity_id | UUID | No | — |
| period_id | UUID | No | — |
| checklist_type | VARCHAR(64) | No | — |
| checklist_status | VARCHAR(16) | No | PENDING |
| evidence_json | JSONB | Yes | — |
| completed_by | UUID | Yes | — |
| completed_at | DATETIME | Yes | — |
| created_at | DATETIME | No | now() |

**Foreign keys:**
- `completed_by` -> `iam_users.id`
- `org_entity_id` -> `cp_entities.id`
- `period_id` -> `accounting_periods.id`
- `tenant_id` -> `iam_tenants.id`

**Indexes:**
- `ix_close_checklists_tenant_entity_type` (tenant_id, org_entity_id, checklist_type)
- `ix_close_checklists_tenant_period` (tenant_id, period_id)

---

### coa_account_groups

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: No
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| industry_template_id | UUID | No | — |
| fs_subline_id | UUID | Yes | — |
| code | VARCHAR(50) | No | — |
| name | VARCHAR(300) | No | — |
| sort_order | INTEGER | No | — |
| is_active | BOOLEAN | No | True |
| created_at | DATETIME | No | now() |

**Foreign keys:**
- `fs_subline_id` -> `coa_fs_sublines.id`
- `industry_template_id` -> `coa_industry_templates.id`

---

### coa_account_subgroups

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: No
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| account_group_id | UUID | No | — |
| code | VARCHAR(50) | No | — |
| name | VARCHAR(300) | No | — |
| sort_order | INTEGER | No | — |
| is_active | BOOLEAN | No | True |
| created_at | DATETIME | No | now() |

**Foreign keys:**
- `account_group_id` -> `coa_account_groups.id`

---

### coa_fs_classifications

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: No
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| code | VARCHAR(50) | No | — |
| name | VARCHAR(200) | No | — |
| sort_order | INTEGER | No | — |
| is_active | BOOLEAN | No | True |
| created_at | DATETIME | No | now() |

---

### coa_fs_line_items

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: No
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| fs_schedule_id | UUID | No | — |
| code | VARCHAR(50) | No | — |
| name | VARCHAR(300) | No | — |
| bs_pl_flag | VARCHAR(20) | Yes | — |
| asset_liability_class | VARCHAR(20) | Yes | — |
| sort_order | INTEGER | No | — |
| is_active | BOOLEAN | No | True |
| created_at | DATETIME | No | now() |

**Foreign keys:**
- `fs_schedule_id` -> `coa_fs_schedules.id`

---

### coa_fs_schedules

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: No
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| fs_classification_id | UUID | No | — |
| gaap | VARCHAR(20) | No | — |
| code | VARCHAR(50) | No | — |
| name | VARCHAR(200) | No | — |
| schedule_number | VARCHAR(20) | Yes | — |
| sort_order | INTEGER | No | — |
| is_active | BOOLEAN | No | True |
| created_at | DATETIME | No | now() |

**Foreign keys:**
- `fs_classification_id` -> `coa_fs_classifications.id`

---

### coa_fs_sublines

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: No
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| fs_line_item_id | UUID | No | — |
| code | VARCHAR(50) | No | — |
| name | VARCHAR(300) | No | — |
| sort_order | INTEGER | No | — |
| is_active | BOOLEAN | No | True |
| created_at | DATETIME | No | now() |

**Foreign keys:**
- `fs_line_item_id` -> `coa_fs_line_items.id`

---

### coa_gaap_mappings

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: No
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| ledger_account_id | UUID | No | — |
| gaap | VARCHAR(20) | No | — |
| fs_schedule_id | UUID | No | — |
| fs_line_item_id | UUID | No | — |
| fs_subline_id | UUID | Yes | — |
| presentation_label | VARCHAR(300) | Yes | — |
| sort_order | INTEGER | Yes | — |
| is_active | BOOLEAN | No | True |
| created_at | DATETIME | No | now() |

**Foreign keys:**
- `fs_line_item_id` -> `coa_fs_line_items.id`
- `fs_schedule_id` -> `coa_fs_schedules.id`
- `fs_subline_id` -> `coa_fs_sublines.id`
- `ledger_account_id` -> `coa_ledger_accounts.id`

---

### coa_industry_templates

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: No
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| code | VARCHAR(50) | No | — |
| name | VARCHAR(200) | No | — |
| description | TEXT | Yes | — |
| is_active | BOOLEAN | No | True |
| created_at | DATETIME | No | now() |
| updated_at | DATETIME | Yes | now() |

---

### coa_ledger_accounts

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| account_subgroup_id | UUID | No | — |
| industry_template_id | UUID | No | — |
| tenant_id | UUID | Yes | — |
| code | VARCHAR(50) | No | — |
| name | VARCHAR(300) | No | — |
| description | TEXT | Yes | — |
| source_type | VARCHAR(14) | No | CoaSourceType.SYSTEM |
| version | INTEGER | No | 1 |
| created_by | UUID | Yes | — |
| normal_balance | VARCHAR(10) | No | — |
| cash_flow_tag | VARCHAR(20) | Yes | — |
| cash_flow_method | VARCHAR(10) | Yes | — |
| bs_pl_flag | VARCHAR(20) | Yes | — |
| asset_liability_class | VARCHAR(20) | Yes | — |
| is_monetary | BOOLEAN | No | False |
| is_related_party | BOOLEAN | No | False |
| is_tax_deductible | BOOLEAN | No | True |
| is_control_account | BOOLEAN | No | False |
| notes_reference | VARCHAR(100) | Yes | — |
| is_active | BOOLEAN | No | True |
| sort_order | INTEGER | No | — |
| created_at | DATETIME | No | now() |
| updated_at | DATETIME | Yes | now() |

**Foreign keys:**
- `account_subgroup_id` -> `coa_account_subgroups.id`
- `created_by` -> `iam_users.id`
- `industry_template_id` -> `coa_industry_templates.id`
- `tenant_id` -> `iam_tenants.id`

**Indexes:**
- `idx_coa_ledger_accounts_code` (code)
- `idx_coa_ledger_accounts_industry_template_id` (industry_template_id)
- `idx_coa_ledger_accounts_source_type` (source_type)
- `idx_coa_ledger_accounts_tenant_id` (tenant_id)
- `uq_coa_ledger_accounts_global_code_ver` (industry_template_id, source_type, version, code)
- `uq_coa_ledger_accounts_tenant_code_ver` (industry_template_id, tenant_id, source_type, version, code)

---

### coa_upload_batches

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | Yes | — |
| template_id | UUID | Yes | — |
| source_type | VARCHAR(14) | No | — |
| upload_mode | VARCHAR(13) | No | CoaUploadMode.APPEND |
| file_name | VARCHAR(255) | No | — |
| upload_status | VARCHAR(10) | No | CoaUploadStatus.PENDING |
| confirmation_status | VARCHAR(9) | No | CoaBatchConfirmationStatus.PENDING |
| error_log | JSONB | Yes | — |
| created_by | UUID | Yes | — |
| created_at | DATETIME | No | now() |
| processed_at | DATETIME | Yes | — |

**Foreign keys:**
- `created_by` -> `iam_users.id`
- `template_id` -> `coa_industry_templates.id`
- `tenant_id` -> `iam_tenants.id`

**Indexes:**
- `idx_coa_upload_batches_source_type` (source_type)
- `idx_coa_upload_batches_template_id` (template_id)
- `idx_coa_upload_batches_tenant_id` (tenant_id)
- `idx_coa_upload_batches_upload_status` (upload_status)

---

### coa_upload_staging_rows

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| batch_id | UUID | No | — |
| tenant_id | UUID | Yes | — |
| template_id | UUID | Yes | — |
| row_number | INTEGER | No | — |
| group_code | VARCHAR(50) | No | — |
| group_name | VARCHAR(300) | No | — |
| subgroup_code | VARCHAR(50) | No | — |
| subgroup_name | VARCHAR(300) | No | — |
| ledger_code | VARCHAR(50) | No | — |
| ledger_name | VARCHAR(300) | No | — |
| ledger_type | VARCHAR(20) | No | — |
| is_control_account | BOOLEAN | No | False |
| validation_errors | JSONB | Yes | — |
| is_valid | BOOLEAN | No | True |
| created_at | DATETIME | No | now() |

**Foreign keys:**
- `batch_id` -> `coa_upload_batches.id`
- `template_id` -> `coa_industry_templates.id`
- `tenant_id` -> `iam_tenants.id`

**Indexes:**
- `idx_coa_upload_staging_rows_batch_id` (batch_id)
- `idx_coa_upload_staging_rows_is_valid` (is_valid)

---

### compliance_controls

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| framework | VARCHAR(20) | No | — |
| control_id | VARCHAR(30) | No | — |
| control_name | VARCHAR(300) | No | — |
| control_description | TEXT | Yes | — |
| category | VARCHAR(100) | No | — |
| status | VARCHAR(20) | No | not_evaluated |
| rag_status | VARCHAR(10) | No | grey |
| last_evaluated_at | DATETIME | Yes | — |
| next_evaluation_due | DATETIME | Yes | — |
| evidence_summary | TEXT | Yes | — |
| auto_evaluable | BOOLEAN | No | False |
| created_at | DATETIME | No | now() |
| updated_at | DATETIME | No | now() |

**Indexes:**
- `idx_compliance_controls_tenant_framework_category` (tenant_id, framework, category)

---

### compliance_events

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: Yes

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| framework | VARCHAR(20) | No | — |
| control_id | VARCHAR(30) | No | — |
| event_type | VARCHAR(50) | No | — |
| previous_status | VARCHAR(20) | Yes | — |
| new_status | VARCHAR(20) | No | — |
| evidence_snapshot | JSONB | Yes | — |
| triggered_by | VARCHAR(100) | No | — |
| notes | TEXT | Yes | — |
| created_at | DATETIME | No | now() |

**Indexes:**
- `idx_compliance_events_tenant_framework_control_created` (tenant_id, framework, control_id)

---

### consolidation_adjustment_definitions

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| organisation_id | UUID | No | — |
| adjustment_code | VARCHAR(128) | No | — |
| adjustment_name | VARCHAR(255) | No | — |
| adjustment_type | VARCHAR(64) | No | — |
| logic_json | JSONB | No | <function dict at 0x00000272FA527BA0> |
| version_token | VARCHAR(64) | No | — |
| effective_from | DATE | No | — |
| effective_to | DATE | Yes | — |
| supersedes_id | UUID | Yes | — |
| status | VARCHAR(32) | No | candidate |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `supersedes_id` -> `consolidation_adjustment_definitions.id`

**Indexes:**
- `idx_consolidation_adjustment_definitions_lookup` (tenant_id, organisation_id, adjustment_code, effective_from, created_at)
- `ix_consolidation_adjustment_definitions_tenant_id` (tenant_id)
- `uq_consolidation_adjustment_definitions_one_active` (tenant_id, organisation_id, adjustment_code)

---

### consolidation_eliminations

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| run_id | UUID | No | — |
| intercompany_pair_id | UUID | No | — |
| entity_from | UUID | No | — |
| entity_to | UUID | No | — |
| account_code | VARCHAR(64) | No | — |
| classification_at_time | VARCHAR(64) | No | — |
| elimination_status | VARCHAR(32) | No | — |
| eliminated_amount_parent | NUMERIC(20, 6) | No | — |
| fx_component_impact_parent | NUMERIC(20, 6) | No | — |
| residual_difference_parent | NUMERIC(20, 6) | No | — |
| rule_code | VARCHAR(64) | No | — |
| reason | TEXT | No | — |
| correlation_id | VARCHAR(64) | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `intercompany_pair_id` -> `intercompany_pairs.id`
- `run_id` -> `consolidation_runs.id`

**Indexes:**
- `idx_consol_elims_status` (tenant_id, run_id, elimination_status)
- `idx_consol_elims_tenant_run` (tenant_id, run_id)
- `ix_consolidation_eliminations_tenant_id` (tenant_id)

---

### consolidation_entities

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| run_id | UUID | No | — |
| entity_id | UUID | No | — |
| entity_currency | VARCHAR(3) | No | — |
| source_snapshot_reference | UUID | No | — |
| expected_rate | NUMERIC(20, 6) | Yes | — |
| correlation_id | VARCHAR(64) | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `run_id` -> `consolidation_runs.id`
- `source_snapshot_reference` -> `normalized_financial_snapshots.snapshot_id`

**Indexes:**
- `idx_consol_entities_tenant_run` (tenant_id, run_id)
- `ix_consolidation_entities_tenant_id` (tenant_id)

---

### consolidation_line_items

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| run_id | UUID | No | — |
| entity_id | UUID | No | — |
| snapshot_line_id | UUID | No | — |
| account_code | VARCHAR(64) | No | — |
| local_currency | VARCHAR(3) | No | — |
| local_amount | NUMERIC(20, 6) | No | — |
| fx_rate_used | NUMERIC(20, 6) | No | — |
| expected_rate | NUMERIC(20, 6) | No | — |
| parent_amount | NUMERIC(20, 6) | No | — |
| fx_delta_component | NUMERIC(20, 6) | No | — |
| ic_reference | VARCHAR(255) | Yes | — |
| ic_counterparty_entity | UUID | Yes | — |
| transaction_date | DATE | Yes | — |
| correlation_id | VARCHAR(64) | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `run_id` -> `consolidation_runs.id`
- `snapshot_line_id` -> `normalized_financial_snapshot_lines.snapshot_line_id`

**Indexes:**
- `idx_consol_lines_account` (tenant_id, run_id, account_code)
- `idx_consol_lines_tenant_run` (tenant_id, run_id)
- `ix_consolidation_line_items_tenant_id` (tenant_id)

---

### consolidation_results

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| run_id | UUID | No | — |
| entity_id | UUID | Yes | — |
| consolidated_account_code | VARCHAR(64) | No | — |
| consolidated_amount_parent | NUMERIC(20, 6) | No | — |
| fx_impact_total | NUMERIC(20, 6) | No | — |
| correlation_id | VARCHAR(64) | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `entity_id` -> `cp_entities.id`
- `run_id` -> `consolidation_runs.id`

**Indexes:**
- `idx_consol_results_tenant_run` (tenant_id, run_id)
- `ix_consolidation_results_entity_id` (entity_id)
- `ix_consolidation_results_tenant_id` (tenant_id)

---

### consolidation_rule_definitions

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| organisation_id | UUID | No | — |
| rule_code | VARCHAR(128) | No | — |
| rule_name | VARCHAR(255) | No | — |
| rule_type | VARCHAR(64) | No | — |
| rule_logic_json | JSONB | No | <function dict at 0x00000272FA524F40> |
| version_token | VARCHAR(64) | No | — |
| effective_from | DATE | No | — |
| effective_to | DATE | Yes | — |
| supersedes_id | UUID | Yes | — |
| status | VARCHAR(32) | No | candidate |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `supersedes_id` -> `consolidation_rule_definitions.id`

**Indexes:**
- `idx_consolidation_rule_definitions_lookup` (tenant_id, organisation_id, rule_code, effective_from, created_at)
- `ix_consolidation_rule_definitions_tenant_id` (tenant_id)
- `uq_consolidation_rule_definitions_one_active` (tenant_id, organisation_id, rule_code)

---

### consolidation_run_events

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| run_id | UUID | No | — |
| event_seq | INTEGER | No | — |
| event_type | VARCHAR(64) | No | — |
| event_time | DATETIME | No | — |
| idempotency_key | VARCHAR(128) | No | — |
| metadata_json | JSONB | Yes | — |
| correlation_id | VARCHAR(64) | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `run_id` -> `consolidation_runs.id`

**Indexes:**
- `idx_consol_run_events_tenant_run` (tenant_id, run_id, event_seq)
- `ix_consolidation_run_events_tenant_id` (tenant_id)

---

### consolidation_runs

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| period_year | INTEGER | No | — |
| period_month | INTEGER | No | — |
| entity_id | UUID | Yes | — |
| parent_currency | VARCHAR(3) | No | — |
| initiated_by | UUID | No | — |
| request_signature | VARCHAR(64) | No | — |
| configuration_json | JSONB | No | — |
| workflow_id | VARCHAR(128) | No | — |
| correlation_id | VARCHAR(64) | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `entity_id` -> `cp_entities.id`

**Indexes:**
- `idx_consol_runs_tenant_created` (tenant_id, created_at)
- `idx_consol_runs_tenant_period` (tenant_id, period_year, period_month)
- `ix_consolidation_runs_entity_id` (entity_id)
- `ix_consolidation_runs_tenant_id` (tenant_id)

---

### consolidation_scopes

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| organisation_id | UUID | No | — |
| scope_code | VARCHAR(128) | No | — |
| scope_name | VARCHAR(255) | No | — |
| hierarchy_id | UUID | No | — |
| scope_selector_json | JSONB | No | <function dict at 0x00000272FA4EB880> |
| version_token | VARCHAR(64) | No | — |
| effective_from | DATE | No | — |
| effective_to | DATE | Yes | — |
| supersedes_id | UUID | Yes | — |
| status | VARCHAR(32) | No | candidate |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `hierarchy_id` -> `entity_hierarchies.id`
- `supersedes_id` -> `consolidation_scopes.id`

**Indexes:**
- `idx_consolidation_scopes_lookup` (tenant_id, organisation_id, scope_code, effective_from, created_at)
- `ix_consolidation_scopes_tenant_id` (tenant_id)
- `uq_consolidation_scopes_one_active` (tenant_id, organisation_id, scope_code)

---

### consolidation_translation_entity_results

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| run_id | UUID | No | — |
| org_entity_id | UUID | No | — |
| functional_currency | VARCHAR(3) | No | — |
| presentation_currency | VARCHAR(3) | No | — |
| closing_rate | NUMERIC(20, 8) | No | — |
| average_rate | NUMERIC(20, 8) | No | — |
| translated_assets | NUMERIC(20, 8) | No | — |
| translated_liabilities | NUMERIC(20, 8) | No | — |
| translated_equity | NUMERIC(20, 8) | No | — |
| translated_net_profit | NUMERIC(20, 8) | No | — |
| cta_amount | NUMERIC(20, 8) | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `org_entity_id` -> `org_entities.id`
- `run_id` -> `consolidation_translation_runs.id`

**Indexes:**
- `ix_consolidation_translation_entity_results_org_entity_id` (org_entity_id)
- `ix_consolidation_translation_entity_results_run_id` (run_id)
- `ix_consolidation_translation_entity_results_tenant_id` (tenant_id)

---

### consolidation_translation_runs

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| org_group_id | UUID | No | — |
| presentation_currency | VARCHAR(3) | No | — |
| as_of_date | DATE | No | — |
| status | VARCHAR(16) | No | — |
| initiated_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `initiated_by` -> `iam_users.id`
- `org_group_id` -> `org_groups.id`

**Indexes:**
- `ix_consolidation_translation_runs_tenant_id` (tenant_id)

---

### covenant_breach_events

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| covenant_id | UUID | No | — |
| tenant_id | UUID | No | — |
| entity_id | UUID | No | — |
| period | VARCHAR(7) | No | — |
| actual_value | NUMERIC(20, 6) | No | — |
| threshold_value | NUMERIC(20, 6) | No | — |
| breach_type | VARCHAR(20) | No | — |
| variance_pct | NUMERIC(8, 4) | No | — |
| computed_at | DATETIME | No | now() |

**Foreign keys:**
- `entity_id` -> `cp_entities.id`

**Indexes:**
- `idx_covenant_breach_events_covenant_period` (covenant_id, period)
- `idx_covenant_breach_events_tenant_entity` (tenant_id, entity_id)
- `idx_covenant_breach_events_tenant_type_created` (tenant_id, breach_type, computed_at)

---

### covenant_definitions

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| entity_id | UUID | No | — |
| facility_name | VARCHAR(200) | No | — |
| lender_name | VARCHAR(200) | No | — |
| covenant_type | VARCHAR(50) | No | — |
| covenant_label | VARCHAR(200) | No | — |
| threshold_value | NUMERIC(20, 6) | No | — |
| threshold_direction | VARCHAR(10) | No | — |
| measurement_frequency | VARCHAR(20) | No | — |
| is_active | BOOLEAN | No | True |
| grace_period_days | INTEGER | No | 0 |
| notification_threshold_pct | NUMERIC(5, 2) | No | 90.00 |
| created_at | DATETIME | No | now() |
| updated_at | DATETIME | No | now() |

**Foreign keys:**
- `entity_id` -> `cp_entities.id`

**Indexes:**
- `idx_covenant_definitions_tenant_active` (tenant_id, is_active)
- `idx_covenant_definitions_tenant_entity` (tenant_id, entity_id)

---

### cp_cost_centres

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| entity_id | UUID | No | — |
| parent_id | UUID | Yes | — |
| cost_centre_code | VARCHAR(50) | No | — |
| cost_centre_name | VARCHAR(200) | No | — |
| description | TEXT | Yes | — |
| is_active | BOOLEAN | No | True |
| created_at | DATETIME | No | now() |
| updated_at | DATETIME | Yes | now() |

**Foreign keys:**
- `entity_id` -> `cp_entities.id`
- `parent_id` -> `cp_cost_centres.id`
- `tenant_id` -> `iam_tenants.id`

**Indexes:**
- `idx_cp_cost_centres_entity_id` (entity_id)
- `idx_cp_cost_centres_parent_id` (parent_id)
- `idx_cp_cost_centres_tenant_id` (tenant_id)

---

### cp_entities

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| entity_code | VARCHAR(64) | No | — |
| entity_name | VARCHAR(255) | No | — |
| organisation_id | UUID | No | — |
| group_id | UUID | Yes | — |
| base_currency | VARCHAR(3) | No | — |
| country_code | VARCHAR(2) | No | — |
| pan | VARCHAR(20) | Yes | — |
| tan | VARCHAR(20) | Yes | — |
| cin | VARCHAR(30) | Yes | — |
| gstin | VARCHAR(20) | Yes | — |
| lei | VARCHAR(30) | Yes | — |
| fiscal_year_start | INTEGER | Yes | — |
| applicable_gaap | VARCHAR(20) | Yes | — |
| tax_rate | NUMERIC(5, 4) | Yes | — |
| state_code | VARCHAR(5) | Yes | — |
| registered_address | TEXT | Yes | — |
| city | VARCHAR(100) | Yes | — |
| pincode | VARCHAR(10) | Yes | — |
| status | VARCHAR(32) | No | active |
| deactivated_at | DATETIME | Yes | — |
| correlation_id | VARCHAR(64) | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `group_id` -> `cp_groups.id`
- `organisation_id` -> `cp_organisations.id`

**Indexes:**
- `idx_cp_entities_group` (tenant_id, group_id)
- `idx_cp_entities_org` (tenant_id, organisation_id)
- `ix_cp_entities_tenant_id` (tenant_id)

---

### cp_groups

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| group_code | VARCHAR(64) | No | — |
| group_name | VARCHAR(255) | No | — |
| organisation_id | UUID | No | — |
| is_active | BOOLEAN | No | True |
| correlation_id | VARCHAR(64) | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `organisation_id` -> `cp_organisations.id`

**Indexes:**
- `idx_cp_groups_org` (tenant_id, organisation_id)
- `ix_cp_groups_tenant_id` (tenant_id)

---

### cp_locations

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| entity_id | UUID | No | — |
| location_name | VARCHAR(200) | No | — |
| location_code | VARCHAR(50) | No | — |
| gstin | VARCHAR(20) | Yes | — |
| state_code | VARCHAR(5) | Yes | — |
| address_line1 | VARCHAR(300) | Yes | — |
| address_line2 | VARCHAR(300) | Yes | — |
| city | VARCHAR(100) | Yes | — |
| state | VARCHAR(100) | Yes | — |
| pincode | VARCHAR(10) | Yes | — |
| country_code | VARCHAR(3) | No | IND |
| is_primary | BOOLEAN | No | False |
| is_active | BOOLEAN | No | True |
| created_at | DATETIME | No | now() |
| updated_at | DATETIME | Yes | now() |

**Foreign keys:**
- `entity_id` -> `cp_entities.id`
- `tenant_id` -> `iam_tenants.id`

**Indexes:**
- `idx_cp_locations_entity_id` (entity_id)
- `idx_cp_locations_tenant_id` (tenant_id)

---

### cp_module_feature_flags

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| module_id | UUID | No | — |
| flag_key | VARCHAR(128) | No | — |
| flag_value | JSONB | No | — |
| rollout_mode | VARCHAR(16) | No | — |
| compute_enabled | BOOLEAN | No | — |
| write_enabled | BOOLEAN | No | — |
| visibility_enabled | BOOLEAN | No | — |
| target_scope_type | VARCHAR(16) | No | tenant |
| target_scope_id | UUID | Yes | — |
| traffic_percent | NUMERIC(5, 2) | Yes | — |
| effective_from | DATETIME | No | — |
| effective_to | DATETIME | Yes | — |
| correlation_id | VARCHAR(64) | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `module_id` -> `cp_module_registry.id`

**Indexes:**
- `idx_cp_feature_flags_lookup` (tenant_id, module_id, flag_key, effective_from)
- `ix_cp_module_feature_flags_tenant_id` (tenant_id)

---

### cp_module_registry

- **Description**: Abstract base with UUID PK and created_at.
- **RLS enabled**: No
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| module_code | VARCHAR(64) | No | — |
| module_name | VARCHAR(255) | No | — |
| engine_context | VARCHAR(64) | No | — |
| is_financial_impacting | BOOLEAN | No | True |
| is_active | BOOLEAN | No | True |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Indexes:**
- `idx_cp_module_registry_engine` (engine_context)

---

### cp_organisations

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| organisation_code | VARCHAR(64) | No | — |
| organisation_name | VARCHAR(255) | No | — |
| parent_organisation_id | UUID | Yes | — |
| supersedes_id | UUID | Yes | — |
| is_active | BOOLEAN | No | True |
| correlation_id | VARCHAR(64) | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `parent_organisation_id` -> `cp_organisations.id`
- `supersedes_id` -> `cp_organisations.id`

**Indexes:**
- `idx_cp_org_tenant_parent` (tenant_id, parent_organisation_id)
- `ix_cp_organisations_tenant_id` (tenant_id)

---

### cp_packages

- **Description**: Abstract base with UUID PK and created_at.
- **RLS enabled**: No
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| package_code | VARCHAR(64) | No | — |
| package_name | VARCHAR(255) | No | — |
| version | VARCHAR(32) | No | — |
| is_active | BOOLEAN | No | True |
| description | VARCHAR(1024) | Yes | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Indexes:**
- `idx_cp_packages_code` (package_code)

---

### cp_permissions

- **Description**: Abstract base with UUID PK and created_at.
- **RLS enabled**: No
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| permission_code | VARCHAR(128) | No | — |
| resource_type | VARCHAR(64) | No | — |
| action | VARCHAR(64) | No | — |
| description | VARCHAR(1024) | Yes | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Indexes:**
- `idx_cp_permissions_resource_action` (resource_type, action)

---

### cp_quota_policies

- **Description**: Abstract base with UUID PK and created_at.
- **RLS enabled**: No
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| quota_type | VARCHAR(64) | No | — |
| window_type | VARCHAR(16) | No | — |
| window_seconds | INTEGER | No | — |
| default_max_value | BIGINT | No | — |
| default_enforcement_mode | VARCHAR(16) | No | — |
| description | VARCHAR(1024) | Yes | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Indexes:**
- `idx_cp_quota_policy_type` (quota_type)

---

### cp_role_permissions

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| role_id | UUID | No | — |
| permission_id | UUID | No | — |
| effect | VARCHAR(8) | No | allow |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `permission_id` -> `cp_permissions.id`
- `role_id` -> `cp_roles.id`

**Indexes:**
- `idx_cp_role_permissions_role` (tenant_id, role_id)
- `ix_cp_role_permissions_tenant_id` (tenant_id)

---

### cp_roles

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| role_code | VARCHAR(64) | No | — |
| role_scope | VARCHAR(32) | No | — |
| inherits_role_id | UUID | Yes | — |
| is_active | BOOLEAN | No | True |
| description | VARCHAR(1024) | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `inherits_role_id` -> `cp_roles.id`

**Indexes:**
- `idx_cp_roles_scope` (tenant_id, role_scope, is_active)
- `ix_cp_roles_tenant_id` (tenant_id)

---

### cp_tenant_isolation_policy

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| isolation_tier | VARCHAR(16) | No | — |
| db_cluster | VARCHAR(128) | No | — |
| schema_name | VARCHAR(128) | No | — |
| worker_pool | VARCHAR(128) | No | — |
| region | VARCHAR(64) | No | — |
| migration_state | VARCHAR(32) | No | — |
| route_version | INTEGER | No | — |
| effective_from | DATETIME | No | — |
| effective_to | DATETIME | Yes | — |
| correlation_id | VARCHAR(64) | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Indexes:**
- `idx_cp_isolation_lookup` (tenant_id, migration_state, route_version)
- `ix_cp_tenant_isolation_policy_tenant_id` (tenant_id)

---

### cp_tenant_migration_events

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| isolation_policy_id | VARCHAR(128) | No | — |
| route_version | INTEGER | No | — |
| event_seq | INTEGER | No | — |
| event_type | VARCHAR(64) | No | — |
| event_time | DATETIME | No | — |
| idempotency_key | VARCHAR(128) | No | — |
| metadata_json | JSONB | Yes | — |
| correlation_id | VARCHAR(64) | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Indexes:**
- `idx_cp_tenant_migration_events` (tenant_id, route_version, event_seq)
- `ix_cp_tenant_migration_events_tenant_id` (tenant_id)

---

### cp_tenant_module_enablement

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| module_id | UUID | No | — |
| enabled | BOOLEAN | No | — |
| enablement_source | VARCHAR(64) | No | — |
| effective_from | DATETIME | No | — |
| effective_to | DATETIME | Yes | — |
| correlation_id | VARCHAR(64) | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `module_id` -> `cp_module_registry.id`

**Indexes:**
- `idx_cp_tenant_module_enabled` (tenant_id, module_id, enabled, effective_from)
- `ix_cp_tenant_module_enablement_tenant_id` (tenant_id)

---

### cp_tenant_package_assignments

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| package_id | UUID | No | — |
| assignment_status | VARCHAR(32) | No | — |
| effective_from | DATETIME | No | — |
| effective_to | DATETIME | Yes | — |
| correlation_id | VARCHAR(64) | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `package_id` -> `cp_packages.id`

**Indexes:**
- `idx_cp_tenant_package_status` (tenant_id, assignment_status, effective_from)
- `ix_cp_tenant_package_assignments_tenant_id` (tenant_id)

---

### cp_tenant_quota_assignments

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| quota_policy_id | UUID | Yes | — |
| quota_type | VARCHAR(64) | No | — |
| window_type | VARCHAR(16) | No | — |
| window_seconds | INTEGER | No | — |
| max_value | BIGINT | No | — |
| enforcement_mode | VARCHAR(16) | No | — |
| effective_from | DATETIME | No | — |
| effective_to | DATETIME | Yes | — |
| correlation_id | VARCHAR(64) | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `quota_policy_id` -> `cp_quota_policies.id`

**Indexes:**
- `idx_cp_tenant_quota_assignment` (tenant_id, quota_type, effective_from)
- `ix_cp_tenant_quota_assignments_tenant_id` (tenant_id)

---

### cp_tenant_quota_usage_events

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| quota_type | VARCHAR(64) | No | — |
| usage_delta | BIGINT | No | — |
| operation_id | UUID | No | — |
| idempotency_key | VARCHAR(128) | No | — |
| request_fingerprint | VARCHAR(128) | No | — |
| source_layer | VARCHAR(32) | No | — |
| window_start | DATETIME | No | — |
| window_end | DATETIME | No | — |
| correlation_id | VARCHAR(64) | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Indexes:**
- `idx_cp_quota_usage_window` (tenant_id, quota_type, window_start, window_end)
- `ix_cp_tenant_quota_usage_events_tenant_id` (tenant_id)

---

### cp_tenant_quota_windows

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| quota_type | VARCHAR(64) | No | — |
| window_start | DATETIME | No | — |
| window_end | DATETIME | No | — |
| consumed_value | BIGINT | No | — |
| last_event_id | UUID | No | — |
| updated_at | DATETIME | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `last_event_id` -> `cp_tenant_quota_usage_events.id`

**Indexes:**
- `idx_cp_quota_window_lookup` (tenant_id, quota_type, window_end)
- `ix_cp_tenant_quota_windows_tenant_id` (tenant_id)

---

### cp_tenants

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| tenant_code | VARCHAR(64) | No | — |
| display_name | VARCHAR(255) | No | — |
| country_code | VARCHAR(2) | No | — |
| region | VARCHAR(64) | No | — |
| billing_tier | VARCHAR(64) | No | — |
| status | VARCHAR(32) | No | active |
| correlation_id | VARCHAR(64) | Yes | — |
| deactivated_at | DATETIME | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Indexes:**
- `idx_cp_tenants_tenant_created` (tenant_id, created_at)
- `ix_cp_tenants_tenant_id` (tenant_id)

---

### cp_user_entity_assignments

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| user_id | UUID | No | — |
| entity_id | UUID | No | — |
| is_active | BOOLEAN | No | True |
| effective_from | DATETIME | No | — |
| effective_to | DATETIME | Yes | — |
| correlation_id | VARCHAR(64) | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `entity_id` -> `cp_entities.id`
- `user_id` -> `iam_users.id`

**Indexes:**
- `idx_cp_user_entity_assignment_user` (tenant_id, user_id, entity_id)
- `ix_cp_user_entity_assignments_tenant_id` (tenant_id)

---

### cp_user_organisation_assignments

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| user_id | UUID | No | — |
| organisation_id | UUID | No | — |
| is_primary | BOOLEAN | No | False |
| is_active | BOOLEAN | No | True |
| effective_from | DATETIME | No | — |
| effective_to | DATETIME | Yes | — |
| correlation_id | VARCHAR(64) | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `organisation_id` -> `cp_organisations.id`
- `user_id` -> `iam_users.id`

**Indexes:**
- `idx_cp_user_org_assignment_user` (tenant_id, user_id, organisation_id)
- `ix_cp_user_organisation_assignments_tenant_id` (tenant_id)

---

### cp_user_role_assignments

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| user_id | UUID | No | — |
| role_id | UUID | No | — |
| context_type | VARCHAR(32) | No | — |
| context_id | UUID | Yes | — |
| is_active | BOOLEAN | No | True |
| effective_from | DATETIME | No | — |
| effective_to | DATETIME | Yes | — |
| assigned_by | UUID | Yes | — |
| correlation_id | VARCHAR(64) | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `role_id` -> `cp_roles.id`
- `user_id` -> `iam_users.id`

**Indexes:**
- `idx_cp_user_role_assignment_lookup` (tenant_id, user_id, context_type)
- `ix_cp_user_role_assignments_tenant_id` (tenant_id)

---

### cp_workflow_approvals

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| stage_instance_id | UUID | No | — |
| acted_by | UUID | No | — |
| decision | VARCHAR(16) | No | — |
| decision_reason | VARCHAR(1024) | Yes | — |
| acted_at | DATETIME | No | — |
| delegated_from | UUID | Yes | — |
| idempotency_key | VARCHAR(128) | No | — |
| request_fingerprint | VARCHAR(128) | No | — |
| correlation_id | VARCHAR(64) | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `acted_by` -> `iam_users.id`
- `delegated_from` -> `iam_users.id`
- `stage_instance_id` -> `cp_workflow_stage_instances.id`

**Indexes:**
- `idx_cp_workflow_approvals_stage` (tenant_id, stage_instance_id, acted_at)
- `ix_cp_workflow_approvals_tenant_id` (tenant_id)

---

### cp_workflow_instance_events

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| workflow_instance_id | UUID | No | — |
| event_seq | INTEGER | No | — |
| event_type | VARCHAR(64) | No | — |
| event_time | DATETIME | No | — |
| idempotency_key | VARCHAR(128) | No | — |
| metadata_json | JSONB | Yes | — |
| correlation_id | VARCHAR(64) | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `workflow_instance_id` -> `cp_workflow_instances.id`

**Indexes:**
- `idx_cp_workflow_instance_events` (tenant_id, workflow_instance_id, event_seq)
- `ix_cp_workflow_instance_events_tenant_id` (tenant_id)

---

### cp_workflow_instances

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| template_id | UUID | No | — |
| template_version_id | UUID | No | — |
| module_id | UUID | No | — |
| resource_type | VARCHAR(64) | No | — |
| resource_id | UUID | No | — |
| initiated_by | UUID | No | — |
| correlation_id | VARCHAR(64) | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `module_id` -> `cp_module_registry.id`
- `template_id` -> `cp_workflow_templates.id`
- `template_version_id` -> `cp_workflow_template_versions.id`

**Indexes:**
- `idx_cp_workflow_instances_tenant_created` (tenant_id, created_at)
- `ix_cp_workflow_instances_tenant_id` (tenant_id)

---

### cp_workflow_stage_events

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| stage_instance_id | UUID | No | — |
| event_seq | INTEGER | No | — |
| event_type | VARCHAR(64) | No | — |
| event_time | DATETIME | No | — |
| idempotency_key | VARCHAR(128) | No | — |
| metadata_json | JSONB | Yes | — |
| correlation_id | VARCHAR(64) | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `stage_instance_id` -> `cp_workflow_stage_instances.id`

**Indexes:**
- `idx_cp_workflow_stage_events` (tenant_id, stage_instance_id, event_seq)
- `ix_cp_workflow_stage_events_tenant_id` (tenant_id)

---

### cp_workflow_stage_instances

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| workflow_instance_id | UUID | No | — |
| template_stage_id | UUID | No | — |
| stage_order | INTEGER | No | — |
| stage_code | VARCHAR(128) | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `template_stage_id` -> `cp_workflow_template_stages.id`
- `workflow_instance_id` -> `cp_workflow_instances.id`

**Indexes:**
- `idx_cp_workflow_stage_instances` (tenant_id, workflow_instance_id)
- `ix_cp_workflow_stage_instances_tenant_id` (tenant_id)

---

### cp_workflow_stage_role_map

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| stage_id | UUID | No | — |
| role_id | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `role_id` -> `cp_roles.id`
- `stage_id` -> `cp_workflow_template_stages.id`

**Indexes:**
- `ix_cp_workflow_stage_role_map_tenant_id` (tenant_id)

---

### cp_workflow_stage_user_map

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| stage_id | UUID | No | — |
| user_id | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `stage_id` -> `cp_workflow_template_stages.id`
- `user_id` -> `iam_users.id`

**Indexes:**
- `ix_cp_workflow_stage_user_map_tenant_id` (tenant_id)

---

### cp_workflow_template_stages

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| template_version_id | UUID | No | — |
| stage_order | INTEGER | No | — |
| stage_code | VARCHAR(128) | No | — |
| stage_type | VARCHAR(32) | No | — |
| approval_mode | VARCHAR(16) | No | — |
| threshold_type | VARCHAR(16) | No | — |
| threshold_value | INTEGER | Yes | — |
| sla_hours | INTEGER | Yes | — |
| escalation_target_role_id | UUID | Yes | — |
| is_terminal | BOOLEAN | No | False |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `template_version_id` -> `cp_workflow_template_versions.id`

**Indexes:**
- `idx_cp_workflow_template_stages_version` (tenant_id, template_version_id)
- `ix_cp_workflow_template_stages_tenant_id` (tenant_id)

---

### cp_workflow_template_versions

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| template_id | UUID | No | — |
| version_no | INTEGER | No | — |
| effective_from | DATETIME | No | — |
| effective_to | DATETIME | Yes | — |
| is_active | BOOLEAN | No | True |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `template_id` -> `cp_workflow_templates.id`

**Indexes:**
- `idx_cp_workflow_template_versions` (tenant_id, template_id, effective_from)
- `ix_cp_workflow_template_versions_tenant_id` (tenant_id)

---

### cp_workflow_templates

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| template_code | VARCHAR(128) | No | — |
| module_id | UUID | No | — |
| is_active | BOOLEAN | No | True |
| created_by | UUID | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `module_id` -> `cp_module_registry.id`

**Indexes:**
- `idx_cp_workflow_templates_module` (tenant_id, module_id)
- `ix_cp_workflow_templates_tenant_id` (tenant_id)

---

### credit_balances

- **Description**: Current credit balance for a tenant.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| tenant_id | UUID | No | — |
| balance | NUMERIC(20, 6) | No | 0 |
| reserved | NUMERIC(20, 6) | No | 0 |
| updated_at | DATETIME | No | <function utc_now at 0x00000272F97EE3E0> |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Indexes:**
- `idx_credit_balances_tenant` (tenant_id)

---

### credit_ledger

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| transaction_type | VARCHAR(32) | No | — |
| credits_delta | INTEGER | No | — |
| credits_balance_after | INTEGER | No | — |
| reference_id | VARCHAR(255) | Yes | — |
| reference_type | VARCHAR(64) | Yes | — |
| description | TEXT | No | — |
| expires_at | DATETIME | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Indexes:**
- `idx_credit_ledger_tenant_created` (tenant_id, created_at)
- `ix_credit_ledger_tenant_id` (tenant_id)

---

### credit_reservations

- **Description**: Temporary credit reservation while a task is running.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| tenant_id | UUID | No | — |
| amount | NUMERIC(20, 6) | No | — |
| task_type | VARCHAR(128) | No | — |
| status | VARCHAR(9) | No | ReservationStatus.pending |
| expires_at | DATETIME | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Indexes:**
- `ix_credit_reservations_tenant_id` (tenant_id)

---

### credit_top_ups

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| credits_purchased | INTEGER | No | — |
| amount_charged | NUMERIC(20, 6) | No | — |
| currency | VARCHAR(3) | No | — |
| provider | VARCHAR(32) | No | — |
| provider_payment_id | VARCHAR(255) | No | — |
| invoice_id | UUID | Yes | — |
| status | VARCHAR(32) | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `invoice_id` -> `billing_invoices.id`

**Indexes:**
- `idx_credit_top_ups_tenant` (tenant_id, status, created_at)
- `ix_credit_top_ups_tenant_id` (tenant_id)

---

### credit_transactions

- **Description**: TIER 1 IMMUTABLE: records every credit movement.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| user_id | UUID | Yes | — |
| task_type | VARCHAR(128) | No | — |
| amount | NUMERIC(20, 6) | No | — |
| direction | VARCHAR(6) | No | — |
| balance_before | NUMERIC(20, 6) | No | — |
| balance_after | NUMERIC(20, 6) | No | — |
| reservation_id | UUID | Yes | — |
| status | VARCHAR(9) | No | CreditTransactionStatus.confirmed |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Indexes:**
- `idx_credit_tx_tenant_created` (tenant_id, created_at)
- `ix_credit_transactions_tenant_id` (tenant_id)

---

### delivery_logs

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| schedule_id | UUID | No | — |
| triggered_at | DATETIME | No | now() |
| completed_at | DATETIME | Yes | — |
| status | VARCHAR(50) | No | PENDING |
| channel_type | VARCHAR(20) | No | — |
| recipient_address | TEXT | No | — |
| source_run_id | UUID | Yes | — |
| error_message | TEXT | Yes | — |
| retry_count | INTEGER | No | 0 |
| idempotency_key | VARCHAR(64) | Yes | — |
| response_metadata | JSONB | No | <function dict at 0x00000272FA0B58A0> |
| created_at | DATETIME | No | now() |

**Foreign keys:**
- `schedule_id` -> `delivery_schedules.id`

**Indexes:**
- `idx_delivery_logs_schedule_triggered_desc` (schedule_id)
- `idx_delivery_logs_tenant_idempotency_key` (tenant_id, idempotency_key)
- `idx_delivery_logs_tenant_status` (tenant_id, status)

---

### delivery_schedules

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| name | VARCHAR(255) | No | — |
| description | TEXT | Yes | — |
| schedule_type | VARCHAR(50) | No | — |
| source_definition_id | UUID | No | — |
| cron_expression | VARCHAR(100) | No | — |
| timezone | VARCHAR(100) | No | UTC |
| recipients | JSONB | No | <function list at 0x00000272FA0B40E0> |
| export_format | VARCHAR(20) | No | PDF |
| is_active | BOOLEAN | No | True |
| last_triggered_at | DATETIME | Yes | — |
| next_run_at | DATETIME | Yes | — |
| webhook_secret | TEXT | Yes | — |
| config | JSONB | No | <function dict at 0x00000272FA0B42C0> |
| created_by | UUID | No | — |
| created_at | DATETIME | No | now() |
| updated_at | DATETIME | No | now() |

**Indexes:**
- `idx_delivery_schedules_tenant_active` (tenant_id, is_active)
- `idx_delivery_schedules_tenant_next_run_at` (tenant_id, next_run_at)

---

### director_signoffs

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| entity_id | UUID | No | — |
| document_type | VARCHAR(50) | No | — |
| document_id | UUID | Yes | — |
| document_reference | VARCHAR(300) | No | — |
| period | VARCHAR(7) | No | — |
| signatory_user_id | UUID | No | — |
| signatory_name | VARCHAR(300) | No | — |
| signatory_role | VARCHAR(100) | No | — |
| mfa_verified | BOOLEAN | No | False |
| mfa_verified_at | DATETIME | Yes | — |
| ip_address | VARCHAR(45) | Yes | — |
| user_agent | VARCHAR(500) | Yes | — |
| declaration_text | TEXT | No | — |
| content_hash | VARCHAR(64) | No | — |
| signature_hash | VARCHAR(64) | No | — |
| status | VARCHAR(20) | No | pending |
| signed_at | DATETIME | Yes | — |
| revocation_reason | TEXT | Yes | — |
| created_at | DATETIME | No | now() |

**Foreign keys:**
- `entity_id` -> `cp_entities.id`

**Indexes:**
- `idx_director_signoffs_tenant_doc_period` (tenant_id, document_type, period)
- `idx_director_signoffs_tenant_entity` (tenant_id, entity_id)
- `idx_director_signoffs_tenant_signatory` (tenant_id, signatory_user_id)

---

### entity_hierarchies

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| organisation_id | UUID | No | — |
| hierarchy_code | VARCHAR(128) | No | — |
| hierarchy_name | VARCHAR(255) | No | — |
| hierarchy_type | VARCHAR(64) | No | — |
| version_token | VARCHAR(64) | No | — |
| effective_from | DATE | No | — |
| effective_to | DATE | Yes | — |
| supersedes_id | UUID | Yes | — |
| status | VARCHAR(32) | No | candidate |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `supersedes_id` -> `entity_hierarchies.id`

**Indexes:**
- `idx_entity_hierarchies_lookup` (tenant_id, organisation_id, hierarchy_code, effective_from, created_at)
- `ix_entity_hierarchies_tenant_id` (tenant_id)
- `uq_entity_hierarchies_one_active` (tenant_id, organisation_id, hierarchy_code)

---

### entity_hierarchy_nodes

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| hierarchy_id | UUID | No | — |
| entity_id | UUID | No | — |
| parent_node_id | UUID | Yes | — |
| node_level | INTEGER | No | — |
| effective_from | DATE | No | — |
| effective_to | DATE | Yes | — |
| supersedes_id | UUID | Yes | — |
| status | VARCHAR(32) | No | candidate |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `hierarchy_id` -> `entity_hierarchies.id`
- `parent_node_id` -> `entity_hierarchy_nodes.id`
- `supersedes_id` -> `entity_hierarchy_nodes.id`

**Indexes:**
- `idx_entity_hierarchy_nodes_lookup` (tenant_id, hierarchy_id, entity_id, node_level, created_at)
- `idx_entity_hierarchy_nodes_parent` (tenant_id, hierarchy_id, parent_node_id)
- `ix_entity_hierarchy_nodes_tenant_id` (tenant_id)
- `uq_entity_hierarchy_nodes_one_active` (tenant_id, hierarchy_id, entity_id)

---

### equity_evidence_links

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| equity_run_id | UUID | No | — |
| result_id | UUID | Yes | — |
| evidence_type | VARCHAR(64) | No | — |
| evidence_ref | TEXT | No | — |
| evidence_label | VARCHAR(255) | No | — |
| evidence_payload_json | JSONB | No | <function dict at 0x00000272FA7F2160> |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `equity_run_id` -> `equity_runs.id`

**Indexes:**
- `idx_equity_evidence_links_run` (tenant_id, equity_run_id, created_at)
- `ix_equity_evidence_links_tenant_id` (tenant_id)

---

### equity_line_definitions

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| organisation_id | UUID | No | — |
| statement_definition_id | UUID | No | — |
| line_code | VARCHAR(128) | No | — |
| line_name | VARCHAR(255) | No | — |
| line_type | VARCHAR(64) | No | — |
| presentation_order | INTEGER | No | — |
| rollforward_required_flag | BOOLEAN | No | True |
| version_token | VARCHAR(64) | No | — |
| effective_from | DATE | No | — |
| effective_to | DATE | Yes | — |
| supersedes_id | UUID | Yes | — |
| status | VARCHAR(32) | No | candidate |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `statement_definition_id` -> `equity_statement_definitions.id`
- `supersedes_id` -> `equity_line_definitions.id`

**Indexes:**
- `idx_equity_line_definitions_lookup` (tenant_id, organisation_id, statement_definition_id, presentation_order, effective_from, created_at)
- `ix_equity_line_definitions_tenant_id` (tenant_id)
- `uq_equity_line_definitions_one_active` (tenant_id, organisation_id, statement_definition_id, line_code)

---

### equity_line_results

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| equity_run_id | UUID | No | — |
| line_no | INTEGER | No | — |
| line_code | VARCHAR(128) | No | — |
| opening_balance | NUMERIC(20, 6) | No | — |
| movement_amount | NUMERIC(20, 6) | No | — |
| closing_balance | NUMERIC(20, 6) | No | — |
| source_currency_amount_nullable | NUMERIC(20, 6) | Yes | — |
| reporting_currency_amount_nullable | NUMERIC(20, 6) | Yes | — |
| ownership_attributed_amount_nullable | NUMERIC(20, 6) | Yes | — |
| lineage_summary_json | JSONB | No | <function dict at 0x00000272FA7B6480> |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `equity_run_id` -> `equity_runs.id`

**Indexes:**
- `idx_equity_line_results_run` (tenant_id, equity_run_id, line_no)
- `ix_equity_line_results_tenant_id` (tenant_id)

---

### equity_rollforward_rule_definitions

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| organisation_id | UUID | No | — |
| rule_code | VARCHAR(128) | No | — |
| rule_name | VARCHAR(255) | No | — |
| rule_type | VARCHAR(64) | No | — |
| source_selector_json | JSONB | No | <function dict at 0x00000272FA781C60> |
| derivation_logic_json | JSONB | No | <function dict at 0x00000272FA782F20> |
| fx_interaction_logic_json_nullable | JSONB | Yes | — |
| ownership_interaction_logic_json_nullable | JSONB | Yes | — |
| version_token | VARCHAR(64) | No | — |
| effective_from | DATE | No | — |
| effective_to | DATE | Yes | — |
| supersedes_id | UUID | Yes | — |
| status | VARCHAR(32) | No | candidate |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `supersedes_id` -> `equity_rollforward_rule_definitions.id`

**Indexes:**
- `idx_equity_rollforward_rule_definitions_lookup` (tenant_id, organisation_id, rule_code, effective_from, created_at)
- `ix_equity_rollforward_rule_definitions_tenant_id` (tenant_id)
- `uq_equity_rollforward_rule_definitions_one_active` (tenant_id, organisation_id, rule_code)

---

### equity_runs

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| organisation_id | UUID | No | — |
| reporting_period | DATE | No | — |
| statement_definition_version_token | VARCHAR(64) | No | — |
| line_definition_version_token | VARCHAR(64) | No | — |
| rollforward_rule_version_token | VARCHAR(64) | No | — |
| source_mapping_version_token | VARCHAR(64) | No | — |
| consolidation_run_ref_nullable | UUID | Yes | — |
| fx_translation_run_ref_nullable | UUID | Yes | — |
| ownership_consolidation_run_ref_nullable | UUID | Yes | — |
| run_token | VARCHAR(64) | No | — |
| run_status | VARCHAR(32) | No | created |
| validation_summary_json | JSONB | No | <function dict at 0x00000272FA7B5DA0> |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `consolidation_run_ref_nullable` -> `multi_entity_consolidation_runs.id`
- `fx_translation_run_ref_nullable` -> `fx_translation_runs.id`
- `ownership_consolidation_run_ref_nullable` -> `ownership_consolidation_runs.id`

**Indexes:**
- `idx_equity_runs_lookup` (tenant_id, organisation_id, reporting_period, created_at)
- `ix_equity_runs_tenant_id` (tenant_id)

---

### equity_source_mappings

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| organisation_id | UUID | No | — |
| mapping_code | VARCHAR(128) | No | — |
| line_code | VARCHAR(128) | No | — |
| source_type | VARCHAR(64) | No | — |
| source_selector_json | JSONB | No | <function dict at 0x00000272FA783420> |
| transformation_logic_json | JSONB | No | <function dict at 0x00000272FA7B4720> |
| version_token | VARCHAR(64) | No | — |
| effective_from | DATE | No | — |
| effective_to | DATE | Yes | — |
| supersedes_id | UUID | Yes | — |
| status | VARCHAR(32) | No | candidate |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `supersedes_id` -> `equity_source_mappings.id`

**Indexes:**
- `idx_equity_source_mappings_lookup` (tenant_id, organisation_id, mapping_code, line_code, effective_from, created_at)
- `ix_equity_source_mappings_tenant_id` (tenant_id)
- `uq_equity_source_mappings_one_active` (tenant_id, organisation_id, mapping_code, line_code, source_type)

---

### equity_statement_definitions

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| organisation_id | UUID | No | — |
| statement_code | VARCHAR(128) | No | — |
| statement_name | VARCHAR(255) | No | — |
| reporting_currency_basis | VARCHAR(32) | No | — |
| ownership_basis_flag | BOOLEAN | No | False |
| version_token | VARCHAR(64) | No | — |
| effective_from | DATE | No | — |
| effective_to | DATE | Yes | — |
| supersedes_id | UUID | Yes | — |
| status | VARCHAR(32) | No | candidate |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `supersedes_id` -> `equity_statement_definitions.id`

**Indexes:**
- `idx_equity_statement_definitions_lookup` (tenant_id, organisation_id, statement_code, effective_from, created_at)
- `ix_equity_statement_definitions_tenant_id` (tenant_id)
- `uq_equity_statement_definitions_one_active` (tenant_id, organisation_id, statement_code)

---

### equity_statement_results

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| equity_run_id | UUID | No | — |
| total_equity_opening | NUMERIC(20, 6) | No | — |
| total_equity_closing | NUMERIC(20, 6) | No | — |
| statement_payload_json | JSONB | No | <function dict at 0x00000272FA7B7CE0> |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `equity_run_id` -> `equity_runs.id`

**Indexes:**
- `idx_equity_statement_results_run` (tenant_id, equity_run_id)
- `ix_equity_statement_results_tenant_id` (tenant_id)

---

### erasure_log

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| user_id | UUID | Yes | — |
| user_id_hash | VARCHAR(64) | No | — |
| requested_by | UUID | Yes | — |
| request_method | VARCHAR(20) | No | — |
| status | VARCHAR(20) | No | — |
| pii_fields_erased | JSONB | No | '[]'::jsonb |
| completed_at | DATETIME | Yes | — |
| created_at | DATETIME | No | now() |

**Indexes:**
- `idx_erasure_log_tenant_created` (tenant_id)

---

### erp_account_external_refs

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | <function uuid4 at 0x00000272FA92E700> |
| tenant_id | UUID | No | — |
| mapping_id | UUID | No | — |
| connector_type | VARCHAR(32) | No | — |
| external_account_id | VARCHAR(256) | No | — |
| external_account_code | VARCHAR(128) | Yes | — |
| external_account_name | VARCHAR(256) | Yes | — |
| internal_account_code | VARCHAR(32) | No | — |
| last_synced_at | DATETIME | Yes | — |
| source_version_token | VARCHAR(256) | Yes | — |
| is_stale | BOOLEAN | No | False |
| stale_detected_at | DATETIME | Yes | — |
| is_active | BOOLEAN | No | True |
| created_at | DATETIME | No | now() |
| updated_at | DATETIME | No | now() |
| chain_hash | VARCHAR(64) | Yes | — |
| previous_hash | VARCHAR(64) | Yes | — |

**Foreign keys:**
- `mapping_id` -> `external_mapping_definitions.id`

**Indexes:**
- `ix_erp_account_external_refs_connector` (tenant_id, connector_type)
- `ix_erp_account_external_refs_internal_code` (tenant_id, connector_type, internal_account_code)
- `ix_erp_account_external_refs_mapping` (mapping_id)
- `ix_erp_account_external_refs_stale` (tenant_id, is_stale)
- `ix_erp_account_external_refs_tenant` (tenant_id)

---

### erp_account_mappings

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| entity_id | UUID | No | — |
| erp_connector_type | VARCHAR(50) | No | — |
| erp_account_code | VARCHAR(200) | No | — |
| erp_account_name | VARCHAR(300) | No | — |
| erp_account_type | VARCHAR(100) | Yes | — |
| tenant_coa_account_id | UUID | Yes | — |
| mapping_confidence | NUMERIC(5, 4) | Yes | — |
| is_auto_mapped | BOOLEAN | No | False |
| is_confirmed | BOOLEAN | No | False |
| confirmed_by | UUID | Yes | — |
| confirmed_at | DATETIME | Yes | — |
| notes | TEXT | Yes | — |
| is_active | BOOLEAN | No | True |
| created_at | DATETIME | No | now() |
| updated_at | DATETIME | Yes | now() |

**Foreign keys:**
- `confirmed_by` -> `iam_users.id`
- `entity_id` -> `cp_entities.id`
- `tenant_coa_account_id` -> `tenant_coa_accounts.id`
- `tenant_id` -> `iam_tenants.id`

**Indexes:**
- `idx_erp_account_mappings_entity_id` (entity_id)
- `idx_erp_account_mappings_erp_connector_type` (erp_connector_type)
- `idx_erp_account_mappings_is_confirmed` (is_confirmed)
- `idx_erp_account_mappings_tenant_id` (tenant_id)

---

### erp_attachment_links

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| attachment_id | UUID | No | — |
| connector_type | VARCHAR(32) | No | — |
| erp_document_id | VARCHAR(256) | Yes | — |
| erp_journal_id | VARCHAR(256) | Yes | — |
| push_status | VARCHAR(16) | No | PENDING |
| push_error | TEXT | Yes | — |
| pushed_at | DATETIME | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `attachment_id` -> `accounting_attachments.id`

**Indexes:**
- `ix_erp_attachment_links_attachment_id` (attachment_id)
- `ix_erp_attachment_links_tenant_id` (tenant_id)

---

### erp_coa_mappings

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| erp_connector_id | UUID | No | — |
| erp_account_id | VARCHAR(256) | No | — |
| internal_account_id | UUID | Yes | — |
| created_at | DATETIME | No | now() |
| updated_at | DATETIME | Yes | now() |

**Foreign keys:**
- `erp_connector_id` -> `erp_connectors.id`
- `internal_account_id` -> `tenant_coa_accounts.id`
- `tenant_id` -> `iam_tenants.id`

**Indexes:**
- `ix_erp_coa_mappings_internal` (tenant_id, internal_account_id)
- `ix_erp_coa_mappings_tenant` (tenant_id)

---

### erp_connectors

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| org_entity_id | UUID | No | — |
| erp_type | VARCHAR(32) | No | — |
| connection_config | JSONB | No | <function dict at 0x00000272FA9F7A60> |
| auth_type | VARCHAR(7) | No | — |
| status | VARCHAR(8) | No | ErpConnectorStatus.ACTIVE |
| last_sync_at | DATETIME | Yes | — |
| created_by | UUID | Yes | — |
| created_at | DATETIME | No | now() |
| updated_at | DATETIME | Yes | now() |

**Foreign keys:**
- `created_by` -> `iam_users.id`
- `org_entity_id` -> `cp_entities.id`
- `tenant_id` -> `iam_tenants.id`

**Indexes:**
- `ix_erp_connectors_entity` (tenant_id, org_entity_id)
- `ix_erp_connectors_status` (tenant_id, status)
- `ix_erp_connectors_tenant` (tenant_id)

---

### erp_journal_mappings

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| erp_connector_id | UUID | No | — |
| internal_journal_id | UUID | No | — |
| erp_journal_id | VARCHAR(256) | No | — |
| created_at | DATETIME | No | now() |

**Foreign keys:**
- `erp_connector_id` -> `erp_connectors.id`
- `internal_journal_id` -> `accounting_jv_aggregates.id`
- `tenant_id` -> `iam_tenants.id`

**Indexes:**
- `ix_erp_journal_mappings_connector` (tenant_id, erp_connector_id)
- `ix_erp_journal_mappings_tenant` (tenant_id)

---

### erp_master_mappings

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| org_entity_id | UUID | No | — |
| erp_connector_id | UUID | No | — |
| entity_type | VARCHAR(8) | No | — |
| erp_id | VARCHAR(256) | No | — |
| internal_id | VARCHAR(256) | No | — |
| created_at | DATETIME | No | now() |
| updated_at | DATETIME | Yes | now() |

**Foreign keys:**
- `erp_connector_id` -> `erp_connectors.id`
- `org_entity_id` -> `cp_entities.id`
- `tenant_id` -> `iam_tenants.id`

**Indexes:**
- `ix_erp_master_mappings_entity_scope` (tenant_id, org_entity_id)
- `ix_erp_master_mappings_tenant_type` (tenant_id, entity_type)

---

### erp_oauth_sessions

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | <function uuid4 at 0x00000272FA8814E0> |
| tenant_id | UUID | No | — |
| entity_id | UUID | Yes | — |
| connection_id | UUID | No | — |
| provider | VARCHAR(32) | No | — |
| state_token | VARCHAR(128) | No | — |
| code_verifier_enc | TEXT | No | — |
| redirect_uri | TEXT | No | — |
| scopes | TEXT | Yes | — |
| status | VARCHAR(16) | No | PENDING |
| expires_at | DATETIME | No | — |
| consumed_at | DATETIME | Yes | — |
| initiated_by_user_id | UUID | Yes | — |
| encrypted_tokens | TEXT | Yes | — |
| token_expires_at | DATETIME | Yes | — |
| created_at | DATETIME | No | now() |

**Foreign keys:**
- `connection_id` -> `external_connections.id`
- `entity_id` -> `cp_entities.id`

**Indexes:**
- `idx_erp_oauth_sessions_connection_status` (connection_id, status)
- `idx_erp_oauth_sessions_tenant_created` (tenant_id, created_at)
- `ix_erp_oauth_sessions_connection_id` (connection_id)
- `ix_erp_oauth_sessions_entity_id` (entity_id)
- `ix_erp_oauth_sessions_state_token` (state_token)
- `ix_erp_oauth_sessions_tenant_id` (tenant_id)

---

### erp_push_events

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| push_run_id | UUID | No | — |
| jv_id | UUID | No | — |
| event_type | VARCHAR(64) | No | — |
| event_data | JSONB | Yes | — |
| occurred_at | DATETIME | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `jv_id` -> `accounting_jv_aggregates.id`
- `push_run_id` -> `erp_push_runs.id`

**Indexes:**
- `ix_erp_push_events_jv_id` (jv_id)
- `ix_erp_push_events_push_run_id` (push_run_id)
- `ix_erp_push_events_tenant_id` (tenant_id)

---

### erp_push_idempotency_keys

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| idempotency_key | VARCHAR(64) | No | — |
| jv_id | UUID | No | — |
| push_run_id | UUID | Yes | — |
| status | VARCHAR(32) | No | — |
| external_journal_id | VARCHAR(256) | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `jv_id` -> `accounting_jv_aggregates.id`
- `push_run_id` -> `erp_push_runs.id`

**Indexes:**
- `ix_erp_push_idempotency_keys_jv_id` (jv_id)
- `ix_erp_push_idempotency_keys_lookup` (tenant_id, idempotency_key, created_at)
- `ix_erp_push_idempotency_keys_tenant_id` (tenant_id)

---

### erp_push_runs

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| jv_id | UUID | No | — |
| jv_version | INTEGER | No | — |
| connection_id | UUID | No | — |
| connector_type | VARCHAR(32) | No | — |
| idempotency_key | VARCHAR(64) | No | — |
| status | VARCHAR(32) | No | — |
| external_journal_id | VARCHAR(256) | Yes | — |
| error_code | VARCHAR(64) | Yes | — |
| error_message | TEXT | Yes | — |
| error_category | VARCHAR(16) | Yes | — |
| attempt_number | INTEGER | No | 1 |
| erp_response | JSONB | Yes | — |
| pushed_at | DATETIME | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `connection_id` -> `external_connections.id`
- `jv_id` -> `accounting_jv_aggregates.id`

**Indexes:**
- `ix_erp_push_runs_connection_id` (connection_id)
- `ix_erp_push_runs_idempotency_key` (tenant_id, idempotency_key)
- `ix_erp_push_runs_jv_id` (jv_id)
- `ix_erp_push_runs_status` (tenant_id, status)
- `ix_erp_push_runs_tenant_id` (tenant_id)

---

### erp_sync_jobs

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| org_entity_id | UUID | No | — |
| erp_connector_id | UUID | No | — |
| sync_type | VARCHAR(6) | No | — |
| module | VARCHAR(9) | No | — |
| status | VARCHAR(7) | No | ErpSyncStatus.PENDING |
| started_at | DATETIME | Yes | — |
| completed_at | DATETIME | Yes | — |
| error_message | TEXT | Yes | — |
| retry_count | INTEGER | No | 0 |
| request_payload | JSONB | Yes | — |
| result_summary | JSONB | Yes | — |
| created_by | UUID | Yes | — |
| created_at | DATETIME | No | now() |
| updated_at | DATETIME | Yes | now() |

**Foreign keys:**
- `created_by` -> `iam_users.id`
- `erp_connector_id` -> `erp_connectors.id`
- `org_entity_id` -> `cp_entities.id`
- `tenant_id` -> `iam_tenants.id`

**Indexes:**
- `idx_erp_sync_jobs_tenant_created` (tenant_id, created_at)
- `ix_erp_sync_jobs_connector` (tenant_id, erp_connector_id)
- `ix_erp_sync_jobs_module` (tenant_id, module)
- `ix_erp_sync_jobs_status` (tenant_id, status)
- `ix_erp_sync_jobs_tenant` (tenant_id)

---

### erp_sync_logs

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: No
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| job_id | UUID | No | — |
| payload_json | JSONB | Yes | — |
| result_json | JSONB | Yes | — |
| created_at | DATETIME | No | now() |

**Foreign keys:**
- `job_id` -> `erp_sync_jobs.id`

**Indexes:**
- `ix_erp_sync_logs_created` (created_at)
- `ix_erp_sync_logs_job` (job_id)

---

### erp_webhook_events

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| connector_type | VARCHAR(32) | No | — |
| message_id | VARCHAR(255) | No | — |
| event_type | VARCHAR(128) | No | — |
| canonical_event_type | VARCHAR(64) | Yes | — |
| payload | JSONB | No | — |
| raw_headers | JSONB | Yes | — |
| signature_verified | BOOLEAN | No | False |
| processed | BOOLEAN | No | False |
| processed_at | DATETIME | Yes | — |
| processing_error | TEXT | Yes | — |
| dead_lettered | BOOLEAN | No | False |
| dead_letter_reason | TEXT | Yes | — |
| received_at | DATETIME | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Indexes:**
- `ix_erp_webhook_events_canonical_type` (tenant_id, canonical_event_type)
- `ix_erp_webhook_events_connector_type` (tenant_id, connector_type)
- `ix_erp_webhook_events_dead_lettered` (tenant_id, dead_lettered)
- `ix_erp_webhook_events_processed` (tenant_id, processed, received_at)
- `ix_erp_webhook_events_tenant_id` (tenant_id)

---

### expense_approvals

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: Yes

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| claim_id | UUID | No | — |
| tenant_id | UUID | No | — |
| approver_id | UUID | No | — |
| approver_role | VARCHAR(50) | No | — |
| action | VARCHAR(20) | No | — |
| comments | TEXT | Yes | — |
| created_at | DATETIME | No | now() |

**Foreign keys:**
- `approver_id` -> `iam_users.id`
- `claim_id` -> `expense_claims.id`

**Indexes:**
- `idx_expense_approvals_claim` (claim_id)

---

### expense_claims

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: Yes

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| entity_id | UUID | No | — |
| location_id | UUID | Yes | — |
| cost_centre_id | UUID | Yes | — |
| submitted_by | UUID | No | — |
| period | VARCHAR(7) | No | — |
| claim_date | DATE | No | — |
| vendor_name | VARCHAR(300) | No | — |
| vendor_gstin | VARCHAR(20) | Yes | — |
| description | TEXT | No | — |
| category | VARCHAR(50) | No | — |
| amount | NUMERIC(20, 2) | No | — |
| currency | VARCHAR(3) | No | INR |
| amount_inr | NUMERIC(20, 2) | No | — |
| receipt_url | TEXT | Yes | — |
| gst_amount | NUMERIC(20, 2) | No | 0 |
| itc_eligible | BOOLEAN | No | False |
| status | VARCHAR(30) | No | submitted |
| policy_violation_type | VARCHAR(50) | Yes | — |
| policy_violation_requires_justification | BOOLEAN | No | False |
| justification | TEXT | Yes | — |
| manager_id | UUID | Yes | — |
| manager_approved_at | DATETIME | Yes | — |
| finance_approved_at | DATETIME | Yes | — |
| gl_account_code | VARCHAR(50) | Yes | — |
| gl_account_name | VARCHAR(200) | Yes | — |
| cost_centre | VARCHAR(100) | Yes | — |
| created_at | DATETIME | No | now() |

**Foreign keys:**
- `cost_centre_id` -> `cp_cost_centres.id`
- `entity_id` -> `cp_entities.id`
- `location_id` -> `cp_locations.id`
- `submitted_by` -> `iam_users.id`

**Indexes:**
- `idx_expense_claims_cost_centre_id` (cost_centre_id)
- `idx_expense_claims_entity_id` (tenant_id, entity_id)
- `idx_expense_claims_location_id` (location_id)
- `idx_expense_claims_tenant_status` (tenant_id, status)
- `idx_expense_claims_tenant_user_period` (tenant_id, submitted_by, period)

---

### expense_policies

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| meal_limit_per_day | NUMERIC(10, 2) | No | 2000 |
| travel_limit_per_night | NUMERIC(10, 2) | No | 8000 |
| receipt_required_above | NUMERIC(10, 2) | No | 500 |
| auto_approve_below | NUMERIC(10, 2) | No | 0 |
| weekend_flag_enabled | BOOLEAN | No | True |
| round_number_flag_enabled | BOOLEAN | No | True |
| personal_merchant_keywords | JSONB | No | <function list at 0x00000272FAC8EAC0> |
| created_at | DATETIME | No | now() |
| updated_at | DATETIME | No | now() |

**Indexes:**
- `idx_expense_policies_tenant` (tenant_id)

---

### external_backdated_modification_alerts

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| sync_run_id | UUID | No | — |
| period_lock_id | UUID | No | — |
| severity | VARCHAR(16) | No | — |
| alert_status | VARCHAR(16) | No | open |
| message | TEXT | No | — |
| details_json | JSONB | No | <function dict at 0x00000272FA9BD120> |
| acknowledged_by | UUID | Yes | — |
| acknowledged_at | DATETIME | Yes | — |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `period_lock_id` -> `external_period_locks.id`
- `sync_run_id` -> `external_sync_runs.id`

**Indexes:**
- `idx_external_backdated_modification_alerts_lookup` (tenant_id, sync_run_id, created_at)
- `ix_external_backdated_modification_alerts_tenant_id` (tenant_id)

---

### external_connection_versions

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| connection_id | UUID | No | — |
| version_no | INTEGER | No | — |
| version_token | VARCHAR(64) | No | — |
| config_snapshot_json | JSONB | No | <function dict at 0x00000272FA8B84A0> |
| supersedes_id | UUID | Yes | — |
| status | VARCHAR(32) | No | candidate |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `connection_id` -> `external_connections.id`
- `supersedes_id` -> `external_connection_versions.id`

**Indexes:**
- `idx_external_connection_versions_lookup` (tenant_id, connection_id, version_no, created_at)
- `ix_external_connection_versions_tenant_id` (tenant_id)

---

### external_connections

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| organisation_id | UUID | No | — |
| entity_id | UUID | Yes | — |
| connector_type | VARCHAR(64) | No | — |
| connection_code | VARCHAR(128) | No | — |
| connection_name | VARCHAR(255) | No | — |
| source_system_instance_id | VARCHAR(255) | No | — |
| data_residency_region | VARCHAR(64) | No | in |
| pii_masking_enabled | BOOLEAN | No | True |
| consent_reference | VARCHAR(255) | Yes | — |
| pinned_connector_version | VARCHAR(64) | Yes | — |
| connection_status | VARCHAR(32) | No | draft |
| secret_ref | TEXT | Yes | — |
| encrypted_tokens | TEXT | Yes | — |
| token_expires_at | DATETIME | Yes | — |
| token_refreshed_at | DATETIME | Yes | — |
| oauth_scopes | TEXT | Yes | — |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Indexes:**
- `idx_external_connections_lookup` (tenant_id, organisation_id, connection_status, created_at)
- `ix_external_connections_tenant_id` (tenant_id)

---

### external_connector_capability_registry

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| connector_type | VARCHAR(64) | No | — |
| dataset_type | VARCHAR(128) | No | — |
| supports_full_sync | BOOLEAN | No | True |
| supports_incremental_sync | BOOLEAN | No | False |
| supports_resumable_extraction | BOOLEAN | No | False |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Indexes:**
- `idx_external_connector_capability_registry_lookup` (tenant_id, connector_type, dataset_type)
- `ix_external_connector_capability_registry_tenant_id` (tenant_id)

---

### external_connector_version_registry

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| connector_type | VARCHAR(64) | No | — |
| version | VARCHAR(64) | No | — |
| checksum | VARCHAR(64) | No | — |
| release_notes | TEXT | Yes | — |
| status | VARCHAR(32) | No | active |
| deprecation_date | DATE | Yes | — |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Indexes:**
- `idx_external_connector_version_registry_lookup` (tenant_id, connector_type, status, created_at)
- `ix_external_connector_version_registry_tenant_id` (tenant_id)

---

### external_data_consent_logs

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| connection_id | UUID | No | — |
| sync_run_id | UUID | Yes | — |
| consent_reference | VARCHAR(255) | No | — |
| consent_action | VARCHAR(32) | No | — |
| consent_payload_json | JSONB | No | <function dict at 0x00000272FA9F6160> |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `connection_id` -> `external_connections.id`
- `sync_run_id` -> `external_sync_runs.id`

**Indexes:**
- `idx_external_data_consent_logs_lookup` (tenant_id, connection_id, created_at)
- `ix_external_data_consent_logs_tenant_id` (tenant_id)

---

### external_mapping_definitions

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| entity_id | UUID | Yes | — |
| organisation_id | UUID | No | — |
| mapping_code | VARCHAR(128) | No | — |
| mapping_name | VARCHAR(255) | No | — |
| dataset_type | VARCHAR(128) | No | — |
| mapping_status | VARCHAR(32) | No | draft |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `entity_id` -> `cp_entities.id`

**Indexes:**
- `idx_external_mapping_definitions_lookup` (tenant_id, organisation_id, mapping_status, created_at)
- `ix_external_mapping_definitions_entity_id` (entity_id)
- `ix_external_mapping_definitions_tenant_id` (tenant_id)

---

### external_mapping_versions

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| entity_id | UUID | Yes | — |
| mapping_definition_id | UUID | No | — |
| version_no | INTEGER | No | — |
| version_token | VARCHAR(64) | No | — |
| mapping_payload_json | JSONB | No | <function dict at 0x00000272FA959080> |
| supersedes_id | UUID | Yes | — |
| status | VARCHAR(32) | No | candidate |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `entity_id` -> `cp_entities.id`
- `mapping_definition_id` -> `external_mapping_definitions.id`
- `supersedes_id` -> `external_mapping_versions.id`

**Indexes:**
- `idx_external_mapping_versions_lookup` (tenant_id, mapping_definition_id, version_no, created_at)
- `ix_external_mapping_versions_entity_id` (entity_id)
- `ix_external_mapping_versions_tenant_id` (tenant_id)

---

### external_normalized_snapshots

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| entity_id | UUID | Yes | — |
| sync_run_id | UUID | No | — |
| dataset_type | VARCHAR(128) | No | — |
| snapshot_token | VARCHAR(64) | No | — |
| storage_ref | VARCHAR(512) | No | — |
| canonical_payload_hash | VARCHAR(64) | No | — |
| frozen | BOOLEAN | No | False |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `entity_id` -> `cp_entities.id`
- `sync_run_id` -> `external_sync_runs.id`

**Indexes:**
- `idx_external_normalized_snapshots_run` (tenant_id, sync_run_id, created_at)
- `ix_external_normalized_snapshots_entity_id` (entity_id)
- `ix_external_normalized_snapshots_tenant_id` (tenant_id)

---

### external_period_locks

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| organisation_id | UUID | No | — |
| entity_id | UUID | Yes | — |
| dataset_type | VARCHAR(128) | No | — |
| period_key | VARCHAR(64) | No | — |
| lock_status | VARCHAR(32) | No | locked |
| lock_reason | TEXT | Yes | — |
| source_sync_run_id | UUID | Yes | — |
| supersedes_id | UUID | Yes | — |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `source_sync_run_id` -> `external_sync_runs.id`
- `supersedes_id` -> `external_period_locks.id`

**Indexes:**
- `idx_external_period_locks_lookup` (tenant_id, organisation_id, dataset_type, period_key)
- `ix_external_period_locks_tenant_id` (tenant_id)

---

### external_raw_snapshots

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| entity_id | UUID | Yes | — |
| sync_run_id | UUID | No | — |
| snapshot_token | VARCHAR(64) | No | — |
| storage_ref | VARCHAR(512) | No | — |
| payload_hash | VARCHAR(64) | No | — |
| payload_size_bytes | INTEGER | No | — |
| frozen | BOOLEAN | No | False |
| created_by_intent_id | UUID | Yes | — |
| recorded_by_job_id | UUID | Yes | — |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `created_by_intent_id` -> `canonical_intents.id`
- `entity_id` -> `cp_entities.id`
- `recorded_by_job_id` -> `canonical_jobs.id`
- `sync_run_id` -> `external_sync_runs.id`

**Indexes:**
- `idx_external_raw_snapshots_run` (tenant_id, sync_run_id, created_at)
- `ix_external_raw_snapshots_entity_id` (entity_id)
- `ix_external_raw_snapshots_tenant_id` (tenant_id)

---

### external_sync_definition_versions

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| sync_definition_id | UUID | No | — |
| version_no | INTEGER | No | — |
| version_token | VARCHAR(64) | No | — |
| period_resolution_json | JSONB | No | <function dict at 0x00000272FA8BACA0> |
| extraction_scope_json | JSONB | No | <function dict at 0x00000272FA8BADE0> |
| supersedes_id | UUID | Yes | — |
| status | VARCHAR(32) | No | candidate |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `supersedes_id` -> `external_sync_definition_versions.id`
- `sync_definition_id` -> `external_sync_definitions.id`

**Indexes:**
- `idx_external_sync_definition_versions_lookup` (tenant_id, sync_definition_id, version_no, created_at)
- `ix_external_sync_definition_versions_tenant_id` (tenant_id)

---

### external_sync_definitions

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| organisation_id | UUID | No | — |
| entity_id | UUID | Yes | — |
| connection_id | UUID | No | — |
| definition_code | VARCHAR(128) | No | — |
| definition_name | VARCHAR(255) | No | — |
| dataset_type | VARCHAR(128) | No | — |
| sync_mode | VARCHAR(32) | No | full |
| definition_status | VARCHAR(32) | No | draft |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `connection_id` -> `external_connections.id`

**Indexes:**
- `idx_external_sync_definitions_lookup` (tenant_id, organisation_id, definition_status, created_at)
- `ix_external_sync_definitions_tenant_id` (tenant_id)

---

### external_sync_drift_reports

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| sync_run_id | UUID | No | — |
| drift_detected | BOOLEAN | No | False |
| drift_severity | VARCHAR(16) | No | none |
| total_variances | INTEGER | No | 0 |
| metrics_checked_json | JSONB | No | <function list at 0x00000272FA9BF920> |
| generated_at | DATETIME | No | — |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `sync_run_id` -> `external_sync_runs.id`

**Indexes:**
- `idx_external_sync_drift_reports_lookup` (tenant_id, sync_run_id, created_at)
- `ix_external_sync_drift_reports_tenant_id` (tenant_id)

---

### external_sync_errors

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| entity_id | UUID | Yes | — |
| sync_run_id | UUID | No | — |
| error_code | VARCHAR(128) | No | — |
| severity | VARCHAR(16) | No | — |
| message | TEXT | No | — |
| details_json | JSONB | No | <function dict at 0x00000272FA95BD80> |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `entity_id` -> `cp_entities.id`
- `sync_run_id` -> `external_sync_runs.id`

**Indexes:**
- `idx_external_sync_errors_run` (tenant_id, sync_run_id, created_at)
- `ix_external_sync_errors_entity_id` (entity_id)
- `ix_external_sync_errors_tenant_id` (tenant_id)

---

### external_sync_evidence_links

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| entity_id | UUID | Yes | — |
| sync_run_id | UUID | No | — |
| evidence_type | VARCHAR(64) | No | — |
| evidence_ref | TEXT | No | — |
| evidence_label | VARCHAR(255) | No | — |
| evidence_payload_json | JSONB | No | <function dict at 0x00000272FA959760> |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `entity_id` -> `cp_entities.id`
- `sync_run_id` -> `external_sync_runs.id`

**Indexes:**
- `idx_external_sync_evidence_links_run` (tenant_id, sync_run_id, created_at)
- `ix_external_sync_evidence_links_entity_id` (entity_id)
- `ix_external_sync_evidence_links_tenant_id` (tenant_id)

---

### external_sync_health_alerts

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| connection_id | UUID | No | — |
| sync_run_id | UUID | Yes | — |
| dataset_type | VARCHAR(128) | Yes | — |
| alert_type | VARCHAR(64) | No | — |
| alert_status | VARCHAR(16) | No | open |
| message | TEXT | No | — |
| payload_json | JSONB | No | <function dict at 0x00000272FA9BFCE0> |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `connection_id` -> `external_connections.id`
- `sync_run_id` -> `external_sync_runs.id`

**Indexes:**
- `idx_external_sync_health_alerts_lookup` (tenant_id, connection_id, alert_status, created_at)
- `ix_external_sync_health_alerts_tenant_id` (tenant_id)

---

### external_sync_publish_events

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| entity_id | UUID | Yes | — |
| sync_run_id | UUID | No | — |
| idempotency_key | VARCHAR(128) | No | — |
| event_status | VARCHAR(32) | No | pending |
| approved_by | UUID | Yes | — |
| approved_at | DATETIME | Yes | — |
| rejection_reason | TEXT | Yes | — |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `entity_id` -> `cp_entities.id`
- `sync_run_id` -> `external_sync_runs.id`

**Indexes:**
- `idx_external_sync_publish_events_lookup` (tenant_id, sync_run_id, created_at)
- `ix_external_sync_publish_events_entity_id` (entity_id)
- `ix_external_sync_publish_events_tenant_id` (tenant_id)

---

### external_sync_runs

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| organisation_id | UUID | No | — |
| entity_id | UUID | Yes | — |
| connection_id | UUID | No | — |
| sync_definition_id | UUID | No | — |
| sync_definition_version_id | UUID | No | — |
| dataset_type | VARCHAR(128) | No | — |
| reporting_period_label | VARCHAR(64) | Yes | — |
| run_token | VARCHAR(64) | No | — |
| idempotency_key | VARCHAR(128) | No | — |
| source_airlock_item_id | UUID | Yes | — |
| source_type | VARCHAR(64) | Yes | — |
| source_external_ref | VARCHAR(255) | Yes | — |
| created_by_intent_id | UUID | Yes | — |
| recorded_by_job_id | UUID | Yes | — |
| run_status | VARCHAR(32) | No | created |
| raw_snapshot_payload_hash | VARCHAR(64) | Yes | — |
| mapping_version_token | VARCHAR(64) | Yes | — |
| normalization_version | VARCHAR(64) | Yes | — |
| validation_summary_json | JSONB | No | <function dict at 0x00000272FA8BB2E0> |
| extraction_total_records | INTEGER | Yes | — |
| extraction_fetched_records | INTEGER | No | 0 |
| extraction_checkpoint | JSONB | Yes | — |
| extraction_chunk_size | INTEGER | No | 500 |
| is_resumable | BOOLEAN | No | False |
| resumed_from_run_id | UUID | Yes | — |
| published_at | DATETIME | Yes | — |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `connection_id` -> `external_connections.id`
- `created_by_intent_id` -> `canonical_intents.id`
- `recorded_by_job_id` -> `canonical_jobs.id`
- `resumed_from_run_id` -> `external_sync_runs.id`
- `source_airlock_item_id` -> `airlock_items.id`
- `sync_definition_id` -> `external_sync_definitions.id`
- `sync_definition_version_id` -> `external_sync_definition_versions.id`

**Indexes:**
- `idx_external_sync_runs_lookup` (tenant_id, organisation_id, dataset_type, created_at)
- `ix_external_sync_runs_tenant_id` (tenant_id)

---

### external_sync_sla_configs

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| organisation_id | UUID | No | — |
| connection_id | UUID | No | — |
| dataset_type | VARCHAR(128) | No | — |
| sla_hours | INTEGER | No | — |
| consecutive_failure_threshold | INTEGER | No | 3 |
| active | BOOLEAN | No | True |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `connection_id` -> `external_connections.id`

**Indexes:**
- `idx_external_sync_sla_configs_lookup` (tenant_id, organisation_id, dataset_type)
- `ix_external_sync_sla_configs_tenant_id` (tenant_id)

---

### fa_asset_classes

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| entity_id | UUID | No | — |
| name | VARCHAR(200) | No | — |
| asset_type | VARCHAR(20) | No | — |
| default_method | VARCHAR(20) | No | — |
| default_useful_life_years | INTEGER | Yes | — |
| default_residual_pct | NUMERIC(5, 4) | Yes | — |
| it_act_block_number | INTEGER | Yes | — |
| it_act_depreciation_rate | NUMERIC(5, 4) | Yes | — |
| coa_asset_account_id | UUID | Yes | — |
| coa_accum_dep_account_id | UUID | Yes | — |
| coa_dep_expense_account_id | UUID | Yes | — |
| is_active | BOOLEAN | No | True |
| created_by_intent_id | UUID | Yes | — |
| recorded_by_job_id | UUID | Yes | — |
| created_at | DATETIME | No | now() |
| updated_at | DATETIME | Yes | now() |

**Foreign keys:**
- `coa_accum_dep_account_id` -> `tenant_coa_accounts.id`
- `coa_asset_account_id` -> `tenant_coa_accounts.id`
- `coa_dep_expense_account_id` -> `tenant_coa_accounts.id`
- `entity_id` -> `cp_entities.id`
- `tenant_id` -> `iam_tenants.id`

**Indexes:**
- `idx_fa_asset_classes_entity_id` (entity_id)
- `idx_fa_asset_classes_name` (name)
- `idx_fa_asset_classes_tenant_id` (tenant_id)

---

### fa_assets

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| entity_id | UUID | No | — |
| location_id | UUID | Yes | — |
| cost_centre_id | UUID | Yes | — |
| asset_class_id | UUID | No | — |
| asset_code | VARCHAR(100) | No | — |
| asset_name | VARCHAR(300) | No | — |
| description | TEXT | Yes | — |
| location | VARCHAR(300) | Yes | — |
| serial_number | VARCHAR(200) | Yes | — |
| purchase_date | DATE | No | — |
| capitalisation_date | DATE | No | — |
| original_cost | NUMERIC(20, 4) | No | — |
| residual_value | NUMERIC(20, 4) | No | 0 |
| useful_life_years | NUMERIC(10, 4) | No | — |
| depreciation_method | VARCHAR(20) | No | — |
| it_act_block_number | INTEGER | Yes | — |
| status | VARCHAR(20) | No | — |
| disposal_date | DATE | Yes | — |
| disposal_proceeds | NUMERIC(20, 4) | Yes | — |
| gaap_overrides | JSONB | Yes | — |
| is_active | BOOLEAN | No | True |
| created_by_intent_id | UUID | Yes | — |
| recorded_by_job_id | UUID | Yes | — |
| created_at | DATETIME | No | now() |
| updated_at | DATETIME | Yes | now() |

**Foreign keys:**
- `asset_class_id` -> `fa_asset_classes.id`
- `cost_centre_id` -> `cp_cost_centres.id`
- `entity_id` -> `cp_entities.id`
- `location_id` -> `cp_locations.id`
- `tenant_id` -> `iam_tenants.id`

**Indexes:**
- `idx_fa_assets_asset_class_id` (asset_class_id)
- `idx_fa_assets_asset_code` (asset_code)
- `idx_fa_assets_cost_centre_id` (cost_centre_id)
- `idx_fa_assets_entity_id` (entity_id)
- `idx_fa_assets_location_id` (location_id)
- `idx_fa_assets_status` (status)
- `idx_fa_assets_tenant_id` (tenant_id)

---

### fa_depreciation_runs

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| entity_id | UUID | No | — |
| asset_id | UUID | No | — |
| run_date | DATE | No | — |
| period_start | DATE | No | — |
| period_end | DATE | No | — |
| gaap | VARCHAR(20) | No | — |
| depreciation_method | VARCHAR(20) | No | — |
| opening_nbv | NUMERIC(20, 4) | No | — |
| depreciation_amount | NUMERIC(20, 4) | No | — |
| closing_nbv | NUMERIC(20, 4) | No | — |
| accumulated_dep | NUMERIC(20, 4) | No | — |
| run_reference | VARCHAR(100) | No | — |
| is_reversal | BOOLEAN | No | False |
| created_by_intent_id | UUID | Yes | — |
| recorded_by_job_id | UUID | Yes | — |
| created_at | DATETIME | No | now() |

**Foreign keys:**
- `asset_id` -> `fa_assets.id`
- `entity_id` -> `cp_entities.id`
- `tenant_id` -> `iam_tenants.id`

**Indexes:**
- `idx_fa_depreciation_runs_asset_id` (asset_id)
- `idx_fa_depreciation_runs_entity_id` (entity_id)
- `idx_fa_depreciation_runs_run_date` (run_date)
- `idx_fa_depreciation_runs_tenant_id` (tenant_id)

---

### fa_impairments

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| entity_id | UUID | No | — |
| asset_id | UUID | No | — |
| impairment_date | DATE | No | — |
| pre_impairment_nbv | NUMERIC(20, 4) | No | — |
| recoverable_amount | NUMERIC(20, 4) | No | — |
| value_in_use | NUMERIC(20, 4) | Yes | — |
| fvlcts | NUMERIC(20, 4) | Yes | — |
| impairment_loss | NUMERIC(20, 4) | No | — |
| discount_rate | NUMERIC(7, 4) | Yes | — |
| created_by_intent_id | UUID | Yes | — |
| recorded_by_job_id | UUID | Yes | — |
| created_at | DATETIME | No | now() |

**Foreign keys:**
- `asset_id` -> `fa_assets.id`
- `entity_id` -> `cp_entities.id`
- `tenant_id` -> `iam_tenants.id`

**Indexes:**
- `idx_fa_impairments_asset_id` (asset_id)
- `idx_fa_impairments_entity_id` (entity_id)
- `idx_fa_impairments_impairment_date` (impairment_date)
- `idx_fa_impairments_tenant_id` (tenant_id)

---

### fa_revaluations

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| entity_id | UUID | No | — |
| asset_id | UUID | No | — |
| revaluation_date | DATE | No | — |
| pre_revaluation_cost | NUMERIC(20, 4) | No | — |
| pre_revaluation_accum_dep | NUMERIC(20, 4) | No | — |
| pre_revaluation_nbv | NUMERIC(20, 4) | No | — |
| fair_value | NUMERIC(20, 4) | No | — |
| revaluation_surplus | NUMERIC(20, 4) | No | — |
| method | VARCHAR(30) | No | — |
| created_by_intent_id | UUID | Yes | — |
| recorded_by_job_id | UUID | Yes | — |
| created_at | DATETIME | No | now() |

**Foreign keys:**
- `asset_id` -> `fa_assets.id`
- `entity_id` -> `cp_entities.id`
- `tenant_id` -> `iam_tenants.id`

**Indexes:**
- `idx_fa_revaluations_asset_id` (asset_id)
- `idx_fa_revaluations_entity_id` (entity_id)
- `idx_fa_revaluations_revaluation_date` (revaluation_date)
- `idx_fa_revaluations_tenant_id` (tenant_id)

---

### far_run_events

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| run_id | UUID | No | — |
| event_seq | INTEGER | No | — |
| event_type | VARCHAR(64) | No | — |
| event_time | DATETIME | No | — |
| idempotency_key | VARCHAR(128) | No | — |
| metadata_json | JSONB | Yes | — |
| correlation_id | VARCHAR(64) | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `run_id` -> `far_runs.id`

**Indexes:**
- `idx_far_run_events_tenant_run` (tenant_id, run_id, event_seq)
- `ix_far_run_events_tenant_id` (tenant_id)

---

### far_runs

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| request_signature | VARCHAR(64) | No | — |
| initiated_by | UUID | No | — |
| configuration_json | JSONB | No | — |
| workflow_id | VARCHAR(128) | No | — |
| correlation_id | VARCHAR(64) | Yes | — |
| created_by_intent_id | UUID | Yes | — |
| recorded_by_job_id | UUID | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Indexes:**
- `idx_far_runs_tenant_created` (tenant_id, created_at)
- `ix_far_runs_tenant_id` (tenant_id)

---

### fdd_engagements

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| engagement_name | VARCHAR(300) | No | — |
| target_company_name | VARCHAR(300) | No | — |
| analysis_period_start | DATE | No | — |
| analysis_period_end | DATE | No | — |
| status | VARCHAR(30) | No | draft |
| credit_cost | INTEGER | No | 2500 |
| credits_reserved_at | DATETIME | Yes | — |
| credits_deducted_at | DATETIME | Yes | — |
| sections_requested | JSONB | No | <function list at 0x00000272FAD98CC0> |
| sections_completed | JSONB | No | <function list at 0x00000272FAD98C20> |
| created_by | UUID | No | — |
| created_at | DATETIME | No | now() |
| updated_at | DATETIME | No | now() |

**Foreign keys:**
- `created_by` -> `iam_users.id`

**Indexes:**
- `idx_fdd_engagements_tenant_status` (tenant_id, status)

---

### fdd_findings

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: Yes

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| engagement_id | UUID | No | — |
| section_id | UUID | No | — |
| tenant_id | UUID | No | — |
| finding_type | VARCHAR(30) | No | — |
| severity | VARCHAR(20) | No | — |
| title | VARCHAR(300) | No | — |
| description | TEXT | No | — |
| financial_impact | NUMERIC(20, 2) | Yes | — |
| financial_impact_currency | VARCHAR(3) | No | INR |
| recommended_action | TEXT | Yes | — |
| created_at | DATETIME | No | now() |

**Foreign keys:**
- `engagement_id` -> `fdd_engagements.id`
- `section_id` -> `fdd_sections.id`

**Indexes:**
- `idx_fdd_findings_engagement_severity_type` (engagement_id, severity, finding_type)

---

### fdd_sections

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: Yes

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| engagement_id | UUID | No | — |
| tenant_id | UUID | No | — |
| section_name | VARCHAR(50) | No | — |
| status | VARCHAR(20) | No | — |
| result_data | JSONB | No | <function dict at 0x00000272FAD9A160> |
| ai_narrative | TEXT | Yes | — |
| computed_at | DATETIME | No | now() |
| duration_seconds | NUMERIC(8, 2) | Yes | — |

**Foreign keys:**
- `engagement_id` -> `fdd_engagements.id`

**Indexes:**
- `idx_fdd_sections_engagement_section` (engagement_id, section_name)

---

### finance_modules

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| module_name | VARCHAR(64) | No | — |
| status | VARCHAR(16) | No | DISABLED |
| configuration_json | JSONB | No | <function dict at 0x00000272ABE2AD40> |
| created_by | UUID | Yes | — |
| created_at | DATETIME | No | now() |
| updated_at | DATETIME | No | now() |

**Foreign keys:**
- `created_by` -> `iam_users.id`
- `tenant_id` -> `iam_tenants.id`

**Indexes:**
- `ix_finance_modules_tenant` (tenant_id)

---

### forecast_assumptions

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| forecast_run_id | UUID | No | — |
| tenant_id | UUID | No | — |
| assumption_key | VARCHAR(100) | No | — |
| assumption_value | NUMERIC(20, 6) | No | — |
| assumption_label | VARCHAR(200) | No | — |
| category | VARCHAR(50) | No | — |
| basis | TEXT | Yes | — |
| created_at | DATETIME | No | now() |
| updated_at | DATETIME | No | now() |

**Foreign keys:**
- `forecast_run_id` -> `forecast_runs.id`

---

### forecast_line_items

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: Yes

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| forecast_run_id | UUID | No | — |
| tenant_id | UUID | No | — |
| period | VARCHAR(7) | No | — |
| is_actual | BOOLEAN | No | False |
| mis_line_item | VARCHAR(300) | No | — |
| mis_category | VARCHAR(100) | No | — |
| amount | NUMERIC(20, 2) | No | — |
| entity_id | UUID | Yes | — |
| created_at | DATETIME | No | now() |

**Foreign keys:**
- `forecast_run_id` -> `forecast_runs.id`

**Indexes:**
- `idx_forecast_line_items_run_period_line` (forecast_run_id, period, mis_line_item)
- `idx_forecast_line_items_tenant_period` (tenant_id, period)

---

### forecast_runs

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: Yes

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| run_name | VARCHAR(200) | No | — |
| forecast_type | VARCHAR(20) | No | — |
| base_period | VARCHAR(7) | No | — |
| horizon_months | INTEGER | No | — |
| status | VARCHAR(20) | No | draft |
| is_published | BOOLEAN | No | False |
| published_at | DATETIME | Yes | — |
| published_by | UUID | Yes | — |
| created_by | UUID | No | — |
| created_at | DATETIME | No | now() |

---

### fx_manual_monthly_rates

- **Description**: Manual monthly rate profile entries.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| period_year | INTEGER | No | — |
| period_month | INTEGER | No | — |
| base_currency | VARCHAR(3) | No | — |
| quote_currency | VARCHAR(3) | No | — |
| rate | NUMERIC(20, 6) | No | — |
| entered_by | UUID | No | — |
| reason | TEXT | No | — |
| supersedes_rate_id | UUID | Yes | — |
| source_type | VARCHAR(32) | No | manual |
| is_month_end_locked | BOOLEAN | No | False |
| correlation_id | VARCHAR(64) | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `supersedes_rate_id` -> `fx_manual_monthly_rates.id`

**Indexes:**
- `idx_fx_manual_tenant_created` (tenant_id, created_at)
- `idx_fx_manual_tenant_period_pair` (tenant_id, period_year, period_month, base_currency, quote_currency)
- `ix_fx_manual_monthly_rates_tenant_id` (tenant_id)

---

### fx_rate_fetch_runs

- **Description**: Live fetch execution metadata for a currency pair and date.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| rate_date | DATE | No | — |
| base_currency | VARCHAR(3) | No | — |
| quote_currency | VARCHAR(3) | No | — |
| status | VARCHAR(20) | No | — |
| provider_count | INTEGER | No | 4 |
| success_count | INTEGER | No | 0 |
| failure_count | INTEGER | No | 0 |
| selected_rate | NUMERIC(20, 6) | Yes | — |
| selected_source | VARCHAR(64) | Yes | — |
| selection_method | VARCHAR(128) | Yes | — |
| fallback_used | BOOLEAN | No | False |
| initiated_by | UUID | Yes | — |
| correlation_id | VARCHAR(64) | Yes | — |
| provider_errors | JSONB | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Indexes:**
- `idx_fx_fetch_runs_tenant_created` (tenant_id, created_at)
- `idx_fx_fetch_runs_tenant_pair_date` (tenant_id, base_currency, quote_currency, rate_date)
- `ix_fx_rate_fetch_runs_tenant_id` (tenant_id)

---

### fx_rate_quotes

- **Description**: Normalized raw provider observation for one pair/date.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| fetch_run_id | UUID | No | — |
| provider_name | VARCHAR(64) | No | — |
| rate_date | DATE | No | — |
| base_currency | VARCHAR(3) | No | — |
| quote_currency | VARCHAR(3) | No | — |
| rate | NUMERIC(20, 6) | No | — |
| source_timestamp | DATETIME | Yes | — |
| correlation_id | VARCHAR(64) | Yes | — |
| raw_payload | JSONB | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `fetch_run_id` -> `fx_rate_fetch_runs.id`

**Indexes:**
- `idx_fx_quotes_fetch_run` (tenant_id, fetch_run_id)
- `idx_fx_quotes_tenant_pair_date_provider` (tenant_id, base_currency, quote_currency, rate_date, provider_name)
- `ix_fx_rate_quotes_tenant_id` (tenant_id)

---

### fx_rate_selection_policies

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| organisation_id | UUID | No | — |
| policy_code | VARCHAR(128) | No | — |
| policy_name | VARCHAR(255) | No | — |
| rate_type | VARCHAR(32) | No | — |
| date_selector_logic_json | JSONB | No | <function dict at 0x00000272FA5C9EE0> |
| fallback_behavior_json | JSONB | No | <function dict at 0x00000272FA5CB240> |
| locked_rate_requirement_flag | BOOLEAN | No | True |
| source_rate_provider_ref | VARCHAR(128) | No | fx_rate_tables_v1 |
| version_token | VARCHAR(64) | No | — |
| effective_from | DATE | No | — |
| effective_to | DATE | Yes | — |
| supersedes_id | UUID | Yes | — |
| status | VARCHAR(32) | No | candidate |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `supersedes_id` -> `fx_rate_selection_policies.id`

**Indexes:**
- `idx_fx_rate_selection_policies_lookup` (tenant_id, organisation_id, policy_code, effective_from, created_at)
- `ix_fx_rate_selection_policies_tenant_id` (tenant_id)
- `uq_fx_rate_selection_policies_one_active` (tenant_id, organisation_id, policy_code)

---

### fx_rates

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | Yes | — |
| from_currency | VARCHAR(3) | No | — |
| to_currency | VARCHAR(3) | No | — |
| rate | NUMERIC(20, 8) | No | — |
| rate_type | VARCHAR(16) | No | — |
| effective_date | DATE | No | — |
| source | VARCHAR(32) | No | manual |
| created_by | UUID | Yes | — |
| created_at | DATETIME | No | now() |

**Foreign keys:**
- `created_by` -> `iam_users.id`
- `tenant_id` -> `iam_tenants.id`

**Indexes:**
- `ix_fx_rates_pair_effective_type` (from_currency, to_currency, effective_date, rate_type)
- `ix_fx_rates_tenant_pair_effective_type` (tenant_id, from_currency, to_currency, effective_date, rate_type)

---

### fx_translated_metric_results

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| run_id | UUID | No | — |
| line_no | INTEGER | No | — |
| source_metric_result_id | UUID | No | — |
| metric_code | VARCHAR(128) | No | — |
| source_currency_code | VARCHAR(3) | No | — |
| reporting_currency_code | VARCHAR(3) | No | — |
| applied_rate_type | VARCHAR(32) | No | — |
| applied_rate_ref | VARCHAR(255) | No | — |
| applied_rate_value | NUMERIC(20, 8) | No | — |
| source_value | NUMERIC(20, 6) | No | — |
| translated_value | NUMERIC(20, 6) | No | — |
| lineage_json | JSONB | No | <function dict at 0x00000272FA604F40> |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `run_id` -> `fx_translation_runs.id`
- `source_metric_result_id` -> `multi_entity_consolidation_metric_results.id`

**Indexes:**
- `idx_fx_translated_metric_results_run` (tenant_id, run_id, line_no)
- `idx_fx_translated_metric_results_source` (tenant_id, run_id, source_metric_result_id)
- `ix_fx_translated_metric_results_tenant_id` (tenant_id)

---

### fx_translated_variance_results

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| run_id | UUID | No | — |
| line_no | INTEGER | No | — |
| source_variance_result_id | UUID | No | — |
| metric_code | VARCHAR(128) | No | — |
| comparison_type | VARCHAR(32) | No | — |
| source_currency_code | VARCHAR(3) | No | — |
| reporting_currency_code | VARCHAR(3) | No | — |
| applied_rate_type | VARCHAR(32) | No | — |
| applied_rate_ref | VARCHAR(255) | No | — |
| applied_rate_value | NUMERIC(20, 8) | No | — |
| source_base_value | NUMERIC(20, 6) | No | — |
| source_current_value | NUMERIC(20, 6) | No | — |
| source_variance_value | NUMERIC(20, 6) | No | — |
| translated_base_value | NUMERIC(20, 6) | No | — |
| translated_current_value | NUMERIC(20, 6) | No | — |
| translated_variance_value | NUMERIC(20, 6) | No | — |
| variance_pct | NUMERIC(20, 6) | Yes | — |
| lineage_json | JSONB | No | <function dict at 0x00000272FA607A60> |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `run_id` -> `fx_translation_runs.id`
- `source_variance_result_id` -> `multi_entity_consolidation_variance_results.id`

**Indexes:**
- `idx_fx_translated_variance_results_run` (tenant_id, run_id, line_no)
- `idx_fx_translated_variance_results_source` (tenant_id, run_id, source_variance_result_id)
- `ix_fx_translated_variance_results_tenant_id` (tenant_id)

---

### fx_translation_evidence_links

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| run_id | UUID | No | — |
| translated_metric_result_id | UUID | Yes | — |
| translated_variance_result_id | UUID | Yes | — |
| evidence_type | VARCHAR(64) | No | — |
| evidence_ref | TEXT | No | — |
| evidence_label | VARCHAR(255) | No | — |
| evidence_payload_json | JSONB | No | <function dict at 0x00000272FA63D760> |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `run_id` -> `fx_translation_runs.id`
- `translated_metric_result_id` -> `fx_translated_metric_results.id`
- `translated_variance_result_id` -> `fx_translated_variance_results.id`

**Indexes:**
- `idx_fx_translation_evidence_links_run` (tenant_id, run_id, created_at)
- `ix_fx_translation_evidence_links_tenant_id` (tenant_id)

---

### fx_translation_rule_definitions

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| organisation_id | UUID | No | — |
| rule_code | VARCHAR(128) | No | — |
| rule_name | VARCHAR(255) | No | — |
| translation_scope_type | VARCHAR(64) | No | — |
| translation_scope_ref | VARCHAR(128) | No | — |
| source_currency_selector_json | JSONB | No | <function dict at 0x00000272FA5C99E0> |
| target_reporting_currency_code | VARCHAR(3) | No | — |
| rule_logic_json | JSONB | No | <function dict at 0x00000272FA5C8900> |
| rate_policy_ref | VARCHAR(128) | No | — |
| version_token | VARCHAR(64) | No | — |
| effective_from | DATE | No | — |
| effective_to | DATE | Yes | — |
| supersedes_id | UUID | Yes | — |
| status | VARCHAR(32) | No | candidate |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `supersedes_id` -> `fx_translation_rule_definitions.id`

**Indexes:**
- `idx_fx_translation_rule_definitions_lookup` (tenant_id, organisation_id, rule_code, effective_from, created_at)
- `ix_fx_translation_rule_definitions_tenant_id` (tenant_id)
- `uq_fx_translation_rule_definitions_one_active` (tenant_id, organisation_id, rule_code)

---

### fx_translation_runs

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| organisation_id | UUID | No | — |
| reporting_period | DATE | No | — |
| reporting_currency_code | VARCHAR(3) | No | — |
| reporting_currency_version_token | VARCHAR(64) | No | — |
| translation_rule_version_token | VARCHAR(64) | No | — |
| rate_policy_version_token | VARCHAR(64) | No | — |
| rate_source_version_token | VARCHAR(64) | No | — |
| source_consolidation_run_refs_json | JSONB | No | <function list at 0x00000272FA5CB880> |
| run_token | VARCHAR(64) | No | — |
| run_status | VARCHAR(32) | No | created |
| validation_summary_json | JSONB | No | <function dict at 0x00000272FA604B80> |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Indexes:**
- `idx_fx_translation_runs_lookup` (tenant_id, organisation_id, reporting_period, created_at)
- `idx_fx_translation_runs_token` (tenant_id, run_token)
- `ix_fx_translation_runs_tenant_id` (tenant_id)

---

### fx_variance_results

- **Description**: Expected-vs-actual FX variance output for IC explanation consumers.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| period_year | INTEGER | No | — |
| period_month | INTEGER | No | — |
| entity_name | VARCHAR(255) | Yes | — |
| base_currency | VARCHAR(3) | No | — |
| quote_currency | VARCHAR(3) | No | — |
| expected_difference | NUMERIC(20, 6) | No | — |
| actual_difference | NUMERIC(20, 6) | No | — |
| fx_variance | NUMERIC(20, 6) | No | — |
| computed_by | UUID | No | — |
| notes | TEXT | Yes | — |
| correlation_id | VARCHAR(64) | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Indexes:**
- `idx_fx_variance_tenant_created` (tenant_id, created_at)
- `idx_fx_variance_tenant_period_pair` (tenant_id, period_year, period_month, base_currency, quote_currency)
- `ix_fx_variance_results_tenant_id` (tenant_id)

---

### gdpr_breach_records

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: Yes

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| breach_type | VARCHAR(50) | No | — |
| description | TEXT | No | — |
| affected_user_count | INTEGER | No | 0 |
| affected_data_types | JSONB | No | <function list at 0x00000272FAC182C0> |
| discovered_at | DATETIME | No | — |
| reported_to_dpa_at | DATETIME | Yes | — |
| notified_users_at | DATETIME | Yes | — |
| severity | VARCHAR(20) | No | — |
| status | VARCHAR(20) | No | open |
| remediation_notes | TEXT | Yes | — |
| created_by | UUID | No | — |
| created_at | DATETIME | No | now() |

**Foreign keys:**
- `created_by` -> `iam_users.id`

**Indexes:**
- `idx_gdpr_breach_tenant_discovered` (tenant_id)

---

### gdpr_consent_records

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| user_id | UUID | No | — |
| consent_type | VARCHAR(50) | No | — |
| granted | BOOLEAN | No | — |
| granted_at | DATETIME | Yes | — |
| withdrawn_at | DATETIME | Yes | — |
| ip_address | VARCHAR(45) | Yes | — |
| user_agent | VARCHAR(500) | Yes | — |
| lawful_basis | VARCHAR(50) | No | consent |
| created_at | DATETIME | No | now() |
| updated_at | DATETIME | No | now() |

**Foreign keys:**
- `user_id` -> `iam_users.id`

**Indexes:**
- `idx_gdpr_consent_tenant_user_type` (tenant_id, user_id, consent_type)

---

### gdpr_data_requests

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: Yes

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| user_id | UUID | No | — |
| request_type | VARCHAR(30) | No | — |
| status | VARCHAR(20) | No | received |
| requested_at | DATETIME | No | now() |
| completed_at | DATETIME | Yes | — |
| rejection_reason | TEXT | Yes | — |
| export_url | TEXT | Yes | — |
| created_at | DATETIME | No | now() |

**Indexes:**
- `idx_gdpr_data_requests_tenant_user_created` (tenant_id, user_id)

---

### gl_entries

- **Description**: General Ledger entry — INSERT ONLY.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| entity_id | UUID | Yes | — |
| period_year | INTEGER | No | — |
| period_month | INTEGER | No | — |
| entity_name | VARCHAR(255) | No | — |
| account_code | VARCHAR(50) | No | — |
| account_name | VARCHAR(255) | No | — |
| debit_amount | NUMERIC(20, 6) | No | 0 |
| credit_amount | NUMERIC(20, 6) | No | 0 |
| description | TEXT | Yes | — |
| source_ref | VARCHAR(255) | Yes | — |
| currency | VARCHAR(3) | No | USD |
| uploaded_by | UUID | No | — |
| created_by_intent_id | UUID | Yes | — |
| recorded_by_job_id | UUID | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `created_by_intent_id` -> `canonical_intents.id`
- `entity_id` -> `cp_entities.id`
- `recorded_by_job_id` -> `canonical_jobs.id`

**Indexes:**
- `idx_gl_entries_account` (tenant_id, account_code)
- `idx_gl_entries_tenant_period` (tenant_id, period_year, period_month)
- `ix_gl_entries_created_by_intent_id` (created_by_intent_id)
- `ix_gl_entries_entity_id` (entity_id)
- `ix_gl_entries_recorded_by_job_id` (recorded_by_job_id)
- `ix_gl_entries_tenant_id` (tenant_id)

---

### gl_normalized_lines

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| run_id | UUID | No | — |
| row_no | INTEGER | No | — |
| journal_id | VARCHAR(128) | Yes | — |
| journal_line_no | VARCHAR(64) | Yes | — |
| posting_date | DATE | Yes | — |
| document_date | DATE | Yes | — |
| posting_period | VARCHAR(16) | No | — |
| legal_entity | VARCHAR(255) | Yes | — |
| account_code | VARCHAR(128) | Yes | — |
| account_name | VARCHAR(255) | Yes | — |
| cost_center | VARCHAR(255) | Yes | — |
| department | VARCHAR(255) | Yes | — |
| business_unit | VARCHAR(255) | Yes | — |
| project | VARCHAR(255) | Yes | — |
| customer | VARCHAR(255) | Yes | — |
| vendor | VARCHAR(255) | Yes | — |
| source_module | VARCHAR(128) | Yes | — |
| source_document_id | VARCHAR(255) | Yes | — |
| currency_code | VARCHAR(3) | No | — |
| debit_amount | NUMERIC(20, 6) | No | — |
| credit_amount | NUMERIC(20, 6) | No | — |
| signed_amount | NUMERIC(20, 6) | No | — |
| local_amount | NUMERIC(20, 6) | No | — |
| transaction_amount | NUMERIC(20, 6) | No | — |
| source_row_ref | VARCHAR(128) | No | — |
| source_column_ref | VARCHAR(128) | No | — |
| normalization_status | VARCHAR(16) | No | — |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `run_id` -> `normalization_runs.id`

**Indexes:**
- `idx_gl_normalized_lines_account_period` (tenant_id, account_code, posting_period)
- `idx_gl_normalized_lines_run` (tenant_id, run_id, row_no)
- `ix_gl_normalized_lines_tenant_id` (tenant_id)

---

### governance_approval_policies

- **Description**: Abstract base with UUID PK and created_at.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| tenant_id | UUID | No | — |
| entity_id | UUID | Yes | — |
| policy_name | VARCHAR(128) | No | — |
| module_key | VARCHAR(64) | No | — |
| mutation_type | VARCHAR(64) | No | — |
| source_type | VARCHAR(64) | Yes | — |
| threshold_amount | NUMERIC(20, 4) | Yes | — |
| required_approver_role | VARCHAR(64) | No | — |
| approval_mode | VARCHAR(32) | No | 'single' |
| active_flag | BOOLEAN | No | true |
| priority | INTEGER | No | 100 |
| policy_payload_json | JSONB | No | <function dict at 0x00000272F9926840> |
| created_by | UUID | Yes | — |
| updated_at | DATETIME | No | now() |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `entity_id` -> `cp_entities.id`

**Indexes:**
- `ix_governance_approval_policies_entity` (tenant_id, entity_id, priority)
- `ix_governance_approval_policies_scope` (tenant_id, module_key, mutation_type, active_flag)
- `ix_governance_approval_policies_tenant_id` (tenant_id)

---

### governance_events

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| module_code | VARCHAR(64) | No | — |
| run_id | UUID | No | — |
| event_type | VARCHAR(64) | No | — |
| event_payload_json | JSONB | No | <function dict at 0x00000272FA823B00> |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Indexes:**
- `idx_governance_events_lookup` (tenant_id, module_code, run_id, created_at)
- `ix_governance_events_tenant_id` (tenant_id)

---

### governance_snapshot_inputs

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| snapshot_id | UUID | No | — |
| input_type | VARCHAR(64) | No | — |
| input_ref | TEXT | No | — |
| input_hash | VARCHAR(64) | Yes | — |
| input_payload_json | JSONB | No | <function dict at 0x00000272F99B4B80> |
| created_by | UUID | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `snapshot_id` -> `governance_snapshots.id`

**Indexes:**
- `ix_governance_snapshot_inputs_ref` (tenant_id, input_type, input_ref)
- `ix_governance_snapshot_inputs_snapshot` (tenant_id, snapshot_id, created_at)
- `ix_governance_snapshot_inputs_tenant_id` (tenant_id)

---

### governance_snapshot_metadata

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| snapshot_id | UUID | No | — |
| metadata_key | VARCHAR(128) | No | — |
| metadata_value_json | JSONB | No | <function dict at 0x00000272F99B6200> |
| created_by | UUID | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `snapshot_id` -> `governance_snapshots.id`

**Indexes:**
- `ix_governance_snapshot_metadata_key` (tenant_id, metadata_key, created_at)
- `ix_governance_snapshot_metadata_snapshot` (tenant_id, snapshot_id, created_at)
- `ix_governance_snapshot_metadata_tenant_id` (tenant_id)

---

### governance_snapshots

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| entity_id | UUID | Yes | — |
| module_key | VARCHAR(64) | No | — |
| snapshot_kind | VARCHAR(64) | No | — |
| subject_type | VARCHAR(64) | No | — |
| subject_id | VARCHAR(128) | No | — |
| version_no | INTEGER | No | — |
| determinism_hash | VARCHAR(64) | No | — |
| replay_supported | BOOLEAN | No | False |
| payload_json | JSONB | No | <function dict at 0x00000272F99B4540> |
| comparison_payload_json | JSONB | No | <function dict at 0x00000272F99B45E0> |
| trigger_event | VARCHAR(64) | Yes | — |
| created_by | UUID | Yes | — |
| snapshot_at | DATETIME | No | now() |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `entity_id` -> `cp_entities.id`

**Indexes:**
- `ix_governance_snapshots_hash` (tenant_id, determinism_hash, created_at)
- `ix_governance_snapshots_subject` (tenant_id, subject_type, subject_id, created_at)
- `ix_governance_snapshots_tenant_id` (tenant_id)

---

### grace_period_logs

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| subscription_id | UUID | No | — |
| grace_period_start | DATETIME | No | — |
| grace_period_end | DATETIME | No | — |
| grace_period_days | INTEGER | No | 7 |
| reason | VARCHAR(64) | No | — |
| resolved_at | DATETIME | Yes | — |
| resolved_by | VARCHAR(255) | Yes | — |
| resolution | VARCHAR(64) | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `subscription_id` -> `tenant_subscriptions.id`

**Indexes:**
- `idx_grace_period_logs_tenant` (tenant_id, subscription_id, grace_period_end, created_at)
- `ix_grace_period_logs_tenant_id` (tenant_id)

---

### gst_rate_master

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: No
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | INTEGER | No | — |
| rate | NUMERIC(10, 4) | No | — |
| description | VARCHAR(128) | Yes | — |

**Indexes:**
- `idx_gst_rate_master_rate` (rate)

---

### gst_recon_items

- **Description**: GST reconciliation break between two return types — INSERT ONLY.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| period_year | INTEGER | No | — |
| period_month | INTEGER | No | — |
| entity_id | UUID | No | — |
| entity_name | VARCHAR(255) | No | — |
| return_type_a | VARCHAR(20) | No | — |
| return_type_b | VARCHAR(20) | No | — |
| return_a_id | UUID | No | — |
| return_b_id | UUID | No | — |
| field_name | VARCHAR(50) | No | — |
| value_a | NUMERIC(20, 6) | No | — |
| value_b | NUMERIC(20, 6) | No | — |
| difference | NUMERIC(20, 6) | No | — |
| created_by_intent_id | UUID | Yes | — |
| recorded_by_job_id | UUID | Yes | — |
| status | VARCHAR(20) | No | open |
| notes | TEXT | Yes | — |
| resolved_by | UUID | Yes | — |
| run_by | UUID | No | — |
| line_item_a_id | UUID | Yes | — |
| line_item_b_id | UUID | Yes | — |
| supplier_gstin | VARCHAR(20) | Yes | — |
| invoice_number | VARCHAR(128) | Yes | — |
| invoice_date | DATE | Yes | — |
| gst_rate | NUMERIC(10, 4) | Yes | — |
| rate_mismatch | BOOLEAN | No | False |
| match_type | VARCHAR(32) | Yes | — |
| itc_eligible | BOOLEAN | Yes | — |
| itc_blocked_reason | VARCHAR(128) | Yes | — |
| reverse_itc | BOOLEAN | No | False |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `entity_id` -> `cp_entities.id`
- `line_item_a_id` -> `gst_return_line_items.id`
- `line_item_b_id` -> `gst_return_line_items.id`
- `return_a_id` -> `gst_returns.id`
- `return_b_id` -> `gst_returns.id`

**Indexes:**
- `idx_gst_recon_entity_id` (tenant_id, entity_id)
- `idx_gst_recon_status` (tenant_id, status)
- `idx_gst_recon_tenant_period` (tenant_id, period_year, period_month)
- `ix_gst_recon_items_tenant_id` (tenant_id)

---

### gst_return_line_items

- **Description**: GST return line item — INSERT ONLY.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| gst_return_id | UUID | No | — |
| return_type | VARCHAR(20) | No | — |
| supplier_gstin | VARCHAR(20) | No | — |
| invoice_number | VARCHAR(128) | No | — |
| invoice_date | DATE | Yes | — |
| taxable_value | NUMERIC(20, 6) | No | 0 |
| igst_amount | NUMERIC(20, 6) | No | 0 |
| cgst_amount | NUMERIC(20, 6) | No | 0 |
| sgst_amount | NUMERIC(20, 6) | No | 0 |
| cess_amount | NUMERIC(20, 6) | No | 0 |
| total_tax | NUMERIC(20, 6) | No | 0 |
| gst_rate | NUMERIC(10, 4) | Yes | — |
| payment_status | VARCHAR(32) | Yes | — |
| expense_category | VARCHAR(64) | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `gst_return_id` -> `gst_returns.id`

**Indexes:**
- `idx_gst_return_line_items_invoice` (tenant_id, supplier_gstin, invoice_number)
- `idx_gst_return_line_items_return` (tenant_id, gst_return_id)
- `ix_gst_return_line_items_tenant_id` (tenant_id)

---

### gst_returns

- **Description**: GST return data record — INSERT ONLY.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| period_year | INTEGER | No | — |
| period_month | INTEGER | No | — |
| entity_id | UUID | No | — |
| entity_name | VARCHAR(255) | No | — |
| location_id | UUID | Yes | — |
| cost_centre_id | UUID | Yes | — |
| gstin | VARCHAR(20) | No | — |
| return_type | VARCHAR(20) | No | — |
| taxable_value | NUMERIC(20, 6) | No | 0 |
| igst_amount | NUMERIC(20, 6) | No | 0 |
| cgst_amount | NUMERIC(20, 6) | No | 0 |
| sgst_amount | NUMERIC(20, 6) | No | 0 |
| cess_amount | NUMERIC(20, 6) | No | 0 |
| total_tax | NUMERIC(20, 6) | No | — |
| created_by_intent_id | UUID | Yes | — |
| recorded_by_job_id | UUID | Yes | — |
| filing_date | DATE | Yes | — |
| status | VARCHAR(20) | No | draft |
| filed_by | UUID | Yes | — |
| notes | TEXT | Yes | — |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `cost_centre_id` -> `cp_cost_centres.id`
- `entity_id` -> `cp_entities.id`
- `location_id` -> `cp_locations.id`

**Indexes:**
- `idx_gst_returns_entity` (tenant_id, entity_name)
- `idx_gst_returns_entity_id` (tenant_id, entity_id)
- `idx_gst_returns_tenant_created` (tenant_id, created_at)
- `idx_gst_returns_tenant_period` (tenant_id, period_year, period_month)
- `idx_gst_returns_type` (tenant_id, return_type)
- `ix_gst_returns_tenant_id` (tenant_id)

---

### iam_sessions

- **Description**: Tracks active refresh token sessions for a user.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| user_id | UUID | No | — |
| tenant_id | UUID | No | — |
| refresh_token_hash | VARCHAR(64) | No | — |
| device_info | TEXT | Yes | — |
| ip_address | VARCHAR(45) | Yes | — |
| expires_at | DATETIME | No | — |
| revoked_at | DATETIME | Yes | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `user_id` -> `iam_users.id`

**Indexes:**
- `idx_iam_sessions_tenant_created` (tenant_id, created_at)
- `ix_iam_sessions_refresh_token_hash` (refresh_token_hash)
- `ix_iam_sessions_tenant_id` (tenant_id)
- `ix_iam_sessions_user_id` (user_id)

---

### iam_tenants

- **Description**: Multi-tenant root entity. Every resource belongs to a tenant.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| display_name | VARCHAR(255) | No | — |
| slug | VARCHAR(100) | No | <function IamTenant.<lambda> at 0x00000272FAF7AC00> |
| tenant_type | VARCHAR(16) | No | — |
| parent_tenant_id | UUID | Yes | — |
| country | VARCHAR(2) | No | — |
| timezone | VARCHAR(64) | No | Asia/Kolkata |
| status | VARCHAR(9) | No | TenantStatus.active |
| is_platform_tenant | BOOLEAN | No | False |
| default_display_scale | VARCHAR(20) | No | 'LAKHS' |
| default_currency | VARCHAR(3) | No | 'INR' |
| number_format_locale | VARCHAR(20) | No | 'en-IN' |
| org_setup_complete | BOOLEAN | No | False |
| org_setup_step | INTEGER | No | 0 |
| pan | VARCHAR(20) | Yes | — |
| gstin | VARCHAR(20) | Yes | — |
| state_code | VARCHAR(5) | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `parent_tenant_id` -> `iam_tenants.id`

**Indexes:**
- `ix_iam_tenants_slug` (slug)
- `ix_iam_tenants_tenant_id` (tenant_id)

---

### iam_users

- **Description**: Platform user. Belongs to exactly one tenant.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| tenant_id | UUID | No | — |
| email | VARCHAR(254) | No | — |
| hashed_password | VARCHAR(255) | No | — |
| full_name | VARCHAR(255) | No | — |
| role | VARCHAR(16) | No | UserRole.read_only |
| totp_secret_encrypted | TEXT | Yes | — |
| is_active | BOOLEAN | No | True |
| is_verified | BOOLEAN | No | True |
| mfa_enabled | BOOLEAN | No | False |
| force_password_change | BOOLEAN | No | False |
| force_mfa_setup | BOOLEAN | No | False |
| password_changed_at | DATETIME | Yes | — |
| last_login_at | DATETIME | Yes | — |
| terms_accepted_at | DATETIME | Yes | — |
| terms_version_accepted | VARCHAR(20) | Yes | — |
| invite_token_hash | VARCHAR(64) | Yes | — |
| invite_expires_at | DATETIME | Yes | — |
| invite_accepted_at | DATETIME | Yes | — |
| display_scale_override | VARCHAR(20) | Yes | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `tenant_id` -> `iam_tenants.id`

**Indexes:**
- `ix_iam_users_email` (email)
- `ix_iam_users_tenant_id` (tenant_id)

---

### iam_workspaces

- **Description**: Workspace within a tenant. Used for scoping financial data.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| tenant_id | UUID | No | — |
| name | VARCHAR(255) | No | — |
| status | VARCHAR(9) | No | WorkspaceStatus.active |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `tenant_id` -> `iam_tenants.id`

**Indexes:**
- `ix_iam_workspaces_tenant_id` (tenant_id)

---

### ic_transactions

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| fiscal_year | INTEGER | No | — |
| transaction_type | VARCHAR(50) | No | — |
| related_party_name | VARCHAR(300) | No | — |
| related_party_country | VARCHAR(3) | No | — |
| transaction_amount | NUMERIC(20, 2) | No | — |
| currency | VARCHAR(3) | No | — |
| transaction_amount_inr | NUMERIC(20, 2) | No | — |
| pricing_method | VARCHAR(10) | No | — |
| arm_length_price | NUMERIC(20, 2) | Yes | — |
| actual_price | NUMERIC(20, 2) | Yes | — |
| adjustment_required | NUMERIC(20, 2) | No | 0.00 |
| is_international | BOOLEAN | No | True |
| description | TEXT | Yes | — |
| created_at | DATETIME | No | now() |

**Indexes:**
- `idx_ic_transactions_tenant_fiscal_year` (tenant_id, fiscal_year)

---

### industry_accrual_schedules

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| entity_id | UUID | No | — |
| schedule_batch_id | UUID | No | — |
| accrual_name | VARCHAR(255) | No | — |
| period_number | INTEGER | No | — |
| period_date | DATE | No | — |
| accrual_amount | NUMERIC(20, 4) | No | — |
| remaining_balance | NUMERIC(20, 4) | No | — |
| created_at | DATETIME | No | now() |

**Foreign keys:**
- `entity_id` -> `cp_entities.id`
- `tenant_id` -> `iam_tenants.id`

**Indexes:**
- `ix_industry_accrual_schedules_tenant_batch` (tenant_id, schedule_batch_id)

---

### industry_asset_schedules

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| asset_id | UUID | No | — |
| period_number | INTEGER | No | — |
| period_date | DATE | No | — |
| depreciation | NUMERIC(20, 4) | No | — |
| net_book_value | NUMERIC(20, 4) | No | — |
| created_at | DATETIME | No | now() |

**Foreign keys:**
- `asset_id` -> `industry_fixed_assets.id`
- `tenant_id` -> `iam_tenants.id`

**Indexes:**
- `ix_industry_asset_schedules_tenant_asset` (tenant_id, asset_id)

---

### industry_billing_schedules

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| subscription_id | UUID | No | — |
| period_number | INTEGER | No | — |
| bill_date | DATE | No | — |
| billing_amount | NUMERIC(20, 4) | No | — |
| deferred_revenue_amount | NUMERIC(20, 4) | No | — |
| created_at | DATETIME | No | now() |

**Foreign keys:**
- `subscription_id` -> `industry_subscriptions.id`
- `tenant_id` -> `iam_tenants.id`

**Indexes:**
- `ix_industry_billing_schedules_tenant_subscription` (tenant_id, subscription_id)

---

### industry_contracts

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| entity_id | UUID | No | — |
| customer_id | VARCHAR(128) | No | — |
| contract_start_date | DATE | No | — |
| contract_end_date | DATE | No | — |
| contract_value | NUMERIC(20, 4) | No | — |
| created_by | UUID | Yes | — |
| created_at | DATETIME | No | now() |

**Foreign keys:**
- `created_by` -> `iam_users.id`
- `entity_id` -> `cp_entities.id`
- `tenant_id` -> `iam_tenants.id`

**Indexes:**
- `ix_industry_contracts_tenant_entity` (tenant_id, entity_id)

---

### industry_fixed_assets

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| entity_id | UUID | No | — |
| asset_name | VARCHAR(256) | No | — |
| cost | NUMERIC(20, 4) | No | — |
| useful_life_years | INTEGER | No | — |
| depreciation_method | VARCHAR(16) | No | — |
| residual_value | NUMERIC(20, 4) | No | 0 |
| created_by | UUID | Yes | — |
| created_at | DATETIME | No | now() |

**Foreign keys:**
- `created_by` -> `iam_users.id`
- `entity_id` -> `cp_entities.id`
- `tenant_id` -> `iam_tenants.id`

**Indexes:**
- `ix_industry_fixed_assets_tenant_entity` (tenant_id, entity_id)

---

### industry_journal_links

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| module_name | VARCHAR(64) | No | — |
| module_record_id | UUID | No | — |
| journal_id | UUID | No | — |
| note | TEXT | Yes | — |
| created_at | DATETIME | No | now() |

**Foreign keys:**
- `journal_id` -> `accounting_jv_aggregates.id`
- `tenant_id` -> `iam_tenants.id`

**Indexes:**
- `ix_industry_journal_links_tenant_reference` (tenant_id, module_name, module_record_id)

---

### industry_lease_schedules

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| lease_id | UUID | No | — |
| period_number | INTEGER | No | — |
| period_date | DATE | No | — |
| opening_liability | NUMERIC(20, 4) | No | — |
| interest_expense | NUMERIC(20, 4) | No | — |
| lease_payment | NUMERIC(20, 4) | No | — |
| closing_liability | NUMERIC(20, 4) | No | — |
| rou_asset_value | NUMERIC(20, 4) | No | — |
| depreciation | NUMERIC(20, 4) | No | — |
| created_at | DATETIME | No | now() |

**Foreign keys:**
- `lease_id` -> `industry_leases.id`
- `tenant_id` -> `iam_tenants.id`

**Indexes:**
- `ix_industry_lease_schedules_tenant_lease` (tenant_id, lease_id)

---

### industry_leases

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| entity_id | UUID | No | — |
| lease_start_date | DATE | No | — |
| lease_end_date | DATE | No | — |
| lease_payment | NUMERIC(20, 4) | No | — |
| discount_rate | NUMERIC(12, 8) | No | — |
| lease_type | VARCHAR(32) | No | — |
| currency | VARCHAR(3) | No | INR |
| created_by | UUID | Yes | — |
| created_at | DATETIME | No | now() |

**Foreign keys:**
- `created_by` -> `iam_users.id`
- `entity_id` -> `cp_entities.id`
- `tenant_id` -> `iam_tenants.id`

**Indexes:**
- `ix_industry_leases_tenant_created` (tenant_id, created_at)
- `ix_industry_leases_tenant_entity` (tenant_id, entity_id)

---

### industry_performance_obligations

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| contract_id | UUID | No | — |
| obligation_type | VARCHAR(64) | No | — |
| allocation_value | NUMERIC(20, 4) | No | — |
| created_at | DATETIME | No | now() |

**Foreign keys:**
- `contract_id` -> `industry_contracts.id`
- `tenant_id` -> `iam_tenants.id`

**Indexes:**
- `ix_industry_obligations_tenant_contract` (tenant_id, contract_id)

---

### industry_prepaid_schedules

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| entity_id | UUID | No | — |
| schedule_batch_id | UUID | No | — |
| prepaid_name | VARCHAR(255) | No | — |
| period_number | INTEGER | No | — |
| period_date | DATE | No | — |
| amortization_amount | NUMERIC(20, 4) | No | — |
| remaining_balance | NUMERIC(20, 4) | No | — |
| created_at | DATETIME | No | now() |

**Foreign keys:**
- `entity_id` -> `cp_entities.id`
- `tenant_id` -> `iam_tenants.id`

**Indexes:**
- `ix_industry_prepaid_schedules_tenant_batch` (tenant_id, schedule_batch_id)

---

### industry_revenue_schedules

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| obligation_id | UUID | No | — |
| period_number | INTEGER | No | — |
| recognition_date | DATE | No | — |
| revenue_amount | NUMERIC(20, 4) | No | — |
| created_at | DATETIME | No | now() |

**Foreign keys:**
- `obligation_id` -> `industry_performance_obligations.id`
- `tenant_id` -> `iam_tenants.id`

**Indexes:**
- `ix_industry_revenue_schedules_tenant_obligation` (tenant_id, obligation_id)

---

### industry_subscriptions

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| entity_id | UUID | No | — |
| subscription_name | VARCHAR(255) | No | — |
| start_date | DATE | No | — |
| end_date | DATE | No | — |
| billing_amount | NUMERIC(20, 4) | No | — |
| revenue_recognition_method | VARCHAR(32) | No | STRAIGHT_LINE |
| created_at | DATETIME | No | now() |

**Foreign keys:**
- `entity_id` -> `cp_entities.id`
- `tenant_id` -> `iam_tenants.id`

**Indexes:**
- `ix_industry_subscriptions_tenant_entity` (tenant_id, entity_id)

---

### intercompany_mapping_rules

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| organisation_id | UUID | No | — |
| rule_code | VARCHAR(128) | No | — |
| source_selector_json | JSONB | No | <function dict at 0x00000272FA527600> |
| counterpart_selector_json | JSONB | No | <function dict at 0x00000272FA526520> |
| treatment_rule_json | JSONB | No | <function dict at 0x00000272FA5276A0> |
| version_token | VARCHAR(64) | No | — |
| effective_from | DATE | No | — |
| effective_to | DATE | Yes | — |
| supersedes_id | UUID | Yes | — |
| status | VARCHAR(32) | No | candidate |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `supersedes_id` -> `intercompany_mapping_rules.id`

**Indexes:**
- `idx_intercompany_mapping_rules_lookup` (tenant_id, organisation_id, rule_code, effective_from, created_at)
- `ix_intercompany_mapping_rules_tenant_id` (tenant_id)
- `uq_intercompany_mapping_rules_one_active` (tenant_id, organisation_id, rule_code)

---

### intercompany_pairs

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| run_id | UUID | No | — |
| match_key_hash | VARCHAR(64) | No | — |
| entity_from | UUID | No | — |
| entity_to | UUID | No | — |
| account_code | VARCHAR(64) | No | — |
| ic_reference | VARCHAR(255) | Yes | — |
| amount_local_from | NUMERIC(20, 6) | No | — |
| amount_local_to | NUMERIC(20, 6) | No | — |
| amount_parent_from | NUMERIC(20, 6) | No | — |
| amount_parent_to | NUMERIC(20, 6) | No | — |
| expected_difference | NUMERIC(20, 6) | No | — |
| actual_difference | NUMERIC(20, 6) | No | — |
| fx_explained | NUMERIC(20, 6) | No | — |
| unexplained_difference | NUMERIC(20, 6) | No | — |
| classification | VARCHAR(64) | No | — |
| correlation_id | VARCHAR(64) | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `run_id` -> `consolidation_runs.id`

**Indexes:**
- `idx_ic_pairs_classification` (tenant_id, run_id, classification)
- `idx_ic_pairs_tenant_run` (tenant_id, run_id)
- `ix_intercompany_pairs_tenant_id` (tenant_id)

---

### invoice_classifications

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| entity_id | UUID | No | — |
| invoice_number | VARCHAR(200) | No | — |
| vendor_name | VARCHAR(300) | Yes | — |
| invoice_date | DATE | Yes | — |
| invoice_amount | NUMERIC(20, 4) | No | — |
| line_description | TEXT | Yes | — |
| classification | VARCHAR(20) | No | — |
| confidence | NUMERIC(5, 4) | No | — |
| classification_method | VARCHAR(20) | No | — |
| rule_matched | VARCHAR(200) | Yes | — |
| ai_reasoning | TEXT | Yes | — |
| requires_human_review | BOOLEAN | No | False |
| human_reviewed_by | UUID | Yes | — |
| human_reviewed_at | DATETIME | Yes | — |
| human_override | VARCHAR(20) | Yes | — |
| routing_action | VARCHAR(20) | Yes | — |
| routed_record_id | UUID | Yes | — |
| created_at | DATETIME | No | now() |

**Foreign keys:**
- `entity_id` -> `cp_entities.id`
- `human_reviewed_by` -> `iam_users.id`
- `tenant_id` -> `iam_tenants.id`

**Indexes:**
- `idx_invoice_classifications_classification` (classification)
- `idx_invoice_classifications_entity_id` (entity_id)
- `idx_invoice_classifications_requires_human_review` (requires_human_review)
- `idx_invoice_classifications_routing_action` (routing_action)
- `idx_invoice_classifications_tenant_id` (tenant_id)

---

### learning_corrections

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| signal_id | UUID | No | — |
| task_type | VARCHAR(50) | No | — |
| input_context | TEXT | No | — |
| correct_output | TEXT | No | — |
| is_validated | BOOLEAN | No | False |
| validated_at | DATETIME | Yes | — |
| validated_by | UUID | Yes | — |
| quality_score | NUMERIC(3, 2) | Yes | — |
| created_at | DATETIME | No | now() |
| updated_at | DATETIME | No | now() |

**Foreign keys:**
- `signal_id` -> `learning_signals.id`

**Indexes:**
- `idx_learning_corrections_tenant_task_validated` (tenant_id, task_type, is_validated)

---

### learning_signals

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| signal_type | VARCHAR(50) | No | — |
| task_type | VARCHAR(50) | No | — |
| original_ai_output | JSONB | No | — |
| human_correction | JSONB | No | — |
| correction_delta | JSONB | No | <function dict at 0x00000272FAF3D6C0> |
| model_used | VARCHAR(100) | No | — |
| provider | VARCHAR(30) | No | — |
| prompt_tokens | INTEGER | No | 0 |
| completion_tokens | INTEGER | No | 0 |
| user_id | UUID | No | — |
| session_id | VARCHAR(100) | Yes | — |
| created_at | DATETIME | No | now() |

**Indexes:**
- `idx_learning_signals_tenant_task` (tenant_id, task_type)
- `idx_learning_signals_tenant_type_created` (tenant_id, signal_type, created_at)

---

### lease_journal_entries

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| run_id | UUID | No | — |
| lease_id | UUID | No | — |
| liability_schedule_id | UUID | Yes | — |
| rou_schedule_id | UUID | Yes | — |
| journal_reference | VARCHAR(128) | No | — |
| entry_date | DATE | No | — |
| debit_account | VARCHAR(64) | No | — |
| credit_account | VARCHAR(64) | No | — |
| amount_reporting_currency | NUMERIC(20, 6) | No | — |
| source_lease_reference | VARCHAR(255) | No | — |
| parent_reference_id | UUID | Yes | — |
| source_reference_id | UUID | Yes | — |
| correlation_id | VARCHAR(64) | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `lease_id` -> `leases.id`
- `liability_schedule_id` -> `lease_liability_schedule.id`
- `rou_schedule_id` -> `lease_rou_schedule.id`
- `run_id` -> `lease_runs.id`

**Indexes:**
- `idx_lease_journal_lease` (tenant_id, lease_id)
- `idx_lease_journal_run` (tenant_id, run_id, entry_date)
- `ix_lease_journal_entries_tenant_id` (tenant_id)

---

### lease_liability_schedule

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| run_id | UUID | No | — |
| lease_id | UUID | No | — |
| payment_id | UUID | Yes | — |
| period_seq | INTEGER | No | — |
| schedule_date | DATE | No | — |
| period_year | INTEGER | No | — |
| period_month | INTEGER | No | — |
| schedule_version_token | VARCHAR(64) | No | — |
| opening_liability_reporting_currency | NUMERIC(20, 6) | No | — |
| interest_expense_reporting_currency | NUMERIC(20, 6) | No | — |
| payment_amount_reporting_currency | NUMERIC(20, 6) | No | — |
| closing_liability_reporting_currency | NUMERIC(20, 6) | No | — |
| fx_rate_used | NUMERIC(20, 6) | No | — |
| source_lease_reference | VARCHAR(255) | No | — |
| parent_reference_id | UUID | Yes | — |
| source_reference_id | UUID | Yes | — |
| correlation_id | VARCHAR(64) | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `lease_id` -> `leases.id`
- `payment_id` -> `lease_payments.id`
- `run_id` -> `lease_runs.id`

**Indexes:**
- `idx_lease_liability_schedule_run` (tenant_id, run_id, schedule_date)
- `ix_lease_liability_schedule_tenant_id` (tenant_id)

---

### lease_modifications

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| run_id | UUID | No | — |
| lease_id | UUID | No | — |
| effective_date | DATE | No | — |
| modification_type | VARCHAR(64) | No | — |
| modification_reason | TEXT | No | — |
| idempotency_key | VARCHAR(128) | No | — |
| prior_schedule_version_token | VARCHAR(64) | No | — |
| new_schedule_version_token | VARCHAR(64) | No | — |
| prior_schedule_reference | VARCHAR(255) | Yes | — |
| new_schedule_reference | VARCHAR(255) | Yes | — |
| remeasurement_delta_reporting_currency | NUMERIC(20, 6) | No | — |
| source_lease_reference | VARCHAR(255) | No | — |
| parent_reference_id | UUID | Yes | — |
| source_reference_id | UUID | Yes | — |
| correlation_id | VARCHAR(64) | Yes | — |
| supersedes_id | UUID | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `lease_id` -> `leases.id`
- `run_id` -> `lease_runs.id`
- `supersedes_id` -> `lease_modifications.id`

**Indexes:**
- `idx_lease_modifications_lease` (tenant_id, lease_id)
- `idx_lease_modifications_run` (tenant_id, run_id, effective_date)
- `ix_lease_modifications_tenant_id` (tenant_id)

---

### lease_payments

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| lease_id | UUID | No | — |
| payment_date | DATE | No | — |
| payment_amount_lease_currency | NUMERIC(20, 6) | No | — |
| payment_type | VARCHAR(64) | No | — |
| payment_sequence | INTEGER | No | — |
| source_lease_reference | VARCHAR(255) | No | — |
| parent_reference_id | UUID | Yes | — |
| source_reference_id | UUID | Yes | — |
| correlation_id | VARCHAR(64) | Yes | — |
| supersedes_id | UUID | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `lease_id` -> `leases.id`
- `supersedes_id` -> `lease_payments.id`

**Indexes:**
- `idx_lease_payments_lease` (tenant_id, lease_id, payment_sequence)
- `ix_lease_payments_tenant_id` (tenant_id)

---

### lease_rou_schedule

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| run_id | UUID | No | — |
| lease_id | UUID | No | — |
| period_seq | INTEGER | No | — |
| schedule_date | DATE | No | — |
| period_year | INTEGER | No | — |
| period_month | INTEGER | No | — |
| schedule_version_token | VARCHAR(64) | No | — |
| opening_rou_reporting_currency | NUMERIC(20, 6) | No | — |
| amortization_expense_reporting_currency | NUMERIC(20, 6) | No | — |
| impairment_amount_reporting_currency | NUMERIC(20, 6) | No | — |
| closing_rou_reporting_currency | NUMERIC(20, 6) | No | — |
| fx_rate_used | NUMERIC(20, 6) | No | — |
| source_lease_reference | VARCHAR(255) | No | — |
| parent_reference_id | UUID | Yes | — |
| source_reference_id | UUID | Yes | — |
| correlation_id | VARCHAR(64) | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `lease_id` -> `leases.id`
- `run_id` -> `lease_runs.id`

**Indexes:**
- `idx_lease_rou_schedule_run` (tenant_id, run_id, schedule_date)
- `ix_lease_rou_schedule_tenant_id` (tenant_id)

---

### lease_run_events

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| run_id | UUID | No | — |
| event_seq | INTEGER | No | — |
| event_type | VARCHAR(64) | No | — |
| event_time | DATETIME | No | — |
| idempotency_key | VARCHAR(128) | No | — |
| metadata_json | JSONB | Yes | — |
| correlation_id | VARCHAR(64) | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `run_id` -> `lease_runs.id`

**Indexes:**
- `idx_lease_run_events_tenant_run` (tenant_id, run_id, event_seq)
- `ix_lease_run_events_tenant_id` (tenant_id)

---

### lease_runs

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| request_signature | VARCHAR(64) | No | — |
| initiated_by | UUID | No | — |
| configuration_json | JSONB | No | — |
| workflow_id | VARCHAR(128) | No | — |
| correlation_id | VARCHAR(64) | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Indexes:**
- `idx_lease_runs_tenant_created` (tenant_id, created_at)
- `ix_lease_runs_tenant_id` (tenant_id)

---

### leases

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| lease_number | VARCHAR(128) | No | — |
| entity_id | UUID | Yes | — |
| counterparty_id | VARCHAR(128) | No | — |
| lease_currency | VARCHAR(3) | No | — |
| commencement_date | DATE | No | — |
| end_date | DATE | No | — |
| payment_frequency | VARCHAR(32) | No | — |
| initial_discount_rate | NUMERIC(20, 6) | No | — |
| discount_rate_source | VARCHAR(64) | No | — |
| discount_rate_reference_date | DATE | No | — |
| discount_rate_policy_code | VARCHAR(64) | No | — |
| initial_measurement_basis | VARCHAR(64) | No | — |
| source_lease_reference | VARCHAR(255) | No | — |
| policy_code | VARCHAR(64) | No | — |
| policy_version | VARCHAR(64) | No | — |
| parent_reference_id | UUID | Yes | — |
| source_reference_id | UUID | Yes | — |
| correlation_id | VARCHAR(64) | Yes | — |
| supersedes_id | UUID | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `entity_id` -> `cp_entities.id`
- `supersedes_id` -> `leases.id`

**Indexes:**
- `idx_leases_tenant_number` (tenant_id, lease_number, created_at)
- `idx_leases_tenant_source` (tenant_id, source_lease_reference)
- `ix_leases_entity_id` (entity_id)
- `ix_leases_tenant_id` (tenant_id)

---

### lineage_graph_snapshots

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| root_run_id | UUID | No | — |
| graph_payload_json | JSONB | No | <function dict at 0x00000272FA821F80> |
| deterministic_hash | VARCHAR(64) | No | — |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Indexes:**
- `idx_lineage_graph_snapshots_lookup` (tenant_id, root_run_id, created_at)
- `ix_lineage_graph_snapshots_tenant_id` (tenant_id)

---

### ma_dd_items

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| workspace_id | UUID | No | — |
| tenant_id | UUID | No | — |
| category | VARCHAR(50) | No | — |
| item_name | VARCHAR(300) | No | — |
| description | TEXT | Yes | — |
| status | VARCHAR(20) | No | open |
| priority | VARCHAR(10) | No | medium |
| assigned_to | UUID | Yes | — |
| due_date | DATE | Yes | — |
| response_notes | TEXT | Yes | — |
| created_at | DATETIME | No | now() |
| updated_at | DATETIME | No | now() |

**Foreign keys:**
- `assigned_to` -> `iam_users.id`
- `workspace_id` -> `ma_workspaces.id`

**Indexes:**
- `idx_ma_dd_items_workspace_status` (workspace_id, status)

---

### ma_documents

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: Yes

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| workspace_id | UUID | No | — |
| tenant_id | UUID | No | — |
| document_name | VARCHAR(300) | No | — |
| document_type | VARCHAR(50) | No | — |
| version | INTEGER | No | 1 |
| file_url | TEXT | Yes | — |
| file_size_bytes | BIGINT | Yes | — |
| uploaded_by | UUID | No | — |
| is_confidential | BOOLEAN | No | True |
| created_at | DATETIME | No | now() |

**Foreign keys:**
- `uploaded_by` -> `iam_users.id`
- `workspace_id` -> `ma_workspaces.id`

**Indexes:**
- `idx_ma_documents_workspace_type` (workspace_id, document_type)

---

### ma_valuations

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: Yes

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| workspace_id | UUID | No | — |
| tenant_id | UUID | No | — |
| valuation_name | VARCHAR(200) | No | — |
| valuation_method | VARCHAR(30) | No | — |
| assumptions | JSONB | No | <function dict at 0x00000272FADFE660> |
| enterprise_value | NUMERIC(20, 2) | No | — |
| equity_value | NUMERIC(20, 2) | No | — |
| net_debt_used | NUMERIC(20, 2) | No | — |
| ev_ebitda_multiple | NUMERIC(8, 4) | No | — |
| ev_revenue_multiple | NUMERIC(8, 4) | No | — |
| valuation_range_low | NUMERIC(20, 2) | No | — |
| valuation_range_high | NUMERIC(20, 2) | No | — |
| computed_at | DATETIME | No | now() |
| computed_by | UUID | No | — |
| notes | TEXT | Yes | — |

**Foreign keys:**
- `computed_by` -> `iam_users.id`
- `workspace_id` -> `ma_workspaces.id`

**Indexes:**
- `idx_ma_valuations_workspace_computed` (workspace_id)

---

### ma_workspace_members

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| workspace_id | UUID | No | — |
| tenant_id | UUID | No | — |
| user_id | UUID | No | — |
| member_role | VARCHAR(30) | No | — |
| added_at | DATETIME | No | now() |
| removed_at | DATETIME | Yes | — |

**Foreign keys:**
- `user_id` -> `iam_users.id`
- `workspace_id` -> `ma_workspaces.id`

**Indexes:**
- `idx_ma_workspace_members_workspace` (workspace_id)

---

### ma_workspaces

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| workspace_name | VARCHAR(300) | No | — |
| deal_codename | VARCHAR(100) | No | — |
| deal_type | VARCHAR(30) | No | — |
| target_company_name | VARCHAR(300) | No | — |
| deal_status | VARCHAR(30) | No | active |
| indicative_deal_value | NUMERIC(20, 2) | Yes | — |
| deal_value_currency | VARCHAR(3) | No | INR |
| credit_cost_monthly | INTEGER | No | 1000 |
| credit_charged_at | DATETIME | Yes | — |
| created_by | UUID | No | — |
| created_at | DATETIME | No | now() |
| updated_at | DATETIME | No | now() |

**Foreign keys:**
- `created_by` -> `iam_users.id`

**Indexes:**
- `idx_ma_workspaces_tenant_status` (tenant_id, deal_status)

---

### marketplace_contributors

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| display_name | VARCHAR(200) | No | — |
| bio | TEXT | Yes | — |
| contributor_tier | VARCHAR(20) | No | community |
| revenue_share_pct | NUMERIC(5, 4) | No | 0.6000 |
| stripe_account_id | VARCHAR(100) | Yes | — |
| total_earnings | NUMERIC(20, 2) | No | 0 |
| total_templates | INTEGER | No | 0 |
| total_downloads | INTEGER | No | 0 |
| rating_average | NUMERIC(3, 2) | No | 0 |
| is_active | BOOLEAN | No | True |
| created_at | DATETIME | No | now() |
| updated_at | DATETIME | No | now() |

**Foreign keys:**
- `tenant_id` -> `iam_tenants.id`

---

### marketplace_payouts

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: No
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| contributor_id | UUID | No | — |
| period_start | DATE | No | — |
| period_end | DATE | No | — |
| total_credits_earned | INTEGER | No | — |
| total_usd_amount | NUMERIC(20, 2) | No | — |
| status | VARCHAR(20) | No | pending |
| stripe_transfer_id | VARCHAR(100) | Yes | — |
| processed_at | DATETIME | Yes | — |
| created_at | DATETIME | No | now() |

**Foreign keys:**
- `contributor_id` -> `marketplace_contributors.id`

---

### marketplace_purchases

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: No
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| template_id | UUID | No | — |
| buyer_tenant_id | UUID | No | — |
| contributor_id | UUID | No | — |
| price_credits_paid | INTEGER | No | — |
| platform_share_credits | INTEGER | No | — |
| contributor_share_credits | INTEGER | No | — |
| platform_share_pct | NUMERIC(5, 4) | No | — |
| contributor_share_pct | NUMERIC(5, 4) | No | — |
| status | VARCHAR(20) | No | completed |
| purchased_at | DATETIME | No | now() |

**Foreign keys:**
- `contributor_id` -> `marketplace_contributors.id`
- `template_id` -> `marketplace_templates.id`

**Indexes:**
- `idx_marketplace_purchases_buyer_purchased_at` (buyer_tenant_id, purchased_at)
- `idx_marketplace_purchases_contributor_purchased_at` (contributor_id, purchased_at)

---

### marketplace_ratings

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: No
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| template_id | UUID | No | — |
| buyer_tenant_id | UUID | No | — |
| rating | INTEGER | No | — |
| review_text | TEXT | Yes | — |
| created_at | DATETIME | No | now() |

**Foreign keys:**
- `template_id` -> `marketplace_templates.id`

---

### marketplace_templates

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| contributor_id | UUID | No | — |
| tenant_id | UUID | No | — |
| title | VARCHAR(300) | No | — |
| description | TEXT | No | — |
| template_type | VARCHAR(50) | No | — |
| industry | VARCHAR(100) | Yes | — |
| price_credits | INTEGER | No | — |
| is_free | BOOLEAN | No | False |
| template_data | JSONB | No | <function dict at 0x00000272FAE6A520> |
| preview_image_url | TEXT | Yes | — |
| tags | JSONB | No | <function list at 0x00000272FAE6A5C0> |
| download_count | INTEGER | No | 0 |
| rating_count | INTEGER | No | 0 |
| rating_sum | INTEGER | No | 0 |
| rating_average | NUMERIC(3, 2) | No | 0 |
| status | VARCHAR(20) | No | draft |
| review_notes | TEXT | Yes | — |
| is_featured | BOOLEAN | No | False |
| created_at | DATETIME | No | now() |
| updated_at | DATETIME | No | now() |

**Foreign keys:**
- `contributor_id` -> `marketplace_contributors.id`

**Indexes:**
- `idx_marketplace_templates_contributor_id` (contributor_id)
- `idx_marketplace_templates_featured_status` (is_featured, status)
- `idx_marketplace_templates_status_type_industry` (status, template_type, industry)

---

### materiality_rules

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| organisation_id | UUID | No | — |
| definition_code | VARCHAR(128) | No | — |
| definition_name | VARCHAR(255) | No | — |
| rule_json | JSONB | No | <function dict at 0x00000272FA2CF600> |
| version_token | VARCHAR(64) | No | — |
| effective_from | DATE | No | — |
| supersedes_id | UUID | Yes | — |
| status | VARCHAR(32) | No | candidate |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `supersedes_id` -> `materiality_rules.id`

**Indexes:**
- `idx_materiality_rules_lookup` (tenant_id, organisation_id, definition_code, effective_from, created_at)
- `ix_materiality_rules_tenant_id` (tenant_id)
- `uq_materiality_rules_one_active` (tenant_id, organisation_id, definition_code)

---

### metric_definition_components

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| metric_definition_id | UUID | No | — |
| component_code | VARCHAR(128) | No | — |
| source_type | VARCHAR(64) | No | — |
| source_key | VARCHAR(255) | No | — |
| operator | VARCHAR(16) | No | add |
| weight | NUMERIC(20, 6) | No | 1 |
| ordinal_position | INTEGER | No | — |
| metadata_json | JSONB | No | <function dict at 0x00000272FA2974C0> |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `metric_definition_id` -> `metric_definitions.id`

**Indexes:**
- `idx_metric_definition_components_metric` (tenant_id, metric_definition_id, ordinal_position)
- `ix_metric_definition_components_tenant_id` (tenant_id)

---

### metric_definitions

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| organisation_id | UUID | No | — |
| definition_code | VARCHAR(128) | No | — |
| definition_name | VARCHAR(255) | No | — |
| metric_code | VARCHAR(128) | No | — |
| formula_type | VARCHAR(64) | No | — |
| formula_json | JSONB | No | <function dict at 0x00000272FA297060> |
| unit_type | VARCHAR(32) | No | amount |
| directionality | VARCHAR(32) | No | neutral |
| version_token | VARCHAR(64) | No | — |
| effective_from | DATE | No | — |
| supersedes_id | UUID | Yes | — |
| status | VARCHAR(32) | No | candidate |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `supersedes_id` -> `metric_definitions.id`

**Indexes:**
- `idx_metric_definitions_lookup` (tenant_id, organisation_id, definition_code, effective_from, created_at)
- `ix_metric_definitions_tenant_id` (tenant_id)
- `uq_metric_definitions_one_active` (tenant_id, organisation_id, definition_code)

---

### metric_evidence_links

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| run_id | UUID | No | — |
| result_type | VARCHAR(16) | No | — |
| result_id | UUID | No | — |
| evidence_type | VARCHAR(64) | No | — |
| evidence_ref | TEXT | No | — |
| evidence_label | VARCHAR(255) | No | — |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `run_id` -> `metric_runs.id`

**Indexes:**
- `idx_metric_evidence_links_result` (tenant_id, run_id, result_type, result_id)
- `idx_metric_evidence_links_run` (tenant_id, run_id, created_at)
- `ix_metric_evidence_links_tenant_id` (tenant_id)

---

### metric_results

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| run_id | UUID | No | — |
| line_no | INTEGER | No | — |
| metric_code | VARCHAR(128) | No | — |
| unit_type | VARCHAR(32) | No | — |
| dimension_json | JSONB | No | <function dict at 0x00000272FA302520> |
| metric_value | NUMERIC(20, 6) | No | — |
| favorable_status | VARCHAR(16) | No | neutral |
| materiality_flag | BOOLEAN | No | False |
| source_summary_json | JSONB | No | <function dict at 0x00000272FA303F60> |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `run_id` -> `metric_runs.id`

**Indexes:**
- `idx_metric_results_metric` (tenant_id, run_id, metric_code)
- `idx_metric_results_run` (tenant_id, run_id, line_no)
- `ix_metric_results_tenant_id` (tenant_id)

---

### metric_runs

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| organisation_id | UUID | No | — |
| reporting_period | DATE | No | — |
| scope_json | JSONB | No | <function dict at 0x00000272FA300C20> |
| mis_snapshot_id | UUID | Yes | — |
| payroll_run_id | UUID | Yes | — |
| gl_run_id | UUID | Yes | — |
| reconciliation_session_id | UUID | Yes | — |
| payroll_gl_reconciliation_run_id | UUID | Yes | — |
| metric_definition_version_token | VARCHAR(64) | No | — |
| variance_definition_version_token | VARCHAR(64) | No | — |
| trend_definition_version_token | VARCHAR(64) | No | — |
| materiality_rule_version_token | VARCHAR(64) | No | — |
| input_signature_hash | VARCHAR(64) | No | — |
| run_token | VARCHAR(64) | No | — |
| status | VARCHAR(32) | No | created |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `gl_run_id` -> `normalization_runs.id`
- `mis_snapshot_id` -> `mis_data_snapshots.id`
- `payroll_gl_reconciliation_run_id` -> `payroll_gl_reconciliation_runs.id`
- `payroll_run_id` -> `normalization_runs.id`
- `reconciliation_session_id` -> `reconciliation_sessions.id`

**Indexes:**
- `idx_metric_runs_lookup` (tenant_id, organisation_id, reporting_period, created_at)
- `idx_metric_runs_token` (tenant_id, run_token)
- `ix_metric_runs_tenant_id` (tenant_id)

---

### mfa_recovery_codes

- **Description**: Abstract base with UUID PK and created_at.
- **RLS enabled**: No
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| user_id | UUID | No | — |
| code_hash | VARCHAR(64) | No | — |
| used_at | DATETIME | Yes | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `user_id` -> `iam_users.id`

**Indexes:**
- `ix_mfa_recovery_codes_user` (user_id)
- `ix_mfa_recovery_codes_user_code` (user_id, code_hash)

---

### minority_interest_rule_definitions

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| organisation_id | UUID | No | — |
| rule_code | VARCHAR(128) | No | — |
| rule_name | VARCHAR(255) | No | — |
| attribution_basis_type | VARCHAR(64) | No | — |
| calculation_logic_json | JSONB | No | <function dict at 0x00000272FA66E520> |
| presentation_logic_json | JSONB | No | <function dict at 0x00000272FA66F6A0> |
| version_token | VARCHAR(64) | No | — |
| effective_from | DATE | No | — |
| effective_to | DATE | Yes | — |
| supersedes_id | UUID | Yes | — |
| status | VARCHAR(32) | No | candidate |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `supersedes_id` -> `minority_interest_rule_definitions.id`

**Indexes:**
- `idx_minority_interest_rule_definitions_lookup` (tenant_id, organisation_id, rule_code, effective_from, created_at)
- `ix_minority_interest_rule_definitions_tenant_id` (tenant_id)
- `uq_minority_interest_rule_definitions_one_active` (tenant_id, organisation_id, rule_code)

---

### mis_canonical_dimension_dictionary

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| version_no | INTEGER | No | — |
| dimension_code | VARCHAR(64) | No | — |
| display_name | VARCHAR(255) | No | — |
| description | TEXT | Yes | — |
| status | VARCHAR(32) | No | active |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Indexes:**
- `idx_mis_canonical_dimension_dict_code` (tenant_id, dimension_code)
- `ix_mis_canonical_dimension_dictionary_tenant_id` (tenant_id)

---

### mis_canonical_metric_dictionary

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| version_no | INTEGER | No | — |
| metric_code | VARCHAR(64) | No | — |
| display_name | VARCHAR(255) | No | — |
| description | TEXT | Yes | — |
| status | VARCHAR(32) | No | active |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Indexes:**
- `idx_mis_canonical_metric_dict_code` (tenant_id, metric_code)
- `ix_mis_canonical_metric_dictionary_tenant_id` (tenant_id)

---

### mis_data_snapshots

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| organisation_id | UUID | No | — |
| entity_id | UUID | Yes | — |
| template_id | UUID | No | — |
| template_version_id | UUID | No | — |
| reporting_period | DATE | No | — |
| upload_artifact_id | UUID | No | — |
| snapshot_token | VARCHAR(64) | No | — |
| source_file_hash | VARCHAR(64) | No | — |
| sheet_name | VARCHAR(255) | No | — |
| snapshot_status | VARCHAR(32) | No | pending |
| validation_summary_json | JSONB | No | <function dict at 0x00000272F9FBB4C0> |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `entity_id` -> `cp_entities.id`
- `template_id` -> `mis_templates.id`
- `template_version_id` -> `mis_template_versions.id`

**Indexes:**
- `idx_mis_data_snapshots_period` (tenant_id, template_id, reporting_period)
- `ix_mis_data_snapshots_tenant_id` (tenant_id)

---

### mis_drift_events

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| template_id | UUID | No | — |
| prior_template_version_id | UUID | No | — |
| candidate_template_version_id | UUID | No | — |
| drift_type | VARCHAR(64) | No | — |
| drift_details_json | JSONB | No | <function dict at 0x00000272FA01CB80> |
| decision_status | VARCHAR(32) | No | pending_review |
| decided_by | UUID | Yes | — |
| decided_at | DATETIME | Yes | — |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `candidate_template_version_id` -> `mis_template_versions.id`
- `prior_template_version_id` -> `mis_template_versions.id`
- `template_id` -> `mis_templates.id`

**Indexes:**
- `idx_mis_drift_events_template` (tenant_id, template_id, created_at)
- `ix_mis_drift_events_tenant_id` (tenant_id)

---

### mis_ingestion_exceptions

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| snapshot_id | UUID | No | — |
| exception_code | VARCHAR(64) | No | — |
| severity | VARCHAR(16) | No | — |
| source_ref | TEXT | No | — |
| message | TEXT | No | — |
| resolution_status | VARCHAR(24) | No | open |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `snapshot_id` -> `mis_data_snapshots.id`

**Indexes:**
- `idx_mis_ingestion_exceptions_snapshot` (tenant_id, snapshot_id, created_at)
- `ix_mis_ingestion_exceptions_tenant_id` (tenant_id)

---

### mis_normalized_lines

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| snapshot_id | UUID | No | — |
| entity_id | UUID | Yes | — |
| line_no | INTEGER | No | — |
| canonical_metric_code | VARCHAR(64) | No | — |
| canonical_dimension_json | JSONB | No | <function dict at 0x00000272F9FEA020> |
| source_row_ref | TEXT | No | — |
| source_column_ref | TEXT | No | — |
| period_value | NUMERIC(18, 6) | No | — |
| currency_code | VARCHAR(3) | No | — |
| sign_applied | VARCHAR(32) | No | as_is |
| validation_status | VARCHAR(16) | No | valid |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `entity_id` -> `cp_entities.id`
- `snapshot_id` -> `mis_data_snapshots.id`

**Indexes:**
- `idx_mis_normalized_lines_snapshot` (tenant_id, snapshot_id, line_no)
- `ix_mis_normalized_lines_tenant_id` (tenant_id)

---

### mis_template_columns

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| template_version_id | UUID | No | — |
| source_column_label | TEXT | No | — |
| normalized_column_label | TEXT | No | — |
| column_role | VARCHAR(32) | No | — |
| data_type | VARCHAR(32) | No | string |
| ordinal_position | INTEGER | No | — |
| canonical_dimension_code | VARCHAR(64) | Yes | — |
| canonical_metric_code | VARCHAR(64) | Yes | — |
| is_required | BOOLEAN | No | False |
| is_period_column | BOOLEAN | No | False |
| is_value_column | BOOLEAN | No | False |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `template_version_id` -> `mis_template_versions.id`

**Indexes:**
- `idx_mis_template_columns_version` (tenant_id, template_version_id)
- `ix_mis_template_columns_tenant_id` (tenant_id)

---

### mis_template_row_mappings

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| template_version_id | UUID | No | — |
| source_row_pattern | TEXT | No | — |
| normalized_row_label | TEXT | No | — |
| canonical_metric_code | VARCHAR(64) | No | — |
| sign_rule | VARCHAR(32) | No | — |
| aggregation_rule | VARCHAR(32) | No | — |
| section_code | VARCHAR(64) | No | — |
| confidence_score | NUMERIC(5, 4) | No | — |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `section_code` -> `mis_template_sections.section_code`
- `template_version_id` -> `mis_template_versions.id`
- `template_version_id` -> `mis_template_sections.template_version_id`

**Indexes:**
- `idx_mis_template_row_mappings_version` (tenant_id, template_version_id)
- `ix_mis_template_row_mappings_tenant_id` (tenant_id)

---

### mis_template_sections

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| template_version_id | UUID | No | — |
| section_code | VARCHAR(64) | No | — |
| section_name | VARCHAR(255) | No | — |
| section_order | INTEGER | No | — |
| start_row_signature | VARCHAR(128) | No | — |
| end_row_signature | VARCHAR(128) | No | — |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `template_version_id` -> `mis_template_versions.id`

**Indexes:**
- `idx_mis_template_sections_version` (tenant_id, template_version_id)
- `ix_mis_template_sections_tenant_id` (tenant_id)

---

### mis_template_versions

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| template_id | UUID | No | — |
| version_no | INTEGER | No | — |
| version_token | VARCHAR(64) | No | — |
| based_on_version_id | UUID | Yes | — |
| supersedes_id | UUID | Yes | — |
| structure_hash | VARCHAR(64) | No | — |
| header_hash | VARCHAR(64) | No | — |
| row_signature_hash | VARCHAR(64) | No | — |
| column_signature_hash | VARCHAR(64) | No | — |
| detection_summary_json | JSONB | No | <function dict at 0x00000272F9F8E480> |
| drift_reason | TEXT | Yes | — |
| status | VARCHAR(32) | No | candidate |
| effective_from | DATE | Yes | — |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `based_on_version_id` -> `mis_template_versions.id`
- `supersedes_id` -> `mis_template_versions.id`
- `template_id` -> `mis_templates.id`

**Indexes:**
- `idx_mis_template_versions_template_created` (tenant_id, template_id, created_at)
- `ix_mis_template_versions_tenant_id` (tenant_id)
- `uq_mis_template_versions_one_active` (template_id)

---

### mis_templates

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| name | VARCHAR(255) | No | legacy_template |
| entity_name | VARCHAR(255) | No | legacy_entity |
| version | INTEGER | No | 1 |
| is_master | BOOLEAN | No | False |
| is_active | BOOLEAN | No | True |
| template_data | JSONB | No | <function dict at 0x00000272F9F534C0> |
| sheet_count | INTEGER | No | 0 |
| organisation_id | UUID | No | — |
| entity_id | UUID | Yes | — |
| template_code | VARCHAR(128) | No | — |
| template_name | VARCHAR(255) | No | — |
| template_type | VARCHAR(64) | No | custom |
| description | TEXT | Yes | — |
| status | VARCHAR(32) | No | active |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `entity_id` -> `cp_entities.id`

**Indexes:**
- `idx_mis_templates_entity` (tenant_id, entity_name)
- `idx_mis_templates_template_code` (tenant_id, template_code)
- `idx_mis_templates_tenant_created` (tenant_id, created_at)
- `ix_mis_templates_tenant_id` (tenant_id)

---

### mis_uploads

- **Description**: Legacy upload table retained for backward compatibility.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| template_id | UUID | Yes | — |
| entity_name | VARCHAR(255) | No | — |
| period_year | INTEGER | No | — |
| period_month | INTEGER | No | — |
| file_name | VARCHAR(500) | No | — |
| file_hash | VARCHAR(64) | No | — |
| status | VARCHAR(50) | No | pending |
| upload_notes | TEXT | Yes | — |
| parsed_data | JSONB | Yes | — |
| uploaded_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `template_id` -> `mis_templates.id`

**Indexes:**
- `idx_mis_uploads_period` (tenant_id, period_year, period_month)
- `idx_mis_uploads_tenant_created` (tenant_id, created_at)
- `ix_mis_uploads_tenant_id` (tenant_id)

---

### module_registry

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: No
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| module_name | VARCHAR(100) | No | — |
| module_version | VARCHAR(20) | No | 1.0.0 |
| description | TEXT | Yes | — |
| is_enabled | BOOLEAN | No | True |
| health_status | VARCHAR(20) | No | unknown |
| last_health_check | DATETIME | Yes | — |
| route_prefix | VARCHAR(100) | Yes | — |
| depends_on | JSONB | No | <function list at 0x00000272FAE368E0> |
| created_at | DATETIME | No | now() |
| updated_at | DATETIME | No | now() |

**Indexes:**
- `idx_module_registry_module_name` (module_name)

---

### monthend_checklists

- **Description**: Month-end closing checklist for a period/entity — INSERT ONLY.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| period_year | INTEGER | No | — |
| period_month | INTEGER | No | — |
| entity_id | UUID | Yes | — |
| entity_name | VARCHAR(255) | No | — |
| status | VARCHAR(20) | No | open |
| closed_at | DATETIME | Yes | — |
| closed_by | UUID | Yes | — |
| notes | TEXT | Yes | — |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `entity_id` -> `cp_entities.id`

**Indexes:**
- `idx_monthend_cl_entity` (tenant_id, entity_name)
- `idx_monthend_cl_tenant_period` (tenant_id, period_year, period_month)
- `ix_monthend_checklists_entity_id` (entity_id)
- `ix_monthend_checklists_tenant_id` (tenant_id)

---

### monthend_tasks

- **Description**: Individual task within a month-end checklist.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| checklist_id | UUID | No | — |
| tenant_id | UUID | No | — |
| task_name | VARCHAR(255) | No | — |
| task_category | VARCHAR(50) | No | other |
| description | TEXT | Yes | — |
| assigned_to | UUID | Yes | — |
| due_date | DATE | Yes | — |
| priority | VARCHAR(20) | No | medium |
| status | VARCHAR(20) | No | pending |
| completed_at | DATETIME | Yes | — |
| completed_by | UUID | Yes | — |
| notes | TEXT | Yes | — |
| sort_order | INTEGER | No | 0 |
| is_required | BOOLEAN | No | True |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `checklist_id` -> `monthend_checklists.id`

**Indexes:**
- `idx_monthend_tasks_checklist` (checklist_id)
- `idx_monthend_tasks_status` (checklist_id, status)
- `ix_monthend_tasks_tenant_id` (tenant_id)

---

### multi_entity_consolidation_evidence_links

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| run_id | UUID | No | — |
| metric_result_id | UUID | Yes | — |
| variance_result_id | UUID | Yes | — |
| evidence_type | VARCHAR(64) | No | — |
| evidence_ref | TEXT | No | — |
| evidence_label | VARCHAR(255) | No | — |
| evidence_payload_json | JSONB | No | <function dict at 0x00000272FA59ACA0> |
| created_by_intent_id | UUID | Yes | — |
| recorded_by_job_id | UUID | Yes | — |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `metric_result_id` -> `multi_entity_consolidation_metric_results.id`
- `run_id` -> `multi_entity_consolidation_runs.id`
- `variance_result_id` -> `multi_entity_consolidation_variance_results.id`

**Indexes:**
- `idx_multi_entity_consolidation_evidence_links_metric` (tenant_id, run_id, metric_result_id)
- `idx_multi_entity_consolidation_evidence_links_run` (tenant_id, run_id, created_at)
- `ix_multi_entity_consolidation_evidence_links_tenant_id` (tenant_id)

---

### multi_entity_consolidation_metric_results

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| run_id | UUID | No | — |
| line_no | INTEGER | No | — |
| metric_code | VARCHAR(128) | No | — |
| scope_json | JSONB | No | <function dict at 0x00000272FA56BE20> |
| currency_code | VARCHAR(3) | No | — |
| aggregated_value | NUMERIC(20, 6) | No | — |
| entity_count | INTEGER | No | — |
| materiality_flag | BOOLEAN | No | False |
| created_by_intent_id | UUID | Yes | — |
| recorded_by_job_id | UUID | Yes | — |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `run_id` -> `multi_entity_consolidation_runs.id`

**Indexes:**
- `idx_multi_entity_consolidation_metric_results_metric` (tenant_id, run_id, metric_code)
- `idx_multi_entity_consolidation_metric_results_run` (tenant_id, run_id, line_no)
- `ix_multi_entity_consolidation_metric_results_tenant_id` (tenant_id)

---

### multi_entity_consolidation_runs

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| organisation_id | UUID | No | — |
| reporting_period | DATE | No | — |
| hierarchy_id | UUID | No | — |
| scope_id | UUID | No | — |
| hierarchy_version_token | VARCHAR(64) | No | — |
| scope_version_token | VARCHAR(64) | No | — |
| rule_version_token | VARCHAR(64) | No | — |
| intercompany_version_token | VARCHAR(64) | No | — |
| adjustment_version_token | VARCHAR(64) | No | — |
| source_run_refs_json | JSONB | No | <function list at 0x00000272FA569120> |
| run_token | VARCHAR(64) | No | — |
| run_status | VARCHAR(32) | No | created |
| validation_summary_json | JSONB | No | <function dict at 0x00000272FA56A480> |
| created_by_intent_id | UUID | Yes | — |
| recorded_by_job_id | UUID | Yes | — |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `hierarchy_id` -> `entity_hierarchies.id`
- `scope_id` -> `consolidation_scopes.id`

**Indexes:**
- `idx_multi_entity_consolidation_runs_lookup` (tenant_id, organisation_id, reporting_period, created_at)
- `idx_multi_entity_consolidation_runs_token` (tenant_id, run_token)
- `ix_multi_entity_consolidation_runs_tenant_id` (tenant_id)

---

### multi_entity_consolidation_variance_results

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| run_id | UUID | No | — |
| line_no | INTEGER | No | — |
| metric_code | VARCHAR(128) | No | — |
| comparison_type | VARCHAR(32) | No | — |
| base_value | NUMERIC(20, 6) | No | — |
| current_value | NUMERIC(20, 6) | No | — |
| variance_value | NUMERIC(20, 6) | No | — |
| variance_pct | NUMERIC(20, 6) | Yes | — |
| materiality_flag | BOOLEAN | No | False |
| created_by_intent_id | UUID | Yes | — |
| recorded_by_job_id | UUID | Yes | — |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `run_id` -> `multi_entity_consolidation_runs.id`

**Indexes:**
- `idx_multi_entity_consolidation_variance_results_metric` (tenant_id, run_id, metric_code)
- `idx_multi_entity_consolidation_variance_results_run` (tenant_id, run_id, line_no)
- `ix_multi_entity_consolidation_variance_results_tenant_id` (tenant_id)

---

### multi_gaap_configs

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| entity_id | UUID | No | — |
| primary_gaap | VARCHAR(20) | No | INDAS |
| secondary_gaaps | JSONB | No | <function list at 0x00000272FD570EA0> |
| revenue_recognition_policy | JSONB | No | <function dict at 0x00000272FD570FE0> |
| lease_classification_policy | JSONB | No | <function dict at 0x00000272FD571300> |
| financial_instruments_policy | JSONB | No | <function dict at 0x00000272FD571440> |
| created_at | DATETIME | No | now() |
| updated_at | DATETIME | No | now() |

**Foreign keys:**
- `entity_id` -> `cp_entities.id`

**Indexes:**
- `idx_multi_gaap_configs_tenant_entity` (tenant_id, entity_id)

---

### multi_gaap_runs

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| entity_id | UUID | No | — |
| period | VARCHAR(7) | No | — |
| gaap_framework | VARCHAR(20) | No | — |
| revenue | NUMERIC(20, 2) | No | — |
| gross_profit | NUMERIC(20, 2) | No | — |
| ebitda | NUMERIC(20, 2) | No | — |
| ebit | NUMERIC(20, 2) | No | — |
| profit_before_tax | NUMERIC(20, 2) | No | — |
| profit_after_tax | NUMERIC(20, 2) | No | — |
| total_assets | NUMERIC(20, 2) | No | — |
| total_equity | NUMERIC(20, 2) | No | — |
| adjustments | JSONB | No | <function list at 0x00000272FD532980> |
| created_by | UUID | No | — |
| created_at | DATETIME | No | now() |

**Foreign keys:**
- `entity_id` -> `cp_entities.id`

**Indexes:**
- `idx_multi_gaap_runs_tenant_entity_period_framework` (tenant_id, entity_id, period, gaap_framework)

---

### narrative_templates

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| organisation_id | UUID | No | — |
| template_code | VARCHAR(128) | No | — |
| template_name | VARCHAR(255) | No | — |
| template_type | VARCHAR(64) | No | — |
| template_text | TEXT | No | — |
| template_body_json | JSONB | No | <function dict at 0x00000272FD2502C0> |
| placeholder_schema_json | JSONB | No | <function dict at 0x00000272FD251800> |
| version_token | VARCHAR(64) | No | — |
| effective_from | DATE | No | — |
| effective_to | DATE | Yes | — |
| supersedes_id | UUID | Yes | — |
| status | VARCHAR(32) | No | candidate |
| created_by | UUID | No | — |
| created_by_intent_id | UUID | Yes | — |
| recorded_by_job_id | UUID | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `supersedes_id` -> `narrative_templates.id`

**Indexes:**
- `idx_narrative_templates_lookup` (tenant_id, organisation_id, template_code, effective_from, created_at)
- `ix_narrative_templates_tenant_id` (tenant_id)
- `uq_narrative_templates_one_active` (tenant_id, organisation_id, template_code)

---

### normalization_evidence_links

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| run_id | UUID | No | — |
| normalized_line_type | VARCHAR(32) | No | — |
| normalized_line_id | UUID | No | — |
| evidence_type | VARCHAR(64) | No | — |
| evidence_ref | TEXT | No | — |
| evidence_label | VARCHAR(255) | No | — |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `run_id` -> `normalization_runs.id`

**Indexes:**
- `idx_normalization_evidence_links_run` (tenant_id, run_id, created_at)
- `idx_normalization_evidence_links_run_line` (tenant_id, run_id, normalized_line_id)
- `ix_normalization_evidence_links_tenant_id` (tenant_id)

---

### normalization_exceptions

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| run_id | UUID | No | — |
| exception_code | VARCHAR(64) | No | — |
| severity | VARCHAR(16) | No | — |
| source_ref | VARCHAR(255) | No | — |
| message | TEXT | No | — |
| resolution_status | VARCHAR(24) | No | open |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `run_id` -> `normalization_runs.id`

**Indexes:**
- `idx_normalization_exceptions_run` (tenant_id, run_id, created_at)
- `idx_normalization_exceptions_severity` (tenant_id, run_id, severity)
- `ix_normalization_exceptions_tenant_id` (tenant_id)

---

### normalization_mappings

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| source_version_id | UUID | No | — |
| mapping_type | VARCHAR(32) | No | — |
| source_field_name | VARCHAR(255) | No | — |
| canonical_field_name | VARCHAR(128) | No | — |
| transform_rule | VARCHAR(64) | Yes | — |
| default_value_json | JSONB | No | <function dict at 0x00000272FA1BEC00> |
| required_flag | BOOLEAN | No | False |
| confidence_score | NUMERIC(5, 4) | No | — |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `source_version_id` -> `normalization_source_versions.id`

**Indexes:**
- `idx_normalization_mappings_field` (tenant_id, source_version_id, canonical_field_name)
- `idx_normalization_mappings_source_version` (tenant_id, source_version_id, mapping_type)
- `ix_normalization_mappings_tenant_id` (tenant_id)

---

### normalization_runs

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| organisation_id | UUID | No | — |
| source_id | UUID | No | — |
| source_version_id | UUID | No | — |
| mapping_version_token | VARCHAR(64) | No | — |
| run_type | VARCHAR(64) | No | — |
| reporting_period | DATE | No | — |
| source_artifact_id | UUID | No | — |
| source_file_hash | VARCHAR(64) | No | — |
| source_airlock_item_id | UUID | Yes | — |
| source_type | VARCHAR(64) | Yes | — |
| source_external_ref | VARCHAR(255) | Yes | — |
| created_by_intent_id | UUID | Yes | — |
| recorded_by_job_id | UUID | Yes | — |
| run_token | VARCHAR(64) | No | — |
| run_status | VARCHAR(32) | No | pending |
| validation_summary_json | JSONB | No | <function dict at 0x00000272FA1F44A0> |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `created_by_intent_id` -> `canonical_intents.id`
- `recorded_by_job_id` -> `canonical_jobs.id`
- `source_airlock_item_id` -> `airlock_items.id`
- `source_id` -> `normalization_sources.id`
- `source_version_id` -> `normalization_source_versions.id`

**Indexes:**
- `idx_normalization_runs_source_period` (tenant_id, source_id, reporting_period)
- `idx_normalization_runs_token` (tenant_id, run_token)
- `ix_normalization_runs_tenant_id` (tenant_id)

---

### normalization_source_versions

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| source_id | UUID | No | — |
| version_no | INTEGER | No | — |
| version_token | VARCHAR(64) | No | — |
| structure_hash | VARCHAR(64) | No | — |
| header_hash | VARCHAR(64) | No | — |
| row_signature_hash | VARCHAR(64) | No | — |
| source_detection_summary_json | JSONB | No | <function dict at 0x00000272FA1BE660> |
| supersedes_id | UUID | Yes | — |
| status | VARCHAR(32) | No | candidate |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `source_id` -> `normalization_sources.id`
- `supersedes_id` -> `normalization_source_versions.id`

**Indexes:**
- `idx_normalization_source_versions_source` (tenant_id, source_id, created_at)
- `ix_normalization_source_versions_tenant_id` (tenant_id)
- `uq_normalization_source_versions_one_active` (source_id)

---

### normalization_sources

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| organisation_id | UUID | No | — |
| source_family | VARCHAR(64) | No | — |
| source_code | VARCHAR(128) | No | — |
| source_name | VARCHAR(255) | No | — |
| status | VARCHAR(32) | No | active |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Indexes:**
- `idx_normalization_sources_family_code` (tenant_id, source_family, source_code)
- `idx_normalization_sources_tenant` (tenant_id, created_at)
- `ix_normalization_sources_tenant_id` (tenant_id)

---

### normalized_financial_snapshot_lines

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| snapshot_line_id | UUID | No | <function uuid4 at 0x00000272F9B2C4A0> |
| snapshot_id | UUID | No | — |
| account_code | VARCHAR(64) | No | — |
| local_amount | NUMERIC(20, 6) | No | — |
| currency | VARCHAR(3) | No | — |
| ic_reference | VARCHAR(255) | Yes | — |
| counterparty_entity | UUID | Yes | — |
| transaction_date | DATE | Yes | — |
| ic_account_class | VARCHAR(64) | Yes | — |
| correlation_id | VARCHAR(64) | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `snapshot_id` -> `normalized_financial_snapshots.snapshot_id`

**Indexes:**
- `idx_norm_snapshot_lines_account` (tenant_id, snapshot_id, account_code)
- `idx_norm_snapshot_lines_tenant_snapshot` (tenant_id, snapshot_id)
- `ix_normalized_financial_snapshot_lines_tenant_id` (tenant_id)

---

### normalized_financial_snapshots

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| snapshot_id | UUID | No | <function uuid4 at 0x00000272F9B0EFC0> |
| entity_id | UUID | No | — |
| period_year | INTEGER | No | — |
| period_month | INTEGER | No | — |
| snapshot_type | VARCHAR(64) | No | normalized_pnl_v1 |
| entity_currency | VARCHAR(3) | No | — |
| produced_by_module | VARCHAR(64) | No | — |
| source_artifact_reference | VARCHAR(255) | No | — |
| supersedes_snapshot_id | UUID | Yes | — |
| correlation_id | VARCHAR(64) | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `supersedes_snapshot_id` -> `normalized_financial_snapshots.snapshot_id`

**Indexes:**
- `idx_norm_snapshots_entity` (tenant_id, entity_id)
- `idx_norm_snapshots_tenant_period` (tenant_id, period_year, period_month)
- `idx_norm_snapshots_type` (tenant_id, snapshot_type)
- `ix_normalized_financial_snapshots_tenant_id` (tenant_id)

---

### notification_events

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| recipient_user_id | UUID | No | — |
| notification_type | VARCHAR(50) | No | — |
| title | VARCHAR(300) | No | — |
| body | TEXT | No | — |
| action_url | TEXT | Yes | — |
| metadata | JSONB | No | <function dict at 0x00000272FAF119E0> |
| channels_sent | JSONB | No | <function list at 0x00000272FAF11BC0> |
| created_at | DATETIME | No | now() |

**Foreign keys:**
- `recipient_user_id` -> `iam_users.id`

**Indexes:**
- `idx_notification_events_tenant_type_created` (tenant_id, notification_type, created_at)
- `idx_notification_events_tenant_user_created` (tenant_id, recipient_user_id, created_at)

---

### notification_preferences

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| user_id | UUID | No | — |
| email_enabled | BOOLEAN | No | True |
| inapp_enabled | BOOLEAN | No | True |
| push_enabled | BOOLEAN | No | False |
| quiet_hours_start | TIME | Yes | — |
| quiet_hours_end | TIME | Yes | — |
| timezone | VARCHAR(50) | No | Asia/Kolkata |
| type_preferences | JSONB | No | <function dict at 0x00000272FAF3C540> |
| created_at | DATETIME | No | now() |
| updated_at | DATETIME | No | now() |

**Indexes:**
- `idx_notification_preferences_tenant_user` (tenant_id, user_id)

---

### notification_read_state

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| notification_event_id | UUID | No | — |
| tenant_id | UUID | No | — |
| user_id | UUID | No | — |
| is_read | BOOLEAN | No | False |
| read_at | DATETIME | Yes | — |
| is_dismissed | BOOLEAN | No | False |
| channels_sent | JSONB | No | <function list at 0x00000272FAF12F20> |
| delivery_status | VARCHAR(20) | No | queued |
| dismissed_at | DATETIME | Yes | — |
| created_at | DATETIME | No | now() |
| updated_at | DATETIME | No | now() |

**Foreign keys:**
- `notification_event_id` -> `notification_events.id`

**Indexes:**
- `idx_notification_read_state_tenant_user` (tenant_id, user_id, updated_at)

---

### observability_evidence_links

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| observability_run_id | UUID | No | — |
| result_id | UUID | Yes | — |
| evidence_type | VARCHAR(64) | No | — |
| evidence_ref | TEXT | No | — |
| evidence_label | VARCHAR(255) | No | — |
| evidence_payload_json | JSONB | No | <function dict at 0x00000272FA85BB00> |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `observability_run_id` -> `observability_runs.id`
- `result_id` -> `observability_results.id`

**Indexes:**
- `idx_observability_evidence_links_lookup` (tenant_id, observability_run_id, created_at)
- `ix_observability_evidence_links_tenant_id` (tenant_id)

---

### observability_results

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| observability_run_id | UUID | No | — |
| result_payload_json | JSONB | No | <function dict at 0x00000272FA859DA0> |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `observability_run_id` -> `observability_runs.id`

**Indexes:**
- `idx_observability_results_lookup` (tenant_id, observability_run_id, created_at)
- `ix_observability_results_tenant_id` (tenant_id)

---

### observability_run_registry

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| module_code | VARCHAR(64) | No | — |
| run_id | UUID | No | — |
| run_token | VARCHAR(64) | No | — |
| version_token_snapshot_json | JSONB | No | <function dict at 0x00000272FA7F34C0> |
| upstream_dependencies_json | JSONB | No | <function list at 0x00000272FA7F3560> |
| execution_time_ms | INTEGER | No | 0 |
| status | VARCHAR(32) | No | discovered |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Indexes:**
- `idx_observability_run_registry_lookup` (tenant_id, module_code, created_at)
- `idx_observability_run_registry_run` (tenant_id, run_id, created_at)
- `ix_observability_run_registry_tenant_id` (tenant_id)

---

### observability_runs

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| operation_type | VARCHAR(64) | No | — |
| input_ref_json | JSONB | No | <function dict at 0x00000272FA858D60> |
| operation_token | VARCHAR(64) | No | — |
| status | VARCHAR(32) | No | created |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Indexes:**
- `idx_observability_runs_lookup` (tenant_id, operation_type, created_at)
- `ix_observability_runs_tenant_id` (tenant_id)

---

### onboarding_state

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| current_step | INTEGER | No | 1 |
| industry | VARCHAR(50) | Yes | — |
| template_applied | BOOLEAN | No | False |
| template_applied_at | DATETIME | Yes | — |
| template_id | VARCHAR(50) | Yes | — |
| erp_connected | BOOLEAN | No | False |
| completed | BOOLEAN | No | False |
| completed_at | DATETIME | Yes | — |
| created_at | DATETIME | No | now() |
| updated_at | DATETIME | No | now() |

**Foreign keys:**
- `tenant_id` -> `iam_tenants.id`

---

### org_entities

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| org_group_id | UUID | No | — |
| cp_entity_id | UUID | Yes | — |
| legal_name | VARCHAR(300) | No | — |
| display_name | VARCHAR(200) | Yes | — |
| entity_type | VARCHAR(50) | No | — |
| country_code | VARCHAR(3) | No | — |
| state_code | VARCHAR(10) | Yes | — |
| functional_currency | VARCHAR(10) | No | — |
| reporting_currency | VARCHAR(10) | No | — |
| fiscal_year_start | INTEGER | No | — |
| applicable_gaap | VARCHAR(20) | No | — |
| industry_template_id | UUID | Yes | — |
| incorporation_number | VARCHAR(100) | Yes | — |
| pan | VARCHAR(20) | Yes | — |
| tan | VARCHAR(20) | Yes | — |
| cin | VARCHAR(30) | Yes | — |
| gstin | VARCHAR(20) | Yes | — |
| lei | VARCHAR(30) | Yes | — |
| tax_jurisdiction | VARCHAR(100) | Yes | — |
| tax_rate | NUMERIC(5, 4) | Yes | — |
| is_active | BOOLEAN | No | True |
| created_at | DATETIME | No | now() |
| updated_at | DATETIME | Yes | now() |

**Foreign keys:**
- `cp_entity_id` -> `cp_entities.id`
- `industry_template_id` -> `coa_industry_templates.id`
- `org_group_id` -> `org_groups.id`
- `tenant_id` -> `iam_tenants.id`

**Indexes:**
- `idx_org_entities_cp_entity_id` (cp_entity_id)
- `idx_org_entities_org_group_id` (org_group_id)
- `idx_org_entities_tenant_id` (tenant_id)

---

### org_entity_erp_configs

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| org_entity_id | UUID | No | — |
| erp_type | VARCHAR(50) | No | — |
| erp_version | VARCHAR(50) | Yes | — |
| connection_config | JSONB | Yes | — |
| is_primary | BOOLEAN | No | True |
| connection_tested | BOOLEAN | No | False |
| connection_tested_at | DATETIME | Yes | — |
| is_active | BOOLEAN | No | True |
| created_at | DATETIME | No | now() |
| updated_at | DATETIME | Yes | now() |

**Foreign keys:**
- `org_entity_id` -> `org_entities.id`
- `tenant_id` -> `iam_tenants.id`

**Indexes:**
- `idx_org_entity_erp_configs_org_entity_id` (org_entity_id)
- `idx_org_entity_erp_configs_tenant_id` (tenant_id)

---

### org_groups

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| group_name | VARCHAR(300) | No | — |
| country_of_incorp | VARCHAR(100) | No | — |
| country_code | VARCHAR(3) | No | — |
| functional_currency | VARCHAR(10) | No | — |
| reporting_currency | VARCHAR(10) | No | — |
| logo_url | TEXT | Yes | — |
| website | VARCHAR(300) | Yes | — |
| created_at | DATETIME | No | now() |
| updated_at | DATETIME | Yes | now() |

**Foreign keys:**
- `tenant_id` -> `iam_tenants.id`

**Indexes:**
- `idx_org_groups_tenant_id` (tenant_id)

---

### org_ownership

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| parent_entity_id | UUID | No | — |
| child_entity_id | UUID | No | — |
| ownership_pct | NUMERIC(7, 4) | No | — |
| consolidation_method | VARCHAR(30) | No | — |
| effective_from | DATE | No | — |
| effective_to | DATE | Yes | — |
| notes | TEXT | Yes | — |
| created_at | DATETIME | No | now() |

**Foreign keys:**
- `child_entity_id` -> `org_entities.id`
- `parent_entity_id` -> `org_entities.id`
- `tenant_id` -> `iam_tenants.id`

**Indexes:**
- `idx_org_ownership_child_entity_id` (child_entity_id)
- `idx_org_ownership_parent_entity_id` (parent_entity_id)
- `idx_org_ownership_tenant_id` (tenant_id)

---

### org_setup_progress

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| current_step | INTEGER | No | 1 |
| step1_data | JSONB | Yes | — |
| step2_data | JSONB | Yes | — |
| step3_data | JSONB | Yes | — |
| step4_data | JSONB | Yes | — |
| step5_data | JSONB | Yes | — |
| step6_data | JSONB | Yes | — |
| completed_at | DATETIME | Yes | — |
| created_at | DATETIME | No | now() |
| updated_at | DATETIME | Yes | now() |

**Foreign keys:**
- `tenant_id` -> `iam_tenants.id`

**Indexes:**
- `idx_org_setup_progress_tenant_id` (tenant_id)

---

### ownership_consolidation_evidence_links

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| ownership_consolidation_run_id | UUID | No | — |
| metric_result_id | UUID | Yes | — |
| variance_result_id | UUID | Yes | — |
| evidence_type | VARCHAR(64) | No | — |
| evidence_ref | TEXT | No | — |
| evidence_label | VARCHAR(255) | No | — |
| evidence_payload_json | JSONB | No | <function dict at 0x00000272FA6DD4E0> |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `metric_result_id` -> `ownership_consolidation_metric_results.id`
- `ownership_consolidation_run_id` -> `ownership_consolidation_runs.id`
- `variance_result_id` -> `ownership_consolidation_variance_results.id`

**Indexes:**
- `idx_ownership_consolidation_evidence_links_run` (tenant_id, ownership_consolidation_run_id, created_at)
- `ix_ownership_consolidation_evidence_links_tenant_id` (tenant_id)

---

### ownership_consolidation_metric_results

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| ownership_consolidation_run_id | UUID | No | — |
| line_no | INTEGER | No | — |
| scope_code | VARCHAR(128) | No | — |
| metric_code | VARCHAR(128) | No | — |
| source_consolidated_value | NUMERIC(20, 6) | No | — |
| ownership_weight_applied | NUMERIC(9, 6) | No | — |
| attributed_value | NUMERIC(20, 6) | No | — |
| minority_interest_value_nullable | NUMERIC(20, 6) | Yes | — |
| reporting_currency_code_nullable | VARCHAR(3) | Yes | — |
| lineage_summary_json | JSONB | No | <function dict at 0x00000272FA6A9260> |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `ownership_consolidation_run_id` -> `ownership_consolidation_runs.id`

**Indexes:**
- `idx_ownership_consolidation_metric_results_metric` (tenant_id, ownership_consolidation_run_id, metric_code)
- `idx_ownership_consolidation_metric_results_run` (tenant_id, ownership_consolidation_run_id, line_no)
- `ix_ownership_consolidation_metric_results_tenant_id` (tenant_id)

---

### ownership_consolidation_rule_definitions

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| organisation_id | UUID | No | — |
| rule_code | VARCHAR(128) | No | — |
| rule_name | VARCHAR(255) | No | — |
| rule_type | VARCHAR(64) | No | — |
| rule_logic_json | JSONB | No | <function dict at 0x00000272FA66CCC0> |
| attribution_policy_json | JSONB | No | <function dict at 0x00000272FA66E020> |
| version_token | VARCHAR(64) | No | — |
| effective_from | DATE | No | — |
| effective_to | DATE | Yes | — |
| supersedes_id | UUID | Yes | — |
| status | VARCHAR(32) | No | candidate |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `supersedes_id` -> `ownership_consolidation_rule_definitions.id`

**Indexes:**
- `idx_ownership_consolidation_rule_definitions_lookup` (tenant_id, organisation_id, rule_code, effective_from, created_at)
- `ix_ownership_consolidation_rule_definitions_tenant_id` (tenant_id)
- `uq_ownership_consolidation_rule_definitions_one_active` (tenant_id, organisation_id, rule_code)

---

### ownership_consolidation_runs

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| organisation_id | UUID | No | — |
| reporting_period | DATE | No | — |
| hierarchy_version_token | VARCHAR(64) | No | — |
| scope_version_token | VARCHAR(64) | No | — |
| ownership_structure_version_token | VARCHAR(64) | No | — |
| ownership_rule_version_token | VARCHAR(64) | No | — |
| minority_interest_rule_version_token | VARCHAR(64) | No | — |
| fx_translation_run_ref_nullable | UUID | Yes | — |
| source_consolidation_run_refs_json | JSONB | No | <function list at 0x00000272FA66FBA0> |
| run_token | VARCHAR(64) | No | — |
| run_status | VARCHAR(32) | No | created |
| validation_summary_json | JSONB | No | <function dict at 0x00000272FA6A8EA0> |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `fx_translation_run_ref_nullable` -> `fx_translation_runs.id`

**Indexes:**
- `idx_ownership_consolidation_runs_lookup` (tenant_id, organisation_id, reporting_period, created_at)
- `idx_ownership_consolidation_runs_token` (tenant_id, run_token)
- `ix_ownership_consolidation_runs_tenant_id` (tenant_id)

---

### ownership_consolidation_variance_results

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| ownership_consolidation_run_id | UUID | No | — |
| line_no | INTEGER | No | — |
| scope_code | VARCHAR(128) | No | — |
| metric_code | VARCHAR(128) | No | — |
| variance_code | VARCHAR(64) | No | — |
| source_current_value | NUMERIC(20, 6) | No | — |
| source_comparison_value | NUMERIC(20, 6) | No | — |
| ownership_weight_applied | NUMERIC(9, 6) | No | — |
| attributed_current_value | NUMERIC(20, 6) | No | — |
| attributed_comparison_value | NUMERIC(20, 6) | No | — |
| attributed_variance_abs | NUMERIC(20, 6) | No | — |
| attributed_variance_pct | NUMERIC(20, 6) | Yes | — |
| attributed_variance_bps | NUMERIC(20, 6) | Yes | — |
| minority_interest_value_nullable | NUMERIC(20, 6) | Yes | — |
| lineage_summary_json | JSONB | No | <function dict at 0x00000272FA6ABBA0> |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `ownership_consolidation_run_id` -> `ownership_consolidation_runs.id`

**Indexes:**
- `idx_ownership_consolidation_variance_results_metric` (tenant_id, ownership_consolidation_run_id, metric_code)
- `idx_ownership_consolidation_variance_results_run` (tenant_id, ownership_consolidation_run_id, line_no)
- `ix_ownership_consolidation_variance_results_tenant_id` (tenant_id)

---

### ownership_relationships

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| organisation_id | UUID | No | — |
| ownership_structure_id | UUID | No | — |
| parent_entity_id | UUID | No | — |
| child_entity_id | UUID | No | — |
| ownership_percentage | NUMERIC(9, 6) | No | — |
| voting_percentage_nullable | NUMERIC(9, 6) | Yes | — |
| control_indicator | BOOLEAN | No | False |
| minority_interest_indicator | BOOLEAN | No | False |
| proportionate_consolidation_indicator | BOOLEAN | No | False |
| effective_from | DATE | No | — |
| effective_to | DATE | Yes | — |
| supersedes_id | UUID | Yes | — |
| status | VARCHAR(32) | No | candidate |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `ownership_structure_id` -> `ownership_structure_definitions.id`
- `supersedes_id` -> `ownership_relationships.id`

**Indexes:**
- `idx_ownership_relationships_child_lookup` (tenant_id, ownership_structure_id, child_entity_id, created_at)
- `idx_ownership_relationships_lookup` (tenant_id, organisation_id, ownership_structure_id, parent_entity_id, child_entity_id, effective_from, created_at)
- `ix_ownership_relationships_tenant_id` (tenant_id)
- `uq_ownership_relationships_one_active` (tenant_id, ownership_structure_id, parent_entity_id, child_entity_id)

---

### ownership_structure_definitions

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| organisation_id | UUID | No | — |
| ownership_structure_code | VARCHAR(128) | No | — |
| ownership_structure_name | VARCHAR(255) | No | — |
| hierarchy_scope_ref | VARCHAR(128) | No | — |
| ownership_basis_type | VARCHAR(64) | No | — |
| version_token | VARCHAR(64) | No | — |
| effective_from | DATE | No | — |
| effective_to | DATE | Yes | — |
| supersedes_id | UUID | Yes | — |
| status | VARCHAR(32) | No | candidate |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `supersedes_id` -> `ownership_structure_definitions.id`

**Indexes:**
- `idx_ownership_structure_definitions_lookup` (tenant_id, organisation_id, ownership_structure_code, effective_from, created_at)
- `ix_ownership_structure_definitions_tenant_id` (tenant_id)
- `uq_ownership_structure_definitions_one_active` (tenant_id, organisation_id, ownership_structure_code)

---

### partner_commissions

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: No
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| partner_id | UUID | No | — |
| referral_id | UUID | No | — |
| referred_tenant_id | UUID | No | — |
| commission_type | VARCHAR(20) | No | — |
| payment_amount | NUMERIC(20, 2) | No | — |
| commission_rate | NUMERIC(5, 4) | No | — |
| commission_amount | NUMERIC(20, 2) | No | — |
| status | VARCHAR(20) | No | pending |
| period | VARCHAR(7) | Yes | — |
| created_at | DATETIME | No | now() |

**Foreign keys:**
- `partner_id` -> `partner_profiles.id`
- `referral_id` -> `referral_tracking.id`

**Indexes:**
- `idx_partner_commissions_partner_status_created` (partner_id, status, created_at)

---

### partner_profiles

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| partner_tier | VARCHAR(20) | No | referral |
| company_name | VARCHAR(300) | No | — |
| contact_email | VARCHAR(300) | No | — |
| website_url | TEXT | Yes | — |
| partner_code | VARCHAR(20) | No | — |
| commission_rate_pct | NUMERIC(5, 4) | No | — |
| total_referrals | INTEGER | No | 0 |
| total_commissions_earned | NUMERIC(20, 2) | No | 0 |
| stripe_account_id | VARCHAR(100) | Yes | — |
| is_active | BOOLEAN | No | True |
| approved_at | DATETIME | Yes | — |
| created_at | DATETIME | No | now() |
| updated_at | DATETIME | No | now() |

---

### password_reset_tokens

- **Description**: Abstract base with UUID PK and created_at.
- **RLS enabled**: No
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| user_id | UUID | No | — |
| token_hash | VARCHAR(64) | No | — |
| reset_attempt_count | INTEGER | No | 0 |
| expires_at | DATETIME | No | — |
| used_at | DATETIME | Yes | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `user_id` -> `iam_users.id`

**Indexes:**
- `ix_password_reset_tokens_hash` (token_hash)
- `ix_password_reset_tokens_user` (user_id)

---

### payment_methods

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| provider | VARCHAR(32) | No | — |
| provider_payment_method_id | VARCHAR(255) | No | — |
| type | VARCHAR(32) | No | — |
| last4 | VARCHAR(8) | Yes | — |
| brand | VARCHAR(64) | Yes | — |
| expiry_month | INTEGER | Yes | — |
| expiry_year | INTEGER | Yes | — |
| is_default | BOOLEAN | No | False |
| billing_details | JSONB | No | <function dict at 0x00000272FAAE0860> |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Indexes:**
- `idx_payment_methods_tenant` (tenant_id, provider, is_default, created_at)
- `ix_payment_methods_tenant_id` (tenant_id)

---

### payroll_gl_reconciliation_mappings

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| organisation_id | UUID | No | — |
| mapping_code | VARCHAR(64) | No | — |
| mapping_name | VARCHAR(255) | No | — |
| payroll_metric_code | VARCHAR(128) | No | — |
| gl_account_selector_json | JSONB | No | <function dict at 0x00000272FA265440> |
| cost_center_rule_json | JSONB | No | <function dict at 0x00000272FA2645E0> |
| department_rule_json | JSONB | No | <function dict at 0x00000272FA2654E0> |
| entity_rule_json | JSONB | No | <function dict at 0x00000272FA265580> |
| effective_from | DATE | No | — |
| supersedes_id | UUID | Yes | — |
| status | VARCHAR(32) | No | candidate |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `supersedes_id` -> `payroll_gl_reconciliation_mappings.id`

**Indexes:**
- `idx_payroll_gl_recon_mappings_lookup` (tenant_id, organisation_id, mapping_code, created_at)
- `ix_payroll_gl_reconciliation_mappings_tenant_id` (tenant_id)
- `uq_payroll_gl_recon_mappings_one_active` (tenant_id, organisation_id, mapping_code)

---

### payroll_gl_reconciliation_rules

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| organisation_id | UUID | No | — |
| rule_code | VARCHAR(64) | No | — |
| rule_name | VARCHAR(255) | No | — |
| rule_type | VARCHAR(64) | No | — |
| tolerance_json | JSONB | No | <function dict at 0x00000272FA265A80> |
| materiality_json | JSONB | No | <function dict at 0x00000272FA266C00> |
| timing_window_json | JSONB | No | <function dict at 0x00000272FA266CA0> |
| classification_behavior_json | JSONB | No | <function dict at 0x00000272FA266D40> |
| effective_from | DATE | No | — |
| supersedes_id | UUID | Yes | — |
| status | VARCHAR(32) | No | candidate |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `supersedes_id` -> `payroll_gl_reconciliation_rules.id`

**Indexes:**
- `idx_payroll_gl_recon_rules_lookup` (tenant_id, organisation_id, rule_code, created_at)
- `ix_payroll_gl_reconciliation_rules_tenant_id` (tenant_id)
- `uq_payroll_gl_recon_rules_one_active` (tenant_id, organisation_id, rule_code)

---

### payroll_gl_reconciliation_run_scopes

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| payroll_gl_reconciliation_run_id | UUID | No | — |
| scope_code | VARCHAR(64) | No | — |
| scope_label | VARCHAR(255) | No | — |
| scope_json | JSONB | No | <function dict at 0x00000272FA294A40> |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `payroll_gl_reconciliation_run_id` -> `payroll_gl_reconciliation_runs.id`

**Indexes:**
- `idx_payroll_gl_recon_run_scopes_run` (tenant_id, payroll_gl_reconciliation_run_id)
- `ix_payroll_gl_reconciliation_run_scopes_tenant_id` (tenant_id)

---

### payroll_gl_reconciliation_runs

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| organisation_id | UUID | No | — |
| reconciliation_session_id | UUID | No | — |
| payroll_run_id | UUID | No | — |
| gl_run_id | UUID | No | — |
| mapping_version_token | VARCHAR(64) | No | — |
| rule_version_token | VARCHAR(64) | No | — |
| reporting_period | DATE | No | — |
| run_token | VARCHAR(64) | No | — |
| status | VARCHAR(32) | No | created |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `gl_run_id` -> `normalization_runs.id`
- `payroll_run_id` -> `normalization_runs.id`
- `reconciliation_session_id` -> `reconciliation_sessions.id`

**Indexes:**
- `idx_payroll_gl_recon_runs_lookup` (tenant_id, organisation_id, reporting_period, created_at)
- `idx_payroll_gl_recon_runs_session` (tenant_id, reconciliation_session_id)
- `ix_payroll_gl_reconciliation_runs_tenant_id` (tenant_id)

---

### payroll_normalized_lines

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| run_id | UUID | No | — |
| row_no | INTEGER | No | — |
| employee_code | VARCHAR(128) | Yes | — |
| employee_name | VARCHAR(255) | Yes | — |
| payroll_period | DATE | No | — |
| legal_entity | VARCHAR(255) | Yes | — |
| department | VARCHAR(255) | Yes | — |
| cost_center | VARCHAR(255) | Yes | — |
| business_unit | VARCHAR(255) | Yes | — |
| location | VARCHAR(255) | Yes | — |
| grade | VARCHAR(128) | Yes | — |
| designation | VARCHAR(255) | Yes | — |
| currency_code | VARCHAR(3) | No | — |
| canonical_metric_code | VARCHAR(128) | No | — |
| amount_value | NUMERIC(20, 6) | No | — |
| source_row_ref | VARCHAR(128) | No | — |
| source_column_ref | VARCHAR(128) | No | — |
| normalization_status | VARCHAR(16) | No | — |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `run_id` -> `normalization_runs.id`

**Indexes:**
- `idx_payroll_normalized_lines_employee_period` (tenant_id, employee_code, payroll_period)
- `idx_payroll_normalized_lines_metric` (tenant_id, canonical_metric_code, payroll_period)
- `idx_payroll_normalized_lines_run` (tenant_id, run_id, row_no)
- `ix_payroll_normalized_lines_tenant_id` (tenant_id)

---

### pipeline_runs

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| sync_run_id | UUID | No | — |
| status | VARCHAR(20) | No | running |
| triggered_at | DATETIME | No | now() |
| completed_at | DATETIME | Yes | — |
| error_message | TEXT | Yes | — |
| created_at | DATETIME | No | now() |

**Indexes:**
- `idx_pipeline_runs_tenant_triggered_desc` (tenant_id)
- `uq_pipeline_runs_tenant_sync_active` (tenant_id, sync_run_id)

---

### pipeline_step_logs

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| pipeline_run_id | UUID | No | — |
| tenant_id | UUID | No | — |
| step_name | VARCHAR(50) | No | — |
| status | VARCHAR(20) | No | running |
| started_at | DATETIME | No | now() |
| completed_at | DATETIME | Yes | — |
| error_message | TEXT | Yes | — |
| result_summary | JSONB | Yes | — |
| created_at | DATETIME | No | now() |

**Foreign keys:**
- `pipeline_run_id` -> `pipeline_runs.id`

**Indexes:**
- `idx_pipeline_step_logs_run_started_desc` (pipeline_run_id)
- `idx_pipeline_step_logs_tenant_status` (tenant_id, status)

---

### ppa_allocations

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: Yes

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| engagement_id | UUID | No | — |
| tenant_id | UUID | No | — |
| allocation_version | INTEGER | No | 1 |
| net_identifiable_assets | NUMERIC(20, 2) | No | — |
| total_intangibles_identified | NUMERIC(20, 2) | No | — |
| goodwill | NUMERIC(20, 2) | No | — |
| deferred_tax_liability | NUMERIC(20, 2) | No | — |
| purchase_price_reconciliation | JSONB | No | — |
| computed_at | DATETIME | No | now() |

**Foreign keys:**
- `engagement_id` -> `ppa_engagements.id`

**Indexes:**
- `idx_ppa_allocations_engagement` (engagement_id)

---

### ppa_engagements

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| engagement_name | VARCHAR(300) | No | — |
| target_company_name | VARCHAR(300) | No | — |
| acquisition_date | DATE | No | — |
| purchase_price | NUMERIC(20, 2) | No | — |
| purchase_price_currency | VARCHAR(3) | No | INR |
| accounting_standard | VARCHAR(20) | No | — |
| status | VARCHAR(20) | No | draft |
| credit_cost | INTEGER | No | 2000 |
| created_by | UUID | No | — |
| created_at | DATETIME | No | now() |
| updated_at | DATETIME | No | now() |

**Foreign keys:**
- `created_by` -> `iam_users.id`

**Indexes:**
- `idx_ppa_engagements_tenant_status` (tenant_id, status)

---

### ppa_intangibles

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: Yes

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| engagement_id | UUID | No | — |
| allocation_id | UUID | No | — |
| tenant_id | UUID | No | — |
| intangible_name | VARCHAR(200) | No | — |
| intangible_category | VARCHAR(50) | No | — |
| fair_value | NUMERIC(20, 2) | No | — |
| useful_life_years | NUMERIC(5, 2) | No | — |
| amortisation_method | VARCHAR(20) | No | — |
| annual_amortisation | NUMERIC(20, 2) | No | — |
| tax_basis | NUMERIC(20, 2) | No | 0 |
| deferred_tax_liability | NUMERIC(20, 2) | No | 0 |
| valuation_method | VARCHAR(50) | No | — |
| valuation_assumptions | JSONB | No | <function dict at 0x00000272FADD2AC0> |
| created_at | DATETIME | No | now() |

**Foreign keys:**
- `allocation_id` -> `ppa_allocations.id`
- `engagement_id` -> `ppa_engagements.id`

**Indexes:**
- `idx_ppa_intangibles_engagement_category` (engagement_id, intangible_category)

---

### prepaid_adjustments

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| run_id | UUID | No | — |
| prepaid_id | UUID | No | — |
| effective_date | DATE | No | — |
| adjustment_type | VARCHAR(64) | No | — |
| adjustment_reason | TEXT | No | — |
| idempotency_key | VARCHAR(128) | No | — |
| prior_schedule_version_token | VARCHAR(64) | No | — |
| new_schedule_version_token | VARCHAR(64) | No | — |
| catch_up_amount_reporting_currency | NUMERIC(20, 6) | No | — |
| source_expense_reference | VARCHAR(255) | No | — |
| parent_reference_id | UUID | Yes | — |
| source_reference_id | UUID | Yes | — |
| correlation_id | VARCHAR(64) | Yes | — |
| supersedes_id | UUID | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `prepaid_id` -> `prepaids.id`
- `run_id` -> `prepaid_runs.id`
- `supersedes_id` -> `prepaid_adjustments.id`

**Indexes:**
- `idx_prepaid_adjustments_tenant_prepaid` (tenant_id, prepaid_id)
- `idx_prepaid_adjustments_tenant_run` (tenant_id, run_id, effective_date)
- `ix_prepaid_adjustments_tenant_id` (tenant_id)

---

### prepaid_amortisation_entries

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| entity_id | UUID | No | — |
| schedule_id | UUID | No | — |
| period_start | DATE | No | — |
| period_end | DATE | No | — |
| amortisation_amount | NUMERIC(20, 4) | No | — |
| is_last_period | BOOLEAN | No | False |
| run_reference | VARCHAR(200) | No | — |
| created_by_intent_id | UUID | Yes | — |
| recorded_by_job_id | UUID | Yes | — |
| created_at | DATETIME | No | now() |

**Foreign keys:**
- `entity_id` -> `cp_entities.id`
- `schedule_id` -> `prepaid_schedules.id`
- `tenant_id` -> `iam_tenants.id`

**Indexes:**
- `idx_prepaid_amortisation_entries_entity_id` (entity_id)
- `idx_prepaid_amortisation_entries_period_start` (period_start)
- `idx_prepaid_amortisation_entries_schedule_id` (schedule_id)
- `idx_prepaid_amortisation_entries_tenant_id` (tenant_id)

---

### prepaid_amortization_schedule

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| run_id | UUID | No | — |
| prepaid_id | UUID | No | — |
| period_seq | INTEGER | No | — |
| amortization_date | DATE | No | — |
| recognition_period_year | INTEGER | No | — |
| recognition_period_month | INTEGER | No | — |
| schedule_version_token | VARCHAR(64) | No | — |
| base_amount_contract_currency | NUMERIC(20, 6) | No | — |
| amortized_amount_reporting_currency | NUMERIC(20, 6) | No | — |
| cumulative_amortized_reporting_currency | NUMERIC(20, 6) | No | — |
| fx_rate_used | NUMERIC(20, 6) | No | — |
| fx_rate_date | DATE | No | — |
| fx_rate_source | VARCHAR(64) | No | — |
| schedule_status | VARCHAR(32) | No | — |
| source_expense_reference | VARCHAR(255) | No | — |
| parent_reference_id | UUID | Yes | — |
| source_reference_id | UUID | Yes | — |
| correlation_id | VARCHAR(64) | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `prepaid_id` -> `prepaids.id`
- `run_id` -> `prepaid_runs.id`

**Indexes:**
- `idx_prepaid_schedule_tenant_prepaid` (tenant_id, prepaid_id)
- `idx_prepaid_schedule_tenant_run` (tenant_id, run_id, amortization_date)
- `ix_prepaid_amortization_schedule_tenant_id` (tenant_id)

---

### prepaid_journal_entries

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| run_id | UUID | No | — |
| prepaid_id | UUID | No | — |
| schedule_id | UUID | No | — |
| journal_reference | VARCHAR(128) | No | — |
| entry_date | DATE | No | — |
| debit_account | VARCHAR(64) | No | — |
| credit_account | VARCHAR(64) | No | — |
| amount_reporting_currency | NUMERIC(20, 6) | No | — |
| source_expense_reference | VARCHAR(255) | No | — |
| parent_reference_id | UUID | Yes | — |
| source_reference_id | UUID | Yes | — |
| correlation_id | VARCHAR(64) | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `prepaid_id` -> `prepaids.id`
- `run_id` -> `prepaid_runs.id`
- `schedule_id` -> `prepaid_amortization_schedule.id`

**Indexes:**
- `idx_prepaid_journal_tenant_prepaid` (tenant_id, prepaid_id)
- `idx_prepaid_journal_tenant_run` (tenant_id, run_id, entry_date)
- `ix_prepaid_journal_entries_tenant_id` (tenant_id)

---

### prepaid_run_events

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| run_id | UUID | No | — |
| event_seq | INTEGER | No | — |
| event_type | VARCHAR(64) | No | — |
| event_time | DATETIME | No | — |
| idempotency_key | VARCHAR(128) | No | — |
| metadata_json | JSONB | Yes | — |
| correlation_id | VARCHAR(64) | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `run_id` -> `prepaid_runs.id`

**Indexes:**
- `idx_prepaid_run_events_tenant_run` (tenant_id, run_id, event_seq)
- `ix_prepaid_run_events_tenant_id` (tenant_id)

---

### prepaid_runs

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| request_signature | VARCHAR(64) | No | — |
| initiated_by | UUID | No | — |
| configuration_json | JSONB | No | — |
| workflow_id | VARCHAR(128) | No | — |
| correlation_id | VARCHAR(64) | Yes | — |
| created_by_intent_id | UUID | Yes | — |
| recorded_by_job_id | UUID | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Indexes:**
- `idx_prepaid_runs_tenant_created` (tenant_id, created_at)
- `ix_prepaid_runs_tenant_id` (tenant_id)

---

### prepaid_schedules

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| entity_id | UUID | No | — |
| location_id | UUID | Yes | — |
| cost_centre_id | UUID | Yes | — |
| reference_number | VARCHAR(100) | No | — |
| description | VARCHAR(300) | No | — |
| prepaid_type | VARCHAR(30) | No | — |
| vendor_name | VARCHAR(200) | Yes | — |
| invoice_number | VARCHAR(100) | Yes | — |
| total_amount | NUMERIC(20, 4) | No | — |
| amortised_amount | NUMERIC(20, 4) | No | 0 |
| remaining_amount | NUMERIC(20, 4) | No | — |
| coverage_start | DATE | No | — |
| coverage_end | DATE | No | — |
| amortisation_method | VARCHAR(20) | No | SLM |
| coa_prepaid_account_id | UUID | Yes | — |
| coa_expense_account_id | UUID | Yes | — |
| status | VARCHAR(20) | No | ACTIVE |
| created_by_intent_id | UUID | Yes | — |
| recorded_by_job_id | UUID | Yes | — |
| created_at | DATETIME | No | now() |
| updated_at | DATETIME | Yes | now() |

**Foreign keys:**
- `coa_expense_account_id` -> `tenant_coa_accounts.id`
- `coa_prepaid_account_id` -> `tenant_coa_accounts.id`
- `cost_centre_id` -> `cp_cost_centres.id`
- `entity_id` -> `cp_entities.id`
- `location_id` -> `cp_locations.id`
- `tenant_id` -> `iam_tenants.id`

**Indexes:**
- `idx_prepaid_schedules_cost_centre_id` (cost_centre_id)
- `idx_prepaid_schedules_entity_id` (entity_id)
- `idx_prepaid_schedules_location_id` (location_id)
- `idx_prepaid_schedules_reference_number` (reference_number)
- `idx_prepaid_schedules_status` (status)
- `idx_prepaid_schedules_tenant_id` (tenant_id)

---

### prepaids

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| prepaid_code | VARCHAR(128) | No | — |
| entity_id | UUID | Yes | — |
| description | TEXT | No | — |
| prepaid_currency | VARCHAR(3) | No | — |
| reporting_currency | VARCHAR(3) | No | — |
| term_start_date | DATE | No | — |
| term_end_date | DATE | No | — |
| base_amount_contract_currency | NUMERIC(20, 6) | No | — |
| period_frequency | VARCHAR(16) | No | — |
| pattern_type | VARCHAR(32) | No | — |
| pattern_json_normalized | JSONB | No | — |
| rate_mode | VARCHAR(32) | No | — |
| source_expense_reference | VARCHAR(255) | No | — |
| parent_reference_id | UUID | Yes | — |
| source_reference_id | UUID | Yes | — |
| correlation_id | VARCHAR(64) | Yes | — |
| supersedes_id | UUID | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `entity_id` -> `cp_entities.id`
- `supersedes_id` -> `prepaids.id`

**Indexes:**
- `idx_prepaids_tenant_code` (tenant_id, prepaid_code, created_at)
- `idx_prepaids_tenant_source` (tenant_id, source_expense_reference)
- `ix_prepaids_entity_id` (entity_id)
- `ix_prepaids_tenant_id` (tenant_id)

---

### proration_records

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| subscription_id | UUID | No | — |
| from_plan_id | UUID | No | — |
| to_plan_id | UUID | No | — |
| proration_date | DATE | No | — |
| credit_amount | NUMERIC(20, 6) | No | 0 |
| debit_amount | NUMERIC(20, 6) | No | 0 |
| currency | VARCHAR(3) | No | — |
| net_adjustment | NUMERIC(20, 6) | No | 0 |
| applied_to_invoice_id | UUID | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `applied_to_invoice_id` -> `billing_invoices.id`
- `subscription_id` -> `tenant_subscriptions.id`

**Indexes:**
- `idx_proration_records_tenant` (tenant_id, subscription_id, proration_date, created_at)
- `ix_proration_records_tenant_id` (tenant_id)

---

### recon_items

- **Description**: GL vs TB reconciliation break — INSERT ONLY.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| entity_id | UUID | Yes | — |
| period_year | INTEGER | No | — |
| period_month | INTEGER | No | — |
| entity_name | VARCHAR(255) | No | — |
| account_code | VARCHAR(50) | No | — |
| account_name | VARCHAR(255) | No | — |
| gl_total | NUMERIC(20, 6) | No | — |
| tb_closing_balance | NUMERIC(20, 6) | No | — |
| difference | NUMERIC(20, 6) | No | — |
| status | VARCHAR(50) | No | open |
| assigned_to | UUID | Yes | — |
| resolution_notes | TEXT | Yes | — |
| resolved_by | UUID | Yes | — |
| recon_type | VARCHAR(50) | No | gl_tb |
| run_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `entity_id` -> `cp_entities.id`

**Indexes:**
- `idx_recon_items_status` (tenant_id, status)
- `idx_recon_items_tenant_period` (tenant_id, period_year, period_month)
- `ix_recon_items_entity_id` (entity_id)
- `ix_recon_items_tenant_id` (tenant_id)

---

### reconciliation_evidence_links

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| session_id | UUID | No | — |
| line_id | UUID | No | — |
| evidence_type | VARCHAR(64) | No | — |
| evidence_ref | TEXT | No | — |
| evidence_label | VARCHAR(255) | No | — |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `line_id` -> `reconciliation_lines.id`
- `session_id` -> `reconciliation_sessions.id`

**Indexes:**
- `idx_recon_evidence_by_line` (tenant_id, line_id, created_at)
- `idx_recon_evidence_by_session` (tenant_id, session_id, created_at)
- `ix_reconciliation_evidence_links_tenant_id` (tenant_id)

---

### reconciliation_exceptions

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| entity_id | UUID | Yes | — |
| session_id | UUID | No | — |
| line_id | UUID | No | — |
| exception_code | VARCHAR(64) | No | — |
| severity | VARCHAR(16) | No | — |
| message | TEXT | No | — |
| owner_role | VARCHAR(64) | Yes | — |
| resolution_status | VARCHAR(32) | No | open |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `entity_id` -> `cp_entities.id`
- `line_id` -> `reconciliation_lines.id`
- `session_id` -> `reconciliation_sessions.id`

**Indexes:**
- `idx_recon_exception_by_session` (tenant_id, session_id, created_at)
- `ix_reconciliation_exceptions_entity_id` (entity_id)
- `ix_reconciliation_exceptions_tenant_id` (tenant_id)

---

### reconciliation_lines

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| entity_id | UUID | Yes | — |
| session_id | UUID | No | — |
| scope_id | UUID | Yes | — |
| line_key | VARCHAR(128) | No | — |
| comparison_dimension_json | JSONB | No | <function dict at 0x00000272FA15EC00> |
| source_a_value | NUMERIC(20, 6) | No | — |
| source_b_value | NUMERIC(20, 6) | No | — |
| variance_value | NUMERIC(20, 6) | No | — |
| variance_abs | NUMERIC(20, 6) | No | — |
| variance_pct | NUMERIC(20, 6) | No | — |
| currency_code | VARCHAR(3) | No | — |
| reconciliation_status | VARCHAR(32) | No | — |
| difference_type | VARCHAR(64) | No | — |
| materiality_flag | BOOLEAN | No | False |
| explanation_hint | TEXT | Yes | — |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `entity_id` -> `cp_entities.id`
- `scope_id` -> `reconciliation_scopes.id`
- `session_id` -> `reconciliation_sessions.id`

**Indexes:**
- `idx_recon_lines_difference_type` (tenant_id, session_id, difference_type)
- `idx_recon_lines_line_key` (tenant_id, session_id, line_key)
- `idx_recon_lines_session` (tenant_id, session_id)
- `idx_recon_lines_status` (tenant_id, session_id, reconciliation_status)
- `ix_reconciliation_lines_entity_id` (entity_id)
- `ix_reconciliation_lines_tenant_id` (tenant_id)

---

### reconciliation_resolution_events

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| session_id | UUID | No | — |
| line_id | UUID | No | — |
| exception_id | UUID | Yes | — |
| event_type | VARCHAR(64) | No | — |
| event_payload_json | JSONB | No | <function dict at 0x00000272FA18E8E0> |
| actor_user_id | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `exception_id` -> `reconciliation_exceptions.id`
- `line_id` -> `reconciliation_lines.id`
- `session_id` -> `reconciliation_sessions.id`

**Indexes:**
- `idx_recon_resolution_event_by_line` (tenant_id, line_id, created_at)
- `idx_recon_resolution_event_by_session` (tenant_id, session_id, created_at)
- `ix_reconciliation_resolution_events_tenant_id` (tenant_id)

---

### reconciliation_scopes

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| session_id | UUID | No | — |
| scope_code | VARCHAR(64) | No | — |
| scope_label | VARCHAR(255) | No | — |
| scope_json | JSONB | No | <function dict at 0x00000272FA15D3A0> |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `session_id` -> `reconciliation_sessions.id`

**Indexes:**
- `idx_reconciliation_scopes_session` (tenant_id, session_id)
- `ix_reconciliation_scopes_tenant_id` (tenant_id)

---

### reconciliation_sessions

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| organisation_id | UUID | No | — |
| reconciliation_type | VARCHAR(64) | No | — |
| source_a_type | VARCHAR(64) | No | — |
| source_a_ref | TEXT | No | — |
| source_b_type | VARCHAR(64) | No | — |
| source_b_ref | TEXT | No | — |
| period_start | DATE | No | — |
| period_end | DATE | No | — |
| matching_rule_version | VARCHAR(64) | No | — |
| tolerance_rule_version | VARCHAR(64) | No | — |
| session_token | VARCHAR(64) | No | — |
| materiality_config_json | JSONB | No | <function dict at 0x00000272FA123BA0> |
| status | VARCHAR(32) | No | created |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Indexes:**
- `idx_recon_session_tenant` (tenant_id, created_at)
- `idx_recon_session_token` (session_token)
- `ix_reconciliation_sessions_tenant_id` (tenant_id)

---

### referral_tracking

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| partner_id | UUID | No | — |
| referred_tenant_id | UUID | Yes | — |
| tenant_id | UUID | No | — |
| referral_code | VARCHAR(20) | No | — |
| referral_email | VARCHAR(300) | Yes | — |
| status | VARCHAR(20) | No | clicked |
| clicked_at | DATETIME | No | now() |
| signed_up_at | DATETIME | Yes | — |
| converted_at | DATETIME | Yes | — |
| first_payment_amount | NUMERIC(20, 2) | Yes | — |
| expires_at | DATETIME | No | — |
| created_at | DATETIME | No | now() |
| updated_at | DATETIME | No | now() |

**Foreign keys:**
- `partner_id` -> `partner_profiles.id`
- `referred_tenant_id` -> `iam_tenants.id`

**Indexes:**
- `idx_referral_tracking_partner_status` (partner_id, status)
- `idx_referral_tracking_referral_code` (referral_code)

---

### report_definitions

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| name | VARCHAR(255) | No | — |
| description | TEXT | Yes | — |
| metric_keys | JSONB | No | <function list at 0x00000272FA053560> |
| filter_config | JSONB | No | <function dict at 0x00000272FA084400> |
| group_by | JSONB | No | <function list at 0x00000272FA0844A0> |
| sort_config | JSONB | No | <function dict at 0x00000272FA084540> |
| export_formats | JSONB | No | <function ReportDefinition.<lambda> at 0x00000272FA084680> |
| config | JSONB | No | <function dict at 0x00000272FA084720> |
| created_by | UUID | No | — |
| created_at | DATETIME | No | now() |
| updated_at | DATETIME | No | now() |
| created_by_intent_id | UUID | Yes | — |
| recorded_by_job_id | UUID | Yes | — |
| is_active | BOOLEAN | No | True |

---

### report_results

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| run_id | UUID | No | — |
| result_data | JSONB | No | — |
| result_hash | VARCHAR(64) | No | — |
| export_path_csv | TEXT | Yes | — |
| export_path_excel | TEXT | Yes | — |
| export_path_pdf | TEXT | Yes | — |
| created_by_intent_id | UUID | Yes | — |
| recorded_by_job_id | UUID | Yes | — |
| created_at | DATETIME | No | now() |

**Foreign keys:**
- `run_id` -> `report_runs.id`

**Indexes:**
- `ux_report_results_run_id` (run_id)

---

### report_runs

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| definition_id | UUID | No | — |
| status | VARCHAR(50) | No | PENDING |
| triggered_by | UUID | No | — |
| started_at | DATETIME | Yes | — |
| completed_at | DATETIME | Yes | — |
| error_message | TEXT | Yes | — |
| row_count | INTEGER | Yes | — |
| run_metadata | JSONB | No | <function dict at 0x00000272FA085B20> |
| created_by_intent_id | UUID | Yes | — |
| recorded_by_job_id | UUID | Yes | — |
| created_at | DATETIME | No | now() |

**Foreign keys:**
- `definition_id` -> `report_definitions.id`

**Indexes:**
- `idx_report_runs_tenant_definition_created_desc` (tenant_id, definition_id)
- `idx_report_runs_tenant_status` (tenant_id, status)

---

### reporting_currency_definitions

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| organisation_id | UUID | No | — |
| reporting_currency_code | VARCHAR(3) | No | — |
| reporting_currency_name | VARCHAR(128) | No | — |
| reporting_scope_type | VARCHAR(64) | No | — |
| reporting_scope_ref | VARCHAR(128) | No | — |
| version_token | VARCHAR(64) | No | — |
| effective_from | DATE | No | — |
| effective_to | DATE | Yes | — |
| supersedes_id | UUID | Yes | — |
| status | VARCHAR(32) | No | candidate |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `supersedes_id` -> `reporting_currency_definitions.id`

**Indexes:**
- `idx_reporting_currency_definitions_lookup` (tenant_id, organisation_id, reporting_scope_type, reporting_scope_ref, effective_from, created_at)
- `ix_reporting_currency_definitions_tenant_id` (tenant_id)
- `uq_reporting_currency_definitions_one_active_scope` (tenant_id, organisation_id, reporting_scope_type, reporting_scope_ref)

---

### revenue_adjustments

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| run_id | UUID | No | — |
| contract_id | UUID | No | — |
| effective_date | DATE | No | — |
| adjustment_type | VARCHAR(64) | No | — |
| adjustment_reason | TEXT | No | — |
| idempotency_key | VARCHAR(128) | No | — |
| prior_schedule_version_token | VARCHAR(64) | No | — |
| new_schedule_version_token | VARCHAR(64) | No | — |
| prior_schedule_reference | VARCHAR(255) | Yes | — |
| new_schedule_reference | VARCHAR(255) | Yes | — |
| catch_up_amount_reporting_currency | NUMERIC(20, 6) | No | — |
| source_contract_reference | VARCHAR(255) | No | — |
| parent_reference_id | UUID | Yes | — |
| source_reference_id | UUID | Yes | — |
| correlation_id | VARCHAR(64) | Yes | — |
| supersedes_id | UUID | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `contract_id` -> `revenue_contracts.id`
- `run_id` -> `revenue_runs.id`
- `supersedes_id` -> `revenue_adjustments.id`

**Indexes:**
- `idx_revenue_adjustments_contract` (tenant_id, contract_id)
- `idx_revenue_adjustments_run` (tenant_id, run_id, effective_date)
- `ix_revenue_adjustments_tenant_id` (tenant_id)

---

### revenue_contract_line_items

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| contract_id | UUID | No | — |
| obligation_id | UUID | Yes | — |
| line_code | VARCHAR(128) | No | — |
| line_amount | NUMERIC(20, 6) | No | — |
| line_currency | VARCHAR(3) | No | — |
| milestone_reference | VARCHAR(255) | Yes | — |
| usage_reference | VARCHAR(255) | Yes | — |
| source_contract_reference | VARCHAR(255) | No | — |
| parent_reference_id | UUID | Yes | — |
| source_reference_id | UUID | Yes | — |
| correlation_id | VARCHAR(64) | Yes | — |
| supersedes_id | UUID | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `contract_id` -> `revenue_contracts.id`
- `obligation_id` -> `revenue_performance_obligations.id`
- `supersedes_id` -> `revenue_contract_line_items.id`

**Indexes:**
- `idx_revenue_line_items_contract` (tenant_id, contract_id)
- `idx_revenue_line_items_obligation` (tenant_id, obligation_id)
- `ix_revenue_contract_line_items_tenant_id` (tenant_id)

---

### revenue_contracts

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| contract_number | VARCHAR(128) | No | — |
| entity_id | UUID | Yes | — |
| customer_id | VARCHAR(128) | No | — |
| contract_currency | VARCHAR(3) | No | — |
| contract_start_date | DATE | No | — |
| contract_end_date | DATE | No | — |
| total_contract_value | NUMERIC(20, 6) | No | — |
| source_contract_reference | VARCHAR(255) | No | — |
| policy_code | VARCHAR(64) | No | — |
| policy_version | VARCHAR(64) | No | — |
| correlation_id | VARCHAR(64) | Yes | — |
| supersedes_id | UUID | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `entity_id` -> `cp_entities.id`
- `supersedes_id` -> `revenue_contracts.id`

**Indexes:**
- `idx_revenue_contracts_tenant_number` (tenant_id, contract_number, created_at)
- `idx_revenue_contracts_tenant_source` (tenant_id, source_contract_reference)
- `ix_revenue_contracts_entity_id` (entity_id)
- `ix_revenue_contracts_tenant_id` (tenant_id)

---

### revenue_journal_entries

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| run_id | UUID | No | — |
| contract_id | UUID | No | — |
| obligation_id | UUID | No | — |
| schedule_id | UUID | No | — |
| journal_reference | VARCHAR(128) | No | — |
| entry_date | DATE | No | — |
| debit_account | VARCHAR(64) | No | — |
| credit_account | VARCHAR(64) | No | — |
| amount_reporting_currency | NUMERIC(20, 6) | No | — |
| source_contract_reference | VARCHAR(255) | No | — |
| parent_reference_id | UUID | Yes | — |
| source_reference_id | UUID | Yes | — |
| correlation_id | VARCHAR(64) | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `contract_id` -> `revenue_contracts.id`
- `obligation_id` -> `revenue_performance_obligations.id`
- `run_id` -> `revenue_runs.id`
- `schedule_id` -> `revenue_schedules.id`

**Indexes:**
- `idx_revenue_journal_contract` (tenant_id, contract_id)
- `idx_revenue_journal_run` (tenant_id, run_id, entry_date)
- `ix_revenue_journal_entries_tenant_id` (tenant_id)

---

### revenue_performance_obligations

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| contract_id | UUID | No | — |
| obligation_code | VARCHAR(128) | No | — |
| description | TEXT | No | — |
| standalone_selling_price | NUMERIC(20, 6) | No | — |
| allocation_basis | VARCHAR(64) | No | — |
| recognition_method | VARCHAR(64) | No | — |
| source_contract_reference | VARCHAR(255) | No | — |
| parent_reference_id | UUID | Yes | — |
| source_reference_id | UUID | Yes | — |
| correlation_id | VARCHAR(64) | Yes | — |
| supersedes_id | UUID | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `contract_id` -> `revenue_contracts.id`
- `supersedes_id` -> `revenue_performance_obligations.id`

**Indexes:**
- `idx_revenue_obligations_contract` (tenant_id, contract_id)
- `idx_revenue_obligations_method` (tenant_id, recognition_method)
- `ix_revenue_performance_obligations_tenant_id` (tenant_id)

---

### revenue_run_events

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| run_id | UUID | No | — |
| event_seq | INTEGER | No | — |
| event_type | VARCHAR(64) | No | — |
| event_time | DATETIME | No | — |
| idempotency_key | VARCHAR(128) | No | — |
| metadata_json | JSONB | Yes | — |
| correlation_id | VARCHAR(64) | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `run_id` -> `revenue_runs.id`

**Indexes:**
- `idx_revenue_run_events_tenant_run` (tenant_id, run_id, event_seq)
- `ix_revenue_run_events_tenant_id` (tenant_id)

---

### revenue_runs

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| request_signature | VARCHAR(64) | No | — |
| initiated_by | UUID | No | — |
| configuration_json | JSONB | No | — |
| workflow_id | VARCHAR(128) | No | — |
| correlation_id | VARCHAR(64) | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Indexes:**
- `idx_revenue_runs_tenant_created` (tenant_id, created_at)
- `ix_revenue_runs_tenant_id` (tenant_id)

---

### revenue_schedules

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| run_id | UUID | No | — |
| contract_id | UUID | No | — |
| obligation_id | UUID | No | — |
| contract_line_item_id | UUID | No | — |
| period_seq | INTEGER | No | — |
| recognition_date | DATE | No | — |
| recognition_period_year | INTEGER | No | — |
| recognition_period_month | INTEGER | No | — |
| schedule_version_token | VARCHAR(64) | No | — |
| recognition_method | VARCHAR(64) | No | — |
| base_amount_contract_currency | NUMERIC(20, 6) | No | — |
| fx_rate_used | NUMERIC(20, 6) | No | — |
| recognized_amount_reporting_currency | NUMERIC(20, 6) | No | — |
| cumulative_recognized_reporting_currency | NUMERIC(20, 6) | No | — |
| schedule_status | VARCHAR(32) | No | — |
| source_contract_reference | VARCHAR(255) | No | — |
| parent_reference_id | UUID | Yes | — |
| source_reference_id | UUID | Yes | — |
| correlation_id | VARCHAR(64) | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `contract_id` -> `revenue_contracts.id`
- `contract_line_item_id` -> `revenue_contract_line_items.id`
- `obligation_id` -> `revenue_performance_obligations.id`
- `run_id` -> `revenue_runs.id`

**Indexes:**
- `idx_revenue_schedules_contract` (tenant_id, contract_id)
- `idx_revenue_schedules_run` (tenant_id, run_id, recognition_date)
- `ix_revenue_schedules_tenant_id` (tenant_id)

---

### risk_contributing_signals

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| run_id | UUID | No | — |
| risk_result_id | UUID | No | — |
| signal_type | VARCHAR(64) | No | — |
| signal_ref | TEXT | No | — |
| contribution_weight | NUMERIC(12, 6) | No | — |
| contribution_score | NUMERIC(12, 6) | No | — |
| signal_payload_json | JSONB | No | <function dict at 0x00000272FA3EA840> |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `risk_result_id` -> `risk_results.id`
- `run_id` -> `risk_runs.id`

**Indexes:**
- `idx_risk_contributing_signals_run` (tenant_id, run_id, risk_result_id, id)
- `ix_risk_contributing_signals_tenant_id` (tenant_id)

---

### risk_definition_dependencies

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| risk_definition_id | UUID | No | — |
| dependency_type | VARCHAR(64) | No | — |
| depends_on_risk_definition_id | UUID | Yes | — |
| signal_reference_code | VARCHAR(128) | Yes | — |
| propagation_factor | NUMERIC(12, 6) | No | 1 |
| amplification_rule_json | JSONB | No | <function dict at 0x00000272FA366CA0> |
| attenuation_rule_json | JSONB | No | <function dict at 0x00000272FA366F20> |
| cap_limit | NUMERIC(12, 6) | No | 1 |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `depends_on_risk_definition_id` -> `risk_definitions.id`
- `risk_definition_id` -> `risk_definitions.id`

**Indexes:**
- `idx_risk_definition_dependencies_depends_on` (tenant_id, depends_on_risk_definition_id)
- `idx_risk_definition_dependencies_risk` (tenant_id, risk_definition_id, dependency_type, id)
- `ix_risk_definition_dependencies_tenant_id` (tenant_id)

---

### risk_definitions

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| organisation_id | UUID | No | — |
| risk_code | VARCHAR(128) | No | — |
| risk_name | VARCHAR(255) | No | — |
| risk_domain | VARCHAR(64) | No | — |
| signal_selector_json | JSONB | No | <function dict at 0x00000272FA365580> |
| definition_json | JSONB | No | <function dict at 0x00000272FA365620> |
| version_token | VARCHAR(64) | No | — |
| effective_from | DATE | No | — |
| effective_to | DATE | Yes | — |
| supersedes_id | UUID | Yes | — |
| status | VARCHAR(32) | No | candidate |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `supersedes_id` -> `risk_definitions.id`

**Indexes:**
- `idx_risk_definitions_lookup` (tenant_id, organisation_id, risk_code, effective_from, created_at)
- `ix_risk_definitions_tenant_id` (tenant_id)
- `uq_risk_definitions_one_active` (tenant_id, organisation_id, risk_code)

---

### risk_evidence_links

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| run_id | UUID | No | — |
| risk_result_id | UUID | No | — |
| evidence_type | VARCHAR(64) | No | — |
| evidence_ref | TEXT | No | — |
| evidence_label | VARCHAR(255) | No | — |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `risk_result_id` -> `risk_results.id`
- `run_id` -> `risk_runs.id`

**Indexes:**
- `idx_risk_evidence_links_result` (tenant_id, run_id, risk_result_id)
- `idx_risk_evidence_links_run` (tenant_id, run_id, created_at)
- `ix_risk_evidence_links_tenant_id` (tenant_id)

---

### risk_materiality_rules

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| organisation_id | UUID | No | — |
| rule_code | VARCHAR(128) | No | — |
| rule_name | VARCHAR(255) | No | — |
| threshold_json | JSONB | No | <function dict at 0x00000272FA3A1BC0> |
| severity_mapping_json | JSONB | No | <function dict at 0x00000272FA3A09A0> |
| propagation_behavior_json | JSONB | No | <function dict at 0x00000272FA3A1C60> |
| escalation_rule_json | JSONB | No | <function dict at 0x00000272FA3A1D00> |
| version_token | VARCHAR(64) | No | — |
| effective_from | DATE | No | — |
| supersedes_id | UUID | Yes | — |
| status | VARCHAR(32) | No | candidate |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `supersedes_id` -> `risk_materiality_rules.id`

**Indexes:**
- `idx_risk_materiality_rules_lookup` (tenant_id, organisation_id, rule_code, effective_from, created_at)
- `ix_risk_materiality_rules_tenant_id` (tenant_id)
- `uq_risk_materiality_rules_one_active` (tenant_id, organisation_id, rule_code)

---

### risk_results

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| run_id | UUID | No | — |
| line_no | INTEGER | No | — |
| risk_code | VARCHAR(128) | No | — |
| risk_name | VARCHAR(255) | No | — |
| risk_domain | VARCHAR(64) | No | — |
| risk_score | NUMERIC(12, 6) | No | — |
| severity | VARCHAR(16) | No | — |
| confidence_score | NUMERIC(12, 6) | No | — |
| materiality_flag | BOOLEAN | No | False |
| board_attention_flag | BOOLEAN | No | False |
| persistence_state | VARCHAR(32) | No | new |
| unresolved_dependency_flag | BOOLEAN | No | False |
| source_summary_json | JSONB | No | <function dict at 0x00000272FA3E9120> |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `run_id` -> `risk_runs.id`

**Indexes:**
- `idx_risk_results_domain_severity` (tenant_id, run_id, risk_domain, severity)
- `idx_risk_results_run` (tenant_id, run_id, line_no)
- `ix_risk_results_tenant_id` (tenant_id)

---

### risk_rollforward_events

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| run_id | UUID | No | — |
| risk_result_id | UUID | No | — |
| event_type | VARCHAR(64) | No | — |
| event_payload_json | JSONB | No | <function dict at 0x00000272FA3EBD80> |
| actor_user_id | UUID | No | — |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `risk_result_id` -> `risk_results.id`
- `run_id` -> `risk_runs.id`

**Indexes:**
- `idx_risk_rollforward_events_run` (tenant_id, run_id, risk_result_id, created_at)
- `ix_risk_rollforward_events_tenant_id` (tenant_id)

---

### risk_runs

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| organisation_id | UUID | No | — |
| reporting_period | DATE | No | — |
| risk_definition_version_token | VARCHAR(64) | No | — |
| propagation_version_token | VARCHAR(64) | No | — |
| weight_version_token | VARCHAR(64) | No | — |
| materiality_version_token | VARCHAR(64) | No | — |
| source_metric_run_ids_json | JSONB | No | <function list at 0x00000272FA3A3380> |
| source_variance_run_ids_json | JSONB | No | <function list at 0x00000272FA3A2200> |
| source_trend_run_ids_json | JSONB | No | <function list at 0x00000272FA3A3420> |
| source_reconciliation_session_ids_json | JSONB | No | <function list at 0x00000272FA3A34C0> |
| run_token | VARCHAR(64) | No | — |
| status | VARCHAR(32) | No | created |
| validation_summary_json | JSONB | No | <function dict at 0x00000272FA3A3560> |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Indexes:**
- `idx_risk_runs_lookup` (tenant_id, organisation_id, reporting_period, created_at)
- `idx_risk_runs_token` (tenant_id, run_token)
- `ix_risk_runs_tenant_id` (tenant_id)

---

### risk_weight_configurations

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| organisation_id | UUID | No | — |
| weight_code | VARCHAR(128) | No | — |
| risk_code | VARCHAR(128) | No | — |
| scope_type | VARCHAR(32) | No | global |
| scope_value | VARCHAR(128) | Yes | — |
| weight_value | NUMERIC(12, 6) | No | — |
| board_critical_override | BOOLEAN | No | False |
| configuration_json | JSONB | No | <function dict at 0x00000272FA3A04A0> |
| version_token | VARCHAR(64) | No | — |
| effective_from | DATE | No | — |
| supersedes_id | UUID | Yes | — |
| status | VARCHAR(32) | No | candidate |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `supersedes_id` -> `risk_weight_configurations.id`

**Indexes:**
- `idx_risk_weight_configurations_lookup` (tenant_id, organisation_id, weight_code, effective_from, created_at)
- `ix_risk_weight_configurations_tenant_id` (tenant_id)
- `uq_risk_weight_configurations_one_active` (tenant_id, organisation_id, weight_code)

---

### run_performance_metrics

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| module_code | VARCHAR(64) | No | — |
| run_id | UUID | No | — |
| query_count | INTEGER | No | 0 |
| execution_time_ms | INTEGER | No | 0 |
| dependency_depth | INTEGER | No | 0 |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Indexes:**
- `idx_run_performance_metrics_lookup` (tenant_id, module_code, run_id, created_at)
- `ix_run_performance_metrics_tenant_id` (tenant_id)

---

### run_token_diff_definitions

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| comparison_type | VARCHAR(64) | No | — |
| allowed_modules_json | JSONB | No | <function list at 0x00000272FA7F3920> |
| version_token | VARCHAR(64) | No | — |
| effective_from | DATE | No | — |
| supersedes_id | UUID | Yes | — |
| status | VARCHAR(32) | No | candidate |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `supersedes_id` -> `run_token_diff_definitions.id`

**Indexes:**
- `idx_run_token_diff_definitions_lookup` (tenant_id, comparison_type, effective_from, created_at)
- `ix_run_token_diff_definitions_tenant_id` (tenant_id)
- `uq_run_token_diff_definitions_one_active` (tenant_id, comparison_type)

---

### run_token_diff_results

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| base_run_id | UUID | No | — |
| compare_run_id | UUID | No | — |
| diff_summary_json | JSONB | No | <function dict at 0x00000272FA820C20> |
| drift_flag | BOOLEAN | No | False |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Indexes:**
- `idx_run_token_diff_results_lookup` (tenant_id, base_run_id, compare_run_id, created_at)
- `ix_run_token_diff_results_tenant_id` (tenant_id)

---

### scenario_definitions

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| scenario_set_id | UUID | No | — |
| tenant_id | UUID | No | — |
| entity_id | UUID | No | — |
| scenario_name | VARCHAR(100) | No | — |
| scenario_label | VARCHAR(200) | No | — |
| is_base_case | BOOLEAN | No | False |
| driver_overrides | JSONB | No | <function dict at 0x00000272FAD64040> |
| colour_hex | VARCHAR(7) | No | #378ADD |
| created_at | DATETIME | No | now() |
| updated_at | DATETIME | No | now() |

**Foreign keys:**
- `entity_id` -> `cp_entities.id`
- `scenario_set_id` -> `scenario_sets.id`

**Indexes:**
- `idx_scenario_definitions_tenant_entity` (tenant_id, entity_id)

---

### scenario_line_items

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: Yes

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| scenario_result_id | UUID | No | — |
| scenario_set_id | UUID | No | — |
| tenant_id | UUID | No | — |
| entity_id | UUID | No | — |
| period | VARCHAR(7) | No | — |
| mis_line_item | VARCHAR(300) | No | — |
| mis_category | VARCHAR(100) | No | — |
| amount | NUMERIC(20, 2) | No | — |
| created_at | DATETIME | No | now() |

**Foreign keys:**
- `entity_id` -> `cp_entities.id`
- `scenario_result_id` -> `scenario_results.id`
- `scenario_set_id` -> `scenario_sets.id`

**Indexes:**
- `idx_scenario_line_items_result_period_line` (scenario_result_id, period, mis_line_item)
- `idx_scenario_line_items_tenant_entity` (tenant_id, entity_id)

---

### scenario_results

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: Yes

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| scenario_set_id | UUID | No | — |
| scenario_definition_id | UUID | No | — |
| tenant_id | UUID | No | — |
| entity_id | UUID | No | — |
| computed_at | DATETIME | No | now() |

**Foreign keys:**
- `entity_id` -> `cp_entities.id`
- `scenario_definition_id` -> `scenario_definitions.id`
- `scenario_set_id` -> `scenario_sets.id`

**Indexes:**
- `idx_scenario_results_tenant_entity` (tenant_id, entity_id)

---

### scenario_sets

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: Yes

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| entity_id | UUID | No | — |
| name | VARCHAR(200) | No | — |
| base_period | VARCHAR(7) | No | — |
| horizon_months | INTEGER | No | 12 |
| base_forecast_run_id | UUID | Yes | — |
| created_by | UUID | No | — |
| created_at | DATETIME | No | now() |

**Foreign keys:**
- `base_forecast_run_id` -> `forecast_runs.id`
- `entity_id` -> `cp_entities.id`

**Indexes:**
- `idx_scenario_sets_tenant_entity` (tenant_id, entity_id)

---

### search_index_entries

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| entity_type | VARCHAR(50) | No | — |
| entity_id | UUID | No | — |
| title | VARCHAR(500) | No | — |
| subtitle | VARCHAR(500) | Yes | — |
| body | TEXT | Yes | — |
| tags | JSONB | No | <function list at 0x00000272FAF78D60> |
| url | TEXT | No | — |
| metadata | JSONB | No | <function dict at 0x00000272FAF78E00> |
| indexed_at | DATETIME | No | now() |
| is_active | BOOLEAN | No | True |

**Indexes:**
- `idx_search_index_entries_tenant_type_active` (tenant_id, entity_type, is_active)

---

### secret_rotation_log

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| secret_type | VARCHAR(50) | No | — |
| resource_id | UUID | Yes | — |
| resource_type | VARCHAR(50) | Yes | — |
| rotated_by | UUID | Yes | — |
| rotation_method | VARCHAR(20) | No | manual |
| status | VARCHAR(20) | No | — |
| failure_reason | TEXT | Yes | — |
| previous_secret_hint | VARCHAR(8) | Yes | — |
| new_secret_hint | VARCHAR(8) | Yes | — |
| initiated_at | DATETIME | No | now() |
| completed_at | DATETIME | Yes | — |
| created_at | DATETIME | No | now() |

**Indexes:**
- `idx_secret_rotation_log_tenant_type_initiated_desc` (tenant_id, secret_type)

---

### statutory_filings

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| entity_id | UUID | No | — |
| form_number | VARCHAR(20) | No | — |
| form_description | VARCHAR(300) | No | — |
| due_date | DATE | No | — |
| filed_date | DATE | Yes | — |
| status | VARCHAR(20) | No | pending |
| filing_reference | VARCHAR(100) | Yes | — |
| penalty_amount | NUMERIC(20, 2) | No | 0.00 |
| notes | TEXT | Yes | — |
| created_at | DATETIME | No | now() |

**Foreign keys:**
- `entity_id` -> `cp_entities.id`

**Indexes:**
- `idx_statutory_filings_tenant_due_status` (tenant_id, due_date, status)
- `idx_statutory_filings_tenant_entity` (tenant_id, entity_id)

---

### statutory_register_entries

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| entity_id | UUID | No | — |
| register_type | VARCHAR(50) | No | — |
| entry_date | DATE | No | — |
| entry_description | TEXT | No | — |
| folio_number | VARCHAR(100) | Yes | — |
| amount | NUMERIC(20, 2) | Yes | — |
| currency | VARCHAR(3) | Yes | — |
| reference_document | TEXT | Yes | — |
| is_active | BOOLEAN | No | True |
| created_at | DATETIME | No | now() |
| updated_at | DATETIME | No | now() |

**Foreign keys:**
- `entity_id` -> `cp_entities.id`

**Indexes:**
- `idx_statutory_register_entries_tenant_entity` (tenant_id, entity_id)
- `idx_statutory_register_entries_tenant_type` (tenant_id, register_type, entry_date)

---

### subscription_events

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| subscription_id | UUID | No | — |
| event_type | VARCHAR(64) | No | — |
| from_plan_id | UUID | Yes | — |
| to_plan_id | UUID | Yes | — |
| from_status | VARCHAR(32) | Yes | — |
| to_status | VARCHAR(32) | No | — |
| provider_event_id | VARCHAR(255) | Yes | — |
| metadata | JSONB | No | <function dict at 0x00000272FAAB4540> |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `subscription_id` -> `tenant_subscriptions.id`

**Indexes:**
- `idx_subscription_events_subscription` (tenant_id, subscription_id, created_at)
- `ix_subscription_events_tenant_id` (tenant_id)

---

### task_registry

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: No
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| task_name | VARCHAR(200) | No | — |
| module_name | VARCHAR(100) | No | — |
| queue_name | VARCHAR(50) | No | — |
| description | TEXT | Yes | — |
| avg_duration_seconds | NUMERIC(8, 2) | Yes | — |
| success_rate_7d | NUMERIC(5, 4) | Yes | — |
| last_run_at | DATETIME | Yes | — |
| last_run_status | VARCHAR(20) | Yes | — |
| is_scheduled | BOOLEAN | No | False |
| schedule_cron | VARCHAR(100) | Yes | — |
| created_at | DATETIME | No | now() |
| updated_at | DATETIME | No | now() |

**Indexes:**
- `idx_task_registry_queue_name` (queue_name)
- `idx_task_registry_task_name` (task_name)

---

### tax_positions

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| position_name | VARCHAR(200) | No | — |
| position_type | VARCHAR(30) | No | — |
| carrying_amount | NUMERIC(20, 2) | No | — |
| tax_base | NUMERIC(20, 2) | No | — |
| temporary_difference | NUMERIC(20, 2) | No | — |
| deferred_tax_impact | NUMERIC(20, 2) | No | — |
| is_asset | BOOLEAN | No | — |
| description | TEXT | Yes | — |
| created_at | DATETIME | No | now() |
| updated_at | DATETIME | No | now() |

**Indexes:**
- `idx_tax_positions_tenant_type` (tenant_id, position_type)

---

### tax_provision_runs

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| entity_id | UUID | Yes | — |
| period | VARCHAR(7) | No | — |
| fiscal_year | INTEGER | No | — |
| applicable_tax_rate | NUMERIC(5, 4) | No | — |
| accounting_profit_before_tax | NUMERIC(20, 2) | No | — |
| permanent_differences | NUMERIC(20, 2) | No | 0.00 |
| timing_differences | NUMERIC(20, 2) | No | 0.00 |
| taxable_income | NUMERIC(20, 2) | No | — |
| current_tax_expense | NUMERIC(20, 2) | No | — |
| deferred_tax_asset | NUMERIC(20, 2) | No | 0.00 |
| deferred_tax_liability | NUMERIC(20, 2) | No | 0.00 |
| net_deferred_tax | NUMERIC(20, 2) | No | — |
| total_tax_expense | NUMERIC(20, 2) | No | — |
| effective_tax_rate | NUMERIC(5, 4) | No | — |
| created_by | UUID | No | — |
| created_at | DATETIME | No | now() |

**Indexes:**
- `idx_tax_provision_runs_tenant_period` (tenant_id, period)

---

### tenant_coa_accounts

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| ledger_account_id | UUID | Yes | — |
| parent_subgroup_id | UUID | Yes | — |
| account_code | VARCHAR(50) | No | — |
| display_name | VARCHAR(300) | No | — |
| is_custom | BOOLEAN | No | False |
| is_active | BOOLEAN | No | True |
| default_cost_centre_id | UUID | Yes | — |
| default_location_id | UUID | Yes | — |
| sort_order | INTEGER | Yes | — |
| created_at | DATETIME | No | now() |
| updated_at | DATETIME | Yes | now() |

**Foreign keys:**
- `ledger_account_id` -> `coa_ledger_accounts.id`
- `parent_subgroup_id` -> `coa_account_subgroups.id`
- `tenant_id` -> `iam_tenants.id`

**Indexes:**
- `idx_tenant_coa_accounts_ledger_account_id` (ledger_account_id)
- `idx_tenant_coa_accounts_tenant_id` (tenant_id)

---

### tenant_subscriptions

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| plan_id | UUID | No | — |
| provider | VARCHAR(32) | No | — |
| provider_subscription_id | VARCHAR(255) | No | — |
| provider_customer_id | VARCHAR(255) | No | — |
| status | VARCHAR(32) | No | — |
| billing_cycle | VARCHAR(16) | No | — |
| current_period_start | DATE | No | — |
| current_period_end | DATE | No | — |
| trial_start | DATE | Yes | — |
| trial_end | DATE | Yes | — |
| start_date | DATE | Yes | — |
| end_date | DATE | Yes | — |
| trial_end_date | DATE | Yes | — |
| auto_renew | BOOLEAN | No | True |
| cancelled_at | DATETIME | Yes | — |
| cancel_at_period_end | BOOLEAN | No | False |
| onboarding_mode | VARCHAR(32) | No | — |
| billing_country | VARCHAR(2) | No | — |
| billing_currency | VARCHAR(3) | No | — |
| metadata | JSONB | No | <function dict at 0x00000272FAAB4180> |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `plan_id` -> `billing_plans.id`

**Indexes:**
- `idx_tenant_subscriptions_current` (tenant_id, status, current_period_end, created_at)
- `ix_tenant_subscriptions_tenant_id` (tenant_id)

---

### tenant_token_budgets

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| tenant_id | UUID | No | — |
| monthly_token_limit | BIGINT | No | 1000000 |
| monthly_cost_limit_usd | NUMERIC(10, 2) | No | 50.00 |
| current_month_tokens | BIGINT | No | 0 |
| current_month_cost_usd | NUMERIC(10, 6) | No | 0 |
| budget_period_start | DATE | No | — |
| alert_threshold_pct | INTEGER | No | 80 |
| hard_stop_on_budget | BOOLEAN | No | false |
| created_at | DATETIME | No | now() |
| updated_at | DATETIME | No | now() |

**Foreign keys:**
- `tenant_id` -> `iam_tenants.id`

**Indexes:**
- `idx_tenant_token_budgets_period` (budget_period_start)

---

### tp_configs

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| consolidated_revenue_threshold | NUMERIC(20, 2) | No | 50000000.00 |
| international_transactions_exist | BOOLEAN | No | False |
| specified_domestic_transactions_exist | BOOLEAN | No | False |
| applicable_methods | JSONB | No | <function list at 0x00000272FD479BC0> |
| created_at | DATETIME | No | now() |
| updated_at | DATETIME | No | now() |

---

### transfer_pricing_docs

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| fiscal_year | INTEGER | No | — |
| document_type | VARCHAR(20) | No | — |
| version | INTEGER | No | 1 |
| content | JSONB | No | <function dict at 0x00000272FD47BB00> |
| ai_narrative | TEXT | Yes | — |
| status | VARCHAR(20) | No | draft |
| filed_at | DATETIME | Yes | — |
| created_by | UUID | No | — |
| created_at | DATETIME | No | now() |

**Indexes:**
- `idx_transfer_pricing_docs_tenant_year_type` (tenant_id, fiscal_year, document_type)

---

### trend_definitions

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| organisation_id | UUID | No | — |
| definition_code | VARCHAR(128) | No | — |
| definition_name | VARCHAR(255) | No | — |
| metric_code | VARCHAR(128) | No | — |
| trend_type | VARCHAR(64) | No | — |
| window_size | INTEGER | No | — |
| configuration_json | JSONB | No | <function dict at 0x00000272FA2CF1A0> |
| version_token | VARCHAR(64) | No | — |
| effective_from | DATE | No | — |
| supersedes_id | UUID | Yes | — |
| status | VARCHAR(32) | No | candidate |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `supersedes_id` -> `trend_definitions.id`

**Indexes:**
- `idx_trend_definitions_lookup` (tenant_id, organisation_id, definition_code, effective_from, created_at)
- `ix_trend_definitions_tenant_id` (tenant_id)
- `uq_trend_definitions_one_active` (tenant_id, organisation_id, definition_code)

---

### trend_results

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| run_id | UUID | No | — |
| line_no | INTEGER | No | — |
| metric_code | VARCHAR(128) | No | — |
| trend_type | VARCHAR(64) | No | — |
| window_size | INTEGER | No | — |
| trend_value | NUMERIC(20, 6) | No | — |
| trend_direction | VARCHAR(16) | No | — |
| source_summary_json | JSONB | No | <function dict at 0x00000272FA336D40> |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `run_id` -> `metric_runs.id`

**Indexes:**
- `idx_trend_results_metric` (tenant_id, run_id, metric_code)
- `idx_trend_results_run` (tenant_id, run_id, line_no)
- `ix_trend_results_tenant_id` (tenant_id)

---

### trial_balance_rows

- **Description**: Trial Balance row — INSERT ONLY.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| entity_id | UUID | Yes | — |
| period_year | INTEGER | No | — |
| period_month | INTEGER | No | — |
| entity_name | VARCHAR(255) | No | — |
| account_code | VARCHAR(50) | No | — |
| account_name | VARCHAR(255) | No | — |
| opening_balance | NUMERIC(20, 6) | No | 0 |
| period_debit | NUMERIC(20, 6) | No | 0 |
| period_credit | NUMERIC(20, 6) | No | 0 |
| closing_balance | NUMERIC(20, 6) | No | — |
| currency | VARCHAR(3) | No | USD |
| uploaded_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `entity_id` -> `cp_entities.id`

**Indexes:**
- `idx_tb_rows_account` (tenant_id, account_code)
- `idx_tb_rows_tenant_period` (tenant_id, period_year, period_month)
- `ix_trial_balance_rows_entity_id` (entity_id)
- `ix_trial_balance_rows_tenant_id` (tenant_id)

---

### user_pii_keys

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| user_id | UUID | No | — |
| encrypted_key | TEXT | Yes | — |
| created_at | DATETIME | No | now() |
| erased_at | DATETIME | Yes | — |

**Foreign keys:**
- `user_id` -> `iam_users.id`

**Indexes:**
- `idx_user_pii_keys_tenant_user` (tenant_id, user_id)

---

### variance_definitions

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| organisation_id | UUID | No | — |
| definition_code | VARCHAR(128) | No | — |
| definition_name | VARCHAR(255) | No | — |
| metric_code | VARCHAR(128) | No | — |
| comparison_type | VARCHAR(64) | No | — |
| configuration_json | JSONB | No | <function dict at 0x00000272FA2CCB80> |
| version_token | VARCHAR(64) | No | — |
| effective_from | DATE | No | — |
| supersedes_id | UUID | Yes | — |
| status | VARCHAR(32) | No | candidate |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `supersedes_id` -> `variance_definitions.id`

**Indexes:**
- `idx_variance_definitions_lookup` (tenant_id, organisation_id, definition_code, effective_from, created_at)
- `ix_variance_definitions_tenant_id` (tenant_id)
- `uq_variance_definitions_one_active` (tenant_id, organisation_id, definition_code)

---

### variance_results

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| run_id | UUID | No | — |
| line_no | INTEGER | No | — |
| metric_code | VARCHAR(128) | No | — |
| comparison_type | VARCHAR(64) | No | — |
| base_period | DATE | Yes | — |
| current_value | NUMERIC(20, 6) | No | — |
| baseline_value | NUMERIC(20, 6) | No | — |
| variance_abs | NUMERIC(20, 6) | No | — |
| variance_pct | NUMERIC(20, 6) | No | — |
| variance_bps | NUMERIC(20, 6) | No | — |
| days_change | NUMERIC(20, 6) | No | — |
| favorable_status | VARCHAR(16) | No | neutral |
| materiality_flag | BOOLEAN | No | False |
| explanation_hint | TEXT | Yes | — |
| created_by | UUID | No | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `run_id` -> `metric_runs.id`

**Indexes:**
- `idx_variance_results_metric_comparison` (tenant_id, run_id, metric_code, comparison_type)
- `idx_variance_results_run` (tenant_id, run_id, line_no)
- `ix_variance_results_tenant_id` (tenant_id)

---

### vendor_portal_submissions

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| entity_id | UUID | Yes | — |
| vendor_id | UUID | Yes | — |
| reference_id | VARCHAR(64) | No | — |
| submitter_email | VARCHAR(256) | No | — |
| submitter_name | VARCHAR(256) | Yes | — |
| vendor_email_verified | BOOLEAN | No | False |
| r2_key | VARCHAR(512) | Yes | — |
| filename | VARCHAR(256) | Yes | — |
| mime_type | VARCHAR(128) | Yes | — |
| file_size_bytes | BIGINT | Yes | — |
| sha256_hash | VARCHAR(64) | Yes | — |
| scan_status | VARCHAR(16) | Yes | — |
| status | VARCHAR(32) | No | RECEIVED |
| processed_at | DATETIME | Yes | — |
| rejection_reason | TEXT | Yes | — |
| jv_id | UUID | Yes | — |
| submitted_at | DATETIME | No | now() |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `entity_id` -> `cp_entities.id`
- `jv_id` -> `accounting_jv_aggregates.id`
- `vendor_id` -> `accounting_vendors.id`

**Indexes:**
- `ix_vendor_portal_submissions_status` (tenant_id, status)
- `ix_vendor_portal_submissions_submitter_email` (tenant_id, submitter_email)
- `ix_vendor_portal_submissions_tenant_id` (tenant_id)
- `ix_vendor_portal_submissions_vendor_id` (vendor_id)

---

### wc_snapshots

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| period | VARCHAR(7) | No | — |
| entity_id | UUID | Yes | — |
| snapshot_date | DATE | No | — |
| ar_total | NUMERIC(20, 2) | No | — |
| ar_current | NUMERIC(20, 2) | No | — |
| ar_30 | NUMERIC(20, 2) | No | — |
| ar_60 | NUMERIC(20, 2) | No | — |
| ar_90 | NUMERIC(20, 2) | No | — |
| dso_days | NUMERIC(8, 2) | No | — |
| ap_total | NUMERIC(20, 2) | No | — |
| ap_current | NUMERIC(20, 2) | No | — |
| ap_30 | NUMERIC(20, 2) | No | — |
| ap_60 | NUMERIC(20, 2) | No | — |
| ap_90 | NUMERIC(20, 2) | No | — |
| dpo_days | NUMERIC(8, 2) | No | — |
| inventory_days | NUMERIC(8, 2) | No | 0 |
| ccc_days | NUMERIC(8, 2) | No | — |
| net_working_capital | NUMERIC(20, 2) | No | — |
| current_ratio | NUMERIC(8, 4) | No | — |
| quick_ratio | NUMERIC(8, 4) | No | — |
| created_at | DATETIME | No | now() |

**Indexes:**
- `idx_wc2_snapshots_tenant_period` (tenant_id, period)

---

### webhook_events

- **Description**: Abstract base for ALL financial tables.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| provider | VARCHAR(32) | No | — |
| provider_event_id | VARCHAR(255) | No | — |
| event_type | VARCHAR(128) | No | — |
| payload | JSONB | No | <function dict at 0x00000272FAAE2FC0> |
| processed | BOOLEAN | No | False |
| processed_at | DATETIME | Yes | — |
| processing_error | TEXT | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Indexes:**
- `idx_webhook_events_tenant` (tenant_id, provider, processed, created_at)
- `ix_webhook_events_tenant_id` (tenant_id)

---

### white_label_audit_log

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| changed_by | UUID | No | — |
| field_changed | VARCHAR(100) | No | — |
| old_value | TEXT | Yes | — |
| new_value | TEXT | Yes | — |
| created_at | DATETIME | No | now() |

**Foreign keys:**
- `changed_by` -> `iam_users.id`

**Indexes:**
- `idx_white_label_audit_log_tenant_created` (tenant_id, created_at)

---

### white_label_configs

- **Description**: Base class used for declarative class definitions.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | UUID | No | gen_random_uuid() |
| tenant_id | UUID | No | — |
| is_enabled | BOOLEAN | No | False |
| custom_domain | VARCHAR(300) | Yes | — |
| domain_verified | BOOLEAN | No | False |
| domain_verification_token | VARCHAR(100) | Yes | — |
| brand_name | VARCHAR(200) | Yes | — |
| logo_url | TEXT | Yes | — |
| favicon_url | TEXT | Yes | — |
| primary_colour | VARCHAR(7) | Yes | — |
| secondary_colour | VARCHAR(7) | Yes | — |
| font_family | VARCHAR(100) | Yes | — |
| hide_powered_by | BOOLEAN | No | False |
| custom_css | TEXT | Yes | — |
| support_email | VARCHAR(300) | Yes | — |
| support_url | TEXT | Yes | — |
| created_at | DATETIME | No | now() |
| updated_at | DATETIME | No | now() |

**Foreign keys:**
- `tenant_id` -> `iam_tenants.id`

**Indexes:**
- `idx_white_label_configs_custom_domain_unique` (custom_domain)

---

### working_capital_snapshots

- **Description**: Working capital point-in-time snapshot — INSERT ONLY.
- **RLS enabled**: Yes
- **Append-only**: No

| Column | Type | Nullable | Default |
|---|---|---|---|
| period_year | INTEGER | No | — |
| period_month | INTEGER | No | — |
| entity_id | UUID | Yes | — |
| entity_name | VARCHAR(255) | No | — |
| currency | VARCHAR(3) | No | USD |
| cash_and_equivalents | NUMERIC(20, 6) | No | 0 |
| accounts_receivable | NUMERIC(20, 6) | No | 0 |
| inventory | NUMERIC(20, 6) | No | 0 |
| prepaid_expenses | NUMERIC(20, 6) | No | 0 |
| other_current_assets | NUMERIC(20, 6) | No | 0 |
| total_current_assets | NUMERIC(20, 6) | No | — |
| accounts_payable | NUMERIC(20, 6) | No | 0 |
| accrued_liabilities | NUMERIC(20, 6) | No | 0 |
| short_term_debt | NUMERIC(20, 6) | No | 0 |
| other_current_liabilities | NUMERIC(20, 6) | No | 0 |
| total_current_liabilities | NUMERIC(20, 6) | No | — |
| working_capital | NUMERIC(20, 6) | No | — |
| current_ratio | NUMERIC(10, 4) | No | — |
| quick_ratio | NUMERIC(10, 4) | No | — |
| cash_ratio | NUMERIC(10, 4) | No | — |
| created_by | UUID | No | — |
| created_by_intent_id | UUID | Yes | — |
| recorded_by_job_id | UUID | Yes | — |
| notes | TEXT | Yes | — |
| tenant_id | UUID | No | — |
| chain_hash | VARCHAR(64) | No | — |
| previous_hash | VARCHAR(64) | No | — |
| id | UUID | No | <function uuid4 at 0x00000272F9783E20> |
| created_at | DATETIME | No | <function utc_now at 0x00000272F9783EC0> |

**Foreign keys:**
- `entity_id` -> `cp_entities.id`

**Indexes:**
- `idx_wc_snapshots_entity` (tenant_id, entity_name)
- `idx_wc_snapshots_tenant_period` (tenant_id, period_year, period_month)
- `ix_working_capital_snapshots_entity_id` (entity_id)
- `ix_working_capital_snapshots_tenant_id` (tenant_id)

---

