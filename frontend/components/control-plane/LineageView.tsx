"use client"

import { useQuery } from "@tanstack/react-query"
import { getLineage } from "@/lib/api/control-plane"
import { controlPlaneQueryKeys } from "@/lib/query/controlPlane"

interface LineageViewProps {
  subjectType: string | null
  subjectId: string | null
}

export function LineageView({ subjectType, subjectId }: LineageViewProps) {
  const lineageQuery = useQuery({
    queryKey: controlPlaneQueryKeys.lineage(subjectType, subjectId),
    queryFn: async () => {
      if (!subjectType || !subjectId) {
        return null
      }
      return getLineage(subjectType, subjectId)
    },
    enabled: Boolean(subjectType && subjectId),
  })

  return (
    <section className="space-y-3 rounded-xl border border-border bg-card p-4">
      <div>
        <h2 className="text-lg font-semibold text-foreground">Lineage</h2>
        <p className="text-sm text-muted-foreground">
          Backend-derived upstream and downstream relationships for the selected control-plane subject.
        </p>
      </div>
      {!subjectType || !subjectId ? (
        <p className="text-sm text-muted-foreground">
          Select a subject to review backend-derived lineage.
        </p>
      ) : lineageQuery.isLoading ? (
        <p className="text-sm text-muted-foreground">Loading lineage...</p>
      ) : lineageQuery.error ? (
        <div className="rounded-xl border border-[hsl(var(--brand-danger)/0.35)] bg-[hsl(var(--brand-danger)/0.12)] p-4 text-sm">
          <p className="font-medium text-foreground">Lineage failed to load</p>
          <p className="mt-1 text-muted-foreground">
            {lineageQuery.error instanceof Error
              ? lineageQuery.error.message
              : "The backend did not return lineage data."}
          </p>
        </div>
      ) : !lineageQuery.data ? (
        <p className="text-sm text-muted-foreground">No lineage data was returned for this subject.</p>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          <article className="rounded-xl border border-border bg-background p-4">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Forward lineage</p>
            <p className="mt-2 text-sm text-foreground">
              Nodes: {lineageQuery.data.forward.nodes.length} / Edges: {lineageQuery.data.forward.edges.length}
            </p>
          </article>
          <article className="rounded-xl border border-border bg-background p-4">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Reverse lineage</p>
            <p className="mt-2 text-sm text-foreground">
              Nodes: {lineageQuery.data.reverse.nodes.length} / Edges: {lineageQuery.data.reverse.edges.length}
            </p>
          </article>
          <div className="rounded-xl border border-border bg-background p-4 md:col-span-2">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Semantics</p>
            <p className="mt-2 text-sm text-foreground">
              {lineageQuery.data.semantics?.authoritative
                ? "Authoritative backend lineage"
                : "Limited by current backend contract"}
            </p>
          </div>
        </div>
      )}
    </section>
  )
}
