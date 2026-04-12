# 📜 Frontend ↔ Backend API Contract Summary

**FinanceOps Control Plane — v1.0 (LOCKED)**
**Date:** 2026-04-12

---

# 🎯 Purpose

This document defines the **actual usable API contract** between frontend and backend.

It corrects:

* Misinterpretation of “missing APIs”
* Confusion between REST endpoints vs Control Plane APIs
* Frontend/backend contract mismatches

This is the **source of truth for frontend development**.

---

# 🧠 Architecture Principle (NON-NEGOTIABLE)

## Control Plane First

This system is **NOT traditional REST-first**.

All operations must follow:

```
UI → Intent → Control Plane → Job → Execution → Record
```

### ❌ DO NOT

* Call mutation APIs directly (bypass intent)
* Expect feature-specific endpoints for everything

### ✅ DO

* Use Control Plane APIs for:

  * timeline
  * lineage
  * determinism
  * snapshots
  * audit

---

# ✅ API STATUS SUMMARY

## 🟢 Fully Supported (Use Immediately)

### 1. Journal APIs (Production Ready)

All lifecycle endpoints exist and are governed:

```
GET    /api/v1/accounting/journals
GET    /api/v1/accounting/journals/{id}
POST   /api/v1/accounting/journals
POST   /api/v1/accounting/journals/{id}/submit
POST   /api/v1/accounting/journals/{id}/approve
POST   /api/v1/accounting/journals/{id}/post
POST   /api/v1/accounting/journals/{id}/reverse
```

✔ Uses `GovernedMutationResponse`
✔ Guard + role enforcement present
✔ Intent-driven execution

👉 **Frontend: build full journal module now**

---

### 2. Control Plane APIs (Core Power Layer)

These replace many “expected” REST endpoints:

```
GET /api/v1/platform/control-plane/jobs
GET /api/v1/platform/control-plane/timeline
GET /api/v1/platform/control-plane/lineage
GET /api/v1/platform/control-plane/impact
GET /api/v1/platform/control-plane/determinism
GET /api/v1/platform/control-plane/snapshots
```

👉 These support:

| Feature           | API                       |
| ----------------- | ------------------------- |
| Object timeline   | control-plane/timeline    |
| Report lineage    | control-plane/lineage     |
| Impact analysis   | control-plane/impact      |
| Determinism proof | control-plane/determinism |
| Snapshot history  | control-plane/snapshots   |

👉 **Frontend must COMPOSE UI from these (not expect new endpoints)**

---

### 3. Report APIs (Already Emit Determinism Data)

Report responses already include:

* `determinism_hash`
* `snapshot_refs`
* `result_hash`

👉 No need to wait for new endpoints
👉 Frontend must **use existing fields**

---

### 4. Month-End / Period Close APIs

```
GET  /api/v1/monthend/
GET  /api/v1/monthend/{id}
POST /api/v1/monthend/{id}/close
```

✔ Fully implemented
✔ Includes checklist + tasks + status

👉 **Frontend can build close cockpit now**

---

### 5. COA APIs (Base Support Available)

```
GET /api/v1/coa/accounts
GET /api/v1/coa/tenant/accounts   (currently used)
```

✔ Listing works
✔ Used for account selection

---

# 🟡 Partial / Needs Extension

## 1. COA Search

```
GET /api/v1/coa/accounts?search=...
```

❌ Not implemented

👉 Needed for:

* autocomplete
* large chart of accounts UX

---

## 2. Month-End Attribution

Missing field:

```
closed_by
```

✔ Exists in DB
❌ Not exposed via API

👉 Needed for:

* audit UI
* period lock overlay

---

## 3. Job Progress

Missing fields:

* `progress`
* `percent_complete`
* `eta`
* `current_step`

👉 Current state:

* only status (queued/running/failed)

---

# 🔴 Actual Missing APIs (REAL GAPS)

## 1. Job Retry

```
POST /api/v1/platform/control-plane/jobs/{job_id}/retry
```

❌ Not implemented
❗ Explicitly marked unsupported in backend

👉 Impact:

* Retry button cannot function

---

# ❗ NOT MISSING (IMPORTANT CLARIFICATION)

The following are **NOT backend gaps**:

| Expected                    | Reality                       |
| --------------------------- | ----------------------------- |
| `/reports/{id}/determinism` | Use control-plane/determinism |
| `/reports/{id}/snapshots`   | Use control-plane/snapshots   |
| `/timeline/{object}`        | Use control-plane/timeline    |
| `/lineage/forward`          | Use control-plane/lineage     |
| `/lineage/reverse`          | Use control-plane/lineage     |

👉 These are **frontend adaptation requirements**, NOT backend work

---

# ⚠️ CRITICAL CONTRACT MISMATCHES

## 1. Report Determinism Fields

### Backend returns:

* `determinism_hash`
* `snapshot_refs`

### Frontend uses:

* `result_hash`

👉 ❌ MISMATCH

### Action:

* Update frontend types
* Use actual determinism fields

---

## 2. Close vs Monthend APIs

### Backend:

```
/api/v1/monthend/*
```

### Frontend:

```
/api/v1/close/*
```

👉 ❌ INCONSISTENT

### Action:

* Standardize on ONE
* Prefer `/monthend/*`

---

## 3. COA Endpoint Confusion

* `/coa/accounts`
* `/coa/tenant/accounts`

👉 Ownership unclear

### Action:

* Decide canonical endpoint
* Align frontend usage

---

# 🚀 FRONTEND BUILD GUIDANCE

## 🟢 Build Now (No Blockers)

* Journal module (full lifecycle)
* Intent panel (stepper + guard UI)
* Object timeline
* Lineage views
* Determinism UI
* Period close cockpit
* State badges
* Guard failure UI

---

## 🟡 Build With Limitations

* Job panel → no progress %, show spinner
* Retry button → hide or disable
* COA autocomplete → client-side filtering

---

## 🔴 Wait for Backend (Optional Enhancements)

* Job retry UX
* Progress bars
* COA search (if large datasets)
* closed_by attribution

---

# 📊 FINAL BACKEND READINESS

| Area          | Status     |
| ------------- | ---------- |
| Journals      | ✅ READY    |
| Control Plane | ✅ READY    |
| Reports       | ✅ READY    |
| Month-End     | ✅ READY    |
| COA           | ⚠️ PARTIAL |
| Jobs          | ⚠️ PARTIAL |

---

## ✅ Overall

👉 **Backend readiness: ~90–95%**

👉 **Frontend is NOT blocked**

👉 Remaining work is:

* frontend implementation
* minor contract alignment

---

# 🧾 FINAL RULES FOR FRONTEND

* Always use **Intent-first execution**
* Never bypass Control Plane
* Compose UI from **generic APIs**
* Do not demand REST-style endpoints unnecessarily
* Treat backend as **source of truth**

---

# 🔒 STATUS

**LOCKED — v1.0**

This document defines the **working contract for frontend development**.

All implementation must follow this unless explicitly updated.
