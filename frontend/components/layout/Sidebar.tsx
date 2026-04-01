"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { useEffect, useMemo, useState } from "react"
import { signOut } from "next-auth/react"
import {
  AlertTriangle,
  BarChart2,
  CalendarClock,
  ChevronDown,
  CreditCard,
  BriefcaseBusiness,
  Store,
  Handshake,
  FileBarChart,
  GitMerge,
  LayoutTemplate,
  Layers,
  Lock,
  RefreshCw,
  ShieldCheck,
} from "lucide-react"
import type { EntityRole } from "@/types/api"
import { useTenantStore } from "@/lib/store/tenant"
import { useUIStore } from "@/lib/store/ui"
import { EntitySwitcher } from "@/components/layout/EntitySwitcher"
import { Button } from "@/components/ui/button"
import type { UserRole } from "@/lib/auth"
import { cn } from "@/lib/utils"

const navItems = [
  { label: "Dashboard", href: "/dashboard", icon: BarChart2 },
  { label: "Sync", href: "/sync", icon: RefreshCw },
  { label: "ERP Connectors", href: "/erp/connectors", icon: RefreshCw },
  { label: "ERP Sync Jobs", href: "/erp/sync", icon: RefreshCw },
  { label: "ERP Mappings", href: "/erp/mappings", icon: GitMerge },
  {
    label: "Reconciliation",
    icon: GitMerge,
    children: [
      { label: "GL / TB", href: "/reconciliation/gl-tb" },
      { label: "Payroll", href: "/reconciliation/payroll" },
    ],
  },
  { label: "MIS", href: "/mis", icon: BarChart2 },
  { label: "Journals", href: "/accounting/journals", icon: FileBarChart },
  { label: "Accounting TB", href: "/accounting/trial-balance", icon: FileBarChart },
  { label: "Accounting P&L", href: "/accounting/pnl", icon: FileBarChart },
  { label: "Accounting BS", href: "/accounting/balance-sheet", icon: FileBarChart },
  { label: "Accounting CF", href: "/accounting/cash-flow", icon: FileBarChart },
  { label: "Accounting Revaluation", href: "/accounting/revaluation", icon: FileBarChart },
  { label: "Period Close", href: "/close", icon: Lock },
  { label: "Close Checklist", href: "/close/checklist", icon: CalendarClock },
  { label: "FX Rates", href: "/fx/rates", icon: FileBarChart },
  { label: "Trial Balance", href: "/trial-balance", icon: FileBarChart },
  { label: "Consolidation", href: "/consolidation", icon: Layers },
  { label: "Consolidation Translation", href: "/consolidation/translation", icon: Layers },
  { label: "Board Packs", href: "/board-pack", icon: LayoutTemplate },
  { label: "Reports", href: "/reports", icon: FileBarChart },
  { label: "Scheduled Delivery", href: "/scheduled-delivery", icon: CalendarClock },
  { label: "Anomalies", href: "/anomalies", icon: AlertTriangle },
  { label: "Billing", href: "/billing", icon: CreditCard },
  { label: "Marketplace", href: "/marketplace", icon: Store },
  { label: "Partner Program", href: "/partner", icon: Handshake },
  { label: "Treasury", href: "/treasury", icon: BarChart2 },
  { label: "Fixed Assets", href: "/fixed-assets", icon: Layers },
  { label: "Prepaid Expenses", href: "/prepaid", icon: CalendarClock },
  { label: "Invoice Classifier", href: "/invoice-classify", icon: AlertTriangle },
  { label: "Tax", href: "/tax", icon: CreditCard },
  { label: "Covenants", href: "/covenants", icon: AlertTriangle },
  { label: "Transfer Pricing", href: "/transfer-pricing", icon: FileBarChart },
  { label: "Signoff", href: "/signoff", icon: ShieldCheck },
  { label: "Statutory", href: "/statutory", icon: CalendarClock },
  { label: "Multi-GAAP", href: "/gaap", icon: Layers },
  { label: "Audit Portal", href: "/audit", icon: BriefcaseBusiness },
] as const

const DIRECTOR_NAV_LABELS = new Set([
  "Dashboard",
  "Board Packs",
  "Signoff",
  "Covenants",
  "Multi-GAAP",
  "Reports",
])

interface SidebarProps {
  tenantId: string
  tenantSlug: string
  orgSetupComplete: boolean
  orgSetupStep: number
  userName: string
  userEmail: string
  userRole: UserRole
  entityRoles: EntityRole[]
}

