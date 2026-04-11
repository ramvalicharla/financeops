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
import { useTenantStore } from "@/lib/store/tenant"
import { Button } from "@/components/ui/button"

interface SnapshotNavigatorProps {
  onSubjectSelected?: (snapshot: GovernanceSnapshot) => void
  initialSnapshotId?: string | null
}

export function SnapshotNavigator({
  onSubjectSelected,
  initialSnapshotId = null,
}: SnapshotNavigatorProps) {
  const activeEntityId = useTenantStore((state) => state.active_entity_id)
  const openDeterminismPanel = useControlPlaneStore((state) => state.openDeterminismPanel)
  const openTimelinePanel = useControlPlaneStore((state) => state.openTimelinePanel)
  const [selectedSnapshotId, setSelectedSnapshotId] = useState<string | null>(initialSnapshotId)

  const snapshotsQuery = useQuery({
    queryKey: controlPlaneQueryKeys.snapshots({ entity_id: activeEntityId ?? undefined, limit: 50 }),
    queryFn: async () => listSnapshots({ entity_id: activeEntityId ?? undefined, limit: 50 }),
  })
  const snapshotRows = snapshotsQuery.data ?? []

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
              (() => {
                const snapshot = snapshotQuery.data
                return (
              <>
                <div className="space-y-1">
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">Selected Subject</p>
                  <p className="break-all font-mono text-sm text-foreground">
                    {snapshot.subject_type}:{snapshot.subject_id}
                  </p>
                </div>
                <div className="space-y-1">
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">Determinism Hash</p>
                  <p className="break-all font-mono text-sm text-foreground">{snapshot.determinism_hash}</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => openDeterminismPanel(snapshot.subject_type, snapshot.subject_id)}
                  >
                    Open Determinism
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => openTimelinePanel(snapshot.subject_type, snapshot.subject_id)}
                  >
                    Open Timeline
                  </Button>
                </div>
                {comparisonQuery.data ? (
                  <div className="rounded-xl border border-border bg-background p-3 text-sm">
                    <p className="font-medium text-foreground">Comparison</p>
                    <p className="mt-2 text-muted-foreground">
                      {comparisonQuery.data.same_hash ? "Hashes match." : "Hashes differ."}
                    </p>
                  </div>
                ) : null}
              </>
                )
              })()
            )}
          </div>
        </div>
      )}
    </div>
  )
}
