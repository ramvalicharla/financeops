import { createMetadata } from "@/lib/metadata"
import { ControlPlaneSnapshotsPage } from "@/components/control-plane/pages/ControlPlaneSnapshotsPage"

export const metadata = createMetadata("Control Plane Snapshot")

export default async function Page({
  params,
}: {
  params: Promise<{ snapshotId: string }>
}) {
  const { snapshotId } = await params
  return <ControlPlaneSnapshotsPage snapshotId={snapshotId} />
}
