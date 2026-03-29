"use client"

import { useEffect, useMemo, useState } from "react"
import { useParams } from "next/navigation"
import { EvidenceUploader } from "@/components/audit/EvidenceUploader"
import { PBCRequestTable } from "@/components/audit/PBCRequestTable"
import { getPBCTracker, respondToPBCRequest } from "@/lib/api/sprint11"
import { type AuditorRequest, type PBCTracker } from "@/lib/types/sprint11"

export default function AuditEngagementPage() {
  const params = useParams<{ engagement_id: string }>()
  const engagementId = params?.engagement_id ?? ""
  const [tracker, setTracker] = useState<PBCTracker | null>(null)
  const [selectedRequest, setSelectedRequest] = useState<AuditorRequest | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = async (): Promise<void> => {
    setLoading(true)
    setError(null)
    try {
      const payload = await getPBCTracker(engagementId)
      setTracker(payload)
      setSelectedRequest(payload.overdue_requests[0] ?? payload.recent_activity[0] ?? null)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Failed to load PBC tracker")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (!engagementId) {
      return
    }
    void load()
  }, [engagementId])

  const allRows = useMemo(() => {
    if (!tracker) {
      return []
    }
    const map = new Map<string, AuditorRequest>()
    for (const row of tracker.overdue_requests) {
      map.set(row.id, row)
    }
    for (const row of tracker.recent_activity) {
      map.set(row.id, row)
    }
    return Array.from(map.values())
  }, [tracker])

  const respond = async (
    row: AuditorRequest,
    payload: {
      status: string
      response_notes?: string
      evidence_urls?: string[]
    },
  ): Promise<void> => {
    try {
      await respondToPBCRequest(engagementId, row.id, payload)
      await load()
    } catch (respondError) {
      setError(respondError instanceof Error ? respondError.message : "Failed to update request")
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-foreground">PBC Tracker</h1>
      {!engagementId ? (
        <p className="text-sm text-red-400">Missing engagement ID.</p>
      ) : null}
      {loading ? <p className="text-sm text-muted-foreground">Loading engagement...</p> : null}
      {error ? <p className="text-sm text-red-400">{error}</p> : null}
      {tracker ? (
        <section className="grid gap-3 md:grid-cols-5">
          <div className="rounded-xl border border-border bg-card p-3 text-sm text-foreground">
            Total: {tracker.total_requests}
          </div>
          <div className="rounded-xl border border-border bg-card p-3 text-sm text-foreground">
            Open: {tracker.open}
          </div>
          <div className="rounded-xl border border-border bg-card p-3 text-sm text-foreground">
            In Progress: {tracker.in_progress}
          </div>
          <div className="rounded-xl border border-border bg-card p-3 text-sm text-foreground">
            Provided: {tracker.provided}
          </div>
          <div className="rounded-xl border border-border bg-card p-3 text-sm text-foreground">
            Completion: {tracker.completion_pct}%
          </div>
        </section>
      ) : null}
      <PBCRequestTable
        rows={allRows}
        onRespond={respond}
      />
      {selectedRequest ? (
        <EvidenceUploader
          requestId={selectedRequest.request_number}
          existingUrls={selectedRequest.evidence_urls}
          onSave={async (urls) => {
            await respond(selectedRequest, {
              status: selectedRequest.status,
              response_notes: selectedRequest.response_notes ?? "",
              evidence_urls: urls,
            })
          }}
        />
      ) : null}
    </div>
  )
}
