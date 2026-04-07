"use client"

import { useEffect, useMemo, useState } from "react"
import { useParams } from "next/navigation"
import { AssumptionsPanel } from "@/components/forecast/AssumptionsPanel"
import { ForecastChart } from "@/components/forecast/ForecastChart"
import { ForecastTable } from "@/components/forecast/ForecastTable"
import {
  computeForecast,
  exportForecast,
  getForecastRun,
  publishForecast,
  updateForecastAssumption,
} from "@/lib/api/forecast"
import type { ForecastRunDetail } from "@/lib/types/forecast"

export default function ForecastRunPage() {
  const params = useParams()
  const runId = Array.isArray(params?.id) ? params.id[0] : params?.id ?? ""
  const [detail, setDetail] = useState<ForecastRunDetail | null>(null)
  const [metric, setMetric] = useState("Revenue")
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const payload = await getForecastRun(runId)
      setDetail(payload)
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : "Failed to load forecast run")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (runId) {
      void load()
    }
  }, [runId])

  const metrics = useMemo(
    () => Array.from(new Set(detail?.line_items.map((row) => row.mis_line_item) ?? [])),
    [detail],
  )

  useEffect(() => {
    if (metrics.length === 0) return
    if (!metrics.includes(metric)) {
      setMetric(metrics[0])
    }
  }, [metric, metrics])

  const handleUpdateAssumption = async (key: string, value: string, basis?: string) => {
    await updateForecastAssumption(runId, key, { value, basis })
    await load()
  }

  const handleRecalculate = async () => {
    await computeForecast(runId)
    await load()
  }

  const handlePublish = async () => {
    await publishForecast(runId)
    await load()
  }

  const handleExport = async () => {
    const blob = await exportForecast(runId)
    const url = URL.createObjectURL(blob)
    const link = document.createElement("a")
    link.href = url
    link.download = `forecast_${runId}.xlsx`
    link.click()
    URL.revokeObjectURL(url)
  }

  if (loading) {
    return <div className="h-64 animate-pulse rounded-xl bg-muted" />
  }

  if (!detail) {
    return <p className="text-sm text-[hsl(var(--brand-danger))]">{error ?? "Forecast run not found"}</p>
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">{detail.run.run_name}</h1>
          <p className="text-sm text-muted-foreground">
            Base period {detail.run.base_period} · horizon {detail.run.horizon_months} months
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handlePublish}
            className="rounded-md border border-border px-3 py-2 text-sm text-foreground"
          >
            Publish
          </button>
          <button
            type="button"
            onClick={handleExport}
            className="rounded-md border border-border px-3 py-2 text-sm text-foreground"
          >
            Export
          </button>
        </div>
      </header>

      {error ? <p className="text-sm text-[hsl(var(--brand-danger))]">{error}</p> : null}

      <div className="grid gap-4 xl:grid-cols-[2fr_1fr]">
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <label className="text-xs uppercase tracking-[0.14em] text-muted-foreground">Metric</label>
            <select
              value={metric}
              onChange={(event) => setMetric(event.target.value)}
              className="rounded-md border border-border bg-background px-3 py-2 text-sm"
            >
              {metrics.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </div>
          <ForecastChart lines={detail.line_items} metric={metric} basePeriod={detail.run.base_period} />
        </div>
        <AssumptionsPanel
          assumptions={detail.assumptions}
          onUpdate={handleUpdateAssumption}
          onRecalculate={handleRecalculate}
        />
      </div>

      <ForecastTable lines={detail.line_items} />
    </div>
  )
}
