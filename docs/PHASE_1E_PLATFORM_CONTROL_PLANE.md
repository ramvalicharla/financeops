# Phase 1E Platform Control Plane

## Section 1 - Bounded Context Definition

### 1.1 Purpose
The Phase 1E Platform Control Plane is the governance and execution-authorization layer for the FinanceOps platform. It owns tenant setup, organizational structure, module entitlement, RBAC resolution, approval routing, quota enforcement, isolation routing, and feature rollout controls.

### 1.2 Explicit Separation from Finance Engines
The control plane is a separate bounded context from finance engines (Revenue, Lease, Prepaid, FAR, Consolidation, FX).

Control plane responsibilities:
- Who is allowed to execute a finance action.
- Whether a finance module is enabled for a tenant.
- Whether approvals are complete for the requested action.
- Whether tenant quotas and isolation policy allow execution.

Finance engine responsibilities:
- Deterministic accounting computations.
- Engine-specific schedule generation.
- Engine-specific journal preview math.

Hard separation rules:
- Finance engines MUST NOT own package enablement, RBAC policy, quotas, or workflow approval state.
- Control plane MUST NOT compute accounting math.
- Cross-context communication occurs via explicit API/service contracts only.

### 1.3 Enforcement-Before-Execution Invariant
Every finance-impacting operation SHALL pass control-plane checks before any domain write or workflow start.

Invariant:
1. Validate tenant state.
2. Validate module entitlement.
3. Resolve user permissions.
4. Resolve workflow and approval eligibility.
5. Validate quota budget.
6. Resolve isolation route.
7. Only then invoke finance engine command.

If any check fails, execution is denied. No engine side effects are allowed before denial.

### 1.4 Interception Model
Control-plane interception applies at all execution entry points:
- Sync API endpoints.
- Async job submission endpoints.
- Temporal workflow start APIs.
- Internal service-to-service command gateways.

A single control-plane gate interface SHALL be called by all engine entry points:
- `ControlPlaneAuthorizer.authorize(command_context)`

Authorization result:
- `allow`: execution may continue.
- `deny`: return explicit reason code.
- `defer`: queue for approval or quota window.

## Section 2 - Core Hierarchy Model

Hierarchy and membership tables in this section represent identity and structural membership only.
Authorization semantics are out of scope for these tables and are owned only by Section 4 RBAC tables.
All membership tables in this section are tenant-scoped and RLS-protected.

### 2.1 Tables

#### 2.1.1 `cp_users`
Purpose: global identity projection for platform users.

Columns:
- `id` UUID PK
- `tenant_id` UUID NOT NULL
- `email` TEXT NOT NULL
- `display_name` TEXT NOT NULL
- `status` TEXT NOT NULL CHECK (`status IN ('active','suspended','deactivated')`)
- `is_service_account` BOOLEAN NOT NULL DEFAULT FALSE
- `correlation_id` UUID NOT NULL
- `created_at` TIMESTAMPTZ NOT NULL
- `deactivated_at` TIMESTAMPTZ NULL

Constraints:
- UNIQUE (`tenant_id`, `email`)

Soft-deactivation rule:
- status transition is recorded via append-only identity lifecycle events.
- current status is a projection derived from latest lifecycle event.

#### 2.1.2 `cp_organisations`
Purpose: tenant organization nodes (parent-child hierarchy).

Columns:
- `id` UUID PK
- `tenant_id` UUID NOT NULL
- `organisation_code` TEXT NOT NULL
- `organisation_name` TEXT NOT NULL
- `parent_organisation_id` UUID NULL FK -> `cp_organisations.id`
- `is_active` BOOLEAN NOT NULL DEFAULT TRUE
- `correlation_id` UUID NOT NULL
- `created_at` TIMESTAMPTZ NOT NULL
- `supersedes_id` UUID NULL FK -> `cp_organisations.id`

Constraints:
- UNIQUE (`tenant_id`, `organisation_code`, `created_at`)

#### 2.1.3 `cp_groups`
Purpose: optional grouping of entities (regional cluster, business unit, reporting bundle).

Columns:
- `id` UUID PK
- `tenant_id` UUID NOT NULL
- `group_code` TEXT NOT NULL
- `group_name` TEXT NOT NULL
- `organisation_id` UUID NOT NULL FK -> `cp_organisations.id`
- `is_active` BOOLEAN NOT NULL DEFAULT TRUE
- `correlation_id` UUID NOT NULL
- `created_at` TIMESTAMPTZ NOT NULL

Constraints:
- UNIQUE (`tenant_id`, `group_code`)

#### 2.1.4 `cp_entities`
Purpose: legal entities under tenant governance.

Columns:
- `id` UUID PK
- `tenant_id` UUID NOT NULL
- `entity_code` TEXT NOT NULL
- `entity_name` TEXT NOT NULL
- `organisation_id` UUID NOT NULL FK -> `cp_organisations.id`
- `group_id` UUID NULL FK -> `cp_groups.id`
- `base_currency` CHAR(3) NOT NULL
- `country_code` CHAR(2) NOT NULL
- `status` TEXT NOT NULL CHECK (`status IN ('active','inactive','deactivated')`)
- `correlation_id` UUID NOT NULL
- `created_at` TIMESTAMPTZ NOT NULL
- `deactivated_at` TIMESTAMPTZ NULL

