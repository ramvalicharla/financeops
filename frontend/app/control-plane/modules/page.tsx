import { createMetadata } from "@/lib/metadata"
import { ControlPlaneModulesPage } from "@/components/control-plane/pages/ControlPlaneModulesPage"

export const metadata = createMetadata("Control Plane Modules")

export default function Page() {
  return <ControlPlaneModulesPage />
}
