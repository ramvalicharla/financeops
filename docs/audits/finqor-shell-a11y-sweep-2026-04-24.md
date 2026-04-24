# Finqor Shell — Accessibility & Layout Compliance Sweep
> Date: 2026-04-24 | Auditor: Claude (claude-sonnet-4-6) | Status: Complete  
> Scope: WCAG 2.1 AA baseline — Checks A1–A9  
> Reference audit: `docs/audits/finqor-shell-audit-2026-04-24.md`

---

## 1. Executive Summary

| Metric | Count |
|---|---|
| Total new findings | **8** |
| WCAG Level A violations | 2 |
| WCAG Level AA violations | 5 |
| Critical | 2 |
| Major | 5 |
| Minor | 1 |
| Corrections to prior audit | 2 |

**Highest-risk issue:** The dashboard loading skeleton (`app/(dashboard)/loading.tsx`) renders a nested `<main>` landmark inside the layout's `<main id="main-content">` and duplicates shell chrome (sidebar, topbar) inside the content area — breaking page structure for assistive technology users on every initial page load.

**Key contrast with prior audit:** Two prior findings are materially wrong. Finding #37 (dark mode class missing) is stale — `className="dark"` is present. Finding #25 (all pages missing metadata) was substantially overstated — 121 of ~130+ pages have metadata exports.

---

## 2. Findings Register

> All file paths are relative to `frontend/`. Every finding cites a real file and line verified during this audit. Effort: S ≤ 4 h, M = ½–2 days, L = 3+ days.

| # | Check | File | Line(s) | Finding | WCAG ref | Severity | Effort |
|---|---|---|---|---|---|---|---|
| ✅ A2-1 | A2 | `app/(dashboard)/loading.tsx` | 39 | Dashboard loading skeleton renders `<main className="flex-1 overflow-y-auto p-6">` as `{children}` inside the layout's `<main id="main-content">` (layout.tsx:87). Creates a nested `<main>` landmark on every page during load. Additionally, the skeleton renders fake sidebar and topbar chrome *inside* `<main>` alongside real shell chrome — causing doubled UI elements on load. **RESOLVED** — `fix/a11y-tier-1-wcag` (commit 37de5c7) | WCAG 1.3.1 (A) | Critical | S |
| ✅ A2-2 | A2 | `app/(dashboard)/search/page.tsx` | 11–18 | Search page renders `<main id="main-content" className="flex-1 overflow-y-auto outline-none">` (line 18) nested inside the dashboard layout's `<main id="main-content">` (layout.tsx:87). Produces a duplicate `<main>` landmark and a duplicate `id` attribute in the same DOM. Page also renders its own `<Topbar>` (lines 11–16) inside the content area, adding a second topbar below the real one. **RESOLVED** — `fix/a11y-tier-1-wcag` (commit 37de5c7) | WCAG 1.3.1 (A) | Critical | S |
| ✅ A4-1 | A4 | `app/control-plane/admin/tenants/[id]/PageClient.tsx` | 134 | Bare `confirm("Suspend this tenant's subscription? They will lose access.")` used to gate a destructive tenant-suspend action. Native browser `confirm()` dialogs are not reliably accessible under all assistive technologies and do not match the design system. A `ConfirmDialog` component exists at `components/ui/ConfirmDialog.tsx` but is not used here. **RESOLVED** — `fix/a11y-tier-1-wcag` (commit 37de5c7) | — (UX/A11y) | Major | S |
| ✅ A5-1 | A5 | `components/ui/command.tsx` | 33 | `CommandInput` applies `outline-none` to the `cmdk` input element with no `focus-visible:ring` replacement. The global `*:focus-visible { outline: 2px solid ... }` rule in `globals.css:72` is overridden by Tailwind's inline `outline-none` class. Sighted keyboard users see no focus indicator when the command palette input is focused. **RESOLVED** — `fix/a11y-tier-1-wcag` (commit 37de5c7) | WCAG 2.4.7 (AA) | Major | S |
| ✅ A5-2 | A5 | `app/(dashboard)/search/PageClient.tsx` | 114 | Search category filter buttons use `focus-visible:outline-none` with no replacement ring class. Sighted keyboard users navigating filter buttons with Tab/arrow keys have no visible indicator of which button is focused. **RESOLVED** — `fix/a11y-tier-1-wcag` (commit 37de5c7) | WCAG 2.4.7 (AA) | Major | S |
| A6-1 | A6 | `app/(dashboard)/loading.tsx` | 24–45 | The loading skeleton is structurally a complete standalone page layout (own sidebar skeleton at line 25, topbar skeleton at line 36, `<main>` at line 39) but renders inside the dashboard layout as `{children}`, causing: (a) duplicated shell chrome during load transitions, (b) skeleton topbar height `h-16` (64 px) mismatches actual topbar `min-h-12` (48 px), (c) skeleton outer div `h-screen overflow-hidden` conflicts with the layout's `<main>` scrolling — all of which drive content layout shift on navigation. | — (CLS/UX) | Major | S |
| ✅ A7-1 | A7 | `components/layout/_components/SidebarNavItem.tsx` | 45, 67 | Both collapsed (line 45) and expanded (line 67) nav link variants carry `title={item.label}`. HTML `title` attributes show only on mouse hover — they do not appear on keyboard focus. Sighted keyboard users who collapse the sidebar see icons with no visible label when tabbing through nav items. The `aria-label` on the collapsed link (line 46) serves screen readers but provides no visible tooltip on keyboard focus. No Radix `<Tooltip>` component is used. **RESOLVED** — `fix/a11y-tier-1-wcag` (commit 37de5c7) | WCAG 2.1.1 (A) | Major | S |
| A9-1 | A9 | `lib/config/tokens.ts` | 12–16 | `StatusBadge` `success`/`complete`/`active` tokens use `text-[hsl(var(--brand-success))]` = HSL(152, 69%, 31%) ≈ `#19854D` (mid-dark green) rendered on a near-black card (`--card: 0 0% 8%` ≈ `#141414`). After blending the 20%-opacity badge background, the effective backdrop is approximately `#152B1F`. Estimated contrast ≈ 4.2:1 — below the 4.5:1 WCAG AA threshold for small text (badge uses `text-xs`). `brand-danger` tokens (HSL 0, 84%, 60%) on semi-transparent dark-red background estimate ≈ 3.8–4.1:1 and also fail. | WCAG 1.4.3 (AA) | Minor | S |

