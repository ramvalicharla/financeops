"use client"

import { usePathname } from "next/navigation"
import { useMemo } from "react"
import { useQuery } from "@tanstack/react-query"
import type { UserRole } from "@/lib/auth"
import { getControlPlaneContext } from "@/lib/api/control-plane"
import { resolveWorkspaceFromTabs } from "@/lib/control-plane"
import { controlPlaneQueryKeys } from "@/lib/query/controlPlane"
import { ContextBarBase } from "@/components/shell/primitives/ContextBarBase"
import { useTenantStore } from "@/lib/store/tenant"

interface ContextHeaderProps {
  tenantSlug: string
  userRole: UserRole
}

export function ContextHeader({ tenantSlug, userRole }: ContextHeaderProps) {
  const pathname = usePathname() ?? ""
  const activeEntityId = useTenantStore((state) => state.active_entity_id)
  const contextQuery = useQuery({
    queryKey: controlPlaneQueryKeys.context({ entity_id: activeEntityId ?? undefined }),
    queryFn: () => getControlPlaneContext({ entity_id: activeEntityId ?? undefined }),
    staleTime: 60_000,
  })

  const matchedWorkspace = useMemo(
    () => resolveWorkspaceFromTabs(pathname, contextQuery.data?.workspace_tabs ?? []),
    [contextQuery.data?.workspace_tabs, pathname],
  )

  return (
    <ContextBarBase>
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
          Active Context
        </span>
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-full border border-border bg-background px-3 py-1 text-sm text-foreground">
            Org{" "}
            <span className="ml-1 font-semibold">
              {contextQuery.data?.current_organisation.organisation_name ??
                contextQuery.data?.tenant_slug ??
                tenantSlug}
            </span>
          </span>
          <span className="rounded-full border border-border bg-background px-3 py-1 text-sm text-foreground">
            Entity{" "}
            <span className="ml-1 font-semibold">
              {contextQuery.data?.current_entity.entity_name ?? "Unavailable"}
            </span>
          </span>
          <span className="rounded-full border border-border bg-background px-3 py-1 text-sm text-foreground">
            Period{" "}
            <span className="ml-1 font-semibold">
              {contextQuery.data?.current_period.period_label ?? "Unavailable"}
            </span>
          </span>
          <span className="rounded-full border border-border bg-background px-3 py-1 text-sm text-foreground">
            Scope <span className="ml-1 font-semibold">{matchedWorkspace?.workspace_name ?? "Control plane"}</span>
          </span>
          <span className="rounded-full border border-border bg-background px-3 py-1 text-sm text-foreground">
            Role <span className="ml-1 font-semibold">{String(userRole).replace(/_/g, " ")}</span>
          </span>
          <span className="rounded-full border border-border bg-background px-3 py-1 text-sm text-muted-foreground">
            Snapshot unavailable in current contract
          </span>
          <span className="rounded-full border border-border bg-background px-3 py-1 text-sm text-muted-foreground">
            Connection derived from backend state
          </span>
          <span className="rounded-full border border-border bg-background px-3 py-1 text-sm text-muted-foreground">
            Event watermark unavailable
          </span>
        </div>
      </div>
    </ContextBarBase>
  )
}
