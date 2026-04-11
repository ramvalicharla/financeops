"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { signOut } from "next-auth/react"
import { useMemo } from "react"
import { useQuery } from "@tanstack/react-query"
import type { EntityRole } from "@/types/api"
import type { UserRole } from "@/lib/auth"
import { getControlPlaneContext, listControlPlaneEntities } from "@/lib/api/control-plane"
import { controlPlaneQueryKeys } from "@/lib/query/controlPlane"
import { EntitySwitcher } from "@/components/layout/EntitySwitcher"
import { Button } from "@/components/ui/button"
import { SidebarBase } from "@/components/shell/primitives/SidebarBase"
import { useTenantStore } from "@/lib/store/tenant"
import { cn } from "@/lib/utils"

const CONTROL_PLANE_NAV = [
  {
    label: "Operate",
    items: [
      { href: "/control-plane/overview", label: "Overview" },
      { href: "/control-plane/intents", label: "Intents" },
      { href: "/control-plane/jobs", label: "Jobs" },
      { href: "/control-plane/timeline", label: "Timeline" },
    ],
  },
  {
    label: "Trace",
    items: [
      { href: "/control-plane/lineage", label: "Lineage" },
      { href: "/control-plane/snapshots", label: "Snapshots" },
      { href: "/control-plane/airlock", label: "Airlock" },
    ],
  },
  {
    label: "Governance",
    items: [
      { href: "/control-plane/entities", label: "Entities" },
      { href: "/control-plane/modules", label: "Modules" },
      { href: "/control-plane/incidents", label: "Incidents" },
      { href: "/control-plane/admin", label: "Admin" },
    ],
  },
] as const

interface AppSidebarProps {
  tenantSlug: string
  userRole: UserRole
  userName: string
  userEmail: string
  entityRoles: EntityRole[]
}

export function AppSidebar({
  tenantSlug,
  userRole,
  userName,
  userEmail,
  entityRoles,
}: AppSidebarProps) {
  const pathname = usePathname() ?? ""
  const activeEntityId = useTenantStore((state) => state.active_entity_id)
  const entitiesQuery = useQuery({
    queryKey: controlPlaneQueryKeys.entities(),
    queryFn: listControlPlaneEntities,
  })
  const contextQuery = useQuery({
    queryKey: controlPlaneQueryKeys.context({ entity_id: activeEntityId ?? undefined }),
    queryFn: () => getControlPlaneContext({ entity_id: activeEntityId ?? undefined }),
    staleTime: 60_000,
  })

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

  const organizationLabel =
    contextQuery.data?.current_organisation.organisation_name ??
    contextQuery.data?.tenant_slug ??
    tenantSlug ??
    "Unavailable"

  return (
    <SidebarBase className="hidden md:flex">
      <div className="border-b border-border px-4 py-4">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
          Financial Control Plane
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
            <p>Period: {contextQuery.data?.current_period.period_label ?? "Unavailable"}</p>
          </div>
        </div>
      </div>

      <nav aria-label="Control plane navigation" className="flex-1 space-y-4 overflow-y-auto p-4">
        {CONTROL_PLANE_NAV.map((section) => (
          <section key={section.label} className="space-y-2">
            <p className="px-2 text-xs uppercase tracking-[0.18em] text-muted-foreground">{section.label}</p>
            <div className="space-y-1">
              {section.items.map((item) => {
                const isActive = pathname === item.href || pathname.startsWith(`${item.href}/`)
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={cn(
                      "block rounded-xl border px-3 py-2 text-sm transition-colors",
                      isActive
                        ? "border-foreground bg-foreground text-background"
                        : "border-transparent bg-card text-muted-foreground hover:border-border hover:text-foreground",
                    )}
                  >
                    {item.label}
                  </Link>
                )
              })}
            </div>
          </section>
        ))}
      </nav>

      <div className="space-y-3 border-t border-border p-4">
        <EntitySwitcher entityRoles={entityOptions} />
        <div className="rounded-2xl border border-border bg-background p-4 shadow-sm">
          <p className="text-sm font-medium text-foreground">{userName}</p>
          <p className="text-xs text-muted-foreground">{userEmail}</p>
          <p className="mt-1 text-xs uppercase tracking-wide text-muted-foreground">
            Role: {String(userRole).replace(/_/g, " ")}
          </p>
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
      </div>
    </SidebarBase>
  )
}
