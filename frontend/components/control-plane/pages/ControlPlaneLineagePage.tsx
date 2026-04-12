"use client"

import { useMemo, useState } from "react"
import type { GovernanceSnapshot } from "@/lib/api/control-plane"
import { ImpactWarningModal } from "@/components/control-plane/ImpactWarningModal"
import { LineageView } from "@/components/control-plane/LineageView"
import { PageScaffold } from "@/components/control-plane/PageScaffold"
import { SnapshotNavigator } from "@/components/control-plane/SnapshotNavigator"
import { StateBadge } from "@/components/ui/StateBadge"
import { Button } from "@/components/ui/button"

export function ControlPlaneLineagePage() {
  const [selectedSnapshot, setSelectedSnapshot] = useState<GovernanceSnapshot | null>(null)
  const [impactOpen, setImpactOpen] = useState(false)

  const subject = useMemo(
    () =>
      selectedSnapshot
        ? { subjectType: selectedSnapshot.subject_type, subjectId: selectedSnapshot.subject_id }
        : { subjectType: null, subjectId: null },
    [selectedSnapshot],
  )

  return (
    <PageScaffold
      title="Lineage"
      description="Backend-derived upstream and downstream relationships for snapshot-backed control-plane subjects."
      actions={
        <Button
          type="button"
          variant="outline"
          onClick={() => setImpactOpen(true)}
          disabled={!subject.subjectType || !subject.subjectId}
        >
          Impact Preview
        </Button>
      }
    >
      <SnapshotNavigator onSubjectSelected={setSelectedSnapshot} />
      {selectedSnapshot ? (
        <div className="rounded-2xl border border-border bg-card p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Selected subject</p>
              <p className="mt-1 break-all font-mono text-sm text-foreground">
                {selectedSnapshot.subject_type}:{selectedSnapshot.subject_id}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <StateBadge label={`v${selectedSnapshot.version_no}`} tone="info" />
              <StateBadge
                label={selectedSnapshot.replay_supported ? "Replay supported" : "Replay limited"}
                tone={selectedSnapshot.replay_supported ? "success" : "warning"}
              />
              <StateBadge label={selectedSnapshot.snapshot_kind} tone="neutral" />
            </div>
          </div>
        </div>
      ) : null}
      <LineageView subjectType={subject.subjectType} subjectId={subject.subjectId} />
      <ImpactWarningModal
        open={impactOpen}
        onClose={() => setImpactOpen(false)}
        subjectType={subject.subjectType}
        subjectId={subject.subjectId}
      />
    </PageScaffold>
  )
}
