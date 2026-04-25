"use client"

import { usePathname } from "next/navigation"
import { useEffect, useMemo, useState } from "react"
import { signOut } from "next-auth/react"
import Link from "next/link"
import { ChevronDown, ChevronsLeft, ChevronsRight, Settings } from "lucide-react"
import { useQuery } from "@tanstack/react-query"
import type { EntityRole } from "@/types/api"
import { SidebarNavGroup } from "@/components/layout/_components/SidebarNavGroup"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { useCurrentEntitlements } from "@/hooks/useBilling"
import type { UserRole } from "@/lib/auth"
import { getControlPlaneContext, listControlPlaneEntities } from "@/lib/api/control-plane"
import { queryKeys } from "@/lib/query/keys"
import { NAV_GROUPS, type NavGroupId } from "@/components/layout/sidebar/nav-config"
import type { NavigationLeafItem } from "@/lib/config/navigation"
import { filterNavigationItems } from "@/lib/ui-access"
import { useTenantStore } from "@/lib/store/tenant"
import { useUIStore } from "@/lib/store/ui"
import { useWorkspaceStore } from "@/lib/store/workspace"
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
  const [groupOpen, setGroupOpen] = useState<Record<NavGroupId, boolean>>({
    workspace: true,
    org: true,
    governance: true,
  })
  const sidebarOpen = useUIStore((state) => state.sidebarOpen)
  const closeSidebar = useUIStore((state) => state.closeSidebar)
  const sidebarCollapsed = useWorkspaceStore((s) => s.sidebarCollapsed)
  const toggleSidebar = useWorkspaceStore((s) => s.toggleSidebar)
  const setTenant = useTenantStore((state) => state.setTenant)
  const entityId = useWorkspaceStore((s) => s.entityId)
  const switchEntity = useWorkspaceStore((s) => s.switchEntity)
  const { setOrgId, setEntityId } = useWorkspaceStore()
  const entitiesQuery = useQuery({
    queryKey: queryKeys.workspace.entities(),
    queryFn: listControlPlaneEntities,
  })
  const contextQuery = useQuery({
    queryKey: queryKeys.workspace.context(entityId),
    queryFn: () =>
      getControlPlaneContext({
        entity_id: entityId ?? undefined,
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
    // Bootstrap workspaceStore — orgId/entityId are workspace context,
    // not identity facts. Phase 2 will decouple these from setTenant.
    setOrgId(tenantId)
    setEntityId(entityRoles.at(0)?.entity_id ?? null)
  }, [entityRoles, orgSetupComplete, orgSetupStep, setEntityId, setOrgId, setTenant, tenantId, tenantSlug])

  useEffect(() => {
    if (!entityId && entitiesQuery.data?.[0]?.id) {
      switchEntity(entitiesQuery.data[0].id)
    }
  }, [entityId, entitiesQuery.data, switchEntity])

  const initials = useMemo(() => {
    const [first, second] = userName.split(" ")
    return `${first?.[0] ?? ""}${second?.[0] ?? ""}`.toUpperCase()
  }, [userName])

  const entitlementsQuery = useCurrentEntitlements({
    enabled: Boolean(tenantId),
  })
  const entitlementsLoaded =
    !entitlementsQuery.isPending && !entitlementsQuery.isLoading

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
          sidebarOpen ? "translate-x-0" : "-translate-x-full",
          "md:translate-x-0",
        )}
        style={{ width: sidebarCollapsed ? "52px" : "220px" }}
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
                  <p className="text-[10px] font-medium uppercase tracking-widest text-muted-foreground">ACTIVE ENTITY</p>
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
          {NAV_GROUPS.map((group, groupIndex) => {
            const filteredItems = filterNavigationItems(
              group.items,
              userRole,
              entitlementsQuery.data,
              entitlementsLoaded,
            ).filter((item): item is NavigationLeafItem => !("children" in item))

            if (!filteredItems.length) return null

            if (sidebarCollapsed) {
              return (
                <div key={group.id}>
                  {groupIndex > 0 && <hr className="my-1 border-border" />}
                  <SidebarNavGroup
                    closeSidebar={closeSidebar}
                    items={filteredItems}
                    pathname={pathname}
                    type="plain"
                  />
                </div>
              )
            }

            return (
              <div key={group.id} className="space-y-1">
                <button
                  type="button"
                  onClick={() =>
                    setGroupOpen((prev) => ({
                      ...prev,
                      [group.id]: !prev[group.id],
                    }))
                  }
                  className="flex w-full items-center justify-between px-3 py-1.5 text-[11px] font-medium uppercase tracking-wide text-muted-foreground hover:text-foreground transition-colors"
                  aria-expanded={groupOpen[group.id]}
                >
                  {group.label}
                  <ChevronDown
                    className={cn(
                      "h-3.5 w-3.5 transition-transform",
                      groupOpen[group.id] ? "rotate-180" : "rotate-0",
                    )}
                  />
                </button>
                {groupOpen[group.id] ? (
                  <SidebarNavGroup
                    closeSidebar={closeSidebar}
                    items={filteredItems}
                    pathname={pathname}
                    type="plain"
                  />
                ) : null}
              </div>
            )
          })}
        </nav>

        {/* ── Footer ─────────────────────────────────────────────────────── */}
        <div className="space-y-2 border-t border-border p-3">
          {sidebarCollapsed ? (
            /* Collapsed footer: avatar sign-out + settings cog below */
            <div className="flex flex-col items-center gap-1 py-1">
              <button
                type="button"
                title={`${userName} · ${String(userRole).replace(/_/g, " ")}\n${userEmail}\nClick to sign out`}
                aria-label="Sign out"
                className="flex h-8 w-8 items-center justify-center rounded-full bg-accent text-sm font-medium hover:opacity-80 transition-opacity"
                onClick={() => signOut({ callbackUrl: "/login" })}
              >
                {initials}
              </button>
              <Link
                href="/settings"
                aria-label="Settings"
                className="flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
              >
                <Settings className="h-4 w-4" />
              </Link>
            </div>
          ) : (
            <>
              <div className="rounded-2xl border border-border bg-background p-4 shadow-sm">
                <div className="mb-2 flex items-center gap-2">
                  <div className="flex h-8 w-8 items-center justify-center rounded-full bg-accent text-sm font-medium">
                    {initials}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-foreground">{userName}</p>
                    <p className="text-xs text-muted-foreground">{userEmail}</p>
                    <p className="text-xs uppercase tracking-wide text-muted-foreground">
                      Role: {String(userRole).replace(/_/g, " ")}
                    </p>
                  </div>
                  <Link
                    href="/settings"
                    aria-label="Settings"
                    className="ml-auto flex-shrink-0 text-muted-foreground hover:text-foreground transition-colors"
                  >
                    <Settings className="h-4 w-4" />
                  </Link>
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
            onClick={toggleSidebar}
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
