"use client"

import { useEffect, useMemo, useState } from "react"
import { useMutation, useQuery } from "@tanstack/react-query"

import {
  compareSnapshots,
  createManualSnapshot,
  getSnapshot,
  listSnapshots,
  type GovernanceSnapshot,
  type SnapshotComparison,
} from "@/lib/api/control-plane"
import { controlPlaneQueryKeys } from "@/lib/query/controlPlane"
import { useControlPlaneStore } from "@/lib/store/controlPlane"
import { useWorkspaceStore } from "@/lib/store/workspace"
import { Button } from "@/components/ui/button"
import { GuardFailureCard, StateBadge } from "@/components/ui"

const summarizeValue = (value: unknown): string => {
  if (value === null) {
    return "null"
  }
  if (value === undefined) {
    return "-"
  }
  if (Array.isArray(value)) {
    return value.length ? `Array with ${value.length} item${value.length === 1 ? "" : "s"}` : "Empty list"
  }
  if (typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>)
    return entries.length ? `${entries.length} structured field${entries.length === 1 ? "" : "s"}` : "Empty object"
  }
  return String(value)
}

function FieldCard({
  label,
  value,
  detail,
}: {
  label: string
  value: unknown
  detail?: string
}) {
  return (
    <div className="rounded-xl border border-border bg-card px-3 py-3">
      <p className="text-[11px] uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-1 break-words text-sm text-foreground">{summarizeValue(value)}</p>
      {detail ? <p className="mt-1 text-xs text-muted-foreground">{detail}</p> : null}
    </div>
  )
}

function ObjectSummaryCard({
  title,
  eyebrow,
  value,
  emptyMessage,
}: {
  title: string
  eyebrow: string
  value: Record<string, unknown> | null | undefined
  emptyMessage: string
}) {
  const entries = value ? Object.entries(value).slice(0, 6) : []

  return (
    <section className="rounded-2xl border border-border bg-background p-4">
      <p className="text-[11px] uppercase tracking-wide text-muted-foreground">{eyebrow}</p>
      <h3 className="mt-1 text-sm font-semibold text-foreground">{title}</h3>
      <div className="mt-3 grid gap-3 md:grid-cols-2">
        {entries.length ? (
          entries.map(([key, nested]) => (
            <div key={key} className="rounded-xl border border-border bg-card px-3 py-3">
              <p className="text-[11px] uppercase tracking-wide text-muted-foreground">{key}</p>
              <p className="mt-1 break-words text-sm text-foreground">{summarizeValue(nested)}</p>
            </div>
          ))
        ) : (
          <div className="rounded-xl border border-dashed border-border bg-muted/30 p-4 text-sm text-muted-foreground md:col-span-2">
            {emptyMessage}
          </div>
        )}
      </div>
    </section>
  )
}

function SnapshotDetailCard({ snapshot }: { snapshot: GovernanceSnapshot }) {
  return (
    <section className="rounded-2xl border border-border bg-background p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <p className="text-[11px] uppercase tracking-wide text-muted-foreground">Selected snapshot</p>
          <p className="break-all font-mono text-sm text-foreground">
            {snapshot.subject_type}:{snapshot.subject_id}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <StateBadge tone="info" status="snapshot" label={`v${snapshot.version_no}`} showIcon={false} />
          <StateBadge
            tone={snapshot.replay_supported ? "success" : "warning"}
            status={snapshot.replay_supported ? "replay_supported" : "replay_limited"}
            label={snapshot.replay_supported ? "Replay supported" : "Replay limited"}
            showIcon={false}
          />
        </div>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <FieldCard label="Snapshot ID" value={snapshot.snapshot_id} />
        <FieldCard label="Module" value={snapshot.module_key} />
        <FieldCard label="Kind" value={snapshot.snapshot_kind} />
        <FieldCard label="Hash" value={snapshot.determinism_hash} />
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <FieldCard label="Version" value={snapshot.version_no} />
        <FieldCard label="Trigger" value={snapshot.trigger_event ?? "-"} />
        <FieldCard label="Snapshot time" value={snapshot.snapshot_at ?? "-"} />
        <FieldCard label="Replay support" value={snapshot.replay_supported ? "Yes" : "No"} />
      </div>

      <div className="mt-4 grid gap-3 lg:grid-cols-2">
        <ObjectSummaryCard
          title="Snapshot payload"
          eyebrow="Payload"
          value={snapshot.payload ?? null}
          emptyMessage="The backend returned no structured snapshot payload."
        />
        <ObjectSummaryCard
          title="Comparison payload"
          eyebrow="Comparison"
          value={snapshot.comparison_payload ?? null}
          emptyMessage="The backend returned no structured comparison payload."
        />
      </div>
    </section>
  )
}

