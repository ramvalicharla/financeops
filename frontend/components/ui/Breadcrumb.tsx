"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"

// ---------------------------------------------------------------------------
// Segment → human-readable label
// Spec-required entries listed first; additional entries below cover routes
// whose raw segment would produce unreadable output from the fallback
// capitaliser (e.g. "kpis" → "Kpis", "pnl" → "Pnl").
// ---------------------------------------------------------------------------
const SEGMENT_LABELS: Readonly<Record<string, string>> = {
  // Spec-mandated
  dashboard: "Dashboard",
  mis: "MIS",
  reconciliation: "Reconciliation",
  "gl-tb": "GL/TB",
  close: "Close",
  anomalies: "Anomalies",
  thresholds: "Thresholds",
  payroll: "Payroll",
  consolidation: "Consolidation",
  banking: "Banking",
  far: "Fixed Assets",
  lease: "Lease Accounting",
  tax: "Tax & GST",
  "board-pack": "Board Pack",
  settings: "Settings",
  billing: "Billing",
  "org-setup": "Org Setup",
  // Additional — raw capitaliser would produce poor output
  kpis: "KPIs",
  cfo: "CFO",
  pnl: "P&L",
  erp: "ERP",
  gaap: "GAAP",
  "multi-gaap": "Multi-GAAP",
  fdd: "FDD",
  ppa: "PPA",
  ma: "M&A",
  ai: "AI",
  fx: "FX",
  "trial-balance": "Trial Balance",
  "balance-sheet": "Balance Sheet",
  "cash-flow": "Cash Flow",
  "transfer-pricing": "Transfer Pricing",
  // Common route words that read better with explicit labels
  accounting: "Accounting",
  journals: "Journals",
  reports: "Reports",
  advisory: "Advisory",
  audit: "Audit",
  signoff: "Sign Off",
  statutory: "Statutory",
  covenants: "Covenants",
  treasury: "Treasury",
  forecast: "Forecast",
  scenarios: "Scenarios",
  budget: "Budget",
  expenses: "Expenses",
  marketplace: "Marketplace",
  modules: "Modules",
  notifications: "Notifications",
  partner: "Partner",
  "fixed-assets": "Fixed Assets",
  prepaid: "Prepaid",
  "working-capital": "Working Capital",
  "invoice-classify": "Invoice Classifier",
  "scheduled-delivery": "Scheduled Delivery",
  "chart-of-accounts": "Chart of Accounts",
  "cost-centres": "Cost Centres",
  entities: "Entities",
  "erp-mapping": "ERP Mapping",
  users: "Users",
  groups: "Groups",
  privacy: "Privacy",
  "white-label": "White Label",
  sync: "Sync",
  translation: "Translation",
  runs: "Runs",
  revaluation: "Revaluation",
  checklist: "Checklist",
  director: "Director",
  variance: "Variance",
  trends: "Trends",
  ratios: "Ratios",
  logs: "Logs",
  invoices: "Invoices",
  plans: "Plans",
  usage: "Usage",
  earnings: "Earnings",
  referrals: "Referrals",
  contribute: "Contribute",
  assets: "Assets",
  revenue: "Revenue",
  new: "New",
  report: "Report",
  documents: "Documents",
  valuation: "Valuation",
  "my-templates": "My Templates",
  connectors: "Connectors",
  mappings: "Mappings",
  rates: "FX Rates",
  narrative: "Narrative",
  recommendations: "Recommendations",
  recommendations_: "Recommendations",
  dashboard_: "Dashboard",
}

// ---------------------------------------------------------------------------
// Segment filters
// ---------------------------------------------------------------------------

/** Standard UUID v4. */
const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

/** Purely numeric (e.g. budget year "2024"). */
const NUMERIC_RE = /^\d+$/

/** ISO period format "YYYY-MM" used in /close/[period]. */
const PERIOD_RE = /^\d{4}-\d{2}$/

/** Bare hex strings ≥ 12 chars — raw IDs without hyphens. */
const HEX_ID_RE = /^[0-9a-f]{16,}$/i

function isIdSegment(segment: string): boolean {
  return (
    UUID_RE.test(segment) ||
    NUMERIC_RE.test(segment) ||
    PERIOD_RE.test(segment) ||
    HEX_ID_RE.test(segment)
  )
}

// ---------------------------------------------------------------------------
// Label resolution
// ---------------------------------------------------------------------------

/** Convert a raw path segment to a display label. */
function toLabel(segment: string): string {
  const known = SEGMENT_LABELS[segment]
  if (known) return known
  // Fallback: capitalise each hyphen-separated word.
  return segment
    .split("-")
    .map((word) =>
      word.length > 0
        ? word.charAt(0).toUpperCase() + word.slice(1)
        : word,
    )
    .join(" ")
}

// ---------------------------------------------------------------------------
// Breadcrumb item construction
// ---------------------------------------------------------------------------

interface BreadcrumbItem {
  label: string
  /** Full cumulative URL path including any ID segments that were skipped
   *  in the display list. This ensures links resolve to the correct page. */
  href: string
}

function buildItems(pathname: string): BreadcrumbItem[] {
  const rawSegments = pathname.split("/").filter(Boolean)
  const items: BreadcrumbItem[] = []

  for (let i = 0; i < rawSegments.length; i++) {
    const segment = rawSegments[i]
    if (isIdSegment(segment)) {
      // Still part of the URL (included in cumulative hrefs) but not shown
      // as a standalone breadcrumb item.
      continue
    }
    items.push({
      label: toLabel(segment),
      href: "/" + rawSegments.slice(0, i + 1).join("/"),
    })
  }

  return items
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function Breadcrumb() {
  const pathname = usePathname() ?? ""

  // Hidden on the root dashboard page — only meaningful on nested routes.
  if (pathname === "/dashboard") {
    return null
  }

  const items = buildItems(pathname)

  // Nothing to display for single-segment or empty paths.
  if (items.length < 2) {
    return null
  }

  return (
    <nav aria-label="Breadcrumb">
      <ol className="flex flex-wrap items-center gap-0">
        {items.map((item, index) => {
          const isLast = index === items.length - 1
          return (
            <li key={item.href} className="flex items-center">
              {isLast ? (
                <span
                  aria-current="page"
                  className="text-sm font-medium text-foreground"
                >
                  {item.label}
                </span>
              ) : (
                <Link
                  href={item.href}
                  className="text-sm text-muted-foreground transition-colors hover:text-foreground"
                >
                  {item.label}
                </Link>
              )}
              {!isLast && (
                <span
                  aria-hidden="true"
                  className="mx-1.5 text-sm text-muted-foreground select-none"
                >
                  ›
                </span>
              )}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