Constraints:
- UNIQUE (`tenant_id`, `entity_code`)

#### 2.1.5 `cp_user_organisation_map`
Purpose: map users to organizations for membership scope only.

Columns:
- `id` UUID PK
- `tenant_id` UUID NOT NULL
- `user_id` UUID NOT NULL FK -> `cp_users.id`
- `organisation_id` UUID NOT NULL FK -> `cp_organisations.id`
- `is_primary` BOOLEAN NOT NULL DEFAULT FALSE
- `is_active` BOOLEAN NOT NULL DEFAULT TRUE
- `effective_from` TIMESTAMPTZ NOT NULL
- `effective_to` TIMESTAMPTZ NULL
- `correlation_id` UUID NOT NULL
- `created_at` TIMESTAMPTZ NOT NULL

Constraints:
- UNIQUE (`tenant_id`, `user_id`, `organisation_id`, `effective_from`)

#### 2.1.6 `cp_user_entity_map`
Purpose: map users to specific legal entities for membership scope only.

Columns:
- `id` UUID PK
- `tenant_id` UUID NOT NULL
- `user_id` UUID NOT NULL FK -> `cp_users.id`
- `entity_id` UUID NOT NULL FK -> `cp_entities.id`
- `is_active` BOOLEAN NOT NULL DEFAULT TRUE
- `effective_from` TIMESTAMPTZ NOT NULL
- `effective_to` TIMESTAMPTZ NULL
- `correlation_id` UUID NOT NULL
- `created_at` TIMESTAMPTZ NOT NULL

Constraints:
- UNIQUE (`tenant_id`, `user_id`, `entity_id`, `effective_from`)

### 2.2 Relationship and Assignment Rules
- Many-to-many is allowed for users to organizations and entities.
- Membership mappings never grant permissions.
- Manager/reviewer/approver/admin semantics are resolved only through Section 4 RBAC role assignments.
- Effective date windows are used for temporal entitlement validity.

### 2.3 Soft-Deactivation Rules
- Users/entities/orgs/groups are not hard deleted.
- Deactivation inserts a new state/event row and sets active flag/status to inactive in current projection.
- Existing historical workflow approvals remain linked to original identity rows.

### 2.4 Tenant-Scoped RLS Rules
Every table SHALL enforce tenant isolation with policy:
- `tenant_id = current_setting('app.current_tenant_id', true)::uuid`

RLS commands:
- `ALTER TABLE ... ENABLE ROW LEVEL SECURITY`
- `ALTER TABLE ... FORCE ROW LEVEL SECURITY`

### 2.5 Identity Lifecycle Event Projection
Identity status for users/entities/orgs/groups is governed by append-only lifecycle events and projection views.

Event table contract (per identity type):
- `<identity>_id` UUID NOT NULL
- `tenant_id` UUID NOT NULL
- `event_seq` BIGINT NOT NULL
- `event_type` TEXT NOT NULL
- `event_time` TIMESTAMPTZ NOT NULL
- `idempotency_key` TEXT NOT NULL
- `metadata_json` JSONB NOT NULL
- `correlation_id` UUID NOT NULL
- `created_at` TIMESTAMPTZ NOT NULL

Constraints:
- UNIQUE (`tenant_id`, `<identity>_id`, `event_seq`)
- UNIQUE (`tenant_id`, `<identity>_id`, `event_type`, `idempotency_key`)

Projection rule:
- Current identity status is derived from highest `event_seq`.

## Section 3 - Package and Module Enablement

### 3.1 Tables

#### 3.1.1 `cp_packages`
- `id` UUID PK
- `package_code` TEXT UNIQUE NOT NULL
- `package_name` TEXT NOT NULL
- `version` TEXT NOT NULL
- `is_active` BOOLEAN NOT NULL
- `created_at` TIMESTAMPTZ NOT NULL

#### 3.1.2 `cp_tenant_package_assignments`
- `id` UUID PK
- `tenant_id` UUID NOT NULL
- `package_id` UUID NOT NULL FK -> `cp_packages.id`
- `assignment_status` TEXT NOT NULL CHECK (`assignment_status IN ('active','scheduled_upgrade','scheduled_downgrade','suspended')`)
- `effective_from` TIMESTAMPTZ NOT NULL
- `effective_to` TIMESTAMPTZ NULL
- `correlation_id` UUID NOT NULL
- `created_at` TIMESTAMPTZ NOT NULL

UNIQUE (`tenant_id`, `package_id`, `effective_from`)

#### 3.1.3 `cp_module_registry`
- `id` UUID PK
- `module_code` TEXT UNIQUE NOT NULL
- `module_name` TEXT NOT NULL
- `engine_context` TEXT NOT NULL CHECK (`engine_context IN ('revenue','lease','prepaid','far','consolidation','fx','platform')`)
- `is_financial_impacting` BOOLEAN NOT NULL
- `created_at` TIMESTAMPTZ NOT NULL

#### 3.1.4 `cp_tenant_module_enablement`
- `id` UUID PK
- `tenant_id` UUID NOT NULL
- `module_id` UUID NOT NULL FK -> `cp_module_registry.id`
- `enabled` BOOLEAN NOT NULL
- `enablement_source` TEXT NOT NULL CHECK (`enablement_source IN ('package','override','trial','support_override')`)
- `effective_from` TIMESTAMPTZ NOT NULL
- `effective_to` TIMESTAMPTZ NULL
- `correlation_id` UUID NOT NULL
- `created_at` TIMESTAMPTZ NOT NULL

