"use client"

import { useEffect, useMemo, useState } from "react"
import { useParams } from "next/navigation"
import { ScaleSelector } from "@/components/ui/ScaleSelector"
import { CashFlowGrid, type EditableField } from "@/components/treasury/CashFlowGrid"
import { WeeklyBridgeChart } from "@/components/treasury/WeeklyBridgeChart"
import { getTreasuryForecast, updateTreasuryWeek } from "@/lib/api/sprint11"
import { useDisplayScale } from "@/lib/store/displayScale"
import { type ForecastSummary } from "@/lib/types/sprint11"

export default function TreasuryDetailPage() {
  const params = useParams<{ id: string }>()
  const forecastId = params?.id ?? ""

  const [summary, setSummary] = useState<ForecastSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const scale = useDisplayScale((state) => state.scale)
  const setScale = useDisplayScale((state) => state.setScale)

  const load = async (): Promise<void> => {
    setLoading(true)
    setError(null)
    try {
      const payload = await getTreasuryForecast(forecastId)
      setSummary(payload)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Failed to load forecast")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (!forecastId) {
      return
    }
    void load()
  }, [forecastId])

  const handleCellEdit = async (
    weekNumber: number,
    field: EditableField,
    value: string,
  ): Promise<void> => {
    if (!summary) {
      return
    }
    const previous = summary
    const nextWeeks = summary.weeks.map((week) =>
      week.week_number === weekNumber ? { ...week, [field]: value } : week,
    )
    setSummary({ ...summary, weeks: nextWeeks })
    try {
      await updateTreasuryWeek(forecastId, weekNumber, { [field]: value })
      await load()
    } catch {
      setSummary(previous)
      setError("Failed to save week assumptions. Changes reverted.")
    }
  }

  const bridgePoints = useMemo(() => {
    if (!summary) {
      return []
    }
    return summary.weeks.map((week) => ({
      week: `W${week.week_number}`,
      opening: week.week_number === 1
        ? Number.parseFloat(summary.opening_balance)
        : Number.parseFloat(summary.weeks[week.week_number - 2].closing_balance),
      inflows: Number.parseFloat(week.total_inflows),
      outflows: Number.parseFloat(week.total_outflows),
      closing: Number.parseFloat(week.closing_balance),
    }))
  }, [summary])

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-2">
        <h1 className="text-2xl font-semibold text-foreground">Forecast Detail</h1>
        <ScaleSelector value={scale} onChange={setScale} />
      </div>
      {!forecastId ? <p className="text-sm text-red-400">Missing forecast ID.</p> : null}
      {loading ? <p className="text-sm text-muted-foreground">Loading forecast...</p> : null}
      {error ? <p className="text-sm text-red-400">{error}</p> : null}
      {summary ? (
        <>
          <CashFlowGrid weeks={summary.weeks} onCellEdit={handleCellEdit} />
          <WeeklyBridgeChart points={bridgePoints} />
        </>
      ) : null}
    </div>
  )
}
