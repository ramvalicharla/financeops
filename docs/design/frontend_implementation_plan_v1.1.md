# 🚀 Frontend Implementation Plan — FinanceOps Control Plane

**v1.1 (FINAL — LOCKED, CORRECTED)**
**Date:** 2026-04-12

---

# 🎯 Purpose

This document defines the **authoritative frontend execution roadmap** based on:

* Backend API contract (control-plane architecture)
* Frontend audit findings
* Governance-first design principles

Focus:

* Fix architectural violations first
* Align UI with **Control Plane execution model**
* Build **governance-grade UX (not CRUD UI)**
* Leverage backend capabilities already available

---

# 🧠 Core Principle (NON-NEGOTIABLE)

## Intent-First Execution

```text
User Action → Intent → Control Plane → Job → Execution → Record
```

---

## ❌ FORBIDDEN

* Direct mutation calls from UI (`approveJournal`, `postJournal`, etc.)
* UI acting as authority
* Blocking UI waiting for execution completion
* Rendering raw JSON as user-facing UI

---

## ✅ REQUIRED

* All mutations must go through `createIntent()`
* UI must be **non-blocking and reactive**
* Backend is the **single source of truth**
* UI must render **structured evidence (not raw payloads)**

---

# 📊 Audit Summary (Condensed)

| Area             | Backend       | Frontend         | Gap                 |
| ---------------- | ------------- | ---------------- | ------------------- |
| Journals         | ✅ Ready       | ⚠️ ~67%          | Intent violation    |
| Control Plane    | ✅ Strong      | ⚠️ Partial usage | Underutilized       |
| Timeline/Lineage | ✅ Exists      | ⚠️ Shallow UI    | Not visualized      |
| Determinism      | ✅ Exists      | ⚠️ Partial       | Not surfaced fully  |
| Period Close     | ⚠️ Minor gaps | ✅ Usable         | Attribution missing |
| Primitives       | N/A           | ❌ Missing        | Blocking            |

👉 **Frontend completeness: ~48%**

---

# 🔴 PHASE 0 — INTENT-FIRST REFACTOR (CRITICAL)

## Objective

Eliminate **all direct mutation flows** and enforce control-plane execution

---

## ⚠️ RULE

👉 Backend mutation APIs must NOT be deleted
👉 They must be **deprecated and blocked in UI**

---

## 0.1 Intent API Wrapper

**File:** `frontend/lib/api/intents.ts`

```ts
export async function createIntent(payload: {
  type: string
  data: Record<string, any>
}) {
  return api.post("/api/v1/platform/control-plane/intents", payload)
}
```

---

## 0.2 Deprecate Direct Mutation APIs

```ts
/**
 * @deprecated DO NOT USE — use createIntent()
 * Internal backend use only
 */
export async function approveJournal(id: string) {
  throw new Error("Direct mutation forbidden. Use createIntent.")
}
```

---

## 0.3 Replace UI Mutation Flow

### ❌ WRONG

```ts
await approveJournal(id)
```

### ✅ CORRECT

```ts
const intent = await createIntent({
  type: "APPROVE_JOURNAL",
  data: { journal_id: id }
})

openIntentPanel(intent.intent_id)
```

---

## ❗ DO NOT DO THIS

```ts
await waitForIntentStatus(...)
```

👉 UI must NOT block

---

## 0.4 Enforcement Guard (MANDATORY)

Add codebase checks:

```bash
grep -r "approveJournal(" frontend/
grep -r "postJournal(" frontend/
grep -r "reverseJournal(" frontend/
```

Optional: ESLint rule to block forbidden imports

---

## Acceptance Criteria

* ❌ Zero direct mutation calls in UI
* ✅ All mutations use `createIntent`
* ✅ IntentPanel opens immediately
* ✅ UI is non-blocking

---

# 🟡 PHASE 1 — FOUNDATION PRIMITIVES

## Objective

Create reusable governance UI components

---

## Components

* `StateBadge`
* `GuardFailureCard`
* `IntentStepper`
* `PeriodSelector`
* `DataTable`

---

## Rules

* No duplication
* Reusable across modules
* Must replace all ad-hoc UI

---

## Acceptance Criteria

* All 5 components exist
* Used in at least 2 modules
* No inline replacements remain

