"use client"

import { useMemo, useState } from "react"
import { usePathname } from "next/navigation"
import { Menu, Search } from "lucide-react"
import { signOut } from "next-auth/react"
import type { EntityRole } from "@/types/api"
import { useTenantStore } from "@/lib/store/tenant"
import { useUIStore } from "@/lib/store/ui"
import { useSearch } from "@/components/search/SearchProvider"
import { NotificationBell } from "@/components/notifications/NotificationBell"
import { ScaleSelector } from "@/components/ui/ScaleSelector"
import { Button } from "@/components/ui/button"
import { EntityLocationSelector } from "@/components/layout/EntityLocationSelector"
import { useDisplayScale } from "@/lib/store/displayScale"
import { cn } from "@/lib/utils"

const pageTitles: Record<string, string> = {
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
}

interface TopbarProps {
  tenantSlug: string
  userName: string
  userEmail: string
  entityRoles: EntityRole[]
}

export function Topbar({
  tenantSlug,
  userName,
  userEmail,
  entityRoles,
}: TopbarProps) {
  const pathname = usePathname() ?? ""
  const [profileOpen, setProfileOpen] = useState(false)
  const { openPalette } = useSearch()
  const toggleSidebar = useUIStore((state) => state.toggleSidebar)
  const billingWarning = useUIStore((state) => state.billingWarning)
  const billingWarningDismissed = useUIStore(
    (state) => state.billingWarningDismissed,
  )
  const dismissBillingWarning = useUIStore((state) => state.dismissBillingWarning)
  const activeEntityId = useTenantStore((state) => state.active_entity_id)
  const scale = useDisplayScale((state) => state.scale)
  const setScale = useDisplayScale((state) => state.setScale)

  const title = pathname.startsWith("/board-pack/")
    ? "Board Pack Run"
      : pathname.startsWith("/reports/")
        ? "Report Run"
      : pathname.startsWith("/scheduled-delivery/logs")
        ? "Delivery Logs"
      : pathname.startsWith("/anomalies/thresholds")
        ? "Anomaly Thresholds"
      : pathname.startsWith("/anomalies/")
        ? "Anomaly Alert"
        : (pageTitles[pathname] ?? "FinanceOps")
  const activeEntity = useMemo(
    () => entityRoles.find((role) => role.entity_id === activeEntityId) ?? null,
    [activeEntityId, entityRoles],
  )

  return (
    <header className="sticky top-0 z-30 border-b border-border bg-background/95 backdrop-blur">
      <div className="flex h-16 items-center justify-between px-4 md:px-6">
        <div className="flex items-center gap-3">
          <button
            aria-label="Open navigation menu"
            className="rounded-md border border-border p-2 text-foreground md:hidden"
            onClick={toggleSidebar}
            type="button"
          >
            <Menu className="h-4 w-4" />
          </button>
          <h1 className="text-lg font-semibold text-foreground">{title}</h1>
        </div>

        <div className="flex items-center gap-3">
          <EntityLocationSelector />
          <ScaleSelector value={scale} onChange={setScale} size="sm" />

          <div className="hidden text-right md:block">
            <p className="text-sm font-medium text-foreground">{tenantSlug}</p>
            <p className="text-xs text-muted-foreground">
              {activeEntity?.entity_name ?? "No active entity"}
            </p>
          </div>

          <button
            type="button"
            onClick={openPalette}
            className="flex items-center gap-2 rounded-md border border-border px-2 py-2 text-xs text-muted-foreground hover:text-foreground md:px-3"
          >
            <Search className="h-3.5 w-3.5" />
            <span className="hidden md:inline">Search</span>
            <span className="hidden rounded border border-border px-1.5 py-0.5 text-[10px] md:inline">
              Ctrl+K
            </span>
          </button>

          <div onClick={() => setProfileOpen(false)}>
            <NotificationBell />
          </div>

          <div className="relative">
            <button
              className="flex h-9 w-9 items-center justify-center rounded-full bg-accent text-sm font-medium text-accent-foreground"
              onClick={() => {
                setProfileOpen((open) => !open)
              }}
              type="button"
            >
              {userName.slice(0, 1).toUpperCase()}
            </button>
            {profileOpen ? (
              <div className="absolute right-0 z-50 mt-2 w-64 rounded-md border border-border bg-card p-3 shadow-lg">
                <p className="text-sm font-medium text-foreground">{userName}</p>
                <p className="text-xs text-muted-foreground">{userEmail}</p>
                <Button
                  className="mt-3 w-full"
                  size="sm"
                  variant="outline"
                  onClick={() => signOut({ callbackUrl: "/login" })}
                  type="button"
                >
                  Sign out
                </Button>
              </div>
            ) : null}
          </div>
        </div>
      </div>

      {billingWarning && !billingWarningDismissed ? (
        <div
          className={cn(
            "flex items-center justify-between gap-2 border-t border-[hsl(var(--brand-warning)/0.5)] bg-[hsl(var(--brand-warning)/0.2)] px-4 py-2 text-sm text-[hsl(var(--brand-warning))] md:px-6",
          )}
        >
          <p>
            Your account is in grace period, ending{" "}
            {billingWarning.split(":").slice(1).join(":") || "soon"}. Update
            payment method.
          </p>
          <button
            className="rounded border border-[hsl(var(--brand-warning)/0.5)] px-2 py-1 text-xs"
            onClick={dismissBillingWarning}
            type="button"
          >
            Dismiss
          </button>
        </div>
      ) : null}
    </header>
  )
}
