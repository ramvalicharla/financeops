"use client"

import { usePathname } from "next/navigation"
import { useCallback, useEffect, useMemo, useState } from "react"
import { signOut } from "next-auth/react"
import Link from "next/link"
import { ChevronDown, ChevronsLeft, ChevronsRight, Settings } from "lucide-react"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { useQuery } from "@tanstack/react-query"
import type { EntityRole } from "@/types/api"
import { EntityCardPicker } from "@/components/layout/EntityCardPicker"
import { SidebarNavGroup } from "@/components/layout/_components/SidebarNavGroup"
import { Button } from "@/components/ui/button"
import { useCurrentEntitlements } from "@/hooks/useBilling"
import type { UserRole } from "@/lib/auth"
import { getControlPlaneContext, listControlPlaneEntities } from "@/lib/api/control-plane"
import { queryKeys } from "@/lib/query/keys"
import { NAV_GROUPS, type NavGroupId, type NavItem } from "@/components/layout/sidebar/nav-config"
import type { NavigationLeafItem } from "@/lib/config/navigation"
import { filterNavigationItems, isTenantViewer } from "@/lib/ui-access"
import { useOrgEntities } from "@/hooks/useOrgEntities"
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

  const orgEntities = useOrgEntities()

  const initials = useMemo(() => {
    const [first, second] = userName.split(" ")
    return `${first?.[0] ?? ""}${second?.[0] ?? ""}`.toUpperCase()
  }, [userName])

  const activeEntityName = useMemo(
    () => orgEntities.entities.find((e) => e.entity_id === entityId)?.entity_name ?? null,
    [orgEntities.entities, entityId],
  )

  const orgInitial = (
    contextQuery.data?.current_organisation.organisation_name?.[0] ??
    tenantSlug?.[0] ??
    "O"
  ).toUpperCase()

  const handleTreeKeyDown = useCallback((e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return
    e.preventDefault()
    const items = Array.from(
      e.currentTarget.querySelectorAll<HTMLButtonElement>("[data-entity-item]"),
    )
    if (!items.length) return
    const idx = items.findIndex((el) => el === document.activeElement)
    const next =
      e.key === "ArrowDown"
        ? (idx + 1) % items.length
        : (idx - 1 + items.length) % items.length
    items[next]?.focus()
  }, [])

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
          "fixed inset-y-0 left-0 z-40 flex flex-col border-r border-border bg-card motion-safe:transition-all motion-safe:duration-200",
          sidebarOpen ? "translate-x-0" : "-translate-x-full",
          "md:translate-x-0",
        )}
        style={{ width: sidebarCollapsed ? "52px" : "220px" }}
      >
        {/* ── Header ─────────────────────────────────────────────────────── */}
        {sidebarCollapsed ? (
          <div className="flex justify-center border-b border-border py-[18px]">
            {entityId !== null ? (
              <Tooltip delayDuration={150}>
                <TooltipTrigger asChild>
                  <button
                    type="button"
                    className="flex h-8 w-8 items-center justify-center rounded-md bg-accent text-accent-foreground text-xs font-semibold hover:opacity-80 transition-opacity shrink-0"
                    onClick={toggleSidebar}
                    aria-label={`Expand sidebar — ${activeEntityName ?? "entity"}`}
                  >
                    {(activeEntityName?.[0] ?? "?").toUpperCase()}
                  </button>
                </TooltipTrigger>
                <TooltipContent side="right">
                  {activeEntityName ?? "entity"}
                </TooltipContent>
              </Tooltip>
            ) : (
              <Tooltip delayDuration={150}>
                <TooltipTrigger asChild>
                  <button
                    type="button"
                    className="flex h-8 w-8 items-center justify-center rounded-md bg-primary text-primary-foreground text-xs font-semibold hover:opacity-80 transition-opacity shrink-0"
                    onClick={toggleSidebar}
                    aria-label={`Expand sidebar — All entities`}
                  >
                    {orgInitial}{orgEntities.entities.length}
                  </button>
                </TooltipTrigger>
                <TooltipContent side="right">
                  All entities
                </TooltipContent>
              </Tooltip>
            )}
          </div>
        ) : (
          <div className="border-b border-border px-4 py-4">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              Finqor
            </p>
            <EntityCardPicker
              entityId={entityId}
              switchEntity={switchEntity}
              entities={orgEntities.entities}
              organizationLabel={organizationLabel}
              activeEntityName={activeEntityName}
              moduleName={contextQuery.data?.current_module.module_name ?? null}
              contextIsLoading={contextQuery.isLoading}
            />
            {/* Entity tree — compact always-visible list in expanded mode (OQ-1: org+entity only) */}
            <div
              className="mt-3 max-h-40 overflow-y-auto rounded-xl border border-border"
              onKeyDown={handleTreeKeyDown}
            >
              <button
                type="button"
                data-entity-item
                className={cn(
                  "flex w-full items-center px-3 py-2 text-xs text-muted-foreground hover:bg-accent hover:text-accent-foreground transition-colors rounded-t-xl",
                  entityId === null && "bg-accent text-accent-foreground font-medium",
                )}
                onClick={() => switchEntity(null)}
              >
                ← All entities
              </button>
              {orgEntities.entities.map((entity, idx) => (
                <button
                  key={entity.entity_id}
                  type="button"
                  data-entity-item
                  className={cn(
                    "flex w-full items-center px-3 py-2 text-xs hover:bg-accent hover:text-accent-foreground transition-colors",
                    idx === orgEntities.entities.length - 1 && "rounded-b-xl",
                    entity.entity_id === entityId && "bg-accent text-accent-foreground font-medium",
                  )}
                  onClick={() => switchEntity(entity.entity_id)}
                >
                  <span className="truncate">{entity.entity_name}</span>
                </button>
              ))}
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
            const isAuditor = isTenantViewer(userRole)
            const filteredItems = filterNavigationItems(
              group.items,
              userRole,
              entitlementsQuery.data,
              entitlementsLoaded,
            )
              .filter((item): item is NavigationLeafItem => !("children" in item))
              .filter((item) => !isAuditor || !(item as NavItem).writesRequired)

            if (!filteredItems.length) return null

            if (sidebarCollapsed) {
              return (
                <div key={group.id}>
                  {groupIndex > 0 && (
                    <hr
                      role="separator"
                      aria-orientation="horizontal"
                      aria-label={`End of ${NAV_GROUPS[groupIndex - 1]?.label ?? "previous"} group`}
                      className="my-1 border-border"
                    />
                  )}
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
                      "h-3.5 w-3.5 motion-safe:transition-transform",
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
              <Tooltip delayDuration={150}>
                <TooltipTrigger asChild>
                  <button
                    type="button"
                    aria-label={`Sign out — signed in as ${userName}, ${isTenantViewer(userRole) ? "read-only access" : String(userRole).replace(/_/g, " ")}`}
                    className="flex h-8 w-8 items-center justify-center rounded-full bg-accent text-sm font-medium hover:opacity-80 transition-opacity"
                    onClick={() => signOut({ callbackUrl: "/login" })}
                  >
                    {initials}
                  </button>
                </TooltipTrigger>
                <TooltipContent side="right">
                  <div>{userName}</div>
                  <div>{isTenantViewer(userRole) ? "Read-only access" : String(userRole).replace(/_/g, " ")}</div>
                  <div>Click to sign out</div>
                </TooltipContent>
              </Tooltip>
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
                    {isTenantViewer(userRole) && (
                      <span className="mt-0.5 inline-flex items-center rounded-full bg-muted px-2 py-0.5 text-[10px] font-medium text-muted-foreground ring-1 ring-inset ring-border">
                        Read-only access
                      </span>
                    )}
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
