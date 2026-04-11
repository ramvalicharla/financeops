import { createMetadata } from "@/lib/metadata"
import { ControlPlaneTimelinePage } from "@/components/control-plane/pages/ControlPlaneTimelinePage"

export const metadata = createMetadata("Control Plane Timeline")

export default function Page() {
  return <ControlPlaneTimelinePage />
}
