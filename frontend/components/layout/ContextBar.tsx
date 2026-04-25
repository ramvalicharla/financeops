"use client"

import { usePathname } from "next/navigation"
import { useMemo } from "react"
import { useQuery } from "@tanstack/react-query"
import { getControlPlaneContext } from "@/lib/api/control-plane"
import { resolveWorkspaceFromTabs } from "@/lib/control-plane"
import { useWorkspaceStore } from "@/lib/store/workspace"
import { queryKeys } from "@/lib/query/keys"

interface ContextBarProps {
  tenantSlug: string
}

export function ContextBar({ tenantSlug: _tenantSlug }: ContextBarProps) {
  const pathname = usePathname() ?? ""
  const activeEntityId = useWorkspaceStore((s) => s.entityId)
  const contextQuery = useQuery({
    queryKey: queryKeys.workspace.context(activeEntityId),
    queryFn: () =>
      getControlPlaneContext({
        entity_id: activeEntityId ?? undefined,
      }),
    staleTime: 60_000,
  })
  const matchedWorkspace = useMemo(
    () => resolveWorkspaceFromTabs(pathname, contextQuery.data?.workspace_tabs ?? []),
    [contextQuery.data?.workspace_tabs, pathname],
  )
  const organizationLabel = contextQuery.isLoading
    ? "Loading..."
    : contextQuery.data?.current_organisation.organisation_name ??
      contextQuery.data?.tenant_slug ??
      "Unavailable"
  const periodValue = contextQuery.data?.current_period.period_label
  const moduleLabel = contextQuery.isLoading
    ? "Loading..."
    : matchedWorkspace?.workspace_name ?? contextQuery.data?.current_module.module_name ?? "Unavailable"
  const entityLabel = contextQuery.isLoading
    ? "Loading..."
    : contextQuery.data?.current_entity.entity_name ?? "Unavailable"

  return (
    <div className="border-b border-border bg-card/70 px-4 py-3 md:px-6">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
          Active Context
        </span>
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-full border border-border bg-background px-3 py-1 text-sm text-foreground">
            Org <span className="ml-1 font-semibold">{organizationLabel}</span>
          </span>
          <span className="text-muted-foreground">&rarr;</span>
          <span className="rounded-full border border-border bg-background px-3 py-1 text-sm text-foreground">
            Entity <span className="ml-1 font-semibold">{entityLabel}</span>
          </span>
          <span className="text-muted-foreground">&rarr;</span>
          <span className="rounded-full border border-border bg-background px-3 py-1 text-sm text-foreground">
            Modules <span className="ml-1 font-semibold">{moduleLabel}</span>
          </span>
          <span className="text-muted-foreground">&rarr;</span>
          <span className="rounded-full border border-[hsl(var(--brand-primary)/0.28)] bg-[hsl(var(--brand-primary)/0.08)] px-3 py-1 text-sm text-foreground">
            Period <span className="ml-1 font-semibold">{periodValue ?? "Unavailable"}</span>
          </span>
        </div>
      </div>
    </div>
  )
}
