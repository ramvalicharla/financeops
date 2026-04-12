"use client"

import { useMemo } from "react"
import { useQuery } from "@tanstack/react-query"
import { getLineage } from "@/lib/api/control-plane"
import { controlPlaneQueryKeys } from "@/lib/query/controlPlane"
import { GuardFailureCard } from "@/components/ui/GuardFailureCard"
import { StateBadge } from "@/components/ui/StateBadge"
import { LineageGraph } from "@/components/control-plane/LineageGraph"

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

  const rootLabel = useMemo(() => {
    if (!subjectType || !subjectId) {
      return "unselected"
    }
    return `${subjectType}:${subjectId}`
  }, [subjectId, subjectType])

  return (
    <section className="space-y-4 rounded-xl border border-border bg-card p-4">
      <div>
        <h2 className="text-lg font-semibold text-foreground">Lineage</h2>
        <p className="text-sm text-muted-foreground">
          Backend-derived upstream and downstream relationships for the selected control-plane subject.
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        <StateBadge label="Backend sourced" tone="info" />
        <StateBadge label="No raw JSON" tone="success" />
        <StateBadge
          label={lineageQuery.data?.semantics?.mode ?? "backend contract"}
          tone={lineageQuery.data?.semantics?.authoritative ? "success" : "warning"}
        />
      </div>

      {!subjectType || !subjectId ? (
        <p className="text-sm text-muted-foreground">
          Select a subject to review backend-derived lineage.
        </p>
      ) : lineageQuery.isLoading ? (
        <p className="text-sm text-muted-foreground">Loading lineage...</p>
      ) : lineageQuery.error ? (
        <GuardFailureCard
          title="Lineage failed to load"
          message={
            lineageQuery.error instanceof Error
              ? lineageQuery.error.message
              : "The backend did not return lineage data."
          }
          tone="danger"
          recommendation="Retry after checking the selected subject scope or backend availability."
        />
      ) : !lineageQuery.data ? (
        <GuardFailureCard
          title="No lineage returned"
          message="The backend responded without lineage data for the selected subject."
          tone="warning"
          recommendation="Select a subject that has backend-tracked relationships or create the relevant snapshots first."
        />
      ) : (
        <div className="space-y-4">
          <div className="grid gap-4 md:grid-cols-3">
            <article className="rounded-xl border border-border bg-background p-4">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">Forward lineage</p>
              <p className="mt-2 text-sm text-foreground">
                {lineageQuery.data.forward.nodes.length} nodes / {lineageQuery.data.forward.edges.length} edges
              </p>
            </article>
            <article className="rounded-xl border border-border bg-background p-4">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">Reverse lineage</p>
              <p className="mt-2 text-sm text-foreground">
                {lineageQuery.data.reverse.nodes.length} nodes / {lineageQuery.data.reverse.edges.length} edges
              </p>
            </article>
            <article className="rounded-xl border border-border bg-background p-4">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">Semantics</p>
              <p className="mt-2 text-sm text-foreground">
                {lineageQuery.data.semantics?.authoritative
                  ? "Authoritative backend lineage"
                  : "Limited by current backend contract"}
              </p>
            </article>
          </div>

          <div className="grid gap-4 xl:grid-cols-2">
            <LineageGraph
              direction="forward"
              title="Forward lineage"
              rootLabel={rootLabel}
              rootHint="Downstream dependencies returned by the backend."
              nodes={lineageQuery.data.forward.nodes}
              edges={lineageQuery.data.forward.edges}
              emptyMessage="The backend returned a shallow forward graph for this subject."
            />
            <LineageGraph
              direction="reverse"
              title="Reverse lineage"
              rootLabel={rootLabel}
              rootHint="Upstream references and downstream impact returned by the backend."
              nodes={lineageQuery.data.reverse.nodes}
              edges={lineageQuery.data.reverse.edges}
              emptyMessage="The backend returned a shallow reverse graph for this subject."
            />
          </div>
        </div>
      )}
    </section>
  )
}
