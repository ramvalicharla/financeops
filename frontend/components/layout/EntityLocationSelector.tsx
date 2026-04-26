"use client"

import { useEffect, useMemo } from "react"
import { useQuery } from "@tanstack/react-query"
import { listLocations } from "@/lib/api/locations"
import { useLocationStore } from "@/lib/store/location"
import { useTenantStore } from "@/lib/store/tenant"
import { useWorkspaceStore } from "@/lib/store/workspace"
import { queryKeys } from "@/lib/query/keys"

export function EntityLocationSelector() {
  const entityRoles = useTenantStore((state) => state.entity_roles)
  const activeEntityId = useWorkspaceStore((s) => s.entityId)
  const switchEntity = useWorkspaceStore((s) => s.switchEntity)
  const activeLocationId = useLocationStore((state) => state.active_location_id)
  const setActiveLocation = useLocationStore((state) => state.setActiveLocation)

  const locationsQuery = useQuery({
    queryKey: queryKeys.settings.entityLocations(activeEntityId),
    queryFn: () =>
      listLocations({
        entity_id: activeEntityId ?? "",
        is_active: true,
        skip: 0,
        limit: 200,
      }),
    enabled: Boolean(activeEntityId),
  })

  const locationItems = useMemo(() => locationsQuery.data?.items ?? [], [locationsQuery.data])
  const entityCount = entityRoles.length

  useEffect(() => {
    if (!activeEntityId) {
      setActiveLocation(null)
      return
    }
    if (!locationItems.length) {
      setActiveLocation(null)
      return
    }
    const match = locationItems.find((item) => item.id === activeLocationId)
    if (match) {
      return
    }
    if (locationItems.length === 1) {
      setActiveLocation(locationItems[0]?.id ?? null)
      return
    }
    const primary = locationItems.find((item) => item.is_primary)
    setActiveLocation(primary?.id ?? null)
  }, [activeEntityId, activeLocationId, locationItems, setActiveLocation])

  const shouldHide = useMemo(() => {
    if (entityCount > 1) {
      return false
    }
    if (entityCount === 1 && locationItems.length <= 1) {
      return true
    }
    return false
  }, [entityCount, locationItems.length])

  if (!entityCount) {
    return null
  }
  if (shouldHide) {
    return null
  }

  return (
    <div className="flex min-w-0 items-center gap-2 overflow-hidden">
      {entityCount > 1 ? (
        <select
          aria-label="Select active entity"
          className="max-w-[132px] rounded-md border border-border bg-background px-2 py-1.5 text-xs text-foreground md:max-w-[220px]"
          value={activeEntityId ?? ""}
          onChange={(event) => {
            const nextEntityId = event.target.value || null
            switchEntity(nextEntityId)
            setActiveLocation(null)
          }}
        >
          <option value="">Select entity</option>
          {entityRoles.map((role) => (
            <option key={role.entity_id} value={role.entity_id}>
              {role.entity_name}
            </option>
          ))}
        </select>
      ) : null}

      {(entityCount > 1 || locationItems.length > 1) && activeEntityId ? (
        <select
          aria-label="Select active location"
          className="max-w-[132px] rounded-md border border-border bg-background px-2 py-1.5 text-xs text-foreground md:max-w-[220px]"
          value={activeLocationId ?? ""}
          onChange={(event) => setActiveLocation(event.target.value || null)}
        >
          <option value="">All locations</option>
          {locationItems.map((item) => (
            <option key={item.id} value={item.id}>
              {item.location_name}
            </option>
          ))}
        </select>
      ) : null}
    </div>
  )
}
