export interface ControlPlaneModuleTab {
  key: string
  label: string
  href: string
  matchPrefixes: string[]
}

export const CONTROL_PLANE_MODULE_TABS: readonly ControlPlaneModuleTab[] = [
  {
    key: "dashboard",
    label: "Dashboard",
    href: "/dashboard",
    matchPrefixes: ["/dashboard", "/ai"],
  },
  {
    key: "erp",
    label: "ERP",
    href: "/erp/sync",
    matchPrefixes: ["/erp", "/sync", "/erp-sync"],
  },
  {
    key: "accounting",
    label: "Accounting",
    href: "/accounting/journals",
    matchPrefixes: ["/accounting", "/fx"],
  },
  {
    key: "reconciliation",
    label: "Reconciliation",
    href: "/reconciliation/gl-tb",
    matchPrefixes: ["/reconciliation", "/bank-recon", "/normalization", "/payroll-gl-reconciliation"],
  },
  {
    key: "close",
    label: "Close",
    href: "/close/checklist",
    matchPrefixes: ["/close", "/monthend"],
  },
  {
    key: "reports",
    label: "Reports",
    href: "/reports",
    matchPrefixes: ["/reports", "/board-pack", "/mis"],
  },
  {
    key: "settings",
    label: "Settings",
    href: "/settings",
    matchPrefixes: ["/settings", "/billing", "/modules", "/admin"],
  },
] as const

export const resolveControlPlaneModule = (pathname: string): ControlPlaneModuleTab => {
  return (
    CONTROL_PLANE_MODULE_TABS.find((item) =>
      item.matchPrefixes.some((prefix) => pathname.startsWith(prefix)),
    ) ?? CONTROL_PLANE_MODULE_TABS[0]
  )
}
