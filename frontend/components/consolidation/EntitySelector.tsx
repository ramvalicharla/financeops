"use client"

import { Button } from "@/components/ui/button"
import { FXRateDisplay } from "@/components/consolidation/FXRateDisplay"
import type { ConsolidationEntity } from "@/types/consolidation"

interface EntitySelectorProps {
  entities: ConsolidationEntity[]
  selectedEntityIds: string[]
  onSelectionChange: (entityIds: string[]) => void
}

export function EntitySelector({
  entities,
  selectedEntityIds,
  onSelectionChange,
}: EntitySelectorProps) {
  const selectAll = () => {
    onSelectionChange(entities.map((entity) => entity.entity_id))
  }

  const deselectAll = () => {
    onSelectionChange([])
  }

  const toggleEntity = (entityId: string) => {
    if (selectedEntityIds.includes(entityId)) {
      onSelectionChange(selectedEntityIds.filter((id) => id !== entityId))
      return
    }
    onSelectionChange([...selectedEntityIds, entityId])
  }

  return (
    <section className="h-full rounded-lg border border-border bg-card p-4">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-lg font-semibold text-foreground">Entities</h3>
        <div className="flex gap-2">
          <Button size="sm" type="button" variant="outline" onClick={selectAll}>
            Select all
          </Button>
          <Button size="sm" type="button" variant="outline" onClick={deselectAll}>
            Deselect all
          </Button>
        </div>
      </div>
      <div className="space-y-2">
        {entities.map((entity) => (
          <label
            key={entity.entity_id}
            className="flex cursor-pointer items-center justify-between rounded-md border border-border px-3 py-2 hover:bg-accent/30"
          >
            <span className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={selectedEntityIds.includes(entity.entity_id)}
                onChange={() => toggleEntity(entity.entity_id)}
              />
              <span className="text-sm text-foreground">{entity.entity_name}</span>
            </span>
            <div className="flex items-center gap-2">
              <span className="rounded-full bg-muted px-2 py-1 text-xs text-muted-foreground">
                {entity.currency}
              </span>
              <FXRateDisplay
                currency={entity.currency}
                rate={entity.fx_rate_to_inr}
              />
            </div>
          </label>
        ))}
      </div>
    </section>
  )
}