UNIQUE (`tenant_id`, `module_id`, `effective_from`)

#### 3.1.5 `cp_module_feature_flags`
- `id` UUID PK
- `tenant_id` UUID NOT NULL
- `module_id` UUID NOT NULL FK -> `cp_module_registry.id`
- `flag_key` TEXT NOT NULL
- `flag_value` JSONB NOT NULL
- `rollout_mode` TEXT NOT NULL CHECK (`rollout_mode IN ('off','on','canary')`)
- `compute_enabled` BOOLEAN NOT NULL
- `write_enabled` BOOLEAN NOT NULL
- `visibility_enabled` BOOLEAN NOT NULL
- `effective_from` TIMESTAMPTZ NOT NULL
- `effective_to` TIMESTAMPTZ NULL
- `correlation_id` UUID NOT NULL
- `created_at` TIMESTAMPTZ NOT NULL

UNIQUE (`tenant_id`, `module_id`, `flag_key`, `effective_from`)

### 3.2 Enablement Rules
- Finance engine command MUST fail with `MODULE_DISABLED` if module enablement is false for tenant and time window.
- Package assignment updates do not mutate history; they append new effective rows.
- Module enablement is evaluated at request-time and workflow-activity-time.

### 3.3 Package Upgrade/Downgrade Policy
- Upgrade: append scheduled assignment row with future `effective_from`.
- Downgrade: append scheduled downgrade row; preserve existing completed workflow access.
- Active workflows started before downgrade continue if grandfather policy allows; otherwise controlled cancellation policy applies.

### 3.4 Migration Impact Rules
- Schema migrations are independent from enablement status.
- Runtime module gate decides execution availability.
- Disabling module does not drop data; it blocks new execution.

## Section 4 - RBAC Model

### 4.0 Source-of-Truth Boundary
- Section 4 RBAC tables are the only authorization source of truth.
- Section 2 membership tables are identity scope inputs only and never grant permissions.
- Authorization decisions are computed exclusively from `cp_roles`, `cp_permissions`, `cp_role_permissions`, and `cp_user_roles`.

### 4.1 Core RBAC Tables

#### 4.1.1 `cp_roles`
- `id` UUID PK
- `tenant_id` UUID NOT NULL
- `role_code` TEXT NOT NULL
- `role_scope` TEXT NOT NULL CHECK (`role_scope IN ('platform','process','module')`)
- `inherits_role_id` UUID NULL FK -> `cp_roles.id`
- `is_active` BOOLEAN NOT NULL
- `created_at` TIMESTAMPTZ NOT NULL

UNIQUE (`tenant_id`, `role_code`)

#### 4.1.2 `cp_permissions`
- `id` UUID PK
- `permission_code` TEXT UNIQUE NOT NULL
- `resource_type` TEXT NOT NULL
- `action` TEXT NOT NULL
- `created_at` TIMESTAMPTZ NOT NULL

#### 4.1.3 `cp_role_permissions`
- `id` UUID PK
- `tenant_id` UUID NOT NULL
- `role_id` UUID NOT NULL FK -> `cp_roles.id`
- `permission_id` UUID NOT NULL FK -> `cp_permissions.id`
- `created_at` TIMESTAMPTZ NOT NULL

UNIQUE (`tenant_id`, `role_id`, `permission_id`)

#### 4.1.4 `cp_user_roles`
- `id` UUID PK
- `tenant_id` UUID NOT NULL
- `user_id` UUID NOT NULL FK -> `cp_users.id`
- `role_id` UUID NOT NULL FK -> `cp_roles.id`
- `context_type` TEXT NOT NULL CHECK (`context_type IN ('tenant','organisation','entity','workflow_template','module')`)
- `context_id` UUID NULL
- `effective_from` TIMESTAMPTZ NOT NULL
- `effective_to` TIMESTAMPTZ NULL
- `created_at` TIMESTAMPTZ NOT NULL

UNIQUE (`tenant_id`, `user_id`, `role_id`, `context_type`, `context_id`, `effective_from`)

### 4.2 Required Roles
Role codes (minimum):
- `ADMIN`
- `INITIATOR`
- `REVIEWER`
- `APPROVER`
- `OBSERVER`

### 4.3 Permission Matrix (Baseline)
- `ADMIN`: full tenant governance control.
- `INITIATOR`: start workflow requests for allowed modules.
- `REVIEWER`: submit review decisions on assigned stages.
- `APPROVER`: approve/reject terminal approval stages.
- `OBSERVER`: read-only access to workflow and engine outputs.

### 4.4 Role Inheritance
If inheritance is enabled:
- `ADMIN` inherits all permissions.
- `APPROVER` MAY inherit reviewer read permissions.
- Inheritance graph MUST be acyclic.

### 4.5 Dynamic Permission Evaluation
Effective permission = union of active user roles in current context + inherited role permissions, evaluated with deterministic scope precedence and deny-over-allow conflict handling.

Evaluation inputs:
- tenant_id
- user_id
- module_code
- resource_scope
- action
- execution_timestamp

