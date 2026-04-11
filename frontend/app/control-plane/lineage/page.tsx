import { createMetadata } from "@/lib/metadata"
import { ControlPlaneLineagePage } from "@/components/control-plane/pages/ControlPlaneLineagePage"

export const metadata = createMetadata("Control Plane Lineage")

export default function Page() {
  return <ControlPlaneLineagePage />
}