function ComparisonSummaryCard({ comparison }: { comparison: SnapshotComparison }) {
  return (
    <section className="rounded-2xl border border-border bg-background p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-[11px] uppercase tracking-wide text-muted-foreground">Comparison</p>
          <p className="mt-1 text-sm text-foreground">Backend comparison for the selected snapshot pair.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <StateBadge
            tone={comparison.same_subject ? "success" : "warning"}
            status={comparison.same_subject ? "same_subject" : "different_subject"}
            label={comparison.same_subject ? "Same subject" : "Different subject"}
            showIcon={false}
          />
          <StateBadge
            tone={comparison.same_hash ? "success" : "warning"}
            status={comparison.same_hash ? "same_hash" : "different_hash"}
            label={comparison.same_hash ? "Hashes match" : "Hashes differ"}
            showIcon={false}
          />
        </div>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <FieldCard label="Left version" value={comparison.left_version} />
        <FieldCard label="Right version" value={comparison.right_version} />
        <FieldCard label="Left hash" value={comparison.left_hash} />
        <FieldCard label="Right hash" value={comparison.right_hash} />
      </div>

      <p className="mt-4 text-sm text-foreground">
        {comparison.same_hash ? "Hashes match." : "Hashes differ."}
      </p>

      <div className="mt-4 grid gap-3 lg:grid-cols-2">
        <ObjectSummaryCard
          title="Left comparison payload"
          eyebrow="Left side"
          value={comparison.comparison.left ?? null}
          emptyMessage="The backend returned a shallow left comparison payload."
        />
        <ObjectSummaryCard
          title="Right comparison payload"
          eyebrow="Right side"
          value={comparison.comparison.right ?? null}
          emptyMessage="The backend returned a shallow right comparison payload."
        />
      </div>
    </section>
  )
}

interface SnapshotNavigatorProps {
  onSubjectSelected?: (snapshot: GovernanceSnapshot) => void
  initialSnapshotId?: string | null
}

