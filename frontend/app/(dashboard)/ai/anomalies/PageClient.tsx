"use client"

import { useQuery } from "@tanstack/react-query"
import { getAiAnomalies } from "@/lib/api/ai-cfo"
import { useTenantStore } from "@/lib/store/tenant"
import { queryKeys } from "@/lib/query/keys"

export default function AiAnomaliesPage() {
  const entityId = useTenantStore((state) => state.active_entity_id)
  const today = new Date().toISOString().slice(0, 10)
  const fromDate = `${today.slice(0, 8)}01`

  const query = useQuery({
    queryKey: queryKeys.ai.anomalies(entityId, fromDate, today),
    queryFn: () =>
      getAiAnomalies({
        org_entity_id: entityId ?? undefined,
        from_date: fromDate,
        to_date: today,
      }),
    enabled: Boolean(entityId),
  })

  const rows = query.data?.rows ?? []
  return (
    <div className="space-y-6 p-6">
      <section className="rounded-xl border border-border bg-card p-4">
        <h1 className="text-xl font-semibold text-foreground">AI Anomalies</h1>
        <p className="text-sm text-muted-foreground">
          Statistical + rule-based anomaly signals with deterministic fact references.
        </p>
      </section>

      <section className="overflow-hidden rounded-xl border border-border bg-card">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-border text-sm">
            <thead className="bg-muted/30">
              <tr className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                <th className="px-4 py-2">Metric</th>
                <th className="px-4 py-2">Type</th>
                <th className="px-4 py-2">Deviation</th>
                <th className="px-4 py-2">Severity</th>
                <th className="px-4 py-2">Explanation</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {rows.map((row) => (
                <tr key={`${row.metric_name}-${row.anomaly_type}-${row.deviation_value}`}>
                  <td className="px-4 py-2">{row.metric_name}</td>
                  <td className="px-4 py-2">{row.anomaly_type}</td>
                  <td className="px-4 py-2">{Number(row.deviation_value).toLocaleString()}</td>
                  <td className="px-4 py-2">{row.severity}</td>
                  <td className="px-4 py-2">{row.explanation}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}

