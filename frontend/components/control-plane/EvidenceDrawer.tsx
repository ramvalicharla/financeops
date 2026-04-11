"use client"

import { useMemo, useState } from "react"
import { useMutation, useQuery } from "@tanstack/react-query"
import {
  getAuditPack,
  getImpact,
  getIntent,
  getLineage,
  listJobs,
  listTimeline,
} from "@/lib/api/control-plane"
import { controlPlaneQueryKeys } from "@/lib/query/controlPlane"
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

const TABS = [
  { id: "summary", label: "Summary" },
  { id: "execution", label: "Execution" },
  { id: "timeline", label: "Timeline" },
  { id: "lineage", label: "Lineage" },
  { id: "impact", label: "Impact" },
  { id: "audit", label: "Audit" },
] as const

type EvidenceTab = (typeof TABS)[number]["id"]

export function EvidenceDrawer() {
  const [activeTab, setActiveTab] = useState<EvidenceTab>("summary")
  const open = useControlPlaneStore((state) => state.evidence_drawer_open)
  const subjectType = useControlPlaneStore((state) => state.evidence_subject_type)
  const subjectId = useControlPlaneStore((state) => state.evidence_subject_id)
  const close = useControlPlaneStore((state) => state.closeEvidenceDrawer)
  const activeEntityId = useTenantStore((state) => state.active_entity_id)

  const summaryQuery = useQuery({
    queryKey: controlPlaneQueryKeys.intent(
      activeTab === "summary" && subjectType === "intent" ? subjectId : null,
    ),
    queryFn: async () => (subjectType === "intent" && subjectId ? getIntent(subjectId) : null),
    enabled: open && activeTab === "summary" && subjectType === "intent" && Boolean(subjectId),
  })
  const executionQuery = useQuery({
    queryKey: controlPlaneQueryKeys.jobs({
      entity_id: activeEntityId ?? undefined,
      limit: 100,
    }),
    queryFn: async () => listJobs({ entity_id: activeEntityId ?? undefined, limit: 100 }),
    enabled: open && activeTab === "execution",
  })
  const timelineQuery = useQuery({
    queryKey: controlPlaneQueryKeys.timeline({
      entity_id: activeEntityId ?? undefined,
      subject_type: subjectType ?? undefined,
      subject_id: subjectId ?? undefined,
      limit: 50,
    }),
    queryFn: async () =>
      listTimeline({
        entity_id: activeEntityId ?? undefined,
        subject_type: subjectType ?? undefined,
        subject_id: subjectId ?? undefined,
        limit: 50,
      }),
    enabled: open && activeTab === "timeline" && Boolean(subjectType && subjectId),
  })
  const lineageQuery = useQuery({
    queryKey: controlPlaneQueryKeys.lineage(subjectType, subjectId),
    queryFn: async () => (subjectType && subjectId ? getLineage(subjectType, subjectId) : null),
    enabled: open && activeTab === "lineage" && Boolean(subjectType && subjectId),
  })
  const impactQuery = useQuery({
    queryKey: controlPlaneQueryKeys.impact(subjectType, subjectId),
    queryFn: async () => (subjectType && subjectId ? getImpact(subjectType, subjectId) : null),
    enabled: open && activeTab === "impact" && Boolean(subjectType && subjectId),
  })
  const auditPackMutation = useMutation({
    mutationFn: async () => {
      if (!subjectType || !subjectId) {
        throw new Error("No evidence subject selected.")
      }
      return getAuditPack(subjectType, subjectId)
    },
    onSuccess: (blob) => downloadBlob(blob, `${subjectType ?? "subject"}-${subjectId ?? "evidence"}-audit-pack.json`),
  })

  const relatedJobs = useMemo(() => {
    const jobs = executionQuery.data ?? []
    if (!subjectType || !subjectId) {
      return jobs.slice(0, 10)
    }
    return jobs.filter((job) => {
      if (subjectType === "job") {
        return job.job_id === subjectId
      }
      if (subjectType === "intent") {
        return job.intent_id === subjectId
      }
      return false
    })
  }, [executionQuery.data, subjectId, subjectType])

  return (
    <Sheet
      open={open}
      onClose={close}
      title="Evidence Drawer"
      description="Backend-derived evidence, execution, lineage, impact, and audit pack references."
      width="max-w-3xl"
    >
      <div className="space-y-4">
        <div className="rounded-2xl border border-border bg-background p-4">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Selected object</p>
          <p className="mt-2 font-mono text-sm text-foreground">
            {subjectType ?? "unselected"}:{subjectId ?? "unselected"}
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          {TABS.map((tab) => (
            <Button
              key={tab.id}
              type="button"
              variant={tab.id === activeTab ? "default" : "outline"}
              size="sm"
              onClick={() => setActiveTab(tab.id)}
            >
              {tab.label}
            </Button>
          ))}
        </div>

        {activeTab === "summary" ? (
          subjectType === "intent" ? (
            summaryQuery.isLoading ? (
              <p className="text-sm text-muted-foreground">Loading summary...</p>
            ) : summaryQuery.data ? (
              <div className="space-y-3 rounded-2xl border border-border bg-card p-4 text-sm">
                <div>
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">Intent</p>
                  <p className="mt-1 font-mono text-foreground">{summaryQuery.data.intent_id}</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">Status</p>
                  <p className="mt-1 text-foreground">{summaryQuery.data.status}</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">Next Action</p>
                  <p className="mt-1 text-foreground">{summaryQuery.data.next_action ?? "Unavailable"}</p>
                </div>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                No summary data was returned for this evidence subject.
              </p>
            )
          ) : (
            <div className="rounded-2xl border border-border bg-card p-4 text-sm text-muted-foreground">
              Summary detail is limited for this subject type in the current backend contract.
            </div>
          )
        ) : null}

        {activeTab === "execution" ? (
          <div className="rounded-2xl border border-border bg-card p-4">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Related jobs</p>
            {executionQuery.isLoading ? (
              <p className="mt-3 text-sm text-muted-foreground">Loading execution evidence...</p>
            ) : relatedJobs.length ? (
              <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
                {relatedJobs.map((job) => (
                  <li key={job.job_id} className="rounded-xl border border-border bg-background px-3 py-3">
                    <p className="font-medium text-foreground">{job.job_type}</p>
                    <p className="mt-1 font-mono text-xs">{job.job_id}</p>
                    <p className="mt-1">{job.status}</p>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-3 text-sm text-muted-foreground">
                No related execution rows were found in the current entity scope.
              </p>
            )}
          </div>
        ) : null}

        {activeTab === "timeline" ? (
          <div className="rounded-2xl border border-border bg-card p-4">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Related timeline</p>
            {timelineQuery.isLoading ? (
              <p className="mt-3 text-sm text-muted-foreground">Loading timeline evidence...</p>
            ) : timelineQuery.data?.length ? (
              <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
                {timelineQuery.data.map((event, index) => (
                  <li key={`${event.timeline_type}-${event.occurred_at}-${index}`} className="rounded-xl border border-border bg-background px-3 py-3">
                    <p className="font-medium text-foreground">{event.timeline_type}</p>
                    <p className="mt-1 text-xs">{event.occurred_at}</p>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-3 text-sm text-muted-foreground">No timeline evidence was returned.</p>
            )}
          </div>
        ) : null}

        {activeTab === "lineage" ? (
          <div className="rounded-2xl border border-border bg-card p-4">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Lineage refs</p>
            {lineageQuery.isLoading ? (
              <p className="mt-3 text-sm text-muted-foreground">Loading lineage...</p>
            ) : lineageQuery.data ? (
              <div className="mt-3 grid gap-3 md:grid-cols-2">
                <div className="rounded-xl border border-border bg-background p-3 text-sm">
                  Forward: {lineageQuery.data.forward.nodes.length} nodes / {lineageQuery.data.forward.edges.length} edges
                </div>
                <div className="rounded-xl border border-border bg-background p-3 text-sm">
                  Reverse: {lineageQuery.data.reverse.nodes.length} nodes / {lineageQuery.data.reverse.edges.length} edges
                </div>
              </div>
            ) : (
              <p className="mt-3 text-sm text-muted-foreground">No lineage data was returned.</p>
            )}
          </div>
        ) : null}

        {activeTab === "impact" ? (
          <div className="rounded-2xl border border-border bg-card p-4">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Impact preview</p>
            {impactQuery.isLoading ? (
              <p className="mt-3 text-sm text-muted-foreground">Loading impact...</p>
            ) : impactQuery.data ? (
              <div className="mt-3 space-y-2 text-sm">
                <p className="text-foreground">{impactQuery.data.warning}</p>
                <p className="text-muted-foreground">
                  Downstream nodes: {impactQuery.data.impacted_count}. Reports: {impactQuery.data.impacted_reports_count}.
                </p>
              </div>
            ) : (
              <p className="mt-3 text-sm text-muted-foreground">No impact data was returned.</p>
            )}
          </div>
        ) : null}

        {activeTab === "audit" ? (
          <div className="rounded-2xl border border-border bg-card p-4">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Audit pack</p>
            <p className="mt-3 text-sm text-muted-foreground">
              Download the backend-generated audit pack for this subject when available.
            </p>
            <Button
              className="mt-3"
              type="button"
              variant="outline"
              onClick={() => auditPackMutation.mutate()}
              disabled={auditPackMutation.isPending || !subjectType || !subjectId}
            >
              Download Audit Pack
            </Button>
          </div>
        ) : null}
      </div>
    </Sheet>
  )
}