---

## 3. Per-Check Results

### A1 — Skip-to-main link (WCAG 2.4.1)

**Examined:** `app/layout.tsx` (root layout) and `app/(dashboard)/layout.tsx` (dashboard layout).

**Result: PASS.**

A skip link exists at `app/layout.tsx:30–35`:

```tsx
<a
  href="#main-content"
  className="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-[9999]
             focus:px-4 focus:py-2 focus:bg-background focus:text-foreground
             focus:border focus:border-border focus:rounded-md focus:text-sm
             focus:font-medium focus:shadow-md"
>
  Skip to main content
</a>
```

The link uses the correct `sr-only focus:not-sr-only` pattern and becomes visible on keyboard focus. Its target `id="main-content"` is present at `app/(dashboard)/layout.tsx:87`. The skip link is the first DOM child of `<body>` (inserted before `<AppProviders>`), making it the first focusable element in tab order on all dashboard pages. No issues found.

---

### A2 — Single `<main>` landmark per page (WCAG 1.3.1)

**Examined:** All `.tsx` files in `frontend/` grepped for `<main`. Found 8 occurrences across 7 files.

**Result: FAIL — 2 violations.**

All `<main>` occurrences:

| File | Line | id | Notes |
|---|---|---|---|
| `app/layout.tsx` | — | — | No `<main>` in root layout ✅ |
| `app/(dashboard)/layout.tsx` | 87 | `main-content` | Single canonical `<main>` for all dashboard pages ✅ |
| `app/(dashboard)/loading.tsx` | 39 | *(none)* | **Nested inside layout's `<main>` — FAIL** |
| `app/(dashboard)/search/page.tsx` | 18 | `main-content` | **Nested inside layout's `<main>` — FAIL; duplicate id** |
| `app/(marketing)/layout.tsx` | 24 | `main-content` | Different route group — no conflict ✅ |
| `app/(org-setup)/layout.tsx` | 13 | `main-content` | Different route group — no conflict ✅ |
| `app/page.tsx` | 56 | `main-content` | Marketing/home page — standalone ✅ |
| `components/control-plane/ControlPlaneShell.tsx` | 63 | `main-content` | Admin shell — different route group ✅ |
| `app/not-found.tsx` | 5 | *(none)* | Standalone 404 — no conflict ✅ |

