# PROMPT 08 — ENFORCE AUDIT COLUMNS + CURRENCY DERIVATION

**Sprint:** 3 (Finance Correctness)
**Audit findings closed:** #15, #16, partial #17
**Risk level:** MEDIUM (schema changes via migration)
**Estimated effort:** M (1-2 weeks)
**Prerequisite:** Prompts 01-07 complete

---

## CONTEXT

Repo root: `D:\finos`
Target files:
- `D:\finos\backend\financeops\db\base.py` (around lines 19, 35)
- `D:\finos\backend\financeops\db\models\users.py` (around line 53)
- `D:\finos\backend\financeops\services\working_capital_service.py` (around line 43)
- `D:\finos\backend\financeops\db\models\bank_recon.py` (around line 28)

The audit found three related finance-correctness issues:
1. Base model classes don't enforce `updated_at`, `created_by`, `updated_by` on all business entities (#15)
2. Currency defaults are hardcoded to USD in places despite India-first / multi-currency requirements (#16)
3. Soft-delete behavior is not centralized in a shared base (partial #17)

Bundling these because they share the same fix surface (base model classes) and the same migration cycle.

---

## SCOPE — DO EXACTLY THIS

### Step 1 — Inventory current state
1. List every base class in `D:\finos\backend\financeops\db\base.py` and what mixins they provide
2. Run: `rg -n "class.*Base\)" D:\finos\backend\financeops\db\models | head -50` — list all model classes
3. For each model, classify which base it inherits from
4. Identify which models are missing audit columns (`created_at`, `updated_at`, `created_by`, `updated_by`)
5. Run: `rg -n "default=.USD|currency.*=.*USD" D:\finos\backend\financeops` — list every USD hardcode
6. Run: `rg -n "deleted_at|is_deleted|soft_delete" D:\finos\backend\financeops\db\models` — map current soft-delete usage

Output a table: `Model | Base | Has audit cols | Has currency | Has soft-delete | Risk`

### Step 2 — Design the new base hierarchy
Propose a clean hierarchy. Likely shape:

```
Base (existing, SQLAlchemy declarative)
└── TimestampedBase             # adds created_at, updated_at
    └── AuditedBase             # adds created_by, updated_by (FK to users)
        └── BusinessEntityBase  # adds tenant_id, soft-delete
            └── MonetaryEntityBase  # adds currency_code (FK to currency)
```

Rules:
- Every model representing user data inherits from at least `AuditedBase`
- Every multi-tenant model inherits from `BusinessEntityBase`
- Every model holding monetary values inherits from `MonetaryEntityBase`
- Currency is NEVER nullable on a monetary model — must be derived from entity/tenant config or explicitly set

**STOP here. Output the proposed hierarchy with the model classification table. Wait for user confirmation.**

### Step 3 — Currency derivation strategy
Define how currency is determined for new records (no more hardcoded USD):
1. If model has a direct `entity_id` FK → currency = entity.functional_currency
2. Else if model has `tenant_id` → currency = tenant.default_currency
3. Else error — model must explicitly declare currency context

Implement this as a SQLAlchemy event listener or a base class method `_derive_currency()`.

### Step 4 — Apply the changes (after confirmation)
Order of operations matters:
1. Create new base classes in `D:\finos\backend\financeops\db\base.py`
2. Generate Alembic migration adding missing columns to existing tables. Migration must:
   - Add columns as nullable first
   - Backfill: `updated_at` = `created_at`, `created_by` = system user UUID, currency = entity/tenant default
   - Then ALTER to NOT NULL
   - This is a multi-step migration — use `op.execute()` for the backfill between schema changes
3. Update model classes to inherit from new bases — go module by module, smallest first
4. Update services that read these fields to handle the new defaults

### Step 5 — Tests
Create `D:\finos\backend\tests\test_audit_columns.py`:
- `test_business_entity_has_created_at_updated_at`
- `test_business_entity_has_created_by_updated_by`
- `test_updated_at_changes_on_update`
- `test_created_by_set_from_request_context`
- `test_monetary_entity_currency_derived_from_entity` (no entity → no record)
- `test_currency_never_defaults_to_usd_silently`
- `test_soft_delete_sets_deleted_at_and_deleted_by`
- `test_soft_deleted_records_excluded_from_default_queries`

### Step 6 — Backfill verification script
Create `D:\finos\backend\scripts\verify_backfill_audit_columns.py`:
- Queries every business table
- Counts rows with NULL `created_by`, `updated_by`, `currency_code`
- Outputs a report
- Exits non-zero if any NULLs found in NOT NULL columns
- This is run post-migration as a sanity check

---

## DO NOT DO

- Do NOT make audit columns nullable in the final schema (only during backfill)
- Do NOT use `default='USD'` anywhere — currency must be derived
- Do NOT auto-add audit columns to non-business tables (sessions, caches, system tables)
- Do NOT modify the journal entry posting logic — that's a different domain concern
- Do NOT batch all model migrations into one Alembic file — use multiple migrations grouped by module

---

## VERIFICATION CHECKLIST

- [ ] All business models inherit from appropriate base in the new hierarchy
- [ ] All migrations apply cleanly forward and reverse on a copy of staging data
- [ ] Backfill verification script reports zero NULLs in NOT NULL audit columns
- [ ] Currency derivation works for all monetary models (no hardcoded USD)
- [ ] All 8 test cases pass
- [ ] Existing tests still pass
- [ ] `alembic heads` returns one head

---

## ROLLBACK PLAN

If migration fails partway:
1. Each migration step has a corresponding `downgrade()` — run `alembic downgrade -1` until stable
2. Do NOT manually edit the alembic_version table
3. If backfill produces wrong values, use the verification script + a corrective migration rather than rolling back

---

## COMMIT MESSAGE

```
feat(domain): enforce audit columns and currency derivation across all business models

- New base hierarchy: TimestampedBase -> AuditedBase -> BusinessEntityBase -> MonetaryEntityBase
- Migrated all business models to inherit from appropriate base
- Currency derivation from entity/tenant config (no more USD hardcodes)
- Soft-delete centralized at BusinessEntityBase
- Backfill migration with verification script

Closes audit findings #15, #16. Partially closes #17.
Required for SOC 2 audit trail completeness and India/multi-currency operation.
```
