TITLE:
FINANCE PLATFORM COMPLETION — CONSOLIDATION, INTERCOMPANY, DATA QUALITY, RECONCILIATION, POLICY
(MASTER DESIGN v1.3 LOCKED)

MODE:
STRICT DESIGN + PHASED EXECUTION READY

GOAL:
Move platform from ~67% → ~85% readiness by completing critical financial flows WITHOUT breaking existing system.

---

# CORE PRINCIPLES

* No regression to working features
* Extend, don’t rewrite
* Prefer wiring over building new modules
* Single source of truth per domain
* Deterministic + auditable outputs
* No destructive cleanup during completion
* Every execution step must be rollback-safe

---

# SECTION 0 — CURRENT STATE (READ-ONLY CONTEXT)

Platform already has:

✔ Core accounting engines (journals, TB, FS)
✔ Workflow + approvals
✔ Audit + lineage
✔ Reporting layer
✔ Partial consolidation, reconciliation, policy, and data quality

Known gaps:

* Consolidation incomplete (intercompany + adjustments stubbed)
* Multiple intercompany paths (legacy + new)
* No centralized data completeness engine
* Reconciliation coverage incomplete
* Policy not centralized

---

# SECTION 1 — TARGET ARCHITECTURE

All financial flows MUST follow:

INGEST → VALIDATE → MAP → RECONCILE → ELIMINATE → ADJUST → CONSOLIDATE → REPORT

---

Domains:

1. Consolidation pipeline
2. Intercompany system
3. Data quality engine
4. Reconciliation engine
5. Policy engine

---

# SECTION 2 — CONSOLIDATION BACKBONE

PROBLEM:

* intercompany_service returns stub values
* adjustment_service returns stub values
* minority_interest is placeholder

---

## REQUIREMENTS

### Intercompany Output

* matched_pairs
* unmatched_items
* elimination_entries

---

### Adjustment Output

* adjustment_entries
* reclassification_entries

---

### Minority Interest

RULE:

minority_interest = subsidiary_nci * (1 - parent_ownership_pct)

---

SOURCE:

* ownership_consolidation.nci_balance
* ownership_consolidation.ownership_percentage

---

CONSTRAINTS:

* compute per subsidiary (NOT only aggregated)
* aggregate after entity-level computation
* include audit trace
* missing data → explicit validation error (NO defaults)

---

## CROSS-CHECK (MANDATORY)

After wiring intercompany and adjustment logic:

Run a consolidation scenario that previously produced dummy outputs.

---

### VALID OUTCOME (MUST SATISFY ONE)

A. Functional:

* elimination_entries count > 0
  OR
* adjustment_entries count > 0

B. Validation failure:

* validation_report.status = FAIL
* explicit failure reason

---

### FORBIDDEN

* zero outputs without validation error
* placeholder values
* silent success

---

### AUDIT REQUIREMENT

Must record:

* elimination evidence OR
* adjustment evidence OR
* validation failure

Must include:

* entity-level traceability
* transaction references

---

# SECTION 3 — INTERCOMPANY UNIFICATION

PROBLEM:

* legacy matcher + new service both exist

---

## REQUIREMENTS

* use legacy matcher as computation engine
* route ALL new-path calls through it
* eliminate duplicate execution paths

---

## STANDARDIZATION

* transaction types:

  * upstream
  * downstream
  * lateral

* matching rules:

  * tolerance-based
  * currency-aware

---

## DEPRECATION RULE

DO NOT delete code

Add in stub files:

```python
# DEPRECATED: routed to legacy engine via intercompany_service.py
```

---

## COMPATIBILITY RULE

* new service acts as wrapper/facade
* API shape unchanged
* deletion deferred to future cleanup

---

# SECTION 4 — DATA COMPLETENESS ENGINE

PROBLEM:

* validation scattered across modules

---

## CAPABILITIES

1. Table-level:

   * required columns
   * null checks
   * type checks

2. Row-level:

   * numeric consistency
   * currency consistency

3. Dataset-level:

   * duplicates
   * cross-table consistency

---

## OUTPUT FORMAT

```yaml
validation_report_example:
  table: gl_entries
  status: FAIL
  failures:
    - column: period_id
      rule: not_null
      row_count: 3
    - rule: cross_table_consistency
      detail: "GL entries missing corresponding TB rows: 47 rows"
  warnings: []
  summary:
    total_rows_checked: 12000
    failed_rows: 50
```

---

## FAILURE BEHAVIOR

* FAIL → block pipeline + return report
* WARN → continue + log audit warning
* PASS → proceed

---

## INTEGRATION

MUST run before:

* consolidation
* reconciliation
* reporting

---

## RULES

* no silent validation bypass
* no auto-fix
* validation must be observable

---

# SECTION 5 — RECONCILIATION EXTENSION

CURRENT:

* GL vs TB
* payroll vs GL
* bank reconciliation

---

## ADD

### AR/AP Ageing vs GL

AGING BUCKETS:

[30, 60, 90, 999]

---

DEFAULT TOLERANCE:

0-30 → 0
31-60 → 100
61-90 → 500
90+ → 1000

---

RULE:

* tolerances configurable (NOT hardcoded)
* output must include bucket-level variance evidence

---

### Inventory vs GL

SOURCE:

inventory_subledger.valuation_table (or canonical equivalent)

---

RULE:

* explicit mapping required
* no inferred datasets

---

# SECTION 6 — ACCOUNTING POLICY ENGINE

PROBLEM:

* policy exists only in Multi-GAAP module

---

## SCOPE (STRICT)

ONLY consolidation-related policies:

* revenue recognition (consolidation impact)
* intercompany profit elimination
* minority interest treatment

---

## OUT OF SCOPE

* FX policy engine
* reporting policy engine

---

## CAPABILITIES

* policy definition
* versioning
* application during consolidation
* audit trail

---

## POLICY RESOLUTION

Select:

highest policy_version_id
WHERE effective_date ≤ current_date

---

# SECTION 7 — OUTPUT REQUIREMENTS

For every execution step:

* files changed
* exact diffs
* tests added
* runtime verification steps

---

# SECTION 8 — EXECUTION STRATEGY

ORDER:

1. Consolidation backbone
2. Intercompany unification
3. Data quality engine
4. Reconciliation extension
5. Policy engine

---

## RULES

* complete one step fully before next
* system must remain deployable
* backward compatibility required

---

# SECTION 9 — VERIFICATION

After each step:

* backend tests pass
* frontend build passes

Verify:

* login
* MFA
* API

---

## FLOW CHECKS

* consolidation correctness
* validation behavior
* reconciliation outputs
* policy determinism

---

# SECTION 10 — FINAL GOAL

✔ Consolidation operational
✔ Intercompany unified
✔ Data quality centralized
✔ Reconciliation enterprise-ready
✔ Policy layer enforced

---

TARGET:

~85% readiness

---

# SECTION 11 — ROLLBACK (MANDATORY)

Each step MUST include:

* revert steps
* file list
* API restoration
* execution < 5 minutes

---

## ROLLBACK TEST

Must be tested in non-production before completion

---

## EVIDENCE

* rollback executed
* APIs restored
* tests passing

---

# FINAL RULE

DO NOT:

* rewrite system
* introduce new frameworks
* break working flows

---

FOCUS:

CONNECT → COMPLETE → STABILIZE
