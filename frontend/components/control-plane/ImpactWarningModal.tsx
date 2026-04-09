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
  const query = useQuery({
    queryKey: ["control-plane-impact", subjectType, subjectId],
    queryFn: async () => getImpact(subjectType ?? "", subjectId ?? ""),
    enabled: open && Boolean(subjectType && subjectId),
  })

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Impact Warning"
      description="Backend-calculated downstream report impact for the selected subject."
      size="md"
    >
      {!subjectType || !subjectId ? (
        <p className="text-sm text-muted-foreground">Select a subject to inspect impact.</p>
      ) : query.isLoading ? (
        <p className="text-sm text-muted-foreground">Loading impact analysis...</p>
      ) : query.error || !query.data ? (
        <p className="text-sm text-[hsl(var(--brand-danger))]">Failed to load impact analysis.</p>
      ) : (
        <div className="space-y-4 text-sm">
          <div className="rounded-xl border border-border bg-background p-4">
            <p className="font-medium text-foreground">{query.data.warning}</p>
            <p className="mt-2 text-muted-foreground">
              {query.data.impacted_count} downstream objects, {query.data.impacted_reports_count} report-like outputs.
            </p>
          </div>
          <pre className="overflow-x-auto rounded-md bg-muted/40 p-3 text-xs text-foreground">
            {JSON.stringify(query.data.impacted_nodes, null, 2)}
          </pre>
        </div>
      )}
    </Dialog>
  )
}
