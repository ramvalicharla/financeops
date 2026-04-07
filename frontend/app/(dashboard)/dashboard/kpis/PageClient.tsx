"use client"

import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { getDrilldown, getKpis } from "@/lib/api/analytics"
import { useTenantStore } from "@/lib/store/tenant"
import { Button } from "@/components/ui/button"

export default function KpisPage() {
  const entityId = useTenantStore((state) => state.active_entity_id)
  const today = new Date().toISOString().slice(0, 10)
  const fromDate = `${today.slice(0, 8)}01`
  const [selectedMetric, setSelectedMetric] = useState<string | null>(null)

  const kpisQuery = useQuery({
    queryKey: ["analytics-kpis-page", entityId, fromDate, today],
    queryFn: () =>
      getKpis({
        org_entity_id: entityId ?? undefined,
        from_date: fromDate,
        to_date: today,
        as_of_date: today,
      }),
    enabled: Boolean(entityId),
  })

  const drilldownQuery = useQuery({
    queryKey: ["analytics-kpi-drilldown", entityId, selectedMetric, fromDate, today],
    queryFn: () =>
      getDrilldown({
        metric_name: selectedMetric ?? "",
        org_entity_id: entityId ?? undefined,
        from_date: fromDate,
        to_date: today,
        as_of_date: today,
      }),
    enabled: Boolean(entityId && selectedMetric),
  })

  return (
    <div className="space-y-6 p-6">
      <section className="rounded-xl border border-border bg-card p-4">
        <h1 className="text-xl font-semibold text-foreground">KPIs</h1>
        <p className="text-sm text-muted-foreground">
          Click any metric for account-to-journal-to-GL drilldown.
        </p>
      </section>

      <section className="overflow-hidden rounded-xl border border-border bg-card">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-border text-sm">
            <thead className="bg-muted/30">
              <tr className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                <th className="px-4 py-2">Metric</th>
                <th className="px-4 py-2">Value</th>
                <th className="px-4 py-2">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {(kpisQuery.data?.rows ?? []).map((row) => (
                <tr key={row.metric_name}>
                  <td className="px-4 py-2">{row.metric_name}</td>
                  <td className="px-4 py-2">{Number(row.metric_value).toLocaleString()}</td>
                  <td className="px-4 py-2">
                    <Button type="button" size="sm" variant="outline" onClick={() => setSelectedMetric(row.metric_name)}>
                      Drilldown
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {selectedMetric ? (
        <section className="rounded-xl border border-border bg-card p-4">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            Drilldown: {selectedMetric}
          </h2>
          <pre className="overflow-x-auto rounded-md bg-background p-3 text-xs">
            {JSON.stringify(drilldownQuery.data ?? {}, null, 2)}
          </pre>
        </section>
      ) : null}
    </div>
  )
}