Deterministic scope precedence (highest to lowest):
1. `entity`
2. `organisation`
3. `workflow_template`
4. `module`
5. `tenant`

Conflict policy:
- Explicit deny at a higher-precedence scope overrides allow at any lower-precedence scope.
- If no explicit allow is found after precedence evaluation, default is deny.

### 4.6 Least-Privilege and Segregation-of-Duties Controls
- Least privilege is mandatory: users receive only required permissions for assigned duties.
- Segregation-of-duties (SoD) rule: the same user cannot be both initiator and terminal approver for the same workflow instance unless tenant exception policy explicitly permits and is audited.
- Role creation is constrained by tenant-level limits on custom roles and inheritance depth.
- Privilege escalation controls require append-only grant events and approval workflow for sensitive roles.

## Section 5 - Workflow and Approval Engine

### 5.1 Tables

#### 5.1.1 `cp_workflow_templates`
- `id` UUID PK
- `tenant_id` UUID NOT NULL
- `template_code` TEXT NOT NULL
- `module_id` UUID NOT NULL FK -> `cp_module_registry.id`
- `created_at` TIMESTAMPTZ NOT NULL

UNIQUE (`tenant_id`, `template_code`)

#### 5.1.2 `cp_workflow_template_versions`
- `id` UUID PK
- `tenant_id` UUID NOT NULL
- `template_id` UUID NOT NULL FK -> `cp_workflow_templates.id`
- `version_no` INT NOT NULL
- `effective_from` TIMESTAMPTZ NOT NULL
- `effective_to` TIMESTAMPTZ NULL
- `is_active` BOOLEAN NOT NULL
- `created_at` TIMESTAMPTZ NOT NULL

UNIQUE (`tenant_id`, `template_id`, `version_no`)
UNIQUE (`tenant_id`, `template_id`, `effective_from`)

#### 5.1.3 `cp_workflow_template_stages`
- `id` UUID PK
- `tenant_id` UUID NOT NULL
- `template_version_id` UUID NOT NULL FK -> `cp_workflow_template_versions.id`
- `stage_order` INT NOT NULL
- `stage_code` TEXT NOT NULL
- `stage_type` TEXT NOT NULL CHECK (`stage_type IN ('review','approval')`)
- `approval_mode` TEXT NOT NULL CHECK (`approval_mode IN ('sequential','parallel')`)
- `threshold_type` TEXT NOT NULL CHECK (`threshold_type IN ('all','any','count')`)
- `threshold_value` INT NULL
- `sla_hours` INT NULL
- `is_terminal` BOOLEAN NOT NULL DEFAULT FALSE
- `created_at` TIMESTAMPTZ NOT NULL

UNIQUE (`tenant_id`, `template_version_id`, `stage_order`)

#### 5.1.4 `cp_workflow_stage_role_map`
- `id` UUID PK
- `tenant_id` UUID NOT NULL
- `stage_id` UUID NOT NULL FK -> `cp_workflow_template_stages.id`
- `role_id` UUID NOT NULL FK -> `cp_roles.id`
- `created_at` TIMESTAMPTZ NOT NULL

UNIQUE (`tenant_id`, `stage_id`, `role_id`)

#### 5.1.5 `cp_workflow_stage_user_map`
- `id` UUID PK
- `tenant_id` UUID NOT NULL
- `stage_id` UUID NOT NULL FK -> `cp_workflow_template_stages.id`
- `user_id` UUID NOT NULL FK -> `cp_users.id`
- `created_at` TIMESTAMPTZ NOT NULL

UNIQUE (`tenant_id`, `stage_id`, `user_id`)

#### 5.1.6 `cp_workflow_instances` (immutable header)
- `id` UUID PK
- `tenant_id` UUID NOT NULL
- `template_id` UUID NOT NULL FK -> `cp_workflow_templates.id`
- `template_version_id` UUID NOT NULL FK -> `cp_workflow_template_versions.id`
- `module_id` UUID NOT NULL FK -> `cp_module_registry.id`
- `resource_type` TEXT NOT NULL
- `resource_id` UUID NOT NULL
- `initiated_by` UUID NOT NULL FK -> `cp_users.id`
- `correlation_id` UUID NOT NULL
- `created_at` TIMESTAMPTZ NOT NULL

#### 5.1.7 `cp_workflow_instance_events` (append-only)
- `id` UUID PK
- `tenant_id` UUID NOT NULL
- `workflow_instance_id` UUID NOT NULL FK -> `cp_workflow_instances.id`
- `event_seq` BIGINT NOT NULL
- `event_type` TEXT NOT NULL CHECK (`event_type IN ('instance_created','instance_running','instance_approved','instance_rejected','instance_cancelled','instance_escalated','instance_failed')`)
- `event_time` TIMESTAMPTZ NOT NULL
- `idempotency_key` TEXT NOT NULL
- `metadata_json` JSONB NOT NULL
- `correlation_id` UUID NOT NULL
- `created_at` TIMESTAMPTZ NOT NULL

UNIQUE (`tenant_id`, `workflow_instance_id`, `event_seq`)
UNIQUE (`tenant_id`, `workflow_instance_id`, `event_type`, `idempotency_key`)

