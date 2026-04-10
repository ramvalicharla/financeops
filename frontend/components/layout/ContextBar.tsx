"use client"

import { usePathname } from "next/navigation"
import { useQuery } from "@tanstack/react-query"
import { getControlPlaneContext } from "@/lib/api/control-plane"
import { resolveControlPlaneModule } from "@/lib/control-plane"
import { useTenantStore } from "@/lib/store/tenant"

interface ContextBarProps {
  tenantSlug: string
}

const periodLabel = (value: string) => {
  const [year, month] = value.split("-")
  if (!year || !month) {
    return value
  }
  return new Date(Number(year), Number(month) - 1, 1).toLocaleDateString(undefined, {
    month: "short",
    year: "numeric",
  })
}

export function ContextBar({ tenantSlug: _tenantSlug }: ContextBarProps) {
  const pathname = usePathname() ?? ""
  const activeEntityId = useTenantStore((state) => state.active_entity_id)
  const workspace = resolveControlPlaneModule(pathname).key
  const contextQuery = useQuery({
    queryKey: ["control-plane-context", activeEntityId, workspace],
    queryFn: () =>
      getControlPlaneContext({
        entity_id: activeEntityId ?? undefined,
        workspace,
        module: workspace,
      }),
    staleTime: 60_000,
  })
  const organizationLabel = contextQuery.isLoading
    ? "Loading..."
    : contextQuery.data?.current_organisation.organisation_name ??
      contextQuery.data?.tenant_slug ??
      "Unavailable"
  const periodValue = contextQuery.data?.current_period.period_label
  const moduleLabel = contextQuery.isLoading
    ? "Loading..."
    : contextQuery.data?.current_module.module_name ?? "Unavailable"
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
            Period <span className="ml-1 font-semibold">{periodLabel(periodValue ?? "Unavailable")}</span>
          </span>
        </div>
      </div>
    </div>
  )
}
