"use client"

import { useMemo, useState } from "react"
import Link from "next/link"
import { useCurrentEntitlements, useUsageAggregates } from "@/hooks/useBilling"

export default function BillingUsagePage() {
  const today = new Date()
  const monthStart = new Date(today.getFullYear(), today.getMonth(), 1)
  const nextMonthStart = new Date(today.getFullYear(), today.getMonth() + 1, 1)
  const [periodStart, setPeriodStart] = useState(monthStart.toISOString().slice(0, 10))
  const [periodEnd, setPeriodEnd] = useState(nextMonthStart.toISOString().slice(0, 10))

  const usageQuery = useUsageAggregates({
    period_start: periodStart || undefined,
    period_end: periodEnd || undefined,
  })
  const entitlementsQuery = useCurrentEntitlements()

  const usageByFeature = useMemo(() => {
    const map = new Map<string, number>()
    for (const row of usageQuery.data ?? []) {
      map.set(row.feature_name, (map.get(row.feature_name) ?? 0) + row.total_usage)
    }
    return map
  }, [usageQuery.data])

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-foreground">Usage & Entitlements</h1>
        <Link
          href="/settings/billing"
          className="rounded-md border border-border px-3 py-2 text-sm hover:bg-accent"
        >
          Back to Billing
        </Link>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <label className="space-y-1 text-sm">
          <span className="text-muted-foreground">Period start</span>
          <input
            type="date"
            className="w-full rounded border border-border bg-background px-3 py-2"
            value={periodStart}
            onChange={(event) => setPeriodStart(event.target.value)}
          />
        </label>
        <label className="space-y-1 text-sm">
          <span className="text-muted-foreground">Period end</span>
          <input
            type="date"
            className="w-full rounded border border-border bg-background px-3 py-2"
            value={periodEnd}
            onChange={(event) => setPeriodEnd(event.target.value)}
          />
        </label>
      </div>

      {entitlementsQuery.isLoading || usageQuery.isLoading ? (
        <p className="text-sm text-muted-foreground">Loading usage...</p>
      ) : null}
      {entitlementsQuery.isError || usageQuery.isError ? (
        <p className="text-sm text-destructive">Failed to load usage data.</p>
      ) : null}

      <div className="overflow-x-auto rounded-md border border-border">
        <table className="w-full min-w-[820px] text-sm">
          <thead>
            <tr className="bg-muted/30">
              <th className="px-3 py-2 text-left font-medium text-foreground">Feature</th>
              <th className="px-3 py-2 text-left font-medium text-foreground">Access Type</th>
              <th className="px-3 py-2 text-right font-medium text-foreground">Limit</th>
              <th className="px-3 py-2 text-right font-medium text-foreground">Used</th>
              <th className="px-3 py-2 text-right font-medium text-foreground">Remaining</th>
              <th className="px-3 py-2 text-left font-medium text-foreground">Source</th>
            </tr>
          </thead>
          <tbody>
            {(entitlementsQuery.data ?? []).map((row) => {
              const used = usageByFeature.get(row.feature_name) ?? 0
              const remaining =
                row.effective_limit === null ? null : Math.max(row.effective_limit - used, 0)
              return (
                <tr key={row.id} className="border-t border-border">
                  <td className="px-3 py-2 text-muted-foreground">{row.feature_name}</td>
                  <td className="px-3 py-2 text-muted-foreground">{row.access_type}</td>
                  <td className="px-3 py-2 text-right text-muted-foreground">
                    {row.effective_limit === null ? "Unlimited" : row.effective_limit}
                  </td>
                  <td className="px-3 py-2 text-right text-muted-foreground">{used}</td>
                  <td className="px-3 py-2 text-right text-muted-foreground">
                    {remaining === null ? "Unlimited" : remaining}
                  </td>
                  <td className="px-3 py-2 text-muted-foreground">{row.source}</td>
                </tr>
              )
            })}
            {!(entitlementsQuery.data ?? []).length ? (
              <tr>
                <td colSpan={6} className="px-3 py-4 text-center text-muted-foreground">
                  No entitlements configured.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  )
}

