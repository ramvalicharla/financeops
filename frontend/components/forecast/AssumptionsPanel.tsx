"use client"

import { useMemo, useState } from "react"
import type { ForecastAssumption } from "@/lib/types/forecast"

interface AssumptionsPanelProps {
  assumptions: ForecastAssumption[]
  onUpdate: (key: string, value: string, basis?: string) => Promise<void>
  onRecalculate: () => Promise<void>
}

export function AssumptionsPanel({ assumptions, onUpdate, onRecalculate }: AssumptionsPanelProps) {
  const [savingKey, setSavingKey] = useState<string | null>(null)
  const [recalculating, setRecalculating] = useState(false)

  const grouped = useMemo(() => {
    const map = new Map<string, ForecastAssumption[]>()
    for (const row of assumptions) {
      const list = map.get(row.category) ?? []
      list.push(row)
      map.set(row.category, list)
    }
    return Array.from(map.entries())
  }, [assumptions])

  const save = async (row: ForecastAssumption, value: string) => {
    setSavingKey(row.assumption_key)
    try {
      await onUpdate(row.assumption_key, value, row.basis ?? undefined)
    } finally {
      setSavingKey(null)
    }
  }

  const recalculate = async () => {
    setRecalculating(true)
    try {
      await onRecalculate()
    } finally {
      setRecalculating(false)
    }
  }

  return (
    <aside className="rounded-xl border border-border bg-card p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-foreground">Assumptions</h2>
        <button
          type="button"
          onClick={recalculate}
          disabled={recalculating}
          className="rounded-md border border-border px-2 py-1 text-xs text-foreground"
        >
          Recalculate
        </button>
      </div>
      <div className="space-y-4">
        {grouped.map(([category, rows]) => (
          <section key={category} className="space-y-2">
            <h3 className="text-xs uppercase tracking-[0.14em] text-muted-foreground">{category}</h3>
            {rows.map((row) => (
              <div key={row.id} className="rounded-md border border-border/60 bg-background px-3 py-2">
                <label className="block text-xs text-muted-foreground">{row.assumption_label}</label>
                <input
                  defaultValue={row.assumption_value}
                  onBlur={(event) => void save(row, event.target.value)}
                  className="mt-1 w-full rounded-md border border-border bg-background px-2 py-1 text-sm text-foreground"
                />
                <p className="mt-1 text-[11px] text-muted-foreground">
                  Last updated {new Date(row.updated_at).toLocaleString()}
                </p>
                {savingKey === row.assumption_key ? (
                  <p className="text-[11px] text-[hsl(var(--brand-primary))]">Saving…</p>
                ) : null}
              </div>
            ))}
          </section>
        ))}
      </div>
    </aside>
  )
}

