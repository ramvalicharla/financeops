---
id: FU-020
title: Complete loading.tsx skeleton coverage + EmptyState pattern unification
opened: 2026-04-27
related_to: SP-5C (Phase 5 a11y polish)
status: open
---

# FU-020 — Complete loading.tsx skeleton coverage + EmptyState unification

## Background

SP-5C applied loading.tsx skeletons to the 15 highest-traffic dashboard
routes (cap per spec). 86 routes remain uncovered. SP-5C also completed
an EmptyState sweep and found that most empty-state rendering in the
codebase uses a consistent bespoke pattern (dashed-border divs, border+
muted-bg paragraphs) rather than the `<EmptyState />` component; only
routes with bare unstyled text were in SP-5C scope.

## Part A — Deferred loading.tsx routes (86 routes)

SP-5C covered 15 of 101 routes missing `loading.tsx`. The remaining 86
were excluded by the hard cap in the SP-5C spec.

### 3 skeleton compositions already exist (inline in SP-5C files):

- **Table-shaped**: header strip + `<TableSkeleton rows cols />` — use
  for single-table pages (registers, logs, item lists)
- **Card+Table-shaped**: 3 stat cards + table — use for module overview
  pages with KPI cards + data grid
- **Card-list/checklist**: stacked card skeletons with title + status pill
  — use for checklist/approval/engagement list pages

### Notable deferred routes (high-priority within this FU):

**Entity-scoped accounting (orgSlug/entitySlug subtree):**
- `accounting/balance-sheet`, `accounting/cash-flow`, `accounting/pnl`,
  `accounting/revaluation`, `accounting/trial-balance`
  → table-shaped skeleton

**Reconciliation sub-routes:**
- `reconciliation/gl-tb`, `reconciliation/payroll`
  → table-shaped skeleton (parent `reconciliation/` already covered)

**Settings sub-pages (many):**
- `settings/`, `settings/entities`, `settings/users`, `settings/team`,
  `settings/billing`, `settings/billing/invoices`, `settings/billing/plans`,
  `settings/billing/usage`, `settings/chart-of-accounts`, `settings/coa`,
  `settings/cost-centres`, `settings/erp-mapping`, `settings/groups`,
  `settings/locations`, `settings/modules`, `settings/modules/assets`,
  `settings/modules/lease`, `settings/modules/prepaid`,
  `settings/modules/revenue`, `settings/privacy`, `settings/privacy/consent`,
  `settings/privacy/my-data`, `settings/white-label`, `settings/airlock`,
  `settings/airlock/[id]`, `settings/control-plane`
  → mix of table-shaped and card-list-shaped

**Detail/sub-routes (low priority — narrow data shape):**
- `expenses/[id]`, `fixed-assets/[id]`, `forecast/[id]`, `scenarios/[id]`,
  `advisory/fdd/[id]`, `advisory/fdd/[id]/report`, `advisory/ma/[id]`,
  `advisory/ma/[id]/documents`, `advisory/ma/[id]/valuation`,
  `advisory/ppa/[id]`, `board-pack/[id]`, `tax/[id]`, `treasury/[id]`,
  `transfer-pricing/[id]`, `prepaid/[id]`
  → detail-shaped (single entity view)

**Other top-level routes not in SP-5C's 15:**
- `director`, `partner`, `partner/earnings`, `partner/referrals`, `fx/rates`,
  `invoice-classify`, `trust`, `trust/gdpr`, `trust/gdpr/breach`,
  `trust/gdpr/consent`, `trust/soc2`, `sync/connect`, `transfer-pricing`,
  `ai`, `ai/dashboard`, `ai/anomalies`, `ai/narrative`, `ai/recommendations`,
  `search`, `erp/mappings`, `governance/audit/[engagement_id]`,
  `consolidation/runs/[id]`, `consolidation/translation`

**Modal interceptors (parallel routes — low value for loading.tsx):**
- `journals/@modal/(.)[id]`, `journals/@modal/(.)new`
  → skip; parallel routes have own loading treatment

### Estimated effort

~2–3 hours. Mechanical: pick the right skeleton shape per route, create
the file, reuse the 3 existing inline compositions. No new infrastructure.

## Part B — EmptyState pattern unification

SP-5C's EmptyState sweep found that most dashboard list pages use a
consistent bespoke empty-state pattern instead of `<EmptyState />`:
- `<div className="rounded-xl border border-dashed border-border p-6 text-sm text-muted-foreground">` — used in budget, signoff, treasury, advisory sub-pages
- `<p className="rounded-md border border-border bg-muted/20 px-3 py-4 text-sm text-muted-foreground">` — used in sync, scheduled-delivery, reports, board-pack

These were out of scope for SP-5C ("improving existing handling"). A future
unification pass could replace these with `<EmptyState />` for visual
consistency, but it requires:
1. Deciding whether to keep or remove the custom icon in `<EmptyState />`
   vs the borderless bespoke style
2. Verifying that `<EmptyState />`'s `py-12` centered layout works in each
   container context (some are inside cards/sections narrower than ideal)

### Recommended scope for this unification (if taken)

Route files with bespoke pattern ripe for replacement:
- `budget/PageClient.tsx` — dashed-border div
- `signoff/PageClient.tsx` — dashed-border paragraph
- `treasury/PageClient.tsx` — dashed-border paragraph
- `advisory/fdd/PageClient.tsx`, `advisory/ma/PageClient.tsx`,
  `advisory/ppa/PageClient.tsx` — dashed-border divs (in grid sections)
- `sync/PageClient.tsx` — border+muted-bg paragraph
- `scheduled-delivery/_components/DeliveryList.tsx` — border+muted-bg
- `reports/_components/ReportList.tsx` (2 instances) — border+muted-bg
- `board-pack/_components/BoardPackList.tsx` (2 instances) — border+muted-bg

Before doing this: review `<EmptyState />`'s visual weight in the contexts
above. Consider adding a `variant="subtle"` prop that skips `py-12` for
sub-card use cases — but that's a component change and belongs in its own PR.

### Table-cell empty states (do NOT replace with EmptyState)

`settings/team/_components/UsersPanel.tsx` and `settings/billing/PageClient.tsx`
use `<td colSpan={N}>` for table-row empty states. This is the correct
accessible pattern for tables. Do not replace with `<EmptyState />`.

## When to do

Part A (loading.tsx): any small-to-medium open slot. Mechanical work.
Part B (EmptyState unification): post-launch polish window. Requires a
design decision on `<EmptyState />` visual weight in sub-card contexts.
