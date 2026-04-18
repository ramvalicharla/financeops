"use client"

import Link from "next/link"
import { useCallback, useEffect, useState } from "react"
import { Plus } from "lucide-react"
import { createForecastRun, listForecastRuns } from "@/lib/api/forecast"
import type { ForecastRun } from "@/lib/types/forecast"

export default function ForecastHomePage() {
  const [rows, setRows] = useState<ForecastRun[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const payload = await listForecastRuns({ limit: 100, offset: 0 })
      setRows(payload.data)
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : "Failed to load forecast runs")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const createRun = async () => {
    setCreating(true)
    try {
      await createForecastRun({
        run_name: `Rolling Forecast ${new Date().toISOString().slice(0, 7)}`,
        forecast_type: "rolling_12",
        base_period: new Date().toISOString().slice(0, 7),
        horizon_months: 12,
      })
      await load()
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : "Failed to create forecast run")
    } finally {
      setCreating(false)
    }
  }

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Forecast Runs</h1>
          <p className="text-sm text-muted-foreground">Rolling 12-month projections with editable assumptions.</p>
        </div>
        <button
          type="button"
          onClick={createRun}
          disabled={creating}
          className="inline-flex items-center gap-2 rounded-md border border-border px-3 py-2 text-sm"
        >
          <Plus className="h-4 w-4" />
          New Forecast
        </button>
      </header>

      {loading ? <div className="h-36 animate-pulse rounded-xl bg-muted" /> : null}
      {error ? <p className="text-sm text-[hsl(var(--brand-danger))]">{error}</p> : null}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {rows.map((row) => (
          <Link key={row.id} href={`/forecast/${row.id}`} className="rounded-xl border border-border bg-card p-4">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium text-foreground">{row.run_name}</p>
              <span className="rounded-full border border-border px-2 py-0.5 text-xs text-muted-foreground">
                {row.status}
              </span>
            </div>
            <p className="mt-1 text-xs text-muted-foreground">Base: {row.base_period}</p>
            <p className="text-xs text-muted-foreground">Horizon: {row.horizon_months} months</p>
          </Link>
        ))}
      </div>
    </div>
  )
}