#### 5.1.8 `cp_workflow_stage_instances` (immutable header)
- `id` UUID PK
- `tenant_id` UUID NOT NULL
- `workflow_instance_id` UUID NOT NULL FK -> `cp_workflow_instances.id`
- `template_stage_id` UUID NOT NULL FK -> `cp_workflow_template_stages.id`
- `created_at` TIMESTAMPTZ NOT NULL

UNIQUE (`tenant_id`, `workflow_instance_id`, `template_stage_id`)

#### 5.1.9 `cp_workflow_stage_events` (append-only)
- `id` UUID PK
- `tenant_id` UUID NOT NULL
- `stage_instance_id` UUID NOT NULL FK -> `cp_workflow_stage_instances.id`
- `event_seq` BIGINT NOT NULL
- `event_type` TEXT NOT NULL CHECK (`event_type IN ('stage_pending','stage_running','stage_approved','stage_rejected','stage_skipped','stage_expired','stage_escalated')`)
- `event_time` TIMESTAMPTZ NOT NULL
- `idempotency_key` TEXT NOT NULL
- `metadata_json` JSONB NOT NULL
- `correlation_id` UUID NOT NULL
- `created_at` TIMESTAMPTZ NOT NULL

UNIQUE (`tenant_id`, `stage_instance_id`, `event_seq`)
UNIQUE (`tenant_id`, `stage_instance_id`, `event_type`, `idempotency_key`)

#### 5.1.10 `cp_workflow_approvals` (append-only decisions)
- `id` UUID PK
- `tenant_id` UUID NOT NULL
- `stage_instance_id` UUID NOT NULL FK -> `cp_workflow_stage_instances.id`
- `acted_by` UUID NOT NULL FK -> `cp_users.id`
- `decision` TEXT NOT NULL CHECK (`decision IN ('approve','reject','abstain')`)
- `decision_reason` TEXT NULL
- `acted_at` TIMESTAMPTZ NOT NULL
- `delegated_from` UUID NULL FK -> `cp_users.id`
- `idempotency_key` TEXT NOT NULL
- `request_fingerprint` TEXT NOT NULL
- `correlation_id` UUID NOT NULL
- `created_at` TIMESTAMPTZ NOT NULL

UNIQUE (`tenant_id`, `stage_instance_id`, `acted_by`, `idempotency_key`)
UNIQUE (`tenant_id`, `stage_instance_id`, `request_fingerprint`)

#### 5.1.11 `cp_workflow_delegations`
- `id` UUID PK
- `tenant_id` UUID NOT NULL
- `from_user_id` UUID NOT NULL FK -> `cp_users.id`
- `to_user_id` UUID NOT NULL FK -> `cp_users.id`
- `scope_type` TEXT NOT NULL CHECK (`scope_type IN ('module','workflow_template','entity')`)
- `scope_id` UUID NULL
- `effective_from` TIMESTAMPTZ NOT NULL
- `effective_to` TIMESTAMPTZ NOT NULL
- `is_active` BOOLEAN NOT NULL
- `created_at` TIMESTAMPTZ NOT NULL

### 5.2 Approval Logic
- Sequential stage: stage `N+1` starts only after stage `N` reaches terminal approval/rejection state.
- Parallel stage: all stage role assignees and named-user assignees are eligible concurrently.
- `threshold_type=all`: stage approves when all required assignees have effective `approve` decisions.
- `threshold_type=any`: stage approves when first effective `approve` decision arrives, unless explicit reject policy wins.
- `threshold_type=count`: stage approves when effective `approve_count >= threshold_value`.
- Reject policy: a terminal reject is emitted when rejection threshold is reached by stage policy.

### 5.3 Deterministic State Derivation (No Mutable Status Columns)
Workflow and stage current state are derived from latest append-only events:
- `workflow_current_state` = event with highest `event_seq` in `cp_workflow_instance_events`.
- `stage_current_state` = event with highest `event_seq` in `cp_workflow_stage_events`.

No update-in-place is permitted for workflow/stage state.

### 5.4 Approval Idempotency and Parallel Concurrency
- Approval write path MUST include deterministic `idempotency_key` and `request_fingerprint`.
- Duplicate approval attempts with same idempotency key are no-op returns of existing decision row.
- Parallel decision handling:
1. Insert approval row idempotently.
2. Recompute stage tallies from append-only approvals sorted by `acted_at`, then `id`.
3. Evaluate threshold policy deterministically.
4. Append exactly one new stage terminal event if threshold reached and no same-type terminal event already exists.
- Terminal event uniqueness is enforced by (`tenant_id`, `stage_instance_id`, `event_type`, `idempotency_key`).

### 5.5 Approval Decision State Machine
Stage state machine:
1. `stage_pending` -> `stage_running`
2. `stage_running` -> `stage_approved`
3. `stage_running` -> `stage_rejected`
4. `stage_running` -> `stage_expired`
5. `stage_running` -> `stage_escalated`

Workflow state machine:
1. `instance_created` -> `instance_running`
2. `instance_running` -> `instance_approved`
3. `instance_running` -> `instance_rejected`
4. `instance_running` -> `instance_cancelled`
5. `instance_running` -> `instance_escalated`
6. `instance_running` -> `instance_failed`

### 5.6 Escalation Logic
- SLA timeout triggers escalation event.
- Escalation target role configured per stage/template.
- Escalation does not mutate prior approvals; it appends escalation event and assignment.

