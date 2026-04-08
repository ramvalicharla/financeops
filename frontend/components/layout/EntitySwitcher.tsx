"use client"

import { useMemo } from "react"
import { useTenantStore } from "@/lib/store/tenant"

type EntitySwitcherOption = {
  entity_id: string
  entity_name: string
  role?: "admin" | "accountant" | "auditor" | "viewer" | null
}

const roleLabelMap: Record<NonNullable<EntitySwitcherOption["role"]>, string> = {
  admin: "Admin",
  accountant: "Accountant",
  auditor: "Auditor",
  viewer: "Viewer",
}

interface EntitySwitcherProps {
  entityRoles: EntitySwitcherOption[]
}

export function EntitySwitcher({ entityRoles }: EntitySwitcherProps) {
  const activeEntityId = useTenantStore((state) => state.active_entity_id)
  const setActiveEntity = useTenantStore((state) => state.setActiveEntity)

  const activeEntity = useMemo(
    () => entityRoles.find((role) => role.entity_id === activeEntityId) ?? null,
    [activeEntityId, entityRoles],
  )

  if (!entityRoles.length) {
    return (
      <div className="rounded-md border border-border bg-muted/30 px-3 py-2 text-sm text-muted-foreground">
        No entity access
      </div>
    )
  }

  return (
    <div className="space-y-2">
      <p className="text-xs uppercase tracking-wide text-muted-foreground">Entity</p>
      <select
        aria-label="Select active scope"
        className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
        value={activeEntityId ?? entityRoles[0]?.entity_id}
        onChange={(event) => setActiveEntity(event.target.value)}
      >
        {entityRoles.map((entityRole) => (
          <option key={entityRole.entity_id} value={entityRole.entity_id}>
            {entityRole.entity_name}
            {entityRole.role ? ` (${roleLabelMap[entityRole.role]})` : ""}
          </option>
        ))}
      </select>
      {activeEntity?.role ? (
        <span className="inline-flex rounded-full bg-accent px-2 py-1 text-xs font-medium text-accent-foreground">
          {roleLabelMap[activeEntity.role]}
        </span>
      ) : null}
    </div>
  )
}
