import { createMetadata } from "@/lib/metadata"
import { ControlPlaneOverviewPage } from "@/components/control-plane/pages/ControlPlaneOverviewPage"

export const metadata = createMetadata("Control Plane Overview")

export default function Page() {
  return <ControlPlaneOverviewPage />
}
