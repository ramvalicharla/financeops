"use client"

import { useMemo, useState } from "react"
import type { GovernanceSnapshot } from "@/lib/api/control-plane"
import { ImpactWarningModal } from "@/components/control-plane/ImpactWarningModal"
import { LineageView } from "@/components/control-plane/LineageView"
import { PageScaffold } from "@/components/control-plane/PageScaffold"
import { SnapshotNavigator } from "@/components/control-plane/SnapshotNavigator"
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
