import { createMetadata } from "@/lib/metadata"
import { ControlPlaneJobsPage } from "@/components/control-plane/pages/ControlPlaneJobsPage"

export const metadata = createMetadata("Control Plane Jobs")

export default function Page() {
  return <ControlPlaneJobsPage />
}