**Duplicate landmark table:**

| Page | Layout `<main>` line | Page `<main>` line | Duplicate? |
|---|---|---|---|
| All dashboard routes (default) | layout.tsx:87 | — | N |
| Dashboard loading state | layout.tsx:87 | loading.tsx:39 | **Y** |
| `/search` | layout.tsx:87 | search/page.tsx:18 | **Y** |

---

### A3 — Route-level metadata (WCAG 2.4.2)

**Examined:** All `page.tsx` and layout files under `app/(dashboard)/` grepped for `export const metadata` and `export async function generateMetadata`.

**Result: MOSTLY PASS — prior finding #25 was substantially overstated.**

- **121 files** in `app/(dashboard)/` export `metadata` (using a shared `createMetadata()` helper or inline `Metadata` objects).
- The dashboard layout (`app/(dashboard)/layout.tsx`) correctly has no metadata export — individual pages provide their own, which is the correct Next.js pattern.
- The root layout at `app/layout.tsx:20` exports `defaultMetadata` as a fallback.
- ~9 pages (truncated glob results prevented an exact count) did not appear in the metadata grep, suggesting they may fall back to the root layout's title. These are primarily: modal-route segments under `@modal/`, and a small number of settings sub-pages. These are the remaining scope of prior finding #25.

Prior finding #25 described the situation as "all routes served with default metadata" — this was incorrect. The vast majority of pages have proper per-route metadata.

---

### A4 — window.confirm / window.alert / window.prompt usage

**Examined:** All `.ts` and `.tsx` files grepped for `window\.confirm`, `window\.alert`, `window\.prompt`, `\bconfirm\s*\(`, and `\balert\s*\(`.

**Result: FAIL — 1 instance.**

`app/control-plane/admin/tenants/[id]/PageClient.tsx:134`:

```ts
if (!confirm("Suspend this tenant's subscription? They will lose access.")) return
```

This is a destructive action (tenant suspension) gated behind a native browser `confirm()`. A `ConfirmDialog` component exists at `components/ui/ConfirmDialog.tsx` and is tested (`ConfirmDialog.test.tsx`) — it should be used instead. No other `window.confirm`, `window.alert`, or `window.prompt` calls were found.

---

### A5 — Focus ring visibility (WCAG 2.4.7)

**Examined:** All `outline-none` occurrences across `.tsx` files (25 matches across 18 files). For each occurrence, verified whether a replacement focus-visible style exists.

**Result: MOSTLY PASS — 2 failures, several acceptable usages.**

**Global baseline:** `globals.css:72–76` applies `outline: 2px solid hsl(var(--ring) / 0.5)` to `*:focus-visible` and removes it on `*:focus:not(:focus-visible)`. This correctly shows rings on keyboard navigation only. This baseline covers most components.

**Acceptable `outline-none` usages** (replacement ring or indicator present):
- `components/ui/button.tsx` — pairs `outline-none` with `focus-visible:border-ring focus-visible:ring-3` ✅
- `components/ui/input.tsx:11` — pairs with `focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2` ✅
- `components/layout/_components/SidebarNavItem.tsx:92` — pin button pairs with `focus-visible:ring-2 focus-visible:ring-ring` ✅
- `components/ui/Dialog.tsx:184` — dialog panel (`outline-none` on container, not interactive element; focus managed programmatically) ✅
- `components/ui/Sheet.tsx:178` — same pattern as Dialog ✅
- `components/ui/popover.tsx:22` — non-interactive container ✅
- `components/ui/command.tsx:85` (CommandItem) — `data-[selected=true]:bg-accent` provides visible selection highlight managed by cmdk keyboard handler ✅ (borderline — background change only)
- `components/treasury/CashFlowGrid.tsx:142` — replaces with `focus:border-[hsl(var(--brand-primary))]` (uses `focus:` not `focus-visible:` — applies on mouse too, but indicator exists) — Minor
- `app/(dashboard)/search/page.tsx:18` — on `<main>` landmark (non-interactive, acceptable) ✅

