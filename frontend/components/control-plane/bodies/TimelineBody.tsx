"use client"

import { useQuery } from "@tanstack/react-query"
import { exportTimeline, getTimelineSemantics, listTimeline, type TimelineEvent } from "@/lib/api/control-plane"
import { controlPlaneQueryKeys } from "@/lib/query/controlPlane"
import { useControlPlaneStore } from "@/lib/store/controlPlane"
import { useTenantStore } from "@/lib/store/tenant"
import { StateBadge } from "@/components/ui"
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

const summarizeValue = (value: unknown): string => {
  if (value === null) {
    return "null"
  }
  if (value === undefined) {
    return "-"
  }
  if (Array.isArray(value)) {
    if (!value.length) {
      return "Empty list"
    }
    return `Array with ${value.length} item${value.length === 1 ? "" : "s"}`
  }
  if (typeof value === "object") {
    const keys = Object.keys(value as Record<string, unknown>)
    return keys.length ? `${keys.length} structured field${keys.length === 1 ? "" : "s"}` : "Empty object"
  }
  return String(value)
}

function FieldCard({ label, value }: { label: string; value: unknown }) {
  return (
    <div className="rounded-xl border border-border bg-card px-3 py-3">
      <p className="text-[11px] uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-1 break-words text-sm text-foreground">{summarizeValue(value)}</p>
    </div>
  )
}

function TimelineEventCard({
  event,
  onOpenEvidence,
}: {
  event: TimelineEvent
  onOpenEvidence: (subjectType: string, subjectId: string) => void
}) {
  const payloadEntries = event.payload ? Object.entries(event.payload).slice(0, 6) : []

  return (
    <article className="rounded-2xl border border-border bg-background p-4 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-2">
          <div className="flex flex-wrap gap-2">
            <StateBadge status={event.timeline_type} label={event.timeline_type} />
            {event.module_key ? (
              <StateBadge tone="neutral" status={event.module_key} label={event.module_key} showIcon={false} />
            ) : null}
            {event.subject_type ? (
              <StateBadge tone="info" status={event.subject_type} label={event.subject_type} showIcon={false} />
            ) : null}
          </div>
          <div className="space-y-1">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Occurred</p>
            <p className="font-medium text-foreground">{event.occurred_at}</p>
          </div>
        </div>

        {event.subject_type && event.subject_id ? (
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => onOpenEvidence(event.subject_type ?? "timeline", event.subject_id ?? "")}
          >
            Open Evidence
          </Button>
        ) : null}
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <FieldCard label="Actor" value={event.actor_user_id ?? "system"} />
        <FieldCard label="Subject" value={`${event.subject_type ?? "-"}:${event.subject_id ?? "-"}`} />
        <FieldCard
          label="Module"
          value={event.module_key ? `${event.module_key} module` : "-"}
        />
        <FieldCard label="Payload" value={event.payload ?? null} />
      </div>

      <section className="mt-4 space-y-3">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Evidence</p>
            <p className="text-sm text-foreground">Structured payload fields returned by the backend.</p>
          </div>
          <StateBadge
            tone={payloadEntries.length ? "success" : "neutral"}
            status={payloadEntries.length ? "structured" : "empty"}
            label={payloadEntries.length ? `${payloadEntries.length} field(s)` : "No payload details"}
            showIcon={false}
          />
        </div>

        {payloadEntries.length ? (
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {payloadEntries.map(([key, value]) => (
              <FieldCard key={key} label={key} value={value} />
            ))}
          </div>
        ) : (
          <div className="rounded-xl border border-dashed border-border bg-muted/30 p-4 text-sm text-muted-foreground">
            The backend returned no structured payload for this event.
          </div>
        )}
      </section>
    </article>
  )
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

      <div className="flex flex-wrap gap-2 text-xs">
        <StateBadge
          tone={semanticsQuery.data?.semantics.authoritative ? "success" : "warning"}
          status={semanticsQuery.data?.semantics.authoritative ? "authoritative" : "limited"}
          label={semanticsQuery.data?.semantics.authoritative ? "Authoritative feed" : "Limited feed"}
          showIcon={false}
        />
        <StateBadge
          tone={semanticsQuery.data?.semantics.append_only_guarantee ? "success" : "warning"}
          status={semanticsQuery.data?.semantics.append_only_guarantee ? "append_only" : "mutable"}
          label={semanticsQuery.data?.semantics.append_only_guarantee ? "Append-only" : "Append-only not guaranteed"}
          showIcon={false}
        />
        <StateBadge
          tone={semanticsQuery.data?.semantics.compliance_grade ? "success" : "neutral"}
          status={semanticsQuery.data?.semantics.compliance_grade ? "compliance" : "informational"}
          label={semanticsQuery.data?.semantics.compliance_grade ? "Compliance-grade" : "Informational"}
          showIcon={false}
        />
      </div>

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
        <div className="space-y-4">
          {(query.data ?? []).map((event, index) => (
            <TimelineEventCard
              key={`${event.timeline_type}-${event.occurred_at}-${index}`}
              event={event}
              onOpenEvidence={openEvidenceDrawer}
            />
          ))}
        </div>
      )}
    </div>
  )
}