### 5.7 Delegation Rules
- Delegation valid only inside effective window.
- Delegated approver action records `delegated_from`.
- Delegation cannot elevate privileges above delegator scope.

### 5.8 Workflow Audit Trail
All workflow lifecycle and decision state is represented by append-only event/approval tables:
- `cp_workflow_instance_events`
- `cp_workflow_stage_events`
- `cp_workflow_approvals`

## Section 6 - Tenant Resource Quotas (Invariant)

### 6.1 Quota Definitions Table: `cp_tenant_quotas`
Columns:
- `id` UUID PK
- `tenant_id` UUID NOT NULL
- `quota_type` TEXT NOT NULL CHECK (`quota_type IN ('api_requests','job_submissions','worker_active_jobs','storage_bytes','export_bytes','ai_inference_calls')`)
- `window_type` TEXT NOT NULL CHECK (`window_type IN ('tumbling','sliding')`)
- `window_seconds` INT NOT NULL
- `max_value` BIGINT NOT NULL
- `enforcement_mode` TEXT NOT NULL CHECK (`enforcement_mode IN ('reject','queue','throttle')`)
- `effective_from` TIMESTAMPTZ NOT NULL
- `effective_to` TIMESTAMPTZ NULL
- `correlation_id` UUID NOT NULL
- `created_at` TIMESTAMPTZ NOT NULL

UNIQUE (`tenant_id`, `quota_type`, `effective_from`)

### 6.2 Quota Usage Event Table: `cp_tenant_quota_usage_events` (append-only)
- `id` UUID PK
- `tenant_id` UUID NOT NULL
- `quota_type` TEXT NOT NULL
- `usage_delta` BIGINT NOT NULL
- `operation_id` UUID NOT NULL
- `idempotency_key` TEXT NOT NULL
- `request_fingerprint` TEXT NOT NULL
- `source_layer` TEXT NOT NULL CHECK (`source_layer IN ('api_ingress','job_submission','worker_pre_execute','export_service','ai_gateway','storage_allocator')`)
- `window_start` TIMESTAMPTZ NOT NULL
- `window_end` TIMESTAMPTZ NOT NULL
- `correlation_id` UUID NOT NULL
- `created_at` TIMESTAMPTZ NOT NULL

UNIQUE (`tenant_id`, `quota_type`, `operation_id`, `idempotency_key`)
UNIQUE (`tenant_id`, `quota_type`, `request_fingerprint`)

### 6.3 Quota Window Projection Table: `cp_tenant_quota_windows` (derived projection)
- `tenant_id` UUID NOT NULL
- `quota_type` TEXT NOT NULL
- `window_start` TIMESTAMPTZ NOT NULL
- `window_end` TIMESTAMPTZ NOT NULL
- `consumed_value` BIGINT NOT NULL
- `last_event_id` UUID NOT NULL
- `updated_at` TIMESTAMPTZ NOT NULL

UNIQUE (`tenant_id`, `quota_type`, `window_start`, `window_end`)

### 6.4 Enforcement Contract by Quota Type

| Quota Type | Source Metric | Enforcement Point | Breach Behavior | Reset Window | Idempotent Accounting |
|---|---|---|---|---|---|
| `api_requests` | accepted API request count | API ingress middleware | reject or throttle | tumbling 60s default | usage event keyed by request id + idempotency key |
| `job_submissions` | workflow/job enqueue count | job submission gateway | reject or queue | sliding 300s default | usage event keyed by job request signature |
| `worker_active_jobs` | active running jobs per tenant | worker pre-execute guard | queue or reject | real-time + 30s reconciliation | start/finish events keyed by operation id |
| `storage_bytes` | persisted bytes allocated | storage allocator and ingestion writer | reject on hard cap | no reset; monotonic with deallocation events | allocation/deallocation events keyed by object id |
| `export_bytes` | generated export byte count | export service preflight + stream finalizer | reject or throttle | tumbling 24h default | event keyed by export request id |
| `ai_inference_calls` | AI inference call count (and optional token sub-metric) | AI gateway | reject or queue | tumbling 60s and 24h profile | event keyed by inference request id |

### 6.5 Bypass-Proof Enforcement Rules
- All API, async, and internal command paths MUST call centralized `QuotaGuard.check_and_record(quota_context)` before execution side effects.
- Non-API worker paths are forbidden from direct execution without quota check result in control-plane context token.
- Quota accounting is append-only events plus deterministic projection; no direct mutable counters.
- Retry behavior must be idempotent and must not double-charge usage.

## Section 7 - Isolation Tier Model

### 7.1 Tier Definitions
- Tier 1: Shared DB, shared schema, RLS isolation.
- Tier 2: Shared DB, schema-per-tenant.
- Tier 3: Dedicated DB per tenant.
- Tier 4: Dedicated cluster per tenant.

### 7.2 Isolation Control Table: `cp_tenant_isolation_policy`
- `id` UUID PK
- `tenant_id` UUID NOT NULL UNIQUE
- `isolation_tier` TEXT NOT NULL CHECK (`isolation_tier IN ('tier1','tier2','tier3','tier4')`)
- `db_cluster` TEXT NOT NULL
- `schema_name` TEXT NOT NULL
- `worker_pool` TEXT NOT NULL
- `region` TEXT NOT NULL
- `migration_state` TEXT NOT NULL CHECK (`migration_state IN ('active','prepare_target','snapshot_copy','incremental_catchup','consistency_verify','read_shadow','write_cutover','final_verify','source_retire','rollback_pending')`)
- `route_version` BIGINT NOT NULL
- `effective_from` TIMESTAMPTZ NOT NULL
- `effective_to` TIMESTAMPTZ NULL
- `correlation_id` UUID NOT NULL
- `created_at` TIMESTAMPTZ NOT NULL

