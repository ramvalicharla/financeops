import { createMetadata } from "@/lib/metadata"
import { ControlPlaneSnapshotsPage } from "@/components/control-plane/pages/ControlPlaneSnapshotsPage"

export const metadata = createMetadata("Control Plane Snapshots")

export default function Page() {
  return <ControlPlaneSnapshotsPage />
}
