import type { LucideIcon } from "lucide-react"
import {
  AlertTriangle,
  BarChart2,
  BriefcaseBusiness,
  CalendarClock,
  CreditCard,
  FileBarChart,
  GitMerge,
  Handshake,
  Layers,
  LayoutTemplate,
  Lock,
  RefreshCw,
  ShieldCheck,
  Store,
} from "lucide-react"

export interface NavigationLeafItem {
  label: string
  href: string
  icon: LucideIcon
}

export interface NavigationGroupItem {
  label: string
  icon: LucideIcon
  children: readonly NavigationLeafItem[]
}

export type NavigationItem = NavigationLeafItem | NavigationGroupItem

export const NAV_ITEMS = [
  { label: "Dashboard", href: "/dashboard", icon: BarChart2 },
  { label: "CFO Dashboard", href: "/dashboard/cfo", icon: BarChart2 },
  { label: "KPI Analytics", href: "/dashboard/kpis", icon: FileBarChart },
  { label: "Variance Analytics", href: "/dashboard/variance", icon: FileBarChart },
  { label: "Trend Analytics", href: "/dashboard/trends", icon: FileBarChart },
  { label: "Ratio Analytics", href: "/dashboard/ratios", icon: FileBarChart },
  { label: "AI CFO Dashboard", href: "/ai/dashboard", icon: AlertTriangle },
  { label: "AI Anomalies", href: "/ai/anomalies", icon: AlertTriangle },
  { label: "AI Recommendations", href: "/ai/recommendations", icon: AlertTriangle },
  { label: "AI Narrative", href: "/ai/narrative", icon: FileBarChart },
  { label: "Sync", href: "/sync", icon: RefreshCw },
  { label: "ERP Connectors", href: "/erp/connectors", icon: RefreshCw },
  { label: "ERP Sync Jobs", href: "/erp/sync", icon: RefreshCw },
  { label: "ERP Mappings", href: "/erp/mappings", icon: GitMerge },
  {
    label: "Reconciliation",
    icon: GitMerge,
    children: [
      { label: "GL / TB", href: "/reconciliation/gl-tb", icon: GitMerge },
      { label: "Payroll", href: "/reconciliation/payroll", icon: GitMerge },
    ],
  },
  { label: "MIS", href: "/mis", icon: BarChart2 },
  { label: "Journals", href: "/accounting/journals", icon: FileBarChart },
  {
    label: "Accounting TB",
    href: "/accounting/trial-balance",
    icon: FileBarChart,
  },
  { label: "Accounting P&L", href: "/accounting/pnl", icon: FileBarChart },
  {
    label: "Accounting BS",
    href: "/accounting/balance-sheet",
    icon: FileBarChart,
  },
  { label: "Accounting CF", href: "/accounting/cash-flow", icon: FileBarChart },
  {
    label: "Accounting Revaluation",
    href: "/accounting/revaluation",
    icon: FileBarChart,
  },
  { label: "Period Close", href: "/close", icon: Lock },
  { label: "Close Checklist", href: "/close/checklist", icon: CalendarClock },
  { label: "FX Rates", href: "/fx/rates", icon: FileBarChart },
  { label: "Trial Balance", href: "/trial-balance", icon: FileBarChart },
  { label: "Consolidation", href: "/consolidation", icon: Layers },
  {
    label: "Consolidation Translation",
    href: "/consolidation/translation",
    icon: Layers,
  },
  { label: "Board Packs", href: "/board-pack", icon: LayoutTemplate },
  { label: "Reports", href: "/reports", icon: FileBarChart },
  {
    label: "Scheduled Delivery",
    href: "/scheduled-delivery",
    icon: CalendarClock,
  },
  { label: "Anomalies", href: "/anomalies", icon: AlertTriangle },
  { label: "Billing", href: "/billing", icon: CreditCard },
  { label: "Marketplace", href: "/marketplace", icon: Store },
  { label: "Partner Program", href: "/partner", icon: Handshake },
  { label: "Treasury", href: "/treasury", icon: BarChart2 },
  { label: "Industry Modules", href: "/modules", icon: Layers },
  { label: "Lease Module", href: "/modules/lease", icon: Layers },
  { label: "Revenue Module", href: "/modules/revenue", icon: Layers },
  { label: "Assets Module", href: "/modules/assets", icon: Layers },
  { label: "Prepaid Module", href: "/modules/prepaid", icon: Layers },
  { label: "Fixed Assets", href: "/fixed-assets", icon: Layers },
  { label: "Prepaid Expenses", href: "/prepaid", icon: CalendarClock },
  {
    label: "Invoice Classifier",
    href: "/invoice-classify",
    icon: AlertTriangle,
  },
  { label: "Tax", href: "/tax", icon: CreditCard },
  { label: "Covenants", href: "/covenants", icon: AlertTriangle },
  {
    label: "Transfer Pricing",
    href: "/transfer-pricing",
    icon: FileBarChart,
  },
  { label: "Signoff", href: "/signoff", icon: ShieldCheck },
  { label: "Statutory", href: "/statutory", icon: CalendarClock },
  { label: "Multi-GAAP", href: "/gaap", icon: Layers },
  { label: "Audit Portal", href: "/audit", icon: BriefcaseBusiness },
] as const satisfies readonly NavigationItem[]

export interface NavGroupDefinition {
  label: string
  hrefs: readonly string[]
}

/**
 * Maps every NAV_ITEMS entry to a labelled group for sidebar rendering.
 * Items in a group are matched by href; the Reconciliation disclosure group
 * is assigned to whichever group contains one of its children's hrefs.
 */