export function Sidebar({
  tenantId,
  tenantSlug,
  orgSetupComplete,
  orgSetupStep,
  userName,
  userEmail,
  userRole,
  entityRoles,
}: SidebarProps) {
  const pathname = usePathname() ?? ""
  const [reconciliationOpen, setReconciliationOpen] = useState(
    pathname.startsWith("/reconciliation"),
  )
  const sidebarOpen = useUIStore((state) => state.sidebarOpen)
  const closeSidebar = useUIStore((state) => state.closeSidebar)
  const setTenant = useTenantStore((state) => state.setTenant)

  useEffect(() => {
    setTenant({
      tenant_id: tenantId,
      tenant_slug: tenantSlug,
      org_setup_complete: orgSetupComplete,
      org_setup_step: orgSetupStep,
      entity_roles: entityRoles,
      active_entity_id: entityRoles.at(0)?.entity_id ?? null,
    })
  }, [entityRoles, orgSetupComplete, orgSetupStep, setTenant, tenantId, tenantSlug])

  useEffect(() => {
    if (pathname.startsWith("/reconciliation")) {
      setReconciliationOpen(true)
    }
  }, [pathname])

  const initials = useMemo(() => {
    const [first, second] = userName.split(" ")
    return `${first?.[0] ?? ""}${second?.[0] ?? ""}`.toUpperCase()
  }, [userName])
  const showTrust = userRole === "finance_leader"
  const showAdvisory = userRole === "finance_leader"
  const showAdmin = [
    "platform_owner",
    "platform_admin",
    "super_admin",
    "admin",
  ].includes(String(userRole))
  const isDirector = userRole === "director"
  const visibleNavItems = useMemo(() => {
    if (userRole !== "director") {
      return navItems
    }
    return navItems.filter((item) => DIRECTOR_NAV_LABELS.has(item.label))
  }, [userRole])

  return (
    <>
      {sidebarOpen ? (
        <button
          aria-label="Close navigation menu"
          className="fixed inset-0 z-30 bg-black/60 md:hidden"
          onClick={closeSidebar}
          type="button"
        />
      ) : null}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex w-60 flex-col border-r border-border bg-card transition-transform duration-200",
          sidebarOpen ? "translate-x-0" : "-translate-x-full",
          "md:translate-x-0",
        )}
      >
        <div className="border-b border-border px-4 py-4">
          <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">
            FinanceOps
          </p>
        </div>

        <nav className="flex-1 space-y-2 overflow-y-auto p-3">
          {visibleNavItems.map((item) => {
            const Icon = item.icon
            if ("children" in item) {
              return (
                <div key={item.label} className="space-y-1">
                  <button
                    type="button"
                    className="flex w-full items-center justify-between rounded-md px-3 py-2 text-sm text-foreground hover:bg-accent"
                    onClick={() => setReconciliationOpen((value) => !value)}
                  >
                    <span className="flex items-center gap-2">
                      <Icon className="h-4 w-4" />
                      {item.label}
                    </span>
                    <ChevronDown
                      className={cn(
                        "h-4 w-4 transition-transform",
                        reconciliationOpen ? "rotate-180" : "rotate-0",
                      )}
                    />
                  </button>
                  {reconciliationOpen ? (
                    <div className="space-y-1 pl-6">
                      {item.children.map((child) => {
                        const isActive = pathname === child.href
                        return (
                          <Link
                            key={child.href}
                            className={cn(
                              "block rounded-md border-l-2 px-3 py-2 text-sm transition",
                              isActive
                                ? "border-l-[hsl(var(--brand-primary))] bg-[hsl(var(--brand-primary)/0.15)] text-foreground"
                                : "border-l-transparent text-muted-foreground hover:bg-accent hover:text-foreground",
                            )}
                            href={child.href}
                            onClick={closeSidebar}
                          >
                            {child.label}
                          </Link>
                        )
                      })}
                    </div>
                  ) : null}
                </div>
              )
            }

            const isActive =
              pathname === item.href || pathname.startsWith(`${item.href}/`)
            return (
              <Link
                key={item.href}
                className={cn(
                  "flex items-center gap-2 rounded-md border-l-2 px-3 py-2 text-sm transition",
                  isActive
                    ? "border-l-[hsl(var(--brand-primary))] bg-[hsl(var(--brand-primary)/0.15)] text-foreground"
                    : "border-l-transparent text-muted-foreground hover:bg-accent hover:text-foreground",
                )}
                href={item.href}
                onClick={closeSidebar}
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </Link>
            )
          })}
          {showTrust ? (
            <div className="mt-3 space-y-1 rounded-md border border-border/60 p-2">
              <p className="px-2 text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                Trust
              </p>
              <Link
                href="/trust"
                onClick={closeSidebar}
                className={cn(
                  "flex items-center gap-2 rounded-md border-l-2 px-3 py-2 text-sm transition",
                  pathname === "/trust" || pathname.startsWith("/trust/")
                    ? "border-l-[hsl(var(--brand-primary))] bg-[hsl(var(--brand-primary)/0.15)] text-foreground"
                    : "border-l-transparent text-muted-foreground hover:bg-accent hover:text-foreground",
                )}
              >
                <ShieldCheck className="h-4 w-4" />
                Trust & Compliance
              </Link>
              <Link
                href="/trust/soc2"
                onClick={closeSidebar}
                className={cn(
                  "block rounded-md border-l-2 px-3 py-2 text-xs transition",
                  pathname === "/trust/soc2"
                    ? "border-l-[hsl(var(--brand-primary))] bg-[hsl(var(--brand-primary)/0.15)] text-foreground"
                    : "border-l-transparent text-muted-foreground hover:bg-accent hover:text-foreground",
                )}
              >
                SOC2
              </Link>
              <Link
                href="/trust/gdpr"
                onClick={closeSidebar}
                className={cn(
                  "block rounded-md border-l-2 px-3 py-2 text-xs transition",
                  pathname === "/trust/gdpr" || pathname.startsWith("/trust/gdpr/")
                    ? "border-l-[hsl(var(--brand-primary))] bg-[hsl(var(--brand-primary)/0.15)] text-foreground"
                    : "border-l-transparent text-muted-foreground hover:bg-accent hover:text-foreground",
                )}
              >
                GDPR
              </Link>
            </div>
          ) : null}
          {showAdvisory ? (
            <div className="mt-3 space-y-1 rounded-md border border-border/60 p-2">
              <p className="px-2 text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                Advisory
              </p>
              <Link
                href="/advisory"
                onClick={closeSidebar}
                className={cn(
                  "flex items-center gap-2 rounded-md border-l-2 px-3 py-2 text-sm transition",
                  pathname === "/advisory" || pathname.startsWith("/advisory/")
                    ? "border-l-[hsl(var(--brand-primary))] bg-[hsl(var(--brand-primary)/0.15)] text-foreground"
                    : "border-l-transparent text-muted-foreground hover:bg-accent hover:text-foreground",
                )}
              >
                <BriefcaseBusiness className="h-4 w-4" />
                Advisory Services
              </Link>
              <Link
                href="/advisory/fdd"
                onClick={closeSidebar}
                className={cn(
                  "block rounded-md border-l-2 px-3 py-2 text-xs transition",
                  pathname === "/advisory/fdd" || pathname.startsWith("/advisory/fdd/")
                    ? "border-l-[hsl(var(--brand-primary))] bg-[hsl(var(--brand-primary)/0.15)] text-foreground"
                    : "border-l-transparent text-muted-foreground hover:bg-accent hover:text-foreground",
                )}
              >
                FDD
              </Link>
              <Link
                href="/advisory/ppa"
                onClick={closeSidebar}
                className={cn(
                  "block rounded-md border-l-2 px-3 py-2 text-xs transition",
                  pathname === "/advisory/ppa" || pathname.startsWith("/advisory/ppa/")
                    ? "border-l-[hsl(var(--brand-primary))] bg-[hsl(var(--brand-primary)/0.15)] text-foreground"
                    : "border-l-transparent text-muted-foreground hover:bg-accent hover:text-foreground",
                )}
              >
                PPA
              </Link>
              <Link
                href="/advisory/ma"
                onClick={closeSidebar}
                className={cn(
                  "block rounded-md border-l-2 px-3 py-2 text-xs transition",
                  pathname === "/advisory/ma" || pathname.startsWith("/advisory/ma/")
                    ? "border-l-[hsl(var(--brand-primary))] bg-[hsl(var(--brand-primary)/0.15)] text-foreground"
                    : "border-l-transparent text-muted-foreground hover:bg-accent hover:text-foreground",
                )}
              >
                M&A
              </Link>
            </div>
          ) : null}
          <div className="mt-3 rounded-md border border-border/60 p-2">
            <p className="px-2 text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
              Settings
            </p>
            <Link
              href="/settings"
              onClick={closeSidebar}
              className={cn(
                "flex items-center gap-2 rounded-md border-l-2 px-3 py-2 text-sm transition",
                pathname === "/settings"
                  ? "border-l-[hsl(var(--brand-primary))] bg-[hsl(var(--brand-primary)/0.15)] text-foreground"
                  : "border-l-transparent text-muted-foreground hover:bg-accent hover:text-foreground",
              )}
            >
              <Lock className="h-4 w-4" />
              Display & Formatting
            </Link>
            {!isDirector ? (
              <Link
                href="/settings/chart-of-accounts"
                onClick={closeSidebar}
                className={cn(
                  "flex items-center gap-2 rounded-md border-l-2 px-3 py-2 text-sm transition",
                  pathname === "/settings/chart-of-accounts" ||
                    pathname.startsWith("/settings/chart-of-accounts/")
                    ? "border-l-[hsl(var(--brand-primary))] bg-[hsl(var(--brand-primary)/0.15)] text-foreground"
                    : "border-l-transparent text-muted-foreground hover:bg-accent hover:text-foreground",
                )}
              >
                <Layers className="h-4 w-4" />
                Chart of Accounts
              </Link>
            ) : null}
            {!isDirector ? (
              <Link
                href="/settings/coa"
                onClick={closeSidebar}
                className={cn(
                  "flex items-center gap-2 rounded-md border-l-2 px-3 py-2 text-sm transition",
                  pathname === "/settings/coa" || pathname.startsWith("/settings/coa/")
                    ? "border-l-[hsl(var(--brand-primary))] bg-[hsl(var(--brand-primary)/0.15)] text-foreground"
                    : "border-l-transparent text-muted-foreground hover:bg-accent hover:text-foreground",
                )}
              >
                <Layers className="h-4 w-4" />
                CoA Uploads
              </Link>
            ) : null}
            {!isDirector ? (
              <Link
                href="/settings/erp-mapping"
                onClick={closeSidebar}
                className={cn(
                  "flex items-center gap-2 rounded-md border-l-2 px-3 py-2 text-sm transition",
                  pathname === "/settings/erp-mapping" ||
                    pathname.startsWith("/settings/erp-mapping/")
                    ? "border-l-[hsl(var(--brand-primary))] bg-[hsl(var(--brand-primary)/0.15)] text-foreground"
                    : "border-l-transparent text-muted-foreground hover:bg-accent hover:text-foreground",
                )}
              >
                <GitMerge className="h-4 w-4" />
                ERP Mapping
              </Link>
            ) : null}
            {!isDirector ? (
              <Link
                href="/settings/groups"
                onClick={closeSidebar}
                className={cn(
                  "flex items-center gap-2 rounded-md border-l-2 px-3 py-2 text-sm transition",
                  pathname === "/settings/groups" || pathname.startsWith("/settings/groups/")
                    ? "border-l-[hsl(var(--brand-primary))] bg-[hsl(var(--brand-primary)/0.15)] text-foreground"
                    : "border-l-transparent text-muted-foreground hover:bg-accent hover:text-foreground",
                )}
              >
                <BriefcaseBusiness className="h-4 w-4" />
                Groups & Entities
              </Link>
            ) : null}
            {!isDirector ? (
              <Link
                href="/settings/users"
                onClick={closeSidebar}
                className={cn(
                  "flex items-center gap-2 rounded-md border-l-2 px-3 py-2 text-sm transition",
                  pathname === "/settings/users" || pathname.startsWith("/settings/users/")
                    ? "border-l-[hsl(var(--brand-primary))] bg-[hsl(var(--brand-primary)/0.15)] text-foreground"
                    : "border-l-transparent text-muted-foreground hover:bg-accent hover:text-foreground",
                )}
              >
                <BriefcaseBusiness className="h-4 w-4" />
                Users & Roles
              </Link>
            ) : null}
            <Link
              href="/settings/privacy"
              onClick={closeSidebar}
              className={cn(
                "flex items-center gap-2 rounded-md border-l-2 px-3 py-2 text-sm transition",
                pathname === "/settings/privacy" ||
                  pathname.startsWith("/settings/privacy/")
                  ? "border-l-[hsl(var(--brand-primary))] bg-[hsl(var(--brand-primary)/0.15)] text-foreground"
                  : "border-l-transparent text-muted-foreground hover:bg-accent hover:text-foreground",
              )}
            >
              <Lock className="h-4 w-4" />
              Privacy Settings
            </Link>
            {showTrust ? (
              <Link
                href="/settings/white-label"
                onClick={closeSidebar}
                className={cn(
                  "flex items-center gap-2 rounded-md border-l-2 px-3 py-2 text-sm transition",
                  pathname === "/settings/white-label"
                    ? "border-l-[hsl(var(--brand-primary))] bg-[hsl(var(--brand-primary)/0.15)] text-foreground"
                    : "border-l-transparent text-muted-foreground hover:bg-accent hover:text-foreground",
                )}
              >
                <Lock className="h-4 w-4" />
                White Label
              </Link>
            ) : null}
          </div>
          {showAdmin ? (
            <div className="mt-3 rounded-md border border-border/60 p-2">
              <p className="px-2 text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                Admin
              </p>
              <Link
                href="/admin"
                onClick={closeSidebar}
                className={cn(
                  "flex items-center gap-2 rounded-md border-l-2 px-3 py-2 text-sm transition",
                  pathname === "/admin" || pathname.startsWith("/admin/")
                    ? "border-l-[hsl(var(--brand-primary))] bg-[hsl(var(--brand-primary)/0.15)] text-foreground"
                    : "border-l-transparent text-muted-foreground hover:bg-accent hover:text-foreground",
                )}
              >
                <ShieldCheck className="h-4 w-4" />
                Admin Console
              </Link>
              <div className="space-y-1 pl-2">
                <Link
                  href="/admin/tenants"
                  onClick={closeSidebar}
                  className={cn(
                    "block rounded-md border-l-2 px-3 py-2 text-xs transition",
                    pathname === "/admin/tenants"
                      ? "border-l-[hsl(var(--brand-primary))] bg-[hsl(var(--brand-primary)/0.15)] text-foreground"
                      : "border-l-transparent text-muted-foreground hover:bg-accent hover:text-foreground",
                  )}
                >
                  Tenants
                </Link>
                <Link
                  href="/admin/users"
                  onClick={closeSidebar}
                  className={cn(
                    "block rounded-md border-l-2 px-3 py-2 text-xs transition",
                    pathname === "/admin/users"
                      ? "border-l-[hsl(var(--brand-primary))] bg-[hsl(var(--brand-primary)/0.15)] text-foreground"
                      : "border-l-transparent text-muted-foreground hover:bg-accent hover:text-foreground",
                  )}
                >
                  Users
                </Link>
                <Link
                  href="/admin/rbac"
                  onClick={closeSidebar}
                  className={cn(
                    "block rounded-md border-l-2 px-3 py-2 text-xs transition",
                    pathname === "/admin/rbac"
                      ? "border-l-[hsl(var(--brand-primary))] bg-[hsl(var(--brand-primary)/0.15)] text-foreground"
                      : "border-l-transparent text-muted-foreground hover:bg-accent hover:text-foreground",
                  )}
                >
                  RBAC
                </Link>
                <Link
                  href="/admin/flags"
                  onClick={closeSidebar}
                  className={cn(
                    "block rounded-md border-l-2 px-3 py-2 text-xs transition",
                    pathname === "/admin/flags"
                      ? "border-l-[hsl(var(--brand-primary))] bg-[hsl(var(--brand-primary)/0.15)] text-foreground"
                      : "border-l-transparent text-muted-foreground hover:bg-accent hover:text-foreground",
                  )}
                >
                  Flags
                </Link>
                <Link
                  href="/admin/modules"
                  onClick={closeSidebar}
                  className={cn(
                    "block rounded-md border-l-2 px-3 py-2 text-xs transition",
                    pathname === "/admin/modules"
                      ? "border-l-[hsl(var(--brand-primary))] bg-[hsl(var(--brand-primary)/0.15)] text-foreground"
                      : "border-l-transparent text-muted-foreground hover:bg-accent hover:text-foreground",
                  )}
                >
                  Modules
                </Link>
              </div>
            </div>
          ) : null}
        </nav>

        <div className="space-y-3 border-t border-border p-3">
          <EntitySwitcher entityRoles={entityRoles} />
          <div className="rounded-md border border-border bg-background p-3">
            <div className="mb-2 flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-accent text-sm font-medium">
                {initials}
              </div>
              <div>
                <p className="text-sm font-medium text-foreground">{userName}</p>
                <p className="text-xs text-muted-foreground">{userEmail}</p>
              </div>
            </div>
            <Button
              className="w-full"
              size="sm"
              variant="outline"
              onClick={() => signOut({ callbackUrl: "/login" })}
              type="button"
            >
              Sign out
            </Button>
          </div>
        </div>
      </aside>
    </>
  )
}
