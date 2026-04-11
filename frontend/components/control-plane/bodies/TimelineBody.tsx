"use client"

import { useQuery } from "@tanstack/react-query"
import { exportTimeline, getTimelineSemantics, listTimeline } from "@/lib/api/control-plane"
import { controlPlaneQueryKeys } from "@/lib/query/controlPlane"
import { useControlPlaneStore } from "@/lib/store/controlPlane"
import { useTenantStore } from "@/lib/store/tenant"
import { Button } from "@/components/ui/button"

interface TimelineBodyProps {
  entityId?: string | null
  subjectType?: string | null
  subjectId?: string | null
  showExport?: boolean
}

const downloadBlob = (blob: Blob, filename: string) => {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement("a")
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}

export function TimelineBody({
  entityId,
  subjectType,
  subjectId,
  showExport = true,
}: TimelineBodyProps) {
  const selectedSubjectType = useControlPlaneStore((state) => state.selected_subject_type)
  const selectedSubjectId = useControlPlaneStore((state) => state.selected_subject_id)
  const openEvidenceDrawer = useControlPlaneStore((state) => state.openEvidenceDrawer)
  const activeEntityId = useTenantStore((state) => state.active_entity_id)

  const resolvedEntityId = entityId ?? activeEntityId
  const resolvedSubjectType = subjectType ?? selectedSubjectType
  const resolvedSubjectId = subjectId ?? selectedSubjectId

  const query = useQuery({
    queryKey: controlPlaneQueryKeys.timeline({
      entity_id: resolvedEntityId ?? undefined,
      subject_type: resolvedSubjectType ?? undefined,
      subject_id: resolvedSubjectId ?? undefined,
      limit: 100,
    }),
    queryFn: async () =>
      listTimeline({
        entity_id: resolvedEntityId ?? undefined,
        subject_type: resolvedSubjectType ?? undefined,
        subject_id: resolvedSubjectId ?? undefined,
        limit: 100,
      }),
  })
  const semanticsQuery = useQuery({
    queryKey: controlPlaneQueryKeys.timelineSemantics(),
    queryFn: getTimelineSemantics,
  })
  const timelineTitle = semanticsQuery.data?.title ?? "Timeline"
  const timelineDescription =
    semanticsQuery.data?.description ?? "Control-plane events returned by the backend timeline API."
  const emptyState =
    semanticsQuery.data?.empty_state ?? "No control-plane events in the current scope."

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-foreground">{timelineTitle}</h2>
          <p className="text-sm text-muted-foreground">{timelineDescription}</p>
        </div>
        <div className="flex gap-2">
          <Button type="button" variant="outline" onClick={() => void query.refetch()}>
            Refresh
          </Button>
          {showExport ? (
            <Button
              type="button"
              variant="outline"
              onClick={async () => {
                const blob = await exportTimeline({
                  entity_id: resolvedEntityId ?? undefined,
                  subject_type: resolvedSubjectType ?? undefined,
                  subject_id: resolvedSubjectId ?? undefined,
                  limit: 500,
                })
                downloadBlob(blob, "timeline-export.json")
              }}
            >
              Export
            </Button>
          ) : null}
        </div>
      </div>

      <p className="text-sm text-muted-foreground">
        {resolvedSubjectId
          ? `Scoped to ${resolvedSubjectType}:${resolvedSubjectId}`
          : "Latest control-plane activity for the current scope."}
      </p>

      {query.isLoading ? (
        <p className="text-sm text-muted-foreground">Loading timeline...</p>
      ) : query.error ? (
        <div className="rounded-2xl border border-[hsl(var(--brand-danger)/0.35)] bg-[hsl(var(--brand-danger)/0.12)] p-4 text-sm">
          <p className="font-medium text-foreground">Timeline failed to load</p>
          <p className="mt-1 text-muted-foreground">
            {query.error instanceof Error ? query.error.message : "The backend did not return timeline data."}
          </p>
        </div>
      ) : !(query.data?.length ?? 0) ? (
        <div className="rounded-2xl border border-dashed border-border bg-muted/30 p-4 text-sm text-muted-foreground">
          {emptyState}
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-border">
          <table className="min-w-full divide-y divide-border text-sm">
            <thead className="bg-muted/30">
              <tr className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                <th className="px-4 py-2">Event</th>
                <th className="px-4 py-2">Time</th>
                <th className="px-4 py-2">Who</th>
                <th className="px-4 py-2">What Changed</th>
                <th className="px-4 py-2">Subject</th>
                <th className="px-4 py-2">Module</th>
                <th className="px-4 py-2">Evidence</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {(query.data ?? []).map((event, index) => (
                <tr key={`${event.timeline_type}-${event.occurred_at}-${index}`}>
                  <td className="px-4 py-2">
                    <span className="rounded-full border border-border bg-background px-3 py-1 text-xs text-foreground">
                      {event.timeline_type}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-muted-foreground">{event.occurred_at}</td>
                  <td className="px-4 py-2 text-muted-foreground">{String(event.actor_user_id ?? "system")}</td>
                  <td className="px-4 py-2 text-muted-foreground">
                    {event.payload ? JSON.stringify(event.payload).slice(0, 90) : "No payload details"}
                  </td>
                  <td className="px-4 py-2 font-mono text-xs text-muted-foreground">
                    {event.subject_type ?? "-"}:{event.subject_id ?? "-"}
                  </td>
                  <td className="px-4 py-2 text-muted-foreground">{event.module_key ?? "-"}</td>
                  <td className="px-4 py-2">
                    {event.subject_type && event.subject_id ? (
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => openEvidenceDrawer(event.subject_type ?? "timeline", event.subject_id ?? "")}
                      >
                        Open
                      </Button>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
