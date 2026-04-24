"use client"

import { useQuery } from "@tanstack/react-query"
import { getAiRecommendations } from "@/lib/api/ai-cfo"
import { useTenantStore } from "@/lib/store/tenant"
import { queryKeys } from "@/lib/query/keys"

export default function AiRecommendationsPage() {
  const entityId = useTenantStore((state) => state.active_entity_id)
  const today = new Date().toISOString().slice(0, 10)
  const fromDate = `${today.slice(0, 8)}01`

  const query = useQuery({
    queryKey: queryKeys.ai.recommendations(entityId, fromDate, today),
    queryFn: () =>
      getAiRecommendations({
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
        <h1 className="text-xl font-semibold text-foreground">AI Recommendations</h1>
        <p className="text-sm text-muted-foreground">
          Decision-ready actions generated from deterministic KPIs, ratios, and variance facts.
        </p>
      </section>

      <section className="space-y-3 rounded-xl border border-border bg-card p-4">
        {rows.map((row) => (
          <div key={`${row.recommendation_type}-${row.message}`} className="rounded-md border border-border p-3">
            <div className="flex items-center justify-between">
              <p className="text-sm font-semibold">{row.recommendation_type}</p>
              <span className="text-xs text-muted-foreground">{row.severity}</span>
            </div>
            <p className="mt-2 text-sm text-muted-foreground">{row.message}</p>
          </div>
        ))}
        {rows.length === 0 ? (
          <p className="text-sm text-muted-foreground">No recommendations generated for this period.</p>
        ) : null}
      </section>
    </div>
  )
}

