"use client"

import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type MutableRefObject,
} from "react"
import { usePathname } from "next/navigation"
import { Ellipsis, Menu, Search } from "lucide-react"
import { signOut } from "next-auth/react"
import { useQuery } from "@tanstack/react-query"
import type { EntityRole } from "@/types/api"
import { NotificationBell } from "@/components/notifications/NotificationBell"
import { useSearch } from "@/components/search/SearchProvider"
import { EntityLocationSelector } from "@/components/layout/EntityLocationSelector"
import { EntitySwitcher } from "@/components/layout/EntitySwitcher"
import { ScaleSelector } from "@/components/ui/ScaleSelector"
import { DensitySelector } from "@/components/ui/DensitySelector"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { Button } from "@/components/ui/button"
import { getControlPlaneContext } from "@/lib/api/control-plane"
import { TOPBAR_PAGE_TITLES } from "@/lib/config/navigation"
import { useControlPlaneStore } from "@/lib/store/controlPlane"
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
  menuId: string
  menuRef: MutableRefObject<HTMLDivElement | null>
  open: boolean
  onClose: () => void
  triggerRef: MutableRefObject<HTMLButtonElement | null>
  userEmail: string
  userName: string
  onToggle: () => void
}

function ProfileMenu({
  menuId,
  menuRef,
  open,
  onClose,
  triggerRef,
  userEmail,
  userName,
  onToggle,
}: ProfileMenuProps) {
  return (
    <div className="relative">
      <button
        ref={triggerRef}
        aria-controls={menuId}
        aria-expanded={open}
        aria-haspopup="menu"
        aria-label="Account menu"
        className="flex h-9 w-9 items-center justify-center rounded-full bg-accent text-sm font-medium text-accent-foreground"
        onClick={onToggle}
        type="button"
      >
        {userName.slice(0, 1).toUpperCase()}
      </button>
      {open ? (
        <div
          id={menuId}
          ref={menuRef}
          role="menu"
          tabIndex={-1}
          className="absolute right-0 z-50 mt-2 w-64 rounded-md border border-border bg-card p-3 shadow-lg"
          onKeyDown={(event) => {
            if (event.key === "Tab") {
              onClose()
              return
            }
            if (event.key === "Escape") {
              onClose()
              triggerRef.current?.focus()
              return
            }
            const items = menuRef.current?.querySelectorAll('[role="menuitem"]')
            if (!items?.length) {
              return
            }
            const current = document.activeElement
            const currentIndex = Array.from(items).indexOf(current as Element)
            if (event.key === "ArrowDown") {
              event.preventDefault()
              const next = items[currentIndex + 1] ?? items[0]
              ;(next as HTMLElement)?.focus()
            }
            if (event.key === "ArrowUp") {
              event.preventDefault()
              const previous = items[currentIndex - 1] ?? items[items.length - 1]
              ;(previous as HTMLElement)?.focus()
            }
          }}
        >
          <p className="text-sm font-medium text-foreground">{userName}</p>
          <p className="text-xs text-muted-foreground">{userEmail}</p>
          <Button
            className="mt-3 w-full"
            size="sm"
            variant="outline"
            onClick={() => signOut({ callbackUrl: "/login" })}
            type="button"
            role="menuitem"
          >
            Sign out
          </Button>
        </div>
      ) : null}
    </div>
  )
}

