"use client"

import Link from "next/link"
import dynamic from "next/dynamic"
import { useMemo } from "react"
import { useQuery } from "@tanstack/react-query"
import type { CfoChartDatum } from "@/components/charts"
import { DataActivationSection } from "@/components/dashboard/DataActivationSection"
import { getKpis, getTrends } from "@/lib/api/analytics"
import { useWorkspaceStore } from "@/lib/store/workspace"
import { queryKeys } from "@/lib/query/keys"

const CfoChart = dynamic(
  () => import("@/components/charts/CfoChart").then((module) => module.CfoChart),
  {
    ssr: false,
    loading: () => <div className="h-64 w-full animate-pulse rounded-lg bg-muted" />,
  },
)

const toAmount = (value: string | number | null | undefined) => Number(value ?? 0)

export default function CfoDashboardPage() {
  const entityId = useWorkspaceStore((s) => s.entityId)
  const today = new Date().toISOString().slice(0, 10)
  const fromDate = `${today.slice(0, 8)}01`

  const kpisQuery = useQuery({
    queryKey: queryKeys.analytics.kpisCfo(entityId, fromDate, today),
    queryFn: () =>
      getKpis({
        org_entity_id: entityId ?? undefined,
        from_date: fromDate,
        to_date: today,
        as_of_date: today,
      }),
    enabled: Boolean(entityId),
  })

  const trendsQuery = useQuery({
    queryKey: queryKeys.analytics.trendsCfo(entityId, fromDate, today),
    queryFn: () =>
      getTrends({
        org_entity_id: entityId ?? undefined,
        from_date: fromDate,
        to_date: today,
        frequency: "monthly",
      }),
    enabled: Boolean(entityId),
  })

  const metrics = useMemo(() => {
    const rows = kpisQuery.data?.rows ?? []
    return Object.fromEntries(
      rows.map((row) => [row.metric_name, row.metric_value]),
    )
  }, [kpisQuery.data])

  const trendData = useMemo<CfoChartDatum[]>(() => {
    const revenue =
      trendsQuery.data?.series.find((item) => item.metric_name === "revenue")
        ?.points ?? []
    const profit =
      trendsQuery.data?.series.find((item) => item.metric_name === "profit")
        ?.points ?? []
    const keys = Array.from(
      new Set([...revenue.map((p) => p.period), ...profit.map((p) => p.period)]),
    )
    return keys.map((period) => ({
      period,
      revenue: toAmount(revenue.find((p) => p.period === period)?.value),
      profit: toAmount(profit.find((p) => p.period === period)?.value),
    }))
  }, [trendsQuery.data])

  return (
    <div className="space-y-6 p-6">
      <section className="rounded-xl border border-border bg-card p-4">
        <h1 className="text-xl font-semibold text-foreground">CFO Dashboard</h1>
        <p className="text-sm text-muted-foreground">
          Executive KPI summary with trend visibility and variance alerts.
        </p>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {[
          ["Revenue", metrics.revenue],
          ["Gross Profit", metrics.gross_profit],
          ["EBITDA", metrics.ebitda],
          ["Net Profit", metrics.net_profit],
        ].map(([label, value]) => (
          <Link
            key={label}
            href="/dashboard/kpis"
            className="rounded-xl border border-border bg-card p-4 transition hover:border-[hsl(var(--brand-primary))]"
          >
            <p className="text-xs uppercase tracking-wide text-muted-foreground">
              {label}
            </p>
            <p className="mt-1 text-2xl font-semibold text-foreground">
              {toAmount(value as string).toLocaleString()}
            </p>
          </Link>
        ))}
      </section>

      <section className="rounded-xl border border-border bg-card p-4">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Revenue vs Profit Trend
        </h2>
        <CfoChart data={trendData} />
      </section>

      <DataActivationSection />

      <section className="rounded-xl border border-border bg-card p-4">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Alert Watch
        </h2>
        <div className="space-y-2">
          {(kpisQuery.data?.alerts ?? []).map((alert) => (
            <div
              key={`${alert.metric_name}-${alert.condition}-${alert.threshold}`}
              className={`rounded-md border p-3 text-sm ${alert.triggered ? "border-[hsl(var(--brand-danger))]" : "border-border"}`}
            >
              <span className="font-medium">{alert.metric_name}</span>{" "}
              {alert.condition} {alert.threshold}
              {" - "}
              current: {alert.metric_value}
              {alert.triggered ? " - Triggered" : " - Normal"}
            </div>
          ))}
          {kpisQuery.data?.alerts?.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No active alert rules configured.
            </p>
          ) : null}
        </div>
      </section>
    </div>
  )
}
