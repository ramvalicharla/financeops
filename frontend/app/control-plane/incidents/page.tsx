import { createMetadata } from "@/lib/metadata"
import { LimitedControlPlanePage } from "@/components/control-plane/pages/LimitedControlPlanePage"

export const metadata = createMetadata("Control Plane Incidents")

export default function Page() {
  return (
    <LimitedControlPlanePage
      title="Incidents"
      description="Operational incident handling is limited by the current backend contract."
      body="Incident system not available in the current backend contract. Use timeline, evidence, and audit-pack surfaces for incident-adjacent investigation."
    />
  )
}
