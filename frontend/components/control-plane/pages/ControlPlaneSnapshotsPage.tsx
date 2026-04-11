"use client"

import { PageScaffold } from "@/components/control-plane/PageScaffold"
import { SnapshotNavigator } from "@/components/control-plane/SnapshotNavigator"

interface ControlPlaneSnapshotsPageProps {
  snapshotId?: string | null
}

export function ControlPlaneSnapshotsPage({ snapshotId }: ControlPlaneSnapshotsPageProps) {
  return (
    <PageScaffold
      title="Snapshots"
      description="Inspect snapshot history, compare versions, and open determinism or timeline evidence."
    >
      <SnapshotNavigator initialSnapshotId={snapshotId} />
    </PageScaffold>
  )
}
