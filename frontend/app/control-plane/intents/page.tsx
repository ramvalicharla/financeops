import { createMetadata } from "@/lib/metadata"
import { ControlPlaneIntentsPage } from "@/components/control-plane/pages/ControlPlaneIntentsPage"

export const metadata = createMetadata("Control Plane Intents")

export default function Page() {
  return <ControlPlaneIntentsPage />
}
