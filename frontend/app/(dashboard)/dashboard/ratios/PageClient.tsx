"use client"

import { useQuery } from "@tanstack/react-query"
import { getRatios } from "@/lib/api/analytics"
import { useWorkspaceStore } from "@/lib/store/workspace"
import { queryKeys } from "@/lib/query/keys"

export default function RatiosPage() {
  const entityId = useWorkspaceStore((s) => s.entityId)
  const today = new Date().toISOString().slice(0, 10)
  const fromDate = `${today.slice(0, 4)}-01-01`

  const ratiosQuery = useQuery({
    queryKey: queryKeys.analytics.ratios(entityId, fromDate, today),
    queryFn: () =>
      getRatios({
        org_entity_id: entityId ?? undefined,
        from_date: fromDate,
        to_date: today,
        as_of_date: today,
      }),
    enabled: Boolean(entityId),
  })

  return (
    <div className="space-y-6 p-6">
      <section className="rounded-xl border border-border bg-card p-4">
        <h1 className="text-xl font-semibold text-foreground">Ratios</h1>
        <p className="text-sm text-muted-foreground">Return, turnover, and working-cycle ratios derived from GL-backed statements.</p>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {(ratiosQuery.data?.rows ?? []).map((row) => (
          <div key={row.metric_name} className="rounded-xl border border-border bg-card p-4">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">{row.metric_name}</p>
            <p className="mt-1 text-2xl font-semibold text-foreground">{Number(row.metric_value).toLocaleString()}</p>
          </div>
        ))}
      </section>
    </div>
  )
}