---

# 🟡 PHASE 2 — GOVERNANCE UI UPGRADE

## Objective

Convert panels into **control-plane UX**

---

## IntentPanel

Replace JSON with:

* IntentStepper
* GuardFailureCard
* Tabs:

  * INTENT
  * EXECUTION
  * AUDIT

---

## JobPanel

Add:

* grouped states
* spinner-based progress (no %)
* duration (derived)
* error recovery UI

---

## Acceptance Criteria

* No JSON visible
* Fully visual lifecycle
* Errors actionable

---

# 🟡 PHASE 3 — JOURNAL MODULE HARDENING

## Objective

Make journal module governance-compliant

---

## Key Fixes

### 1. Intent Integration

All mutations → intent

---

### 2. COA Autocomplete

Replace `<select>` with search UI

---

### 3. Timeline Integration

Use:

```
/api/v1/platform/control-plane/timeline
```

---

### 4. StateBadge Usage

Apply everywhere

---

## Acceptance Criteria

* Fully intent-driven
* Timeline visible
* UX improved

---

# 🟡 PHASE 4 — AUDIT & TRACEABILITY LAYER

## Objective

Unlock backend power (already available)

---

## APIs to Use (DO NOT CREATE NEW ONES)

* control-plane/timeline
* control-plane/lineage
* control-plane/determinism
* control-plane/snapshots

---

## Components

* ObjectTimeline
* DeterminismProof
* LineageView
* SnapshotNavigator

---

## ⚠️ UI RULE

❌ No raw JSON rendering
✅ Structured evidence display

---

## Acceptance Criteria

* Real data only
* No mocks
* Fully integrated

---

# 🟡 PHASE 5 — PERIOD CLOSE GOVERNANCE

## Objective

Align close workflows with governance model

---

## Actions

* Use `/monthend/*` APIs
* Add ApprovalGraph
* Improve progress tracking
* Add PeriodLockOverlay

---

## Acceptance Criteria

* Clear approval visibility
* Correct API usage
* Attribution handled (even if partial)

---

# 🟡 PHASE 6 — ADVANCED LINEAGE & UX

## Objective

Build differentiation layer

---

## Features

* visual lineage graph
* impact warnings
* batch preview
* snapshot diff

---

## Acceptance Criteria

* Graph-based UI
* Clear dependency visibility
* No shallow summaries

---

# 📊 EFFORT ESTIMATION (REALISTIC)

| Phase   | Optimistic | Realistic |
| ------- | ---------- | --------- |
| Phase 0 | 2–3 days   | 1 week    |
| Phase 1 | 3 days     | 1 week    |
| Phase 2 | 4 days     | 1–2 weeks |
| Phase 3 | 4–6 days   | 2 weeks   |
| Phase 4 | 1 week     | 3–4 weeks |
| Phase 5 | 4 days     | 2 weeks   |
| Phase 6 | 1 week     | 2–3 weeks |

---

# 🚨 LAUNCH BLOCKERS

1. ❌ Intent-first violation (CRITICAL)
2. ❌ Missing primitives
3. ❌ Weak lifecycle UX
4. ❌ Shallow traceability
5. ❌ Inconsistent control-plane usage

---

# 📋 FINAL EXECUTION ORDER (LOCKED)

```
1. 🔴 Phase 0 — Intent-First Refactor
2. 🟡 Phase 1 — Primitives
3. 🟡 Phase 2 — Governance UI
4. 🟡 Phase 3 — Journal Module
5. 🟡 Phase 4 — Audit Layer
6. 🟡 Phase 5 — Close Governance
7. 🟡 Phase 6 — Advanced UX
```

---

# 📊 FINAL TARGET STATE

| Stage           | Completeness |
| --------------- | ------------ |
| Current         | ~48%         |
| After Phase 0–3 | ~75–80%      |
| Final           | ~90–95%      |

---

# 🔒 STATUS

**LOCKED — v1.1 FINAL**

This is the **authoritative execution plan**.

---

## 🚨 ENFORCEMENT

Any code that:

* bypasses intent
* blocks UI on execution
* renders raw JSON
* introduces duplicate primitives

👉 MUST be rejected.

---

**Start with Phase 0. Do not skip.**
