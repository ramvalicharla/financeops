"use client"

import { useMemo } from "react"
import { useQuery } from "@tanstack/react-query"
import { listControlPlaneEntities } from "@/lib/api/control-plane"
import { useControlPlaneStore } from "@/lib/store/controlPlane"
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

export function ContextBar({ tenantSlug }: ContextBarProps) {
  const activeEntityId = useTenantStore((state) => state.active_entity_id)
  const currentModule = useControlPlaneStore((state) => state.current_module)
  const currentPeriod = useControlPlaneStore((state) => state.current_period)
  const currentOrg = useControlPlaneStore((state) => state.current_org) ?? tenantSlug
  const entitiesQuery = useQuery({
    queryKey: ["control-plane-entities"],
    queryFn: listControlPlaneEntities,
  })

  const activeEntity = useMemo(
    () => entitiesQuery.data?.find((entity) => entity.id === activeEntityId) ?? null,
    [activeEntityId, entitiesQuery.data],
  )

  return (
    <div className="border-b border-border bg-card/60 px-4 py-3 md:px-6">
      <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
        <span className="font-medium text-foreground">Context</span>
        <span>Org: {currentOrg}</span>
        <span>&rarr;</span>
        <span>Entity: {activeEntity?.entity_name ?? "No active entity"}</span>
        <span>&rarr;</span>
        <span>Module: {currentModule ?? "Dashboard"}</span>
        <span>&rarr;</span>
        <span>Period: {periodLabel(currentPeriod)}</span>
      </div>
    </div>
  )
}
