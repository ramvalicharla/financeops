"use client"

import { useMemo, useState } from "react"
import { useMutation } from "@tanstack/react-query"
import { getAuditPack, type GovernanceSnapshot } from "@/lib/api/control-plane"
import { SnapshotNavigator } from "@/components/control-plane/SnapshotNavigator"
import { LineageView } from "@/components/control-plane/LineageView"
import { ImpactWarningModal } from "@/components/control-plane/ImpactWarningModal"
import { Button } from "@/components/ui/button"

const downloadBlob = (blob: Blob, filename: string) => {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement("a")
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}

export default function ControlPlanePage() {
  const [selectedSnapshot, setSelectedSnapshot] = useState<GovernanceSnapshot | null>(null)
  const [impactOpen, setImpactOpen] = useState(false)

  const subject = useMemo(
    () =>
      selectedSnapshot
        ? { subjectType: selectedSnapshot.subject_type, subjectId: selectedSnapshot.subject_id }
        : { subjectType: null, subjectId: null },
    [selectedSnapshot],
  )

  const auditPackMutation = useMutation({
    mutationFn: async () => {
      if (!subject.subjectType || !subject.subjectId) {
        throw new Error("No subject selected")
      }
      return getAuditPack(subject.subjectType, subject.subjectId)
    },
    onSuccess: (blob) => downloadBlob(blob, "audit-pack.json"),
  })

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-border bg-card p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Control Plane</p>
            <h1 className="mt-2 text-2xl font-semibold text-foreground">Determinism, Timeline, Lineage</h1>
            <p className="mt-2 max-w-3xl text-sm text-muted-foreground">
              Backend-driven evidence surfaces for replay, snapshots, dependency tracing, and audit export.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => setImpactOpen(true)}
              disabled={!subject.subjectType || !subject.subjectId}
            >
              Impact Warning
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => auditPackMutation.mutate()}
              disabled={!subject.subjectType || !subject.subjectId || auditPackMutation.isPending}
            >
              Export Audit Pack
            </Button>
          </div>
        </div>
      </section>

      <SnapshotNavigator onSubjectSelected={setSelectedSnapshot} />
      <LineageView subjectType={subject.subjectType} subjectId={subject.subjectId} />

      <ImpactWarningModal
        open={impactOpen}
        onClose={() => setImpactOpen(false)}
        subjectType={subject.subjectType}
        subjectId={subject.subjectId}
      />
    </div>
  )
}