export function Topbar({
  tenantSlug: _tenantSlug,
  userName,
  userEmail,
  entityRoles,
}: TopbarProps) {
  const pathname = usePathname() ?? ""
  const [profileOpen, setProfileOpen] = useState(false)
  const [mobileActionsOpen, setMobileActionsOpen] = useState(false)
  const mobileActionsRef = useRef<HTMLDivElement>(null)
  const mobileActionsButtonRef = useRef<HTMLButtonElement>(null)
  const mobileProfileTriggerRef = useRef<HTMLButtonElement>(null)
  const mobileProfileMenuRef = useRef<HTMLDivElement>(null)
  const desktopProfileTriggerRef = useRef<HTMLButtonElement>(null)
  const desktopProfileMenuRef = useRef<HTMLDivElement>(null)
  const { openPalette } = useSearch()
  const toggleSidebar = useUIStore((state) => state.toggleSidebar)
  const billingWarning = useUIStore((state) => state.billingWarning)
  const billingWarningDismissed = useUIStore(
    (state) => state.billingWarningDismissed,
  )
  const dismissBillingWarning = useUIStore((state) => state.dismissBillingWarning)
  const openJobPanel = useControlPlaneStore((state) => state.openJobPanel)
  const openTimelinePanel = useControlPlaneStore((state) => state.openTimelinePanel)
  const activeEntityId = useTenantStore((state) => state.active_entity_id)
  const contextQuery = useQuery({
    queryKey: ["control-plane-context", activeEntityId],
    queryFn: () =>
      getControlPlaneContext({
        entity_id: activeEntityId ?? undefined,
      }),
    staleTime: 60_000,
  })
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
              "Finqor")

  const orgName =
    contextQuery.data?.current_organisation?.organisation_name ??
    contextQuery.data?.tenant_slug ??
    _tenantSlug ??
    "Finqor"

  const contextSummary = useMemo(() => {
    if (contextQuery.isLoading) {
      return "Loading backend context"
    }
    const organization =
      contextQuery.data?.current_organisation?.organisation_name ??
      contextQuery.data?.tenant_slug ??
      "Organization unavailable"
    const period = contextQuery.data?.current_period.period_label ?? "Period unavailable"
    return `${organization} · ${period}`
  }, [
    contextQuery.data?.current_organisation?.organisation_name,
    contextQuery.data?.current_period.period_label,
    contextQuery.data?.tenant_slug,
    contextQuery.isLoading,
  ])

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

  useEffect(() => {
    if (!profileOpen) {
      return
    }

    const handlePointerDown = (event: MouseEvent) => {
      const target = event.target as Node
      if (
        mobileProfileMenuRef.current?.contains(target) ||
        mobileProfileTriggerRef.current?.contains(target) ||
        desktopProfileMenuRef.current?.contains(target) ||
        desktopProfileTriggerRef.current?.contains(target)
      ) {
        return
      }
      setProfileOpen(false)
    }

    document.addEventListener("mousedown", handlePointerDown)
    return () => {
      document.removeEventListener("mousedown", handlePointerDown)
    }
  }, [profileOpen])

  return (
    <header className="sticky top-0 z-30 border-b border-border bg-background/95 backdrop-blur">
      <div className="relative md:hidden">
        <div className="flex min-h-16 items-center gap-2 px-4 py-2">
          <div className="flex items-center gap-3">
            <div className="hidden rounded-full border border-border px-3 py-1 text-xs uppercase tracking-[0.16em] text-muted-foreground lg:block">
              {contextQuery.isLoading ? (
                <div className="h-4 w-32 animate-pulse rounded bg-muted" />
              ) : (
                orgName
              )}
            </div>
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
            menuId="mobile-account-menu"
            menuRef={mobileProfileMenuRef}
            open={profileOpen}
            onClose={() => setProfileOpen(false)}
            triggerRef={mobileProfileTriggerRef}
            userEmail={userEmail}
            userName={userName}
            onToggle={() => {
              setMobileActionsOpen(false)
              const opening = !profileOpen
              setProfileOpen((open) => !open)
              if (opening) {
                setTimeout(() => {
                  const firstItem = mobileProfileMenuRef.current?.querySelector('[role="menuitem"]')
                  ;(firstItem as HTMLElement | null)?.focus()
                }, 10)
              }
            }}
          />
        </div>

        {mobileActionsOpen ? (
          <div
            ref={mobileActionsRef}
            className="absolute inset-x-4 top-full z-40 rounded-md border border-border bg-card p-3 shadow-lg"
          >
            <div className="space-y-3">
              {entityRoles.length > 1 ? (
                <div className="space-y-1">
                  <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                    Entity
                  </p>
                  <EntitySwitcher entityRoles={entityRoles} />
                </div>
              ) : null}

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
                  openTimelinePanel()
                }}
                className="flex w-full items-center justify-between rounded-md border border-border px-3 py-2 text-sm text-muted-foreground hover:text-foreground"
              >
                <span>Timeline</span>
              </button>

              <button
                type="button"
                onClick={() => {
                  setMobileActionsOpen(false)
                  openJobPanel()
                }}
                className="flex w-full items-center justify-between rounded-md border border-border px-3 py-2 text-sm text-muted-foreground hover:text-foreground"
              >
                <span>Jobs</span>
              </button>

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

              <div className="flex items-center justify-between rounded-md border border-border px-3 py-2">
                <span className="text-sm text-foreground">Notifications</span>
                <NotificationBell onTrigger={() => setProfileOpen(false)} />
              </div>
            </div>
          </div>
        ) : null}
      </div>

      <div className="hidden min-h-16 items-center justify-between gap-6 px-4 py-3 md:flex md:px-6">
          <div className="space-y-1">
            <div className="flex items-center gap-1.5">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                {contextQuery.isLoading ? (
                  <span className="inline-block h-4 w-32 animate-pulse rounded bg-muted align-middle" />
                ) : (
                  orgName
                )}
              </p>
              {!contextQuery.isLoading && entityRoles.length > 0 ? (
                <>
                  <span className="text-xs text-muted-foreground">/</span>
                  <EntitySwitcher entityRoles={entityRoles} />
                </>
              ) : null}
            </div>
            <div className="flex items-center gap-3">
              <h1 className="text-lg font-semibold text-foreground">{title}</h1>
              <span className="rounded-full border border-border bg-card px-3 py-1 text-xs text-muted-foreground">
                {contextSummary}
              </span>
            </div>
          </div>

        <div className="flex items-center gap-3">
          <EntityLocationSelector />
          <div className="flex items-center gap-2 border-r border-border pr-3">
            <DensitySelector />
            <ScaleSelector value={scale} onChange={setScale} size="sm" />
          </div>

          <button
            type="button"
            onClick={() => openTimelinePanel()}
            className="rounded-md border border-border px-3 py-2 text-xs text-muted-foreground hover:text-foreground"
          >
            Timeline
          </button>

          <button
            type="button"
            onClick={() => openJobPanel()}
            className="rounded-md border border-border px-3 py-2 text-xs text-muted-foreground hover:text-foreground"
          >
            Jobs
          </button>

          <Tooltip>
            <TooltipTrigger asChild>
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
            </TooltipTrigger>
            <TooltipContent side="bottom">
              <p>Launch Command Palette (Ctrl+K)</p>
            </TooltipContent>
          </Tooltip>

          <NotificationBell onTrigger={() => setProfileOpen(false)} />

          <ProfileMenu
            menuId="desktop-account-menu"
            menuRef={desktopProfileMenuRef}
            open={profileOpen}
            onClose={() => setProfileOpen(false)}
            triggerRef={desktopProfileTriggerRef}
            userEmail={userEmail}
            userName={userName}
            onToggle={() => {
              const opening = !profileOpen
              setProfileOpen((open) => !open)
              if (opening) {
                setTimeout(() => {
                  const firstItem = desktopProfileMenuRef.current?.querySelector('[role="menuitem"]')
                  ;(firstItem as HTMLElement | null)?.focus()
                }, 10)
              }
            }}
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