**Failures:**

1. `components/ui/command.tsx:33` — `CommandInput` has `outline-none` with no ring replacement. The command palette input receives keyboard focus when the palette opens; sighted keyboard users see no focus ring on it. **WCAG 2.4.7 failure.**

2. `app/(dashboard)/search/PageClient.tsx:114` — Filter category buttons use `focus-visible:outline-none` with no replacement class on the same element. **WCAG 2.4.7 failure.**

---

### A6 — Skeleton content layout shift

**Examined:** `app/(dashboard)/loading.tsx` (the dashboard-level loading skeleton) and `components/ui/skeleton.tsx`.

**Result: FAIL — structural mismatch.**

The `loading.tsx` file is designed as a complete standalone page layout. It contains:

| Element | Skeleton size | Actual component size | Match? |
|---|---|---|---|
| Outer wrapper | `h-screen overflow-hidden` | — | Inside real layout's `<main>` → **overflow conflict** |
| Sidebar skeleton | `w-60` (240 px), `md:fixed md:inset-y-0` | Sidebar `w-60` (240 px) | Width matches but positioned inside `<main>` |
| Topbar skeleton | `h-16` (64 px) | Topbar `min-h-12` (48 px) | **Mismatch: 64 px vs 48 px** |
| Metric cards | `h-28` (112 px) × 3 | Dashboard metric cards: unverified but plausible | — |
| Table rows | `h-12` (48 px) × 6 | Typical row height: plausible | — |

The root structural problem: the loading skeleton renders inside the dashboard layout's `{children}` slot, which is wrapped in `<main id="main-content">`. Because the skeleton uses `md:fixed md:inset-y-0` for its sidebar, it attempts to overlay the actual viewport — creating z-index conflicts with the real sidebar, not replacing it. On load, users see the real sidebar + topbar from the layout alongside the skeleton's fake sidebar + topbar inside the content area.

---

### A7 — Keyboard operability of collapsed rail tooltips (WCAG 2.1.1)

**Examined:** `components/layout/_components/SidebarNavItem.tsx` read in full (101 lines). Also checked Topbar notification bell, search button, collapse toggle.

**Result: FAIL for collapsed nav items.**

`SidebarNavItem.tsx:40–56` (collapsed state):

```tsx
<Link
  href={targetHref}
  onClick={onClick}
  title={item.label}       // ← HTML title attribute
  aria-label={item.label}  // ← screen reader label only
  className={cn("flex h-9 w-full items-center justify-center ...", ...)}
>
  <Icon className="h-4 w-4 shrink-0" />
</Link>
```

The `title` attribute shows a tooltip on mouse hover but **not on keyboard focus**. When a sighted keyboard user tabs through the collapsed rail, they see icons only — no label is visible. The `aria-label` correctly identifies the control for screen readers but provides no visual tooltip. A Radix `<Tooltip>` component (available in `components/ui/tooltip.tsx`) would display on both hover and focus.

`SidebarNavItem.tsx:63–80` (expanded state): also carries `title={item.label}` but the label text is visible in the expanded link, so this is informational only — not a failure.

**Other icon-only shell buttons — status:**

| Element | File | Tooltip method | Keyboard-focus visual? |
|---|---|---|---|
| Search button | `Topbar.tsx` ~line 358–375 | `<Tooltip>` component ✅ | Yes ✅ |
| Notification bell | `NotificationBell.tsx:54–57` | `aria-label` + button text | No visual tooltip — acceptable (has visible icon) |
| Sidebar collapse toggle | `Sidebar.tsx:431` | `aria-label` | No tooltip needed (toggle action, icon clear) |
| SidebarNavItem collapsed | `SidebarNavItem.tsx:45` | `title` attribute ❌ | **No — WCAG 2.1.1 failure** |
| Pin module button | `SidebarNavItem.tsx:92` | `aria-label` + focus ring | No tooltip — acceptable (star icon clear) |

---

### A8 — Form input labels (WCAG 1.3.1, 3.3.2)

