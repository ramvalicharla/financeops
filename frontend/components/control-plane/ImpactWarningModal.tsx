"use client"

import { useQuery } from "@tanstack/react-query"
import { getImpact } from "@/lib/api/control-plane"
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
    queryKey: ["control-plane-impact", subjectType, subjectId],
    queryFn: async () => {
      if (!subjectType || !subjectId) {
        return null
      }
      return getImpact(subjectType, subjectId)
    },
    enabled: open && Boolean(subjectType && subjectId),
  })

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Impact Preview"
      description="Backend-derived downstream effects for the selected subject."
      size="md"
    >
      {!subjectType || !subjectId ? (
        <p className="text-sm text-muted-foreground">Select a subject to review backend-derived impact.</p>
      ) : impactQuery.isLoading ? (
        <p className="text-sm text-muted-foreground">Loading impact analysis...</p>
      ) : impactQuery.error ? (
        <div className="rounded-xl border border-[hsl(var(--brand-danger)/0.35)] bg-[hsl(var(--brand-danger)/0.12)] p-4 text-sm">
          <p className="font-medium text-foreground">Impact failed to load</p>
          <p className="mt-1 text-muted-foreground">
            {impactQuery.error instanceof Error ? impactQuery.error.message : "The backend did not return impact data."}
          </p>
        </div>
      ) : !impactQuery.data ? (
        <p className="text-sm text-muted-foreground">No backend impact data was returned for this subject.</p>
      ) : (
        <div className="space-y-4 text-sm">
          <div className="rounded-xl border border-border bg-background p-4">
            <p className="font-medium text-foreground">{impactQuery.data.warning}</p>
            <p className="mt-2 text-muted-foreground">
              Downstream nodes: {impactQuery.data.impacted_count} · Reports: {impactQuery.data.impacted_reports_count}
            </p>
          </div>
          <div className="rounded-xl border border-border bg-background p-4">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Semantics</p>
            <p className="mt-2 text-sm text-foreground">
              {impactQuery.data.semantics?.authoritative
                ? "Authoritative backend impact"
                : "Limited by current backend contract"}
            </p>
          </div>
        </div>
      )}
    </Dialog>
  )
}