export const NAV_GROUP_DEFINITIONS: readonly NavGroupDefinition[] = [
  {
    label: "Financials",
    hrefs: [
      "/dashboard",
      "/dashboard/cfo",
      "/dashboard/kpis",
      "/dashboard/variance",
      "/dashboard/trends",
      "/dashboard/ratios",
      "/mis",
      "/accounting/journals",
      "/accounting/trial-balance",
      "/accounting/pnl",
      "/accounting/balance-sheet",
      "/accounting/cash-flow",
      "/accounting/revaluation",
      "/trial-balance",
      "/fx/rates",
      "/close",
      "/close/checklist",
      "/treasury",
      // Reconciliation sub-items — assigns the disclosure group to this section
      "/reconciliation/gl-tb",
      "/reconciliation/payroll",
    ],
  },
  {
    label: "Assets & Leases",
    hrefs: [
      "/fixed-assets",
      "/prepaid",
      "/modules",
      "/modules/lease",
      "/modules/revenue",
      "/modules/assets",
      "/modules/prepaid",
    ],
  },
  {
    label: "Consolidation",
    hrefs: [
      "/consolidation",
      "/consolidation/translation",
      "/gaap",
    ],
  },
  {
    label: "Tax & Compliance",
    hrefs: [
      "/tax",
      "/invoice-classify",
      "/transfer-pricing",
      "/covenants",
      "/signoff",
      "/statutory",
    ],
  },
  {
    label: "Reporting",
    hrefs: [
      "/board-pack",
      "/reports",
      "/scheduled-delivery",
      "/anomalies",
      "/ai/anomalies",
      "/ai/narrative",
      "/ai/dashboard",
      "/ai/recommendations",
    ],
  },
  {
    label: "Integrations",
    hrefs: [
      "/sync",
      "/erp/connectors",
      "/erp/sync",
      "/erp/mappings",
    ],
  },
  {
    label: "Admin",
    hrefs: [
      "/billing",
      "/marketplace",
      "/partner",
      "/audit",
    ],
  },
]

export const DIRECTOR_NAV_LABELS = [
  "Dashboard",
  "Board Packs",
  "Signoff",
  "Covenants",
  "Multi-GAAP",
  "Reports",
] as const

export const TRUST_NAV_ITEMS = [
  { label: "Trust & Compliance", href: "/trust", icon: ShieldCheck },
  { label: "SOC2", href: "/trust/soc2", icon: ShieldCheck },
  { label: "GDPR", href: "/trust/gdpr", icon: ShieldCheck },
] as const satisfies readonly NavigationLeafItem[]

export const ADVISORY_NAV_ITEMS = [
  { label: "Advisory Services", href: "/advisory", icon: BriefcaseBusiness },
  { label: "FDD", href: "/advisory/fdd", icon: BriefcaseBusiness },
  { label: "PPA", href: "/advisory/ppa", icon: BriefcaseBusiness },
  { label: "M&A", href: "/advisory/ma", icon: BriefcaseBusiness },
] as const satisfies readonly NavigationLeafItem[]

export const SETTINGS_NAV_ITEMS = [
  { label: "Display & Formatting", href: "/settings", icon: Lock },
  {
    label: "Chart of Accounts",
    href: "/settings/chart-of-accounts",
    icon: Layers,
  },
  { label: "CoA Uploads", href: "/settings/coa", icon: Layers },
  { label: "ERP Mapping", href: "/settings/erp-mapping", icon: GitMerge },
  { label: "Airlock", href: "/settings/airlock", icon: ShieldCheck },
  { label: "Control Plane", href: "/settings/control-plane", icon: ShieldCheck },
  {
    label: "Groups & Entities",
    href: "/settings/groups",
    icon: BriefcaseBusiness,
  },
  { label: "Users & Roles", href: "/settings/users", icon: BriefcaseBusiness },
  { label: "Privacy Settings", href: "/settings/privacy", icon: Lock },
  { label: "White Label", href: "/settings/white-label", icon: Lock },
] as const satisfies readonly NavigationLeafItem[]

export const ADMIN_NAV_ITEMS = [
  { label: "Admin Console", href: "/admin", icon: ShieldCheck },
  { label: "Tenants", href: "/admin/tenants", icon: ShieldCheck },
  { label: "Users", href: "/admin/users", icon: ShieldCheck },
  { label: "RBAC", href: "/admin/rbac", icon: ShieldCheck },
  { label: "Flags", href: "/admin/flags", icon: ShieldCheck },
  { label: "Modules", href: "/admin/modules", icon: ShieldCheck },
] as const satisfies readonly NavigationLeafItem[]

export const TOPBAR_PAGE_TITLES = {
  "/sync": "Sync",
  "/sync/connect": "Connect Source",
  "/reconciliation/gl-tb": "GL / TB Reconciliation",
  "/reconciliation/payroll": "Payroll Reconciliation",
  "/mis": "MIS Dashboard",
  "/consolidation": "Multi-Entity Consolidation",
  "/board-pack": "Board Packs",
  "/reports": "Custom Reports",
  "/scheduled-delivery": "Scheduled Delivery",
  "/scheduled-delivery/logs": "Delivery Logs",
  "/anomalies": "Anomaly Detection",
  "/anomalies/thresholds": "Anomaly Thresholds",
  "/onboarding": "Workspace Onboarding",
  "/billing": "Billing",
  "/notifications": "Notifications",
  "/treasury": "Treasury",
  "/tax": "Tax Provision",
  "/covenants": "Debt Covenants",
  "/transfer-pricing": "Transfer Pricing",
  "/signoff": "Digital Signoff",
  "/statutory": "Statutory Compliance",
  "/gaap": "Multi-GAAP",
  "/audit": "Audit Portal",
} as const
