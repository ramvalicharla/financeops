"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { useParams } from "next/navigation"
import { BudgetTable } from "@/components/budget/BudgetTable"
import { BudgetVsActualChart } from "@/components/budget/BudgetVsActualChart"
import { exportBudgetVsActual, getBudgetVsActual, listBudgetVersions } from "@/lib/api/budget"
import type { BudgetVersion, BudgetVsActualPayload } from "@/lib/types/budget"

const periodsForYear = (year: number): string[] =>
  Array.from({ length: 12 }, (_, index) => `${year}-${String(index + 1).padStart(2, "0")}`)

export default function BudgetYearPage() {
  const params = useParams()
  const yearParam = Array.isArray(params?.year) ? params.year[0] : params?.year
  const year = Number.parseInt(yearParam ?? "", 10)
  const [versions, setVersions] = useState<BudgetVersion[]>([])
  const [versionId, setVersionId] = useState<string>("")
  const [period, setPeriod] = useState<string>(`${year}-12`)
  const [payload, setPayload] = useState<BudgetVsActualPayload | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [metric, setMetric] = useState<string>("Revenue")

  useEffect(() => {
    const load = async () => {
      setLoading(true)
      setError(null)
      try {
        const versionPayload = await listBudgetVersions({
          fiscal_year: year,
          limit: 100,
          offset: 0,
        })
        setVersions(versionPayload.data)
        const preferred = versionPayload.data.find((item) => item.status === "approved") ?? versionPayload.data[0]
        const selectedVersionId = preferred?.id ?? ""
        setVersionId(selectedVersionId)
        const data = await getBudgetVsActual({
          fiscal_year: year,
          period,
          version_id: selectedVersionId || undefined,
        })
        setPayload(data)
      } catch (fetchError) {
        setError(fetchError instanceof Error ? fetchError.message : "Failed to load budget view")
      } finally {
        setLoading(false)
      }
    }
    if (Number.isFinite(year)) {
      void load()
    }
  }, [period, year])

  useEffect(() => {
    if (!versionId) return
    const loadForVersion = async () => {
      try {
        const data = await getBudgetVsActual({
          fiscal_year: year,
          period,
          version_id: versionId,
        })
        setPayload(data)
      } catch (fetchError) {
        setError(fetchError instanceof Error ? fetchError.message : "Failed to refresh budget view")
      }
    }
    void loadForVersion()
  }, [period, versionId, year])

  const metrics = useMemo(() => payload?.lines.map((line) => line.mis_line_item) ?? [], [payload])

  useEffect(() => {
    if (metrics.length === 0) return
    if (!metrics.includes(metric)) {
      setMetric(metrics[0])
    }
  }, [metric, metrics])

  const onExport = async () => {
    if (!payload) return
    const blob = await exportBudgetVsActual({
      fiscal_year: year,
      period,
      version_id: payload.version_id,
    })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = `Budget_vs_Actual_${year}_${period}.xlsx`
    a.click()
    URL.revokeObjectURL(url)
  }

  if (!Number.isFinite(year)) {
    return <p className="text-sm text-[hsl(var(--brand-danger))]">Invalid fiscal year.</p>
  }

  if (loading) {
    return <div className="h-64 animate-pulse rounded-xl bg-muted" />
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Budget vs Actual {year}</h1>
          <p className="text-sm text-muted-foreground">Compare approved budget against current actuals.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={versionId}
            onChange={(event) => setVersionId(event.target.value)}
            className="rounded-md border border-border bg-background px-3 py-2 text-sm"
          >
            {versions.map((version) => (
              <option key={version.id} value={version.id}>
                {version.version_name} ({version.status})
              </option>
            ))}
          </select>
          <select
            value={period}
            onChange={(event) => setPeriod(event.target.value)}
            className="rounded-md border border-border bg-background px-3 py-2 text-sm"
          >
            {periodsForYear(year).map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={onExport}
            className="rounded-md border border-border px-3 py-2 text-sm text-foreground"
          >
            Export to Excel
          </button>
        </div>
      </header>

      {error ? <p className="text-sm text-[hsl(var(--brand-danger))]">{error}</p> : null}
      {payload ? (
        <>
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
          <BudgetVsActualChart rows={payload.lines} metric={metric} />
          <BudgetTable rows={payload.lines} />
        </>
      ) : null}
    </div>
  )
}
