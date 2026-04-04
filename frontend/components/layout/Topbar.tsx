"use client"

import { useEffect, useMemo, useRef, useState } from "react"
import { usePathname } from "next/navigation"
import { Ellipsis, Menu, Search } from "lucide-react"
import { signOut } from "next-auth/react"
import type { EntityRole } from "@/types/api"
import { NotificationBell } from "@/components/notifications/NotificationBell"
import { useSearch } from "@/components/search/SearchProvider"
import { EntityLocationSelector } from "@/components/layout/EntityLocationSelector"
import { ScaleSelector } from "@/components/ui/ScaleSelector"
import { Button } from "@/components/ui/button"
import { TOPBAR_PAGE_TITLES } from "@/lib/config/navigation"
import { useTenantStore } from "@/lib/store/tenant"
import { useUIStore } from "@/lib/store/ui"
import { useDisplayScale } from "@/lib/store/displayScale"
import { cn } from "@/lib/utils"

interface TopbarProps {
  tenantSlug: string
  userName: string
  userEmail: string
  entityRoles: EntityRole[]
}

interface ProfileMenuProps {
  open: boolean
  userEmail: string
  userName: string
  onToggle: () => void
}

function ProfileMenu({
  open,
  userEmail,
  userName,
  onToggle,
}: ProfileMenuProps) {
  return (
    <div className="relative">
      <button
        className="flex h-9 w-9 items-center justify-center rounded-full bg-accent text-sm font-medium text-accent-foreground"
        onClick={onToggle}
        type="button"
      >
        {userName.slice(0, 1).toUpperCase()}
      </button>
      {open ? (
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
  )
}

export function Topbar({
  tenantSlug,
  userName,
  userEmail,
  entityRoles,
}: TopbarProps) {
  const pathname = usePathname() ?? ""
  const [profileOpen, setProfileOpen] = useState(false)
  const [mobileActionsOpen, setMobileActionsOpen] = useState(false)
  const mobileActionsRef = useRef<HTMLDivElement>(null)
  const mobileActionsButtonRef = useRef<HTMLButtonElement>(null)
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
            : (TOPBAR_PAGE_TITLES[pathname as keyof typeof TOPBAR_PAGE_TITLES] ??
              "FinanceOps")

  const activeEntity = useMemo(
    () => entityRoles.find((role) => role.entity_id === activeEntityId) ?? null,
    [activeEntityId, entityRoles],
  )

  useEffect(() => {
    if (!mobileActionsOpen) {
      return
    }

    const handlePointerDown = (event: MouseEvent) => {
      const target = event.target as Node
      if (
        mobileActionsRef.current?.contains(target) ||
        mobileActionsButtonRef.current?.contains(target)
      ) {
        return
      }
      setMobileActionsOpen(false)
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setMobileActionsOpen(false)
      }
    }

    document.addEventListener("mousedown", handlePointerDown)
    document.addEventListener("keydown", handleKeyDown)
    return () => {
      document.removeEventListener("mousedown", handlePointerDown)
      document.removeEventListener("keydown", handleKeyDown)
    }
  }, [mobileActionsOpen])

  return (
    <header className="sticky top-0 z-30 border-b border-border bg-background/95 backdrop-blur">
      <div className="relative md:hidden">
        <div className="flex min-h-16 items-center gap-2 px-4 py-2">
          <div className="flex items-center gap-3">
            <button
              aria-label="Open navigation menu"
              className="rounded-md border border-border p-2 text-foreground"
              onClick={toggleSidebar}
              type="button"
            >
              <Menu className="h-4 w-4" />
            </button>
            <h1 className="max-w-[120px] truncate text-lg font-semibold text-foreground">
              {title}
            </h1>
          </div>

          <div className="min-w-0 flex-1 overflow-hidden">
            <EntityLocationSelector />
          </div>

          <button
            ref={mobileActionsButtonRef}
            aria-expanded={mobileActionsOpen}
            aria-haspopup="dialog"
            aria-label="Open mobile actions"
            className="rounded-md border border-border p-2 text-foreground"
            onClick={() => setMobileActionsOpen((open) => !open)}
            type="button"
          >
            <Ellipsis className="h-4 w-4" />
          </button>

          <ProfileMenu
            open={profileOpen}
            userEmail={userEmail}
            userName={userName}
            onToggle={() => {
              setMobileActionsOpen(false)
              setProfileOpen((open) => !open)
            }}
          />
        </div>

        {mobileActionsOpen ? (
          <div
            ref={mobileActionsRef}
            className="absolute inset-x-4 top-full z-40 rounded-md border border-border bg-card p-3 shadow-lg"
          >
            <div className="space-y-3">
              <div className="space-y-1">
                <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                  Scale
                </p>
                <ScaleSelector value={scale} onChange={setScale} size="sm" />
              </div>

              <button
                type="button"
                onClick={() => {
                  setMobileActionsOpen(false)
                  openPalette()
                }}
                className="flex w-full items-center justify-between rounded-md border border-border px-3 py-2 text-sm text-muted-foreground hover:text-foreground"
              >
                <span className="flex items-center gap-2">
                  <Search className="h-4 w-4" />
                  Search
                </span>
                <span className="rounded border border-border px-1.5 py-0.5 text-[10px]">
                  Ctrl+K
                </span>
              </button>

              <div
                className="flex items-center justify-between rounded-md border border-border px-3 py-2"
                onClick={() => setProfileOpen(false)}
              >
                <span className="text-sm text-foreground">Notifications</span>
                <NotificationBell />
              </div>
            </div>
          </div>
        ) : null}
      </div>

      <div className="hidden h-16 items-center justify-between px-4 md:flex md:px-6">
        <div className="flex items-center gap-3">
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

          <ProfileMenu
            open={profileOpen}
            userEmail={userEmail}
            userName={userName}
            onToggle={() => setProfileOpen((open) => !open)}
          />
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
