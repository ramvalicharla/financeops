import { createMetadata } from "@/lib/metadata"
import { ControlPlaneAirlockPage } from "@/components/control-plane/pages/ControlPlaneAirlockPage"

export const metadata = createMetadata("Control Plane Airlock")

export default function Page() {
  return <ControlPlaneAirlockPage />
}