UNIQUE (`tenant_id`, `route_version`)
UNIQUE (`tenant_id`, `effective_from`)

### 7.3 Isolation Routing Resolution Contract
- DB session routing resolves (`db_cluster`, `schema_name`, `region`) from latest active route version.
- Worker routing resolves (`worker_pool`, `region`) from latest active route version.
- Routing decision is cached in a signed route snapshot with TTL and version pin.
- Any missing route attribute causes fail-closed denial: `ISOLATION_ROUTE_UNAVAILABLE`.

### 7.4 Tenant Migration Workflow
Phases:
1. `prepare_target`
2. `snapshot_copy`
3. `incremental_catchup`
4. `consistency_verify`
5. `read_shadow`
6. `write_cutover`
7. `final_verify`
8. `source_retire`

### 7.5 Zero-Downtime Strategy
- Use dual-read shadow validation before write cutover.
- Use write-forwarding during brief cutover window if required.
- Maintain idempotent replay log for failed cutover recovery.

### 7.6 Data Verification
- Row-count parity by table.
- Hash parity on deterministic canonical projection.
- Sampled foreign key integrity checks.

### 7.7 Deterministic Cutover and Rollback Semantics
- Cutover appends new route version row with `migration_state='write_cutover'` and a higher `route_version`.
- Route activation is atomic by (`tenant_id`, `route_version`) and never mutates prior versions.
- Rollback appends new route version returning to prior stable (`db_cluster`, `schema_name`, `worker_pool`, `region`) and replays delta log idempotently.
- Migration is complete only after post-cutover reconciliation passes.

## Section 8 - Feature Flags

### 8.1 Flag Storage
Use `cp_module_feature_flags` with append-only effective dating.

### 8.2 Feature Flag Schema Clarification
- `rollout_mode` TEXT NOT NULL CHECK (`rollout_mode IN ('off','on','canary')`)
- `compute_enabled` BOOLEAN NOT NULL
- `write_enabled` BOOLEAN NOT NULL
- `visibility_enabled` BOOLEAN NOT NULL

Dark-launch equivalent is represented explicitly as:
- `compute_enabled=true`
- `write_enabled=false`
- `visibility_enabled=false`

### 8.3 Rollout Modes
- `off`: hard disabled.
- `on`: enabled for all tenant users.
- `canary`: enabled for scoped subset (user IDs, entities, percentages).

### 8.4 Canary Model
Canary targeting fields in `flag_value`:
- `target_user_ids`
- `target_entity_ids`
- `traffic_percent`
- `start_at`
- `end_at`

Decision function SHALL be deterministic for same request fingerprint.

### 8.5 Non-Overlap and Precedence Rules
- Non-overlap constraint: for (`tenant_id`, `module_id`, `flag_key`, target scope), effective windows must not overlap.
- Precedence order:
1. entity-targeted rule
2. user-targeted rule
3. canary percentage rule
4. module default rule
- Tie-breaker for same scope is highest `effective_from`.

### 8.6 Rollback
Rollback is append-only:
- Insert new flag row with `rollout_mode='off'` and higher effective timestamp.
- Do not mutate historical flag rows.

## Section 9 - Control-Plane Enforcement Flow

### 9.1 Request Flow
API Request
-> Tenant validation
-> Module enablement check
-> RBAC check
-> Workflow eligibility check
-> Quota check
-> Isolation routing
-> Finance engine execution

### 9.2 Fail-Closed Interception Contract
Mandatory interception applies to:
- API request handlers.
- Background job handlers.
- Internal command handlers.
- Workflow start handlers.
- Workflow activity handlers for financial-impacting actions.

No finance execution path may run without a validated control-plane context token.

Control-plane context token minimum claims:
- `tenant_id`
- `module_code`
- `decision` (`allow`)
- `policy_snapshot_version`
- `quota_check_id`
- `isolation_route_version`
- `issued_at`
- `expires_at`
- `correlation_id`
- `signature`

Finance executors MUST reject missing/expired/invalid tokens with `CONTROL_PLANE_CONTEXT_REQUIRED`.

### 9.3 Detailed Gate Outcomes
- Tenant validation fail: `TENANT_INVALID`.
- Module disabled: `MODULE_DISABLED`.
- RBAC fail: `PERMISSION_DENIED`.
- Workflow required but missing approval: `WORKFLOW_APPROVAL_REQUIRED`.
- Quota exceeded: `QUOTA_EXCEEDED`.
- Isolation route missing: `ISOLATION_ROUTE_UNAVAILABLE`.

### 9.4 Centralized Gate Interface
- `ControlPlaneAuthorizer.authorize(command_context)` is the single entrypoint for policy decision.
- `ControlPlaneAuthorizer.issue_context_token(allow_decision)` produces signed context for downstream execution.
- Internal service invocations must forward token; direct ungated executor calls are prohibited.