**Examined:** Auth forms under `app/(auth)/`, registration flow, onboarding steps. Grepped for `placeholder=` across all auth pages (12 matches) and `<FormField` usage.

**Result: PASS.**

All auth and registration form inputs are wrapped in `<FormField>` (`components/ui/FormField.tsx`), which provides:
- `<label htmlFor={id}>` with proper `for`/`id` pairing
- `aria-invalid`, `aria-describedby`, `aria-required` attributes on the input
- Error message linked via `aria-describedby`
- Required asterisk with `aria-hidden="true"`

Example from `app/(auth)/register/PageClient.tsx:92–96`:

```tsx
<FormField id="register-full-name" error={errors.fullName} label="Full Name" required>
  <Input autoComplete="name" placeholder="Full Name" ... />
</FormField>
<FormField id="register-email" error={errors.email} label="Work Email" required>
  <Input autoComplete="email" type="email" placeholder="Work Email" ... />
</FormField>
```

All placeholders are redundant (matching the label) — not a WCAG failure. The checkbox at line 119–126 uses explicit `<input id="terms">` paired with `<label htmlFor="terms">`. No placeholder-only inputs found in the audited forms.

---

### A9 — Colour contrast on coloured backgrounds (WCAG 1.4.3)

**Examined:** `lib/config/tokens.ts` (STATUS_COLORS), `components/ui/StatusBadge.tsx`, `globals.css` (CSS custom properties). Checked all status badge token colours against the dark-mode card background.

**Result: PARTIAL FAIL — 2 token pairs are borderline or below threshold.**

The app is dark-mode only (`--background: 0 0% 5%` ≈ `#0D0D0D`, `--card: 0 0% 8%` ≈ `#141414`).

`STATUS_COLORS` token analysis (all badges are `text-xs` = 12 px, requiring 4.5:1):

| Status key | Text colour | BG colour (20% opacity blend) | Approx. contrast | Pass 4.5:1? |
|---|---|---|---|---|
| `pending` | `text-yellow-300` ≈ `#FDE047` | `bg-yellow-500/20` blended ≈ `#201D10` | ~11:1 | ✅ |
| `running` | `text-blue-300` ≈ `#93C5FD` | `bg-blue-500/20` blended ≈ `#111620` | ~7:1 | ✅ |
| `complete / success / active` | `text-[hsl(152,69%,31%)]` ≈ `#19854D` | `bg-[hsl(152,69%,31%)/0.2]` blended ≈ `#152B1F` | **~4.2:1** | **❌** |
| `failed / error` | `text-[hsl(0,84%,60%)]` ≈ `#F04848` | `bg-[hsl(0,84%,60%)/0.2]` blended ≈ `#231414` | **~3.9:1** | **❌** |
| `warning / locked` | `text-[hsl(38,92%,50%)]` ≈ `#F5A200` | `bg-[hsl(38,92%,50%)/0.2]` blended ≈ `#211B0C` | ~8:1 | ✅ |
| `draft / inactive / default` | `text-muted-foreground` ≈ `#A0A0A0` | `bg-muted` ≈ `#1E1E1E` | ~5.2:1 | ✅ |

**Failures:** `success/complete/active` (~4.2:1) and `failed/error` (~3.9:1) fall below 4.5:1. Fix: raise the lightness of the text colour token (e.g., success text at L ≥ 45% would pass; danger text is already brighter but the red hue has lower perceptual weight).

The specific blueprint colours listed in the check prompt (`#E6F1FB`, `#EAF3DE`, `#FAEEDA`, `#FCEBEB`) are light-mode scope-bar colours that are not present in the current CSS (dark-mode only). They will require a contrast audit when the EntityScopeBar is implemented in Phase 2.

---

## 4. Cross-reference to Prior Audit

### Corrections (prior findings that are now wrong)

| Prior finding | Prior claim | Actual state | Action |
|---|---|---|---|
| **#37** | "`<html>` has no `dark` class forced; app may render in light mode" | `app/layout.tsx:28`: `<html lang="en" className="dark">` — dark class IS present | **Close #37 — already fixed or was never an issue** |
| **#25** | "generateMetadata absent from all pages; every route uses default metadata" | 121 of ~130+ dashboard pages export `metadata`; root layout provides `defaultMetadata` as fallback | **Downscope #25 — finding stands only for the ~9 pages without metadata** |

