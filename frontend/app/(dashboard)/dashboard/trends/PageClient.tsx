"use client"

import dynamic from "next/dynamic"
import { useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import type { TrendsChartDatum } from "@/components/charts"
import { getTrends } from "@/lib/api/analytics"
import { useWorkspaceStore } from "@/lib/store/workspace"
import { queryKeys } from "@/lib/query/keys"

const TrendsChart = dynamic(
  () =>
    import("@/components/charts/TrendsChart").then(
      (module) => module.TrendsChart,
    ),
  {
    ssr: false,
    loading: () => <div className="h-64 w-full animate-pulse rounded-lg bg-muted" />,
  },
)

const toAmount = (value: string | number | null | undefined) => Number(value ?? 0)

export default function TrendsPage() {
  const entityId = useWorkspaceStore((s) => s.entityId)
  const today = new Date().toISOString().slice(0, 10)
  const defaultFrom = `${today.slice(0, 4)}-01-01`
  const [frequency, setFrequency] = useState("monthly")

  const trendsQuery = useQuery({
    queryKey: queryKeys.analytics.trends(entityId, defaultFrom, today, frequency),
    queryFn: () =>
      getTrends({
        org_entity_id: entityId ?? undefined,
        from_date: defaultFrom,
        to_date: today,
        frequency,
      }),
    enabled: Boolean(entityId),
  })

  const chartData = useMemo<TrendsChartDatum[]>(() => {
    const series = trendsQuery.data?.series ?? []
    const periods = Array.from(
      new Set(series.flatMap((item) => item.points.map((point) => point.period))),
    ).sort()
    return periods.map((period) => {
      const row: Record<string, number | string> = { period }
      for (const item of series) {
        const point = item.points.find((p) => p.period === period)
        row[item.metric_name] = toAmount(point?.value)
      }
      return row as TrendsChartDatum
    })
  }, [trendsQuery.data])

  return (
    <div className="space-y-6 p-6">
      <section className="rounded-xl border border-border bg-card p-4">
        <h1 className="text-xl font-semibold text-foreground">Trends</h1>
        <p className="text-sm text-muted-foreground">
          Revenue, expense, profit, and cash trajectory over time.
        </p>
      </section>

      <section className="rounded-xl border border-border bg-card p-4">
        <label
          htmlFor="frequency"
          className="text-xs uppercase tracking-wide text-muted-foreground"
        >
          Frequency
        </label>
        <select
          id="frequency"
          value={frequency}
          onChange={(event) => setFrequency(event.target.value)}
          className="ml-3 rounded-md border border-border bg-background px-3 py-2 text-sm"
        >
          <option value="monthly">Monthly</option>
          <option value="quarterly">Quarterly</option>
        </select>
      </section>

      <section className="rounded-xl border border-border bg-card p-4">
        <TrendsChart data={chartData} />
      </section>
    </div>
  )
}
