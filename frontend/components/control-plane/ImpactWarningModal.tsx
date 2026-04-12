"use client"

import { useMemo } from "react"
import { useQuery } from "@tanstack/react-query"
import { getImpact } from "@/lib/api/control-plane"
import { controlPlaneQueryKeys } from "@/lib/query/controlPlane"
import { GuardFailureCard } from "@/components/ui/GuardFailureCard"
import { StateBadge } from "@/components/ui/StateBadge"
import { summarizeLineageNode } from "@/components/control-plane/LineageGraph"
import { Dialog } from "@/components/ui/Dialog"

interface ImpactWarningModalProps {
  open: boolean
  onClose: () => void
  subjectType: string | null
  subjectId: string | null
}

export function ImpactWarningModal({
  open,
  onClose,
  subjectType,
  subjectId,
}: ImpactWarningModalProps) {
  const impactQuery = useQuery({
    queryKey: controlPlaneQueryKeys.impact(subjectType, subjectId),
    queryFn: async () => {
      if (!subjectType || !subjectId) {
        return null
      }
      return getImpact(subjectType, subjectId)
    },
    enabled: open && Boolean(subjectType && subjectId),
  })

  const impactedNodes = useMemo(
    () => (impactQuery.data?.impacted_nodes ?? []).map((node, index) => summarizeLineageNode(node, index)),
    [impactQuery.data?.impacted_nodes],
  )
  const hasReports = Boolean(impactQuery.data && impactQuery.data.impacted_reports_count > 0)

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Impact Preview"
      description="Backend-derived downstream effects for the selected subject."
      size="md"
    >
      {!subjectType || !subjectId ? (
        <p className="text-sm text-muted-foreground">
          Select a subject to review backend-derived impact.
        </p>
      ) : impactQuery.isLoading ? (
        <p className="text-sm text-muted-foreground">Loading impact analysis...</p>
      ) : impactQuery.error ? (
        <GuardFailureCard
          title="Impact failed to load"
          message={
            impactQuery.error instanceof Error
              ? impactQuery.error.message
              : "The backend did not return impact data."
          }
          tone="danger"
          recommendation="Retry after checking the selected subject scope or backend availability."
        />
      ) : !impactQuery.data ? (
        <GuardFailureCard
          title="No impact returned"
          message="The backend responded without downstream impact data for the selected subject."
          tone="warning"
          recommendation="Select a subject with known downstream references or create the relevant control-plane snapshots."
        />
      ) : (
        <div className="space-y-4">
          <GuardFailureCard
            title={hasReports ? "Downstream reports impacted" : "Downstream dependency preview"}
            message={impactQuery.data.warning}
            tone={hasReports ? "danger" : "warning"}
            violations={[
              { label: "Impacted nodes", detail: String(impactQuery.data.impacted_count) },
              { label: "Impacted reports", detail: String(impactQuery.data.impacted_reports_count) },
            ]}
            recommendation={
              hasReports
                ? "Review the impacted reports before approving any change to this subject."
                : "No downstream reports are currently referenced, but the dependency graph still deserves review."
            }
          />

          <div className="flex flex-wrap gap-2">
            <StateBadge label="Backend sourced" tone="info" />
            <StateBadge
              label={
                impactQuery.data.semantics?.authoritative
                  ? "Authoritative backend impact"
                  : "Limited backend impact"
              }
              tone={impactQuery.data.semantics?.authoritative ? "success" : "warning"}
            />
            <StateBadge
              label={impactQuery.data.semantics?.authoritative ? "Authoritative" : "Limited"}
              tone={impactQuery.data.semantics?.authoritative ? "success" : "warning"}
            />
            <StateBadge label={`${impactQuery.data.impacted_count} nodes`} tone="neutral" />
            <StateBadge label={`${impactQuery.data.impacted_reports_count} reports`} tone="neutral" />
          </div>

          <div className="space-y-2">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Impacted nodes</p>
            {impactedNodes.length ? (
              <div className="grid gap-3">
                {impactedNodes.map((node) => (
                  <article key={node.id} className="rounded-xl border border-border bg-background p-4 text-sm">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="space-y-1">
                        <p className="font-semibold text-foreground">{node.title}</p>
                        {node.subtitle ? <p className="text-muted-foreground">{node.subtitle}</p> : null}
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {node.badges.map((badge) => (
                          <StateBadge key={`${node.id}-${badge.label}`} label={badge.label} tone={badge.tone} />
                        ))}
                      </div>
                    </div>
                    {node.details.length ? (
                      <div className="mt-3 grid gap-2 sm:grid-cols-2">
                        {node.details.map((detail) => (
                          <div key={`${node.id}-${detail.label}`} className="rounded-lg border border-border/70 bg-card px-3 py-2">
                            <p className="text-[11px] uppercase tracking-wide text-muted-foreground">
                              {detail.label}
                            </p>
                            <p className="mt-1 break-all text-foreground">{detail.value}</p>
                          </div>
                        ))}
                      </div>
                    ) : null}
                  </article>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                The backend returned impact counts without node-level details.
              </p>
            )}
          </div>
        </div>
      )}
    </Dialog>
  )
}
