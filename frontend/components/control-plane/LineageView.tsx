"use client"

import { useQuery } from "@tanstack/react-query"
import { getLineage } from "@/lib/api/control-plane"

interface LineageViewProps {
  subjectType: string | null
  subjectId: string | null
}

export function LineageView({ subjectType, subjectId }: LineageViewProps) {
  const query = useQuery({
    queryKey: ["control-plane-lineage", subjectType, subjectId],
    queryFn: async () => getLineage(subjectType ?? "", subjectId ?? ""),
    enabled: Boolean(subjectType && subjectId),
  })

  return (
    <section className="space-y-3 rounded-xl border border-border bg-card p-4">
      <div>
        <h2 className="text-lg font-semibold text-foreground">Lineage</h2>
        <p className="text-sm text-muted-foreground">Forward and reverse references for the selected subject.</p>
      </div>
      {!subjectType || !subjectId ? (
        <p className="text-sm text-muted-foreground">Select a snapshot-backed subject to inspect lineage.</p>
      ) : query.isLoading ? (
        <p className="text-sm text-muted-foreground">Loading lineage...</p>
      ) : query.error || !query.data ? (
        <p className="text-sm text-[hsl(var(--brand-danger))]">Failed to load lineage.</p>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          <div className="rounded-xl border border-border bg-background p-3">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Forward</p>
            <p className="mt-2 text-sm text-foreground">
              {query.data.forward.nodes.length} nodes / {query.data.forward.edges.length} edges
            </p>
            <pre className="mt-2 overflow-x-auto rounded-md bg-muted/40 p-3 text-xs text-foreground">
              {JSON.stringify(query.data.forward, null, 2)}
            </pre>
          </div>
          <div className="rounded-xl border border-border bg-background p-3">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Reverse</p>
            <p className="mt-2 text-sm text-foreground">
              {query.data.reverse.nodes.length} nodes / {query.data.reverse.edges.length} edges
            </p>
            <pre className="mt-2 overflow-x-auto rounded-md bg-muted/40 p-3 text-xs text-foreground">
              {JSON.stringify(query.data.reverse, null, 2)}
            </pre>
          </div>
        </div>
      )}
    </section>
  )
}
