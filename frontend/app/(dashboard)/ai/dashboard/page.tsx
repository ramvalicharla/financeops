"use client"

import Link from "next/link"
import { useQuery } from "@tanstack/react-query"
import { getAiAnomalies, getAiRecommendations } from "@/lib/api/ai-cfo"
import { useTenantStore } from "@/lib/store/tenant"

export default function AiDashboardPage() {
  const entityId = useTenantStore((state) => state.active_entity_id)
  const today = new Date().toISOString().slice(0, 10)
  const fromDate = `${today.slice(0, 8)}01`

  const anomaliesQuery = useQuery({
    queryKey: ["ai-dashboard-anomalies", entityId, fromDate, today],
    queryFn: () =>
      getAiAnomalies({
        org_entity_id: entityId ?? undefined,
        from_date: fromDate,
        to_date: today,
      }),
    enabled: Boolean(entityId),
  })

  const recommendationsQuery = useQuery({
    queryKey: ["ai-dashboard-recommendations", entityId, fromDate, today],
    queryFn: () =>
      getAiRecommendations({
        org_entity_id: entityId ?? undefined,
        from_date: fromDate,
        to_date: today,
      }),
    enabled: Boolean(entityId),
  })

  const anomalies = anomaliesQuery.data?.rows ?? []
  const recommendations = recommendationsQuery.data?.rows ?? []

  return (
    <div className="space-y-6 p-6">
      <section className="rounded-xl border border-border bg-card p-4">
        <h1 className="text-xl font-semibold text-foreground">AI CFO Dashboard</h1>
        <p className="text-sm text-muted-foreground">
          Rule-validated anomaly signals, recommendations, and narratives grounded in deterministic analytics.
        </p>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-xl border border-border bg-card p-4">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Anomalies</p>
          <p className="mt-1 text-2xl font-semibold text-foreground">{anomalies.length}</p>
          <Link className="mt-2 inline-block text-xs text-[hsl(var(--brand-primary))]" href="/ai/anomalies">
            View anomalies
          </Link>
        </div>
        <div className="rounded-xl border border-border bg-card p-4">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Recommendations</p>
          <p className="mt-1 text-2xl font-semibold text-foreground">{recommendations.length}</p>
          <Link className="mt-2 inline-block text-xs text-[hsl(var(--brand-primary))]" href="/ai/recommendations">
            View recommendations
          </Link>
        </div>
        <div className="rounded-xl border border-border bg-card p-4">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Narrative</p>
          <p className="mt-1 text-2xl font-semibold text-foreground">Board-ready</p>
          <Link className="mt-2 inline-block text-xs text-[hsl(var(--brand-primary))]" href="/ai/narrative">
            Open narrative
          </Link>
        </div>
        <div className="rounded-xl border border-border bg-card p-4">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Deterministic Guard</p>
          <p className="mt-1 text-2xl font-semibold text-foreground">Active</p>
          <p className="mt-2 text-xs text-muted-foreground">AI outputs validated against source facts.</p>
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-xl border border-border bg-card p-4">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            Latest Anomaly Signals
          </h2>
          <div className="space-y-2">
            {anomalies.slice(0, 5).map((item) => (
              <div key={`${item.metric_name}-${item.anomaly_type}-${item.deviation_value}`} className="rounded-md border border-border p-3 text-sm">
                <div className="font-medium">{item.anomaly_type}</div>
                <div className="text-muted-foreground">{item.explanation}</div>
              </div>
            ))}
            {anomalies.length === 0 ? <p className="text-sm text-muted-foreground">No anomaly signals in this period.</p> : null}
          </div>
        </div>

        <div className="rounded-xl border border-border bg-card p-4">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            Priority Recommendations
          </h2>
          <div className="space-y-2">
            {recommendations.slice(0, 5).map((item) => (
              <div key={`${item.recommendation_type}-${item.message}`} className="rounded-md border border-border p-3 text-sm">
                <div className="font-medium">{item.recommendation_type}</div>
                <div className="text-muted-foreground">{item.message}</div>
              </div>
            ))}
            {recommendations.length === 0 ? (
              <p className="text-sm text-muted-foreground">No recommendations generated for this scope.</p>
            ) : null}
          </div>
        </div>
      </section>
    </div>
  )
}

