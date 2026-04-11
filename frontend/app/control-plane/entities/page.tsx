import { createMetadata } from "@/lib/metadata"
import { ControlPlaneEntitiesPage } from "@/components/control-plane/pages/ControlPlaneEntitiesPage"

export const metadata = createMetadata("Control Plane Entities")

export default function Page() {
  return <ControlPlaneEntitiesPage />
}
