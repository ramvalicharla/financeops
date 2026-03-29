"use client"

import { useMemo, useState } from "react"

interface ScenarioSliderProps {
  values: {
    revenue_growth_pct_monthly: number
    cogs_pct_of_revenue: number
    opex_growth_pct_monthly: number
  }
  onChange: (values: Record<string, string>) => Promise<void>
  onRecompute: () => Promise<void>
  impactPreview: string
}

export function ScenarioSlider({ values, onChange, onRecompute, impactPreview }: ScenarioSliderProps) {
  const [local, setLocal] = useState(values)
  const [saving, setSaving] = useState(false)
  const entries = useMemo(
    () => [
      { key: "revenue_growth_pct_monthly", label: "Revenue growth %", min: -10, max: 20, step: 0.1 },
      { key: "cogs_pct_of_revenue", label: "COGS % of revenue", min: 20, max: 90, step: 0.1 },
      { key: "opex_growth_pct_monthly", label: "OpEx growth %", min: -5, max: 15, step: 0.1 },
    ],
    [],
  )

  const persist = async () => {
    setSaving(true)
    try {
      await onChange(
        Object.fromEntries(
          Object.entries(local).map(([key, value]) => [key, value.toFixed(2)]),
        ),
      )
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="rounded-xl border border-border bg-card p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-foreground">Driver Controls</h2>
        <p className="text-xs text-muted-foreground">EBITDA {impactPreview} vs base case</p>
      </div>
      <div className="space-y-4">
        {entries.map((entry) => (
          <div key={entry.key}>
            <div className="mb-1 flex items-center justify-between text-xs text-muted-foreground">
              <span>{entry.label}</span>
              <span>{local[entry.key as keyof typeof local].toFixed(2)}%</span>
            </div>
            <input
              type="range"
              min={entry.min}
              max={entry.max}
              step={entry.step}
              value={local[entry.key as keyof typeof local]}
              onChange={(event) =>
                setLocal((current) => ({
                  ...current,
                  [entry.key]: Number.parseFloat(event.target.value),
                }))
              }
              className="w-full"
            />
          </div>
        ))}
      </div>
      <div className="mt-4 flex items-center gap-2">
        <button
          type="button"
          onClick={() => void persist()}
          className="rounded-md border border-border px-3 py-2 text-sm"
          disabled={saving}
        >
          Save Overrides
        </button>
        <button
          type="button"
          onClick={() => void onRecompute()}
          className="rounded-md bg-[hsl(var(--brand-primary))] px-3 py-2 text-sm font-medium text-black"
        >
          Recompute
        </button>
      </div>
    </section>
  )
}

