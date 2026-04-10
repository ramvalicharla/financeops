"use client"

import { usePathname } from "next/navigation"
import { useEffect, useMemo, useState } from "react"
import { signOut } from "next-auth/react"
import { useQuery } from "@tanstack/react-query"
import type { EntityRole } from "@/types/api"
import { EntitySwitcher } from "@/components/layout/EntitySwitcher"
import { SidebarDisclosureGroup, SidebarNavGroup } from "@/components/layout/_components/SidebarNavGroup"
import { Button } from "@/components/ui/button"
import { useCurrentEntitlements } from "@/hooks/useBilling"
import type { UserRole } from "@/lib/auth"
import { getControlPlaneContext, listControlPlaneEntities } from "@/lib/api/control-plane"
import { resolveControlPlaneModule } from "@/lib/control-plane"
import {
  ADMIN_NAV_ITEMS,
  ADVISORY_NAV_ITEMS,
  DIRECTOR_NAV_LABELS,
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
  const setTenant = useTenantStore((state) => state.setTenant)
  const activeEntityId = useTenantStore((state) => state.active_entity_id)
  const setActiveEntity = useTenantStore((state) => state.setActiveEntity)
  const activeWorkspace = resolveControlPlaneModule(pathname).key
  const entitiesQuery = useQuery({
    queryKey: ["control-plane-entities"],
    queryFn: listControlPlaneEntities,
  })
  const contextQuery = useQuery({
    queryKey: ["control-plane-context", activeEntityId, activeWorkspace],
    queryFn: () =>
      getControlPlaneContext({
        entity_id: activeEntityId ?? undefined,
        workspace: activeWorkspace,
        module: activeWorkspace,
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

  const entityOptions = useMemo(() => {
    if (entityRoles.length) {
      return entityRoles
    }
    return (entitiesQuery.data ?? []).map((entity) => ({
      entity_id: entity.id,
      entity_name: entity.entity_name,
      role: null,
    }))
  }, [entitiesQuery.data, entityRoles])

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

  const primaryNavItems = visibleNavItems.filter(
    (item) => !("children" in item),
  ) as readonly NavigationLeafItem[]
  const reconciliationItem = visibleNavItems.find(
    (item) => "children" in item,
  ) as NavigationGroupItem | undefined
  const organizationLabel =
    contextQuery.isLoading
      ? "Loading..."
      : contextQuery.data?.current_organisation.organisation_name ??
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
          "fixed inset-y-0 left-0 z-40 flex w-60 flex-col border-r border-border bg-card transition-transform duration-200",
          sidebarOpen ? "translate-x-0" : "-translate-x-full",
          "md:translate-x-0",
        )}
      >
        <div className="border-b border-border px-4 py-4">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            FinanceOps
          </p>
          <div className="mt-3 rounded-2xl border border-border bg-background p-4 shadow-sm">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs uppercase tracking-wide text-muted-foreground">Organization</p>
                <p className="mt-1 text-sm font-semibold text-foreground">{organizationLabel}</p>
              </div>
              <span className="rounded-full bg-muted px-2.5 py-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                Backend
              </span>
            </div>
            <div className="mt-3 space-y-2 rounded-xl border border-border bg-background px-3 py-3 text-sm text-muted-foreground">
              <p>Entity: {contextQuery.data?.current_entity.entity_name ?? "Unavailable"}</p>
              <p>Workspace: {contextQuery.data?.current_module.module_name ?? "Unavailable"}</p>
            </div>
          </div>
        </div>

        <nav aria-label="Main navigation" className="flex-1 space-y-3 overflow-y-auto p-3">
          <SidebarNavGroup
            closeSidebar={closeSidebar}
            items={primaryNavItems}
            pathname={pathname}
            type="plain"
          />

          {reconciliationItem ? (
            <SidebarDisclosureGroup
              closeSidebar={closeSidebar}
              item={reconciliationItem}
              open={reconciliationOpen}
              pathname={pathname}
              onToggle={() => setReconciliationOpen((value) => !value)}
            />
          ) : null}

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

        <div className="space-y-3 border-t border-border p-3">
          <EntitySwitcher entityRoles={entityOptions} />
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
        </div>
      </aside>
    </>
  )
}