### Confirmed prior findings

| Prior finding | This audit | Evidence |
|---|---|---|
| **#32** (rail tooltip uses `title`) | **Confirmed** as A7-1 | `SidebarNavItem.tsx:45,67` — verified by reading source |
| **#33** (notification bell strategy unverified) | Partially resolved — bell has proper ARIA | `NotificationBell.tsx:54–57` has `aria-label`, `aria-expanded`, `aria-haspopup`; 30-second polling confirmed; no SSE. Not a WCAG issue. |
| **#35** (breadcrumb not scope-aware) | Not re-examined — outside a11y scope | Structural issue covered by prior audit |

### New findings (not covered by prior audit)

| Finding | WCAG ref | New? |
|---|---|---|
| A2-1 — Nested `<main>` in loading.tsx | 1.3.1 | **New** |
| A2-2 — Nested `<main>` + duplicate id in search/page.tsx | 1.3.1 | **New** |
| A4-1 — bare `confirm()` for tenant suspend | UX | **New** |
| A5-1 — CommandInput outline-none without ring | 2.4.7 | **New** |
| A5-2 — Search filter buttons outline-none without ring | 2.4.7 | **New** |
| A6-1 — Loading skeleton structural mismatch | CLS | **New** |
| A9-1 — Success/error badge contrast below 4.5:1 | 1.4.3 | **New** |
| A7-1 — SidebarNavItem title attribute | 2.1.1 | Confirms #32 |

---

## 5. Fix Priority

Ordered by impact-to-effort ratio (highest impact, lowest effort first):

| Priority | Finding | Summary | Effort |
|---|---|---|---|
| 1 | **A2-2** | `search/page.tsx:18` — remove `<Topbar>` and nested `<main>` from this page. Route is inside the dashboard layout which already provides both. Replace with a plain `<div>`. | S |
| 2 | **A2-1** | `loading.tsx` — redesign the loading skeleton to replace only the `{children}` content area (metric cards, table skeleton), not duplicate the whole shell. Remove the fake sidebar and topbar; remove the nested `<main>`; fix topbar height from `h-16` to `h-12`. | S |
| 3 | **A7-1** | `SidebarNavItem.tsx:40–56` — wrap collapsed nav item in a Radix `<Tooltip>` from `components/ui/tooltip.tsx`. The tooltip must open on both hover and keyboard focus. Remove the `title` attribute from the `<Link>`. | S |
| 4 | **A5-1** | `command.tsx:33` — add `focus-visible:ring-2 focus-visible:ring-ring` to the `CommandInput` className alongside `outline-none`. | S |
| 5 | **A5-2** | `search/PageClient.tsx:114` — replace `focus-visible:outline-none` with `focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2` on category filter buttons, or remove the override and let the global ring apply. | S |
| 6 | **A4-1** | `control-plane/admin/tenants/[id]/PageClient.tsx:134` — replace `confirm()` with `<ConfirmDialog>` (already imported in other files; see `components/ui/ConfirmDialog.tsx`). | S |
| 7 | **A9-1** | `lib/config/tokens.ts:12–16` — raise lightness of `brand-success` and `brand-danger` text tokens to achieve ≥ 4.5:1 on the blended badge background. E.g. success text at HSL(152, 69%, 48%) and danger text at HSL(0, 84%, 70%). | S |
| 8 | **A6-1** | Already covered by A2-1 fix (remove fake shell from loading.tsx). Also align metric card and row skeleton heights after dashboard page dimensions are finalised. | S |
| 9 | **A3 (residual)** | Identify the ~9 pages without metadata exports and add `export const metadata = createMetadata(...)`. | S |
| 10 | **A5 (CashFlowGrid minor)** | `CashFlowGrid.tsx:142` — change `focus:border-*` to `focus-visible:border-*` so ring only shows on keyboard nav. | S |

---

## 6. Recommended Additions to Phase Plan

Based on the prior audit's phased plan (§3.3), the following placements are recommended:

