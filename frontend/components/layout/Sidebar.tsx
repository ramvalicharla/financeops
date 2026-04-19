"use client"

import { usePathname } from "next/navigation"
import { useEffect, useMemo, useState } from "react"
import { signOut } from "next-auth/react"
import { ChevronsLeft, ChevronsRight } from "lucide-react"
import { useQuery } from "@tanstack/react-query"
import type { EntityRole } from "@/types/api"
import { SidebarDisclosureGroup, SidebarNavGroup } from "@/components/layout/_components/SidebarNavGroup"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { useCurrentEntitlements } from "@/hooks/useBilling"
import type { UserRole } from "@/lib/auth"
import { getControlPlaneContext, listControlPlaneEntities } from "@/lib/api/control-plane"
import {
  ADMIN_NAV_ITEMS,
  ADVISORY_NAV_ITEMS,
  DIRECTOR_NAV_LABELS,
  NAV_GROUP_DEFINITIONS,
  NAV_ITEMS,
  type NavigationGroupItem,
  type NavigationLeafItem,
  SETTINGS_NAV_ITEMS,
  TRUST_NAV_ITEMS,
} from "@/lib/config/navigation"
import { filterNavigationItems } from "@/lib/ui-access"
import { useTenantStore } from "@/lib/store/tenant"
import { useUIStore } from "@/lib/store/ui"
import { cn } from "@/lib/utils"

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
  const sidebarCollapsed = useUIStore((state) => state.sidebarCollapsed)
  const toggleSidebarCollapsed = useUIStore((state) => state.toggleSidebarCollapsed)
  const setTenant = useTenantStore((state) => state.setTenant)
  const activeEntityId = useTenantStore((state) => state.active_entity_id)
  const setActiveEntity = useTenantStore((state) => state.setActiveEntity)
  const entitiesQuery = useQuery({
    queryKey: ["control-plane-entities"],
    queryFn: listControlPlaneEntities,
  })
  const contextQuery = useQuery({
    queryKey: ["control-plane-context", activeEntityId],
    queryFn: () =>
      getControlPlaneContext({
        entity_id: activeEntityId ?? undefined,
      }),
    staleTime: 60_000,
  })

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
    if (!activeEntityId && entitiesQuery.data?.[0]?.id) {
      setActiveEntity(entitiesQuery.data[0].id)
    }
  }, [activeEntityId, entitiesQuery.data, setActiveEntity])

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
  const entitlementsQuery = useCurrentEntitlements({
    enabled: Boolean(tenantId),
  })
  const entitlementsLoaded =
    !entitlementsQuery.isPending && !entitlementsQuery.isLoading

  const directorNavLabels = useMemo<Set<string>>(
    () => new Set(DIRECTOR_NAV_LABELS),
    [],
  )

  const visibleNavItems = useMemo(() => {
    const filteredItems = filterNavigationItems(
      NAV_ITEMS,
      userRole,
      entitlementsQuery.data,
      entitlementsLoaded,
    )
    if (userRole !== "director") {
      return filteredItems
    }
    return filteredItems.filter((item) => directorNavLabels.has(item.label))
  }, [
    directorNavLabels,
    entitlementsLoaded,
    entitlementsQuery.data,
    userRole,
  ])

  const visibleSettingsItems = useMemo(
    () =>
      filterNavigationItems(
        SETTINGS_NAV_ITEMS,
        userRole,
        entitlementsQuery.data,
        entitlementsLoaded,
      )
        .filter((item): item is NavigationLeafItem => !("children" in item))
        .filter((item) => {
        if (!showTrust && item.href === "/settings/white-label") {
          return false
        }
        if (
          isDirector &&
          item.href !== "/settings" &&
          item.href !== "/settings/privacy"
        ) {
          return false
        }
        return true
        }),
    [
      entitlementsLoaded,
      entitlementsQuery.data,
      isDirector,
      showTrust,
      userRole,
    ],
  )

  const reconciliationItem = visibleNavItems.find(
    (item) => "children" in item,
  ) as NavigationGroupItem | undefined

  const pinnedModules = useUIStore((state) => state.pinnedModules)
  const pinnedItems = useMemo(() => {
    const allLeafs: NavigationLeafItem[] = []
    
    // Extract leafs from standard items
    visibleNavItems.forEach(item => {
      if (!("children" in item)) allLeafs.push(item)
      else allLeafs.push(...item.children)
    })
    
    // Extract leafs from groups (Trust, Advisory, Settings, Admin)
    TRUST_NAV_ITEMS.forEach(i => allLeafs.push(i))
    ADVISORY_NAV_ITEMS.forEach(i => allLeafs.push(i))
    visibleSettingsItems.forEach(i => allLeafs.push(i as NavigationLeafItem))
    
    // Filter down to what's pinned, removing duplicates just in case
    const map = new Map<string, NavigationLeafItem>()
    allLeafs.forEach(i => {
      if (pinnedModules.includes(i.href) && !map.has(i.href)) {
        map.set(i.href, i)
      }
    })
    return Array.from(map.values())
  }, [visibleNavItems, visibleSettingsItems, pinnedModules])

  const organizationLabel =
    contextQuery.data?.current_organisation.organisation_name ??
    contextQuery.data?.tenant_slug ??
    "Unavailable"

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
          "fixed inset-y-0 left-0 z-40 flex flex-col border-r border-border bg-card transition-all duration-200",
          // Width: collapse only applies on desktop (md+); mobile always hides via translate
          sidebarCollapsed ? "md:w-14 w-60" : "w-60",
          sidebarOpen ? "translate-x-0" : "-translate-x-full",
          "md:translate-x-0",
        )}
      >
        {/* ── Header ─────────────────────────────────────────────────────── */}
        {sidebarCollapsed ? (
          <div className="flex justify-center border-b border-border py-[18px]">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary shrink-0">
              <span className="text-primary-foreground font-bold text-sm select-none">F</span>
            </div>
          </div>
        ) : (
          <div className="border-b border-border px-4 py-4">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              Finqor
            </p>
            <div className="mt-3 rounded-2xl border border-border bg-background p-4 shadow-sm">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">Organization</p>
                  {contextQuery.isLoading ? (
                    <Skeleton className="mt-1 h-5 w-32" />
                  ) : (
                    <p className="mt-1 text-sm font-semibold text-foreground">{organizationLabel}</p>
                  )}
                </div>
                <span className="rounded-full bg-muted px-2.5 py-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                  Backend
                </span>
              </div>
              <div className="mt-3 space-y-2 rounded-xl border border-border bg-background px-3 py-3 text-sm text-muted-foreground">
                {contextQuery.isLoading ? (
                  <>
                    <Skeleton className="h-4 w-40" />
                    <Skeleton className="h-4 w-32" />
                  </>
                ) : (
                  <>
                    <p>Entity: {contextQuery.data?.current_entity.entity_name ?? "Unavailable"}</p>
                    <p>Workspace: {contextQuery.data?.current_module.module_name ?? "Unavailable"}</p>
                  </>
                )}
              </div>
            </div>
          </div>
        )}

        {/* ── Nav ────────────────────────────────────────────────────────── */}
        <nav
          aria-label="Main navigation"
          className={cn(
            "flex-1 overflow-y-auto p-3",
            sidebarCollapsed ? "space-y-1" : "space-y-3",
          )}
        >
          {pinnedItems.length > 0 ? (
            <SidebarNavGroup
              closeSidebar={closeSidebar}
              items={pinnedItems}
              label="Pinned"
              pathname={pathname}
            />
          ) : null}

          {NAV_GROUP_DEFINITIONS.map((group) => {
            const hrefSet = new Set<string>(group.hrefs)
            const leafItems = visibleNavItems.filter(
              (item): item is NavigationLeafItem =>
                !("children" in item) && hrefSet.has(item.href),
            )
            const disclosureInGroup =
              reconciliationItem != null &&
              reconciliationItem.children.some((child) => hrefSet.has(child.href))

            if (!leafItems.length && !disclosureInGroup) return null

            return (
              <div key={group.label} className="space-y-1">
                {!sidebarCollapsed ? (
                  <div className="px-3 py-1.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                    {group.label}
                  </div>
                ) : null}
                {leafItems.length > 0 ? (
                  <SidebarNavGroup
                    closeSidebar={closeSidebar}
                    items={leafItems}
                    pathname={pathname}
                    type="plain"
                  />
                ) : null}
                {disclosureInGroup ? (
                  <SidebarDisclosureGroup
                    closeSidebar={closeSidebar}
                    item={reconciliationItem}
                    open={reconciliationOpen}
                    pathname={pathname}
                    onToggle={() => setReconciliationOpen((value) => !value)}
                  />
                ) : null}
              </div>
            )
          })}

          {showTrust ? (
            <SidebarNavGroup
              closeSidebar={closeSidebar}
              items={TRUST_NAV_ITEMS}
              label="Trust"
              pathname={pathname}
            />
          ) : null}

          {showAdvisory ? (
            <SidebarNavGroup
              closeSidebar={closeSidebar}
              items={ADVISORY_NAV_ITEMS}
              label="Advisory"
              pathname={pathname}
            />
          ) : null}

          <SidebarNavGroup
            closeSidebar={closeSidebar}
            items={visibleSettingsItems}
            label="Settings"
            pathname={pathname}
          />

          {showAdmin ? (
            <>
              <SidebarNavGroup
                closeSidebar={closeSidebar}
                items={ADMIN_NAV_ITEMS.slice(0, 1)}
                label="Admin"
                pathname={pathname}
              />
              <SidebarNavGroup
                closeSidebar={closeSidebar}
                items={ADMIN_NAV_ITEMS.slice(1)}
                pathname={pathname}
                type="nested"
              />
            </>
          ) : null}
        </nav>

        {/* ── Footer ─────────────────────────────────────────────────────── */}
        <div className="space-y-2 border-t border-border p-3">
          {sidebarCollapsed ? (
            /* Collapsed footer: initials avatar acts as a sign-out shortcut */
            <div className="flex justify-center py-1">
              <button
                type="button"
                title={`${userName} · ${String(userRole).replace(/_/g, " ")}\n${userEmail}\nClick to sign out`}
                aria-label="Sign out"
                className="flex h-8 w-8 items-center justify-center rounded-full bg-accent text-sm font-medium hover:opacity-80 transition-opacity"
                onClick={() => signOut({ callbackUrl: "/login" })}
              >
                {initials}
              </button>
            </div>
          ) : (
            <>
              <div className="rounded-2xl border border-border bg-background p-4 shadow-sm">
                <div className="mb-2 flex items-center gap-2">
                  <div className="flex h-8 w-8 items-center justify-center rounded-full bg-accent text-sm font-medium">
                    {initials}
                  </div>
                  <div>
                    <p className="text-sm font-medium text-foreground">{userName}</p>
                    <p className="text-xs text-muted-foreground">{userEmail}</p>
                    <p className="text-xs uppercase tracking-wide text-muted-foreground">
                      Role: {String(userRole).replace(/_/g, " ")}
                    </p>
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
            </>
          )}

          {/* Collapse toggle — desktop only (mobile sidebar uses translate) */}
          <button
            type="button"
            onClick={toggleSidebarCollapsed}
            aria-label={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
            className="hidden md:flex w-full h-8 items-center justify-center hover:bg-accent rounded-md transition-colors"
          >
            {sidebarCollapsed ? (
              <ChevronsRight size={14} />
            ) : (
              <>
                <ChevronsLeft size={14} />
                <span className="ml-2 text-xs text-muted-foreground">Collapse</span>
              </>
            )}
          </button>
        </div>
      </aside>
    </>
  )
}