export function SnapshotNavigator({
  onSubjectSelected,
  initialSnapshotId = null,
}: SnapshotNavigatorProps) {
  const activeEntityId = useWorkspaceStore((s) => s.entityId)
  const openDeterminismPanel = useControlPlaneStore((state) => state.openDeterminismPanel)
  const openTimelinePanel = useControlPlaneStore((state) => state.openTimelinePanel)
  const [selectedSnapshotId, setSelectedSnapshotId] = useState<string | null>(initialSnapshotId)

  const snapshotsQuery = useQuery({
    queryKey: controlPlaneQueryKeys.snapshots({ entity_id: activeEntityId ?? undefined, limit: 50 }),
    queryFn: async () => listSnapshots({ entity_id: activeEntityId ?? undefined, limit: 50 }),
  })
  const snapshotRows = useMemo(() => snapshotsQuery.data ?? [], [snapshotsQuery.data])

  useEffect(() => {
    if (!selectedSnapshotId && snapshotRows[0]?.snapshot_id) {
      setSelectedSnapshotId(snapshotRows[0].snapshot_id)
    }
  }, [selectedSnapshotId, snapshotRows])

  useEffect(() => {
    if (initialSnapshotId) {
      setSelectedSnapshotId(initialSnapshotId)
    }
  }, [initialSnapshotId])

  const selectedSnapshot = useMemo(
    () => snapshotRows.find((row) => row.snapshot_id === selectedSnapshotId) ?? null,
    [selectedSnapshotId, snapshotRows],
  )

  const snapshotQuery = useQuery({
    queryKey: controlPlaneQueryKeys.snapshot(selectedSnapshotId),
    queryFn: async () => (selectedSnapshotId ? getSnapshot(selectedSnapshotId) : null),
    enabled: Boolean(selectedSnapshotId),
  })

  const compareTarget = useMemo(() => {
    if (!selectedSnapshot || !snapshotRows.length) {
      return null
    }
    return (
      snapshotRows.find(
        (row) =>
          row.snapshot_id !== selectedSnapshot.snapshot_id &&
          row.subject_type === selectedSnapshot.subject_type &&
          row.subject_id === selectedSnapshot.subject_id,
      ) ?? null
    )
  }, [selectedSnapshot, snapshotRows])

  const comparisonQuery = useQuery({
    queryKey: controlPlaneQueryKeys.snapshotCompare(selectedSnapshotId, compareTarget?.snapshot_id ?? null),
    queryFn: async (): Promise<SnapshotComparison | null> =>
      selectedSnapshotId && compareTarget
        ? compareSnapshots(selectedSnapshotId, compareTarget.snapshot_id)
        : null,
    enabled: Boolean(selectedSnapshotId && compareTarget),
  })

  const manualSnapshot = useMutation({
    mutationFn: async () => {
      if (!selectedSnapshot) {
        throw new Error("No snapshot subject selected")
      }
      return createManualSnapshot(selectedSnapshot.subject_type, selectedSnapshot.subject_id)
    },
    onSuccess: (snapshot) => {
      setSelectedSnapshotId(snapshot.snapshot_id)
    },
  })

  useEffect(() => {
    if (snapshotQuery.data && onSubjectSelected) {
      onSubjectSelected(snapshotQuery.data)
    }
  }, [onSubjectSelected, snapshotQuery.data])

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-2">
        <div>
          <h2 className="text-lg font-semibold text-foreground">Snapshots</h2>
          <p className="text-sm text-muted-foreground">Version history and compare surface for governed outputs.</p>
        </div>
        <div className="flex gap-2">
          <Button type="button" variant="outline" onClick={() => void snapshotsQuery.refetch()}>
            Refresh
          </Button>
          <Button
            type="button"
            variant="outline"
            onClick={() => manualSnapshot.mutate()}
            disabled={!selectedSnapshot || manualSnapshot.isPending}
          >
            Manual Snapshot
          </Button>
        </div>
      </div>

      {snapshotsQuery.isLoading ? (
        <p className="text-sm text-muted-foreground">Loading snapshots...</p>
      ) : !snapshotRows.length ? (
        <p className="text-sm text-muted-foreground">No snapshots available for the current scope.</p>
      ) : (
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
          <div className="overflow-x-auto rounded-xl border border-border bg-card">
            <table className="min-w-full divide-y divide-border text-sm">
              <thead className="bg-muted/30">
                <tr className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="px-4 py-2">Subject</th>
                  <th className="px-4 py-2">Version</th>
                  <th className="px-4 py-2">Hash</th>
                  <th className="px-4 py-2">Inspect</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {snapshotRows.map((snapshot) => (
                  <tr key={snapshot.snapshot_id}>
                    <td className="px-4 py-2 text-foreground">
                      {snapshot.subject_type}:{snapshot.subject_id}
                    </td>
                    <td className="px-4 py-2 text-muted-foreground">{snapshot.version_no}</td>
                    <td className="px-4 py-2 font-mono text-xs text-muted-foreground">
                      {snapshot.determinism_hash.slice(0, 12)}...
                    </td>
                    <td className="px-4 py-2">
                      <Button
                        type="button"
                        variant={selectedSnapshotId === snapshot.snapshot_id ? "default" : "outline"}
                        onClick={() => setSelectedSnapshotId(snapshot.snapshot_id)}
                      >
                        Open
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="space-y-4 rounded-xl border border-border bg-card p-4">
            {!snapshotQuery.data ? (
              <p className="text-sm text-muted-foreground">Select a snapshot to inspect.</p>
            ) : (
              <>
                <SnapshotDetailCard snapshot={snapshotQuery.data} />
                <div className="flex flex-wrap gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => openDeterminismPanel(snapshotQuery.data!.subject_type, snapshotQuery.data!.subject_id)}
                  >
                    Open Determinism
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => openTimelinePanel(snapshotQuery.data!.subject_type, snapshotQuery.data!.subject_id)}
                  >
                    Open Timeline
                  </Button>
                </div>

                {compareTarget ? (
                  comparisonQuery.isLoading ? (
                    <p className="text-sm text-muted-foreground">Loading comparison evidence...</p>
                  ) : comparisonQuery.error ? (
                    <GuardFailureCard
                      title="Comparison failed to load"
                      message={
                        comparisonQuery.error instanceof Error
                          ? comparisonQuery.error.message
                          : "The backend did not return comparison evidence."
                      }
                      recommendation="Use the selected snapshot summary and hash fields above as the authoritative evidence."
                      tone="warning"
                    />
                  ) : comparisonQuery.data ? (
                    <ComparisonSummaryCard comparison={comparisonQuery.data} />
                  ) : (
                    <GuardFailureCard
                      title="Comparison unavailable"
                      message="The backend returned no comparison payload for the selected pair."
                      recommendation="Inspect the selected snapshot and compare target individually if the compare response is shallow."
                      tone="warning"
                    />
                  )
                ) : (
                  <GuardFailureCard
                    title="Comparison unavailable"
                    message="No sibling snapshot was found for the selected subject, so there is nothing to compare against yet."
                    recommendation="Create another backend-backed snapshot for the same subject to enable a structured comparison view."
                    tone="warning"
                  />
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