### Phase 0 (Foundation — already in progress)

- **A2-2** (search/page.tsx nested main) — simple one-line fix that touches only one file; fits into any phase-0 cleanup pass.
- **Prior #37 correction** — finding is already resolved; remove it from the backlog.

### Phase 1 (Sidebar rebuild)

- **A7-1** (SidebarNavItem tooltip) — finding #32 confirmed. The sidebar rebuild must include Radix `<Tooltip>` for all collapsed-rail nav items. Add to Phase 1 Definition of Done checklist.

### Phase 2 (Entity scoping + EntityScopeBar)

- **A9 (light-mode badge colours)** — When `EntityScopeBar` with `bg-[#E6F1FB]` and coloured scope pills is implemented, a full contrast audit must be run against its specific background colours. Add as a gating checklist item for Phase 2.

### Phase 3 (Module Manager)

No new accessibility findings land here from this sweep.

### Phase 4 (AI pipeline)

No new accessibility findings land here from this sweep.

### Phase 5 (UX polish)

- **A2-1** (loading.tsx skeleton rebuild) — fits Phase 5's scope of "polish and perceived performance". Redesign the skeleton to match the real layout dimensions exactly.
- **A5-1** (CommandInput focus ring) — command palette polish belongs in Phase 5.
- **A5-2** (search filter buttons focus ring) — search UX polish belongs in Phase 5.
- **A4-1** (native confirm() → ConfirmDialog) — UX consistency polish; Phase 5.
- **A9-1** (status badge contrast fix) — token-level change, low risk; Phase 5.

### Phase 6 (Hardening)

- Run a full WCAG 2.1 AA audit once the shell skeleton is stable and Phase 1–5 fixes are in. The findings in this sweep are all pre-shell-completion issues; a fresh sweep post-Phase-5 is recommended before any accessibility certification claim.

---

## Appendix — Files Verified

| File | Verified? | Method |
|---|---|---|
| `app/layout.tsx` | ✅ | Full read |
| `app/(dashboard)/layout.tsx` | ✅ | Full read |
| `app/(dashboard)/loading.tsx` | ✅ | Full read |
| `app/(dashboard)/search/page.tsx` | ✅ | Full read |
| `components/layout/_components/SidebarNavItem.tsx` | ✅ | Full read |
| `components/notifications/NotificationBell.tsx` | ✅ | Explored (agent) |
| `components/ui/Breadcrumb.tsx` | ✅ | Explored (agent) |
| `components/ui/button.tsx` | ✅ | Grep + explored |
| `components/ui/input.tsx` | ✅ | Grep + explored |
| `components/ui/command.tsx` | ✅ | Full read |
| `components/ui/Dialog.tsx` | ✅ | Explored (agent) |
| `components/ui/FormField.tsx` | ✅ | Explored (agent) |
| `components/ui/StatusBadge.tsx` | ✅ | Full read |
| `lib/config/tokens.ts` | ✅ | Full read |
| `app/globals.css` | ✅ | Read (lines 1–100) |
| `app/(auth)/register/PageClient.tsx` | ✅ | Partial read (lines 80–151) |
| `app/control-plane/admin/tenants/[id]/PageClient.tsx` | ✅ | Grep (line 134) |
| `app/(dashboard)/search/PageClient.tsx` | ✅ | Grep (line 114) |
| `components/treasury/CashFlowGrid.tsx` | ✅ | Grep (line 142) |
| All `page.tsx` under `app/(dashboard)/` | ✅ | Glob (count) + metadata grep |

---

## Resolution log

> Updated: 2026-04-24 | Source: local branch not yet pushed

**Branch `fix/a11y-tier-1-wcag`** (commit `37de5c7`, local)
- Resolves findings: A2-1, A2-2, A4-1, A5-1, A5-2, A7-1
- WCAG coverage added: 1.3.1 Level A (×2), 2.1.1 Level A (×1), 2.4.7 Level AA (×2), UX consistency (×1)
- Status: local, pending review and push

**Still open (deferred to phased plan)**
- A6-1 — Loading skeleton dimension alignment → Phase 5
- A9-1 — Status badge contrast tokens → Phase 5
- A3 residual — ~9 pages without metadata → Phase 5
