"use client"

import { useMemo, useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { deriveConsolidationMethod } from "@/components/org-setup/constants"
import type { OrgEntity, OwnershipPayload } from "@/lib/api/orgSetup"

interface Step3OwnershipProps {
  entities: OrgEntity[]
  submitting: boolean
  onSubmit: (relationships: OwnershipPayload[]) => Promise<void>
}

interface RelationshipDraft {
  parent_entity_id: string
  child_entity_id: string
  ownership_pct: string
  effective_from: string
  notes: string
}

const defaultDraft = (): RelationshipDraft => ({
  parent_entity_id: "",
  child_entity_id: "",
  ownership_pct: "51.0000",
  effective_from: new Date().toISOString().slice(0, 10),
  notes: "",
})

export function Step3Ownership({ entities, submitting, onSubmit }: Step3OwnershipProps) {
  const [rows, setRows] = useState<RelationshipDraft[]>([defaultDraft()])

  const entityById = useMemo(() => {
    return new Map(entities.map((entity) => [entity.id, entity]))
  }, [entities])

  if (entities.length <= 1) {
    return (
      <section className="space-y-4 rounded-xl border border-border bg-card p-5">
        <h2 className="text-lg font-semibold text-foreground">Ownership structure</h2>
        <p className="text-sm text-muted-foreground">
          Single entity - no ownership structure required.
        </p>
        <div className="flex justify-end">
          <Button disabled={submitting} onClick={() => onSubmit([])}>
            {submitting ? "Saving..." : "Continue"}
          </Button>
        </div>
      </section>
    )
  }

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const payload: OwnershipPayload[] = rows
      .filter((row) => row.parent_entity_id && row.child_entity_id)
      .map((row) => ({
        parent_entity_id: row.parent_entity_id,
        child_entity_id: row.child_entity_id,
        ownership_pct: row.ownership_pct,
        effective_from: row.effective_from,
        notes: row.notes || null,
      }))
    await onSubmit(payload)
  }

  const updateRow = <K extends keyof RelationshipDraft>(
    index: number,
    key: K,
    value: RelationshipDraft[K],
  ) => {
    setRows((previous) => {
      const next = [...previous]
      next[index] = { ...next[index], [key]: value }
      return next
    })
  }

  return (
    <form className="space-y-4 rounded-xl border border-border bg-card p-5" onSubmit={handleSubmit}>
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-foreground">Ownership structure</h2>
        <Button type="button" variant="outline" onClick={() => setRows((previous) => [...previous, defaultDraft()])}>
          Add relationship
        </Button>
      </div>
      <div className="space-y-3">
        {rows.map((row, index) => {
          const childEntityType = entityById.get(row.child_entity_id)?.entity_type
          const method = childEntityType
            ? deriveConsolidationMethod(row.ownership_pct, childEntityType)
            : "-"
          return (
            <div key={index} className="grid gap-3 rounded-lg border border-border bg-background/40 p-4 md:grid-cols-5">
              <select
                value={row.parent_entity_id}
                onChange={(event) => updateRow(index, "parent_entity_id", event.target.value)}
                className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
              >
                <option value="">Parent entity</option>
                {entities.map((entity) => (
                  <option key={entity.id} value={entity.id}>
                    {entity.display_name ?? entity.legal_name}
                  </option>
                ))}
              </select>
              <select
                value={row.child_entity_id}
                onChange={(event) => updateRow(index, "child_entity_id", event.target.value)}
                className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
              >
                <option value="">Child entity</option>
                {entities
                  .filter((entity) => entity.id !== row.parent_entity_id)
                  .map((entity) => (
                    <option key={entity.id} value={entity.id}>
                      {entity.display_name ?? entity.legal_name}
                    </option>
                  ))}
              </select>
              <Input
                placeholder="Ownership %"
                value={row.ownership_pct}
                onChange={(event) => updateRow(index, "ownership_pct", event.target.value)}
                min="0.01"
                max="100.00"
              />
              <Input
                type="date"
                value={row.effective_from}
                onChange={(event) => updateRow(index, "effective_from", event.target.value)}
              />
              <div className="flex items-center justify-between gap-2">
                <span className="rounded-full bg-muted px-2 py-1 text-xs text-foreground">{method}</span>
                {rows.length > 1 ? (
                  <button
                    type="button"
                    className="text-xs text-[hsl(var(--brand-danger))]"
                    onClick={() => setRows((previous) => previous.filter((_, rowIndex) => rowIndex !== index))}
                  >
                    Remove
                  </button>
                ) : null}
              </div>
            </div>
          )
        })}
      </div>
      <div className="flex justify-end">
        <Button type="submit" disabled={submitting}>
          {submitting ? "Saving..." : "Continue"}
        </Button>
      </div>
    </form>
  )
}
