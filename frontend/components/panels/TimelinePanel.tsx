"use client"

import { useQuery } from "@tanstack/react-query"
import { exportTimeline, listTimeline } from "@/lib/api/control-plane"
import { useControlPlaneStore } from "@/lib/store/controlPlane"
import { useTenantStore } from "@/lib/store/tenant"
import { Button } from "@/components/ui/button"
import { Sheet } from "@/components/ui/Sheet"

const downloadBlob = (blob: Blob, filename: string) => {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement("a")
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}

export function TimelinePanel() {
  const activePanel = useControlPlaneStore((state) => state.active_panel)
  const closePanel = useControlPlaneStore((state) => state.closePanel)
  const selectedSubjectType = useControlPlaneStore((state) => state.selected_subject_type)
  const selectedSubjectId = useControlPlaneStore((state) => state.selected_subject_id)
  const activeEntityId = useTenantStore((state) => state.active_entity_id)

  const query = useQuery({
    queryKey: ["control-plane-timeline", activeEntityId, selectedSubjectType, selectedSubjectId],
    queryFn: async () =>
      listTimeline({
        entity_id: activeEntityId ?? undefined,
        subject_type: selectedSubjectType ?? undefined,
        subject_id: selectedSubjectId ?? undefined,
        limit: 100,
      }),
    enabled: activePanel === "timeline",
  })

  return (
    <Sheet
      open={activePanel === "timeline"}
      onClose={closePanel}
      title="Timeline Panel"
      description="Unified append-only chain across governance, jobs, records, and evidence."
      width="max-w-3xl"
    >
      <div className="space-y-4">
        <div className="flex items-center justify-between gap-2">
          <p className="text-sm text-muted-foreground">
            {selectedSubjectId
              ? `Scoped to ${selectedSubjectType}:${selectedSubjectId}`
              : "Latest control-plane activity for the current scope."}
          </p>
          <div className="flex gap-2">
            <Button type="button" variant="outline" onClick={() => void query.refetch()}>
              Refresh
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={async () => {
                const blob = await exportTimeline({
                  entity_id: activeEntityId ?? undefined,
                  subject_type: selectedSubjectType ?? undefined,
                  subject_id: selectedSubjectId ?? undefined,
                  limit: 500,
                })
                downloadBlob(blob, "timeline-export.json")
              }}
            >
              Export
            </Button>
          </div>
        </div>
        {query.isLoading ? (
          <p className="text-sm text-muted-foreground">Loading timeline...</p>
        ) : query.error ? (
          <p className="text-sm text-[hsl(var(--brand-danger))]">Failed to load timeline.</p>
        ) : !(query.data?.length ?? 0) ? (
          <p className="text-sm text-muted-foreground">No timeline events in the current scope.</p>
        ) : (
          <div className="overflow-x-auto rounded-xl border border-border">
            <table className="min-w-full divide-y divide-border text-sm">
              <thead className="bg-muted/30">
                <tr className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="px-4 py-2">Event</th>
                  <th className="px-4 py-2">Time</th>
                  <th className="px-4 py-2">Subject</th>
                  <th className="px-4 py-2">Module</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {(query.data ?? []).map((event, index) => (
                  <tr key={`${event.timeline_type}-${event.occurred_at}-${index}`}>
                    <td className="px-4 py-2 text-foreground">{event.timeline_type}</td>
                    <td className="px-4 py-2 text-muted-foreground">{event.occurred_at}</td>
                    <td className="px-4 py-2 font-mono text-xs text-muted-foreground">
                      {event.subject_type ?? "-"}:{event.subject_id ?? "-"}
                    </td>
                    <td className="px-4 py-2 text-muted-foreground">{event.module_key ?? "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </Sheet>
  )
}