### 9.5 Multi-Step Workflow Enforcement
For Temporal workflows:
- Gate check at workflow start.
- Re-check module enablement, RBAC scope, and quota before each critical activity stage.
- Verify context token validity before each financial-impacting activity.
- Abort workflow with explicit policy code on post-start policy violation.

## Section 10 - RLS and Governance Enforcement

### 10.1 Global vs Tenant-Scoped Table Classification
Global registry tables (platform-owned, not tenant-RLS filtered):
- `cp_packages`
- `cp_module_registry`
- `cp_permissions`

Tenant-scoped control-plane tables (tenant-RLS mandatory):
- `cp_users`
- `cp_organisations`
- `cp_groups`
- `cp_entities`
- `cp_user_organisation_map`
- `cp_user_entity_map`
- `cp_tenant_package_assignments`
- `cp_tenant_module_enablement`
- `cp_module_feature_flags`
- `cp_roles`
- `cp_role_permissions`
- `cp_user_roles`
- `cp_workflow_templates`
- `cp_workflow_template_versions`
- `cp_workflow_template_stages`
- `cp_workflow_stage_role_map`
- `cp_workflow_stage_user_map`
- `cp_workflow_instances`
- `cp_workflow_instance_events`
- `cp_workflow_stage_instances`
- `cp_workflow_stage_events`
- `cp_workflow_approvals`
- `cp_workflow_delegations`
- `cp_tenant_quotas`
- `cp_tenant_quota_usage_events`
- `cp_tenant_quota_windows`
- `cp_tenant_isolation_policy`

### 10.2 RLS Expectations
All tenant-scoped tables MUST have:
- `ENABLE ROW LEVEL SECURITY`
- `FORCE ROW LEVEL SECURITY`
- Tenant policy using `app.current_tenant_id`.

Global registry table access model:
- write access: platform-admin service principals only
- read access: controlled read paths only
- no tenant context is used for global table filtering

### 10.3 Append-Only Policy
Append-only required tables:
- package assignment history
- module enablement history
- feature flags
- role grants
- workflow instance events
- workflow stage events
- approvals
- quota usage events and quota windows projection lineage
- isolation policy history
- identity lifecycle events

Projection tables may use current-state materialization if built from append-only source streams.

### 10.4 AuditWriter-Only Writes
All control-plane writes MUST use centralized `AuditWriter` insertion paths.
Direct `session.add` in domain services is prohibited.

### 10.5 Correlation ID Propagation
Every control-plane write and workflow event SHALL store correlation ID.
Correlation ID must propagate through:
- API layer
- service layer
- workflow metadata
- audit records

### 10.6 Scale Hardening Notes
- RBAC evaluation caching: maintain tenant-scoped permission snapshots keyed by (`tenant_id`, `user_id`, `context_hash`, `policy_version`) with event-driven invalidation.
- Quota scaling: ingest quota usage as append-only events, aggregate asynchronously into window projections, and partition quota event tables by (`tenant_id`, `window_start`).
- Isolation routing cache: maintain signed route snapshots keyed by (`tenant_id`, `route_version`) with TTL and invalidation on new route version events.

## Section 11 - Exit Criteria for Phase 1E

Phase 1E is complete only when all criteria below are met.

### 11.1 Tenant Automation
- Tenant provisioning API creates tenant policy, default package assignment, default roles, and isolation policy in one deterministic flow.
- Automated provisioning is idempotent by request signature.

### 11.2 RBAC Enforcement
- Every finance engine endpoint and internal command handler is gated by control-plane authorization.
- Permission denials are deterministic and carry policy reason codes.

### 11.3 Approval Workflow
- Workflow templates execute with sequential and parallel stage support.
- Threshold logic (`all`,`any`,`count`) is tested and deterministic.
- Delegation and escalation are audited and reproducible.
- Workflow and stage state is derived from append-only events only.
- Approval idempotency and parallel concurrency race scenarios are test-covered.

### 11.4 Quota Enforcement
- API ingress, job submission, worker execution, export service, AI gateway, and storage allocator enforce quota decisions.
- `reject`, `queue`, and `throttle` paths are test-covered.
- Quota usage accounting is idempotent on retries and duplicate deliveries.

### 11.5 Isolation Tier Selection
- Tenant isolation tier is selectable via control-plane policy.
- Routing resolution works for all tiers.
- Tier migration runbook is executable and tested in staging.

### 11.6 Feature Flags
- Per-tenant module flags support `off/on/canary` and explicit `compute_enabled/write_enabled/visibility_enabled`.
- Canary targeting and rollback are deterministic and append-only.
- Effective-window non-overlap and precedence rules are validated.

### 11.7 Deterministic Tests
Minimum test suites required:
- unit tests for policy evaluators (module enablement, RBAC, quota, flag evaluation)
- integration tests for end-to-end gate flow before finance execution
- migration tests for isolation tier move verification
- workflow tests for approval, escalation, delegation
- fail-closed interception tests for API, background, and internal command paths
- RLS isolation tests for all tenant-scoped control-plane tables
- append-only rejection tests for protected tables

### 11.8 Non-Negotiable Completion Conditions
- No finance engine executes without control-plane allow decision.
- No control-plane table bypasses RLS.
- No protected control-plane history table permits update/delete.
- No write path bypasses AuditWriter.
