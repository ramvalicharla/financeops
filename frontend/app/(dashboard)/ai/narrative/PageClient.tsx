"use client"

import { useQuery } from "@tanstack/react-query"
import { getAiAuditSamples, getAiNarrative, getAiSuggestions, getAiVarianceExplanation } from "@/lib/api/ai-cfo"
import { useWorkspaceStore } from "@/lib/store/workspace"
import { queryKeys } from "@/lib/query/keys"

export default function AiNarrativePage() {
  const entityId = useWorkspaceStore((s) => s.entityId)
  const today = new Date().toISOString().slice(0, 10)
  const fromDate = `${today.slice(0, 8)}01`

  const narrativeQuery = useQuery({
    queryKey: queryKeys.ai.narrative(entityId, fromDate, today),
    queryFn: () =>
      getAiNarrative({
        org_entity_id: entityId ?? undefined,
        from_date: fromDate,
        to_date: today,
      }),
    enabled: Boolean(entityId),
  })

  const explanationQuery = useQuery({
    queryKey: queryKeys.ai.varianceExplanation(entityId, fromDate, today),
    queryFn: () =>
      getAiVarianceExplanation({
        metric_name: "revenue",
        org_entity_id: entityId ?? undefined,
        from_date: fromDate,
        to_date: today,
      }),
    enabled: Boolean(entityId),
  })

  const suggestionsQuery = useQuery({
    queryKey: queryKeys.ai.suggestions(entityId, fromDate, today),
    queryFn: () =>
      getAiSuggestions({
        org_entity_id: entityId ?? undefined,
        from_date: fromDate,
        to_date: today,
      }),
    enabled: Boolean(entityId),
  })

  const sampleQuery = useQuery({
    queryKey: queryKeys.ai.auditSamples(entityId, fromDate, today),
    queryFn: () =>
      getAiAuditSamples({
        org_entity_id: entityId ?? undefined,
        from_date: fromDate,
        to_date: today,
        mode: "risk_based",
        sample_size: 10,
      }),
    enabled: Boolean(entityId),
  })

  const narrative = narrativeQuery.data

  return (
    <div className="space-y-6 p-6">
      <section className="rounded-xl border border-border bg-card p-4">
        <h1 className="text-xl font-semibold text-foreground">AI Financial Narrative</h1>
        <p className="text-sm text-muted-foreground">
          Board-ready narrative grounded in deterministic data and validated for numeric consistency.
        </p>
      </section>

      <section className="rounded-xl border border-border bg-card p-4">
        <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-muted-foreground">Summary</h2>
        <p className="text-sm text-foreground">{narrative?.summary ?? "No narrative available."}</p>
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-xl border border-border bg-card p-4">
          <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-muted-foreground">Highlights</h3>
          <ul className="space-y-2 text-sm text-foreground">
            {(narrative?.highlights ?? []).map((item) => (
              <li key={item}>- {item}</li>
            ))}
          </ul>
        </div>
        <div className="rounded-xl border border-border bg-card p-4">
          <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-muted-foreground">Drivers</h3>
          <ul className="space-y-2 text-sm text-foreground">
            {(narrative?.drivers ?? []).map((item) => (
              <li key={item}>- {item}</li>
            ))}
          </ul>
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-xl border border-border bg-card p-4">
          <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-muted-foreground">Risks</h3>
          <ul className="space-y-2 text-sm text-foreground">
            {(narrative?.risks ?? []).map((item) => (
              <li key={item}>- {item}</li>
            ))}
          </ul>
        </div>
        <div className="rounded-xl border border-border bg-card p-4">
          <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-muted-foreground">Actions</h3>
          <ul className="space-y-2 text-sm text-foreground">
            {(narrative?.actions ?? []).map((item) => (
              <li key={item}>- {item}</li>
            ))}
          </ul>
        </div>
      </section>

      <section className="rounded-xl border border-border bg-card p-4">
        <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-muted-foreground">Revenue Variance Explanation</h3>
        <p className="text-sm text-foreground">{String(explanationQuery.data?.explanation ?? "No explanation generated.")}</p>
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-xl border border-border bg-card p-4">
          <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-muted-foreground">Suggested Journals</h3>
          <ul className="space-y-2 text-sm text-foreground">
            {(suggestionsQuery.data?.rows ?? []).slice(0, 5).map((item) => (
              <li key={`${item.title}-${item.reason}`}>- {item.title}</li>
            ))}
          </ul>
        </div>
        <div className="rounded-xl border border-border bg-card p-4">
          <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-muted-foreground">Audit Samples</h3>
          <ul className="space-y-2 text-sm text-foreground">
            {(sampleQuery.data?.rows ?? []).slice(0, 5).map((item) => (
              <li key={item.journal_id}>
                - {item.journal_number} ({Number(item.risk_score).toLocaleString()} risk)
              </li>
            ))}
          </ul>
        </div>
      </section>
    </div>
  )
}

