"use client"

import { useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { getVariance } from "@/lib/api/analytics"
import { useTenantStore } from "@/lib/store/tenant"
import { queryKeys } from "@/lib/query/keys"

const abs = (value: string | number | null | undefined) => Math.abs(Number(value ?? 0))

export default function VariancePage() {
  const entityId = useTenantStore((state) => state.active_entity_id)
  const [comparison, setComparison] = useState("prev_month")
  const today = new Date().toISOString().slice(0, 10)
  const fromDate = `${today.slice(0, 8)}01`

  const varianceQuery = useQuery({
    queryKey: queryKeys.analytics.variance(entityId, fromDate, today, comparison),
    queryFn: () =>
      getVariance({
        org_entity_id: entityId ?? undefined,
        from_date: fromDate,
        to_date: today,
        comparison,
      }),
    enabled: Boolean(entityId),
  })

  const highVariance = useMemo(
    () =>
      (varianceQuery.data?.account_variances ?? []).filter((item) => abs(item.variance_percent) >= 20),
    [varianceQuery.data],
  )

  return (
    <div className="space-y-6 p-6">
      <section className="rounded-xl border border-border bg-card p-4">
        <h1 className="text-xl font-semibold text-foreground">Variance Analysis</h1>
        <p className="text-sm text-muted-foreground">Period-over-period and prior-year comparison with outlier highlighting.</p>
      </section>

      <section className="rounded-xl border border-border bg-card p-4">
        <label className="text-xs uppercase tracking-wide text-muted-foreground" htmlFor="comparison">
          Comparison
        </label>
        <select
          id="comparison"
          value={comparison}
          onChange={(event) => setComparison(event.target.value)}
          className="ml-3 rounded-md border border-border bg-background px-3 py-2 text-sm"
        >
          <option value="prev_month">Previous Month</option>
          <option value="prior_year">Prior Year</option>
        </select>
      </section>

      <section className="overflow-hidden rounded-xl border border-border bg-card">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-border text-sm">
            <thead className="bg-muted/30">
              <tr className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                <th className="px-4 py-2">Metric</th>
                <th className="px-4 py-2">Current</th>
                <th className="px-4 py-2">Previous</th>
                <th className="px-4 py-2">Variance</th>
                <th className="px-4 py-2">Variance %</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {(varianceQuery.data?.metric_variances ?? []).map((row) => (
                <tr key={row.metric_name}>
                  <td className="px-4 py-2">{row.metric_name}</td>
                  <td className="px-4 py-2">{Number(row.current_value).toLocaleString()}</td>
                  <td className="px-4 py-2">{Number(row.previous_value).toLocaleString()}</td>
                  <td className="px-4 py-2">{Number(row.variance_value).toLocaleString()}</td>
                  <td className="px-4 py-2">{row.variance_percent ? `${Number(row.variance_percent).toFixed(2)}%` : "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="rounded-xl border border-border bg-card p-4">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">High Account Variances (&gt;=20%)</h2>
        <div className="space-y-2">
          {highVariance.slice(0, 50).map((row) => (
            <div key={row.account_code} className="rounded-md border border-[hsl(var(--brand-danger))] p-3 text-sm">
              {row.account_code} - {row.account_name}: {Number(row.variance_value).toLocaleString()} ({Number(row.variance_percent ?? 0).toFixed(2)}%)
            </div>
          ))}
          {highVariance.length === 0 ? (
            <p className="text-sm text-muted-foreground">No high-variance accounts for selected comparison.</p>
          ) : null}
        </div>
      </section>
    </div>
  )
}

